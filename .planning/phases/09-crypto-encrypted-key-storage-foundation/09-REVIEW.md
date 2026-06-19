---
phase: 09-crypto-encrypted-key-storage-foundation
reviewed: 2026-06-18T00:00:00Z
depth: standard
files_reviewed: 8
files_reviewed_list:
  - backend/config.py
  - backend/services/crypto_service.py
  - backend/services/sql_service.py
  - backend/tests/test_config.py
  - backend/tests/test_crypto_service.py
  - backend/tests/test_sql_keys_lockdown.py
  - supabase/migrations/20240301000025_create_user_api_keys.sql
  - supabase/migrations/20240301000026_harden_sql_tool_allowlist.sql
findings:
  critical: 2
  warning: 5
  info: 3
  total: 10
status: issues_found
---

# Phase 9: Code Review Report

**Reviewed:** 2026-06-18
**Depth:** standard
**Files Reviewed:** 8
**Status:** issues_found

## Summary

This phase delivers the BYOK encrypted-key-storage foundation: a `MultiFernet`
crypto service, a `user_api_keys` table with own-row RLS plus a `REVOKE SELECT
... FROM authenticated`, and a "Gate 2" FROM-table allowlist hardening of the
`execute_readonly_query` SQL RPC. The crypto round-trip/rotation logic is correct
and the secret-handling discipline (no logging of plaintext/ciphertext/master
key) is observed.

The serious problems are in **Gate 2, the SQL-tool FROM-table allowlist**. The
allowlist parser — both the SQL `regexp_matches` loop in migration 026 (the real
enforcing gate) and its Python mirror `is_query_allowlisted` — extracts only
identifiers immediately following a `FROM`/`JOIN` keyword. It does **not** see
tables introduced by a comma cross-join, and it mis-parses schema-qualified names
(capturing the schema, not the table). Both yield default-*allow* on
attacker-controlled SQL that references a non-allowlisted table. The keys table
itself is still saved by the Gate-1 `REVOKE` (defense-in-depth working as
intended), but Gate 2's broader purpose — denying every non-allowlisted table
(e.g. `auth.users`, other users' data via tables not behind the REVOKE) — is
defeated. The test suite asserts only the easy `FROM user_api_keys` / `JOIN`
shapes and therefore reports a false PASS on the gate.

There is also a separate correctness issue: the comma-join false-*negative* will
reject legitimate multi-table comma queries, and the empty-`KEY_ENCRYPTION_SECRET`
default crashes the crypto service with an opaque error.

## Critical Issues

### CR-01: FROM-table allowlist bypassed by comma cross-join (Gate 2 defeated)

**File:** `supabase/migrations/20240301000026_harden_sql_tool_allowlist.sql:66-73`
(mirror: `backend/services/sql_service.py:22,33-36`)

**Issue:** The allowlist loop only inspects identifiers that follow a `FROM` or
`JOIN` keyword. SQL allows additional FROM-list tables separated by commas
(implicit cross join), which the regex never sees. Verified against the exact
regex:

```
'select * from threads, user_api_keys' -> ['threads']
'select * from threads, auth.users'    -> ['threads']
```

Only `threads` is extracted, so the allowlist check passes, and the query reaches
execution with the non-allowlisted table in scope. The same bypass applies to the
Python `is_query_allowlisted` mirror. For `user_api_keys` specifically the Gate-1
`REVOKE` (migration 025) still blocks the read, but Gate 2's stated job is to deny
*any* non-allowlisted table — e.g. `select t.id from threads t, auth.users u where
u.id = ...` reaches `auth.users` (not behind the REVOKE), and any future table
added without a REVOKE is exposed. This is a default-*allow* failure on
attacker-controlled SQL, i.e. a real exfiltration path through the gate that was
specifically added to close it.

**Fix:** Do not rely on a FROM/JOIN-keyword regex to enumerate referenced tables
— it cannot parse SQL. Prefer one of:

- Enforce table access with Postgres privileges (the approach that already works
  in Gate 1): `REVOKE SELECT` on every non-allowlisted table from the
  `authenticated` role, so the SECURITY DEFINER body running `SET LOCAL role =
  'authenticated'` is denied by the engine regardless of query shape. This is the
  only robust gate.
- If a textual check is kept as defense-in-depth, also split the FROM-list on
  commas and validate every comma-separated source, and reject schema-qualified
  references (see CR-02). At minimum, extend the regex to capture a token after a
  comma in the FROM clause, e.g. handle `,\s*"?([a-z_][a-z0-9_]*)` in addition to
  `(?:from|join)\s+...`. Note even this remains best-effort and should not be the
  sole gate.

Whatever fix is chosen, the SQL loop in migration 026 and the Python
`is_query_allowlisted` mirror must be updated together, and the test added below
(WR-01) must cover the comma-join case.

### CR-02: Schema-qualified table reference mis-parsed — allowlist captures the schema, not the table

**File:** `supabase/migrations/20240301000026_harden_sql_tool_allowlist.sql:67-70`
(mirror: `backend/services/sql_service.py:22,33-36`)

**Issue:** For a schema-qualified name the regex stops at the first identifier and
captures the schema, never the table:

```
'select * from public.user_api_keys'   -> ['public']
'select * from auth.users'             -> ['auth']
'select * from messages.user_api_keys' -> ['messages']
```

`select * from messages.user_api_keys` extracts `messages` — which IS in the
allowlist — so the query passes Gate 2 while actually targeting
`messages.user_api_keys`. (Postgres would resolve `messages.user_api_keys` as
schema `messages`.`user_api_keys`; there is no such schema in this DB so it would
error, but the *gate* did not reject it, and a real cross-schema name such as
`auth.users` is mis-handled symmetrically: it extracts `auth` and is rejected,
which is a separate false-negative for any legitimately schema-qualified query.)
The combination means the allowlist cannot reason about schema-qualified
identifiers at all — both directions (false-allow and false-deny) are wrong.

**Fix:** Reject or explicitly normalize schema-qualified identifiers. Extend the
capture to include an optional schema segment and validate the fully-qualified
name against an allowlist of `public.<table>` only, e.g. capture
`(?:from|join)\s+"?([a-z_][a-z0-9_.]*)` then split on `.` and require the schema
to be `public` (or absent) and the table to be in `ALLOWED_SQL_TABLES`. As with
CR-01, the durable fix is privilege-based (per-table `REVOKE`), since a regex
cannot reliably parse SQL. Update migration 026, `is_query_allowlisted`, and the
tests together.

## Warnings

### WR-01: Exfiltration test suite asserts only the trivially-blocked shapes — false PASS on the gate

**File:** `backend/tests/test_sql_keys_lockdown.py:19-30`

**Issue:** The probe only checks `FROM user_api_keys`, `JOIN user_api_keys`, and
case variants — exactly the cases the regex already handles. It never exercises a
comma cross-join (`from threads, user_api_keys`) or a schema-qualified reference
(`from public.user_api_keys`), which are the actual bypasses (CR-01, CR-02). The
suite therefore reports GREEN while the gate is bypassable, defeating the stated
purpose of "asserting the allowlist logic at a deterministic seam."

**Fix:** Add explicit failing cases before fixing CR-01/CR-02 (red-then-green):

```python
def test_comma_cross_join_blocked():
    assert is_query_allowlisted("select * from threads, user_api_keys") is False
    assert is_query_allowlisted("select * from documents d, user_api_keys k") is False

def test_schema_qualified_keys_blocked():
    assert is_query_allowlisted("select * from public.user_api_keys") is False
    assert is_query_allowlisted("select * from messages.user_api_keys") is False
```

### WR-02: Legitimate comma-join queries silently rejected (false negative)

**File:** `backend/services/sql_service.py:33-36`,
`supabase/migrations/20240301000026_harden_sql_tool_allowlist.sql:66-73`

**Issue:** As a side effect of CR-01, a legitimate comma cross-join over
allowlisted tables — e.g. `select * from documents d, document_chunks c where
c.document_id = d.id` — extracts only `documents`, which passes; but
`select * from messages m, threads t where m.thread_id = t.id` extracts only
`messages` and passes too, so this one happens to work, while a query whose FIRST
FROM-list entry is allowlisted but a later comma entry is a typo'd/unknown name is
never validated. The parser's coverage of the legitimate Text-to-SQL surface is
inconsistent: comma-list members after the first are simply not checked. This is a
correctness gap that will produce confusing, non-deterministic allow/deny behavior
for multi-table queries.

**Fix:** Same as CR-01 — validate every FROM-list source, not just the token after
the FROM/JOIN keyword. Once all comma members are parsed, both the security
(WR-01) and correctness (this) issues are resolved together.

### WR-03: Empty `KEY_ENCRYPTION_SECRET` (the default) crashes with an opaque error

**File:** `backend/services/crypto_service.py:19-22`; default at
`backend/config.py:23`

**Issue:** `key_encryption_secret` defaults to `""`. With the default (or any
all-whitespace value), `_multifernet()` builds an empty key list and
`MultiFernet([])` raises `ValueError: MultiFernet requires at least one Fernet
instance` (verified via the backend venv). Any call to `encrypt_key` /
`decrypt_key` / `rotate_token` then fails with a generic, non-actionable
`ValueError` that does not tell the operator the master key is unset. In a BYOK
write/read path this surfaces as a 500 with an unclear cause.

**Fix:** Validate configuration explicitly and fail with a clear message:

```python
def _multifernet() -> MultiFernet:
    keys = [k.strip() for k in get_settings().key_encryption_secret.split(",") if k.strip()]
    if not keys:
        raise RuntimeError(
            "KEY_ENCRYPTION_SECRET is not configured; cannot encrypt/decrypt BYOK keys"
        )
    return MultiFernet([Fernet(k.encode()) for k in keys])
```

Do not include the key value or any ciphertext in the message (preserve D-04).

### WR-04: UPDATE RLS policy has `USING` but no `WITH CHECK` — row can be re-owned to another user

**File:** `supabase/migrations/20240301000025_create_user_api_keys.sql:38-41`

**Issue:** The UPDATE policy specifies only `USING (auth.uid() = user_id)`. For
UPDATE, `USING` gates which existing rows are visible/updatable, while `WITH
CHECK` gates the *new* row values. Without `WITH CHECK`, a user who can update
their own row could set `user_id` to another user's id (changing ownership) or
otherwise write a row that violates the ownership invariant. `user_id` is the PK
here so a direct re-assignment would collide, but the missing `WITH CHECK` is a
real RLS pitfall and leaves the policy weaker than the INSERT policy which
correctly uses `WITH CHECK`. Defense-in-depth: the service-role backend bypasses
RLS, but the policy is the user-JWT contract and should be airtight.

**Fix:** Add a matching `WITH CHECK` clause:

```sql
CREATE POLICY "Users can update own key row"
  ON user_api_keys FOR UPDATE
  USING (auth.uid() = user_id)
  WITH CHECK (auth.uid() = user_id);
```

### WR-05: `key_version` column is never set/incremented by the crypto layer — rotation bookkeeping can drift

**File:** `supabase/migrations/20240301000025_create_user_api_keys.sql:17`;
`backend/services/crypto_service.py:35-37`

**Issue:** The table carries `key_version INTEGER NOT NULL DEFAULT 1` documented as
"which master key encrypted this row," but `rotate_token` / `encrypt_key` neither
read nor return a version, and nothing in this phase updates the column on
rotation. After a `rotate_token` re-encrypts a row under a new primary key, the
stored `key_version` will still read `1`, making the column actively misleading
for any future migration/rotation tooling that trusts it. Either the column or the
crypto API is incomplete.

**Fix:** Either (a) have the rotation/persistence path update `key_version`
alongside `encrypted_key` (the crypto service can't do this alone — the row-writer
must), or (b) drop the column until a phase actually maintains it, to avoid relying
on a value that is never updated. At minimum, document in the phase summary that
`key_version` is a placeholder not maintained in Phase 9 so downstream phases
don't trust it.

## Info

### IN-01: `is_query_allowlisted` empty-match returns False but is unused at runtime — verify the SQL gate matches

**File:** `backend/services/sql_service.py:25-36`

**Issue:** The Python helper returns `False` when no FROM/JOIN is found (defensive
default-deny), but the comment and summaries make clear it is NOT wired into
`execute_sql`'s runtime path — only the SQL RPC enforces. That is a deliberate
design choice, but it means the unit test validates a function that production
never calls; the SQL loop in migration 026 is the only thing that matters, and it
has the opposite default for the "no FROM" case (the SQL loop simply never enters
and the query is *allowed*). The two "mirrors" therefore disagree on the empty
case. Not exploitable on its own (a SELECT with no FROM reads no table), but the
"single source of truth" claim is inaccurate.

**Fix:** Document the intentional divergence, or wire the same helper logic into
both so "mirror" is literally true. Add a comment in migration 026 noting the
no-FROM case is allowed there.

### IN-02: `truncated` flag uses `>=` and can report false positives at the boundary

**File:** `backend/services/sql_service.py:93`

**Issue:** `truncated` is `len(rows) >= settings.sql_max_rows`. A result of exactly
`sql_max_rows` rows that was *not* truncated (the source had exactly that many)
reports `truncated: True`. Minor UX inaccuracy, not a correctness/security issue.

**Fix:** Acceptable as a conservative signal; if exactness matters, fetch
`max_rows + 1` in the RPC and report truncation when more than `max_rows` come
back.

### IN-03: Broad `except Exception` returns `str(e)` to the caller — verify no secret leakage on the BYOK path

**File:** `backend/services/sql_service.py:95-97`

**Issue:** `execute_sql` catches all exceptions and returns `str(e)` in the
response dict, which is then surfaced to the LLM/tool result (`chat.py:403-404`).
On the SQL path this is acceptable (it returns Postgres error text), but the same
broad-catch-and-return-`str(e)` pattern must NOT be copied onto the forthcoming
BYOK encrypt/decrypt endpoints, where an exception string could carry ciphertext
or key material and would violate D-04. Flagging now as the BYOK persistence layer
is built on top of this phase.

**Fix:** Keep the SQL path as-is, but when the BYOK key read/write endpoints are
added, do not echo raw exception strings to clients; log server-side with a
generic client message.

---

_Reviewed: 2026-06-18_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
