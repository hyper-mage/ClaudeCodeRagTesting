# KEY-ROTATION-RUNBOOK — BYOK master-key rotation (Phase 9, D-02 / D-04)

Operational runbook for rotating `KEY_ENCRYPTION_SECRET`, the app-layer master key that
encrypts user OpenRouter keys in `user_api_keys.encrypted_key`. Rotation is **lazy** via
`MultiFernet`: both the new and the old key are configured during a rotation window, every
read re-encrypts stale rows under the new key, and the old key is dropped once all rows have
migrated.

This procedure satisfies ROADMAP success criterion #4 (documented rotation path).

## Invariants (do not violate)

- **`KEY_ENCRYPTION_SECRET` is a comma-separated list of url-safe base64 Fernet keys, NEW KEY FIRST.**
  Example during rotation: `KEY_ENCRYPTION_SECRET="<new>,<old>"`.
- **Encrypt always uses the FIRST (primary) key.** `MultiFernet` encrypts under `keys[0]`.
- **Decrypt tries EACH key in order.** This is why the old key must remain present until every
  row is re-encrypted.
- **`crypto_service` reads the key list at call time** via `get_settings().key_encryption_secret`
  (`backend/services/crypto_service.py`, helper `_multifernet()`), so a restart picks up the new list.
- **Distinct value per environment (D-04).** Dev uses `.env`; prod uses `.env.prod` + the Fly
  secret store. **Never copy the dev key into prod** — a single leak must not compromise both
  environments, and rotating one must not break the other (see Pitfall: cross-env key reuse).
- **`key_version`** is an integer counter on `user_api_keys` recording which master key encrypted
  a given row. Encrypt/insert paths (Phase 10) write the current primary version; the lazy
  re-encrypt path (Phase 11) bumps it.
  - **WR-05 — Phase 9 placeholder, NOT maintained here.** Phase 9 ships only the stateless
    `crypto_service` (encrypt/decrypt/rotate operate on token strings) and the `user_api_keys`
    table DDL with `key_version INTEGER NOT NULL DEFAULT 1`. **No code in Phase 9 reads, sets, or
    increments `key_version`** — `crypto_service` cannot, because it never touches storage; the
    row-writer must. Until the Phase 10 persistence layer lands, **do not trust the stored
    `key_version` as ground truth for which key encrypted a row** (every row will read the `1`
    default regardless of the actual encrypting key). The contract for downstream phases is:
    Phase 10 insert/update sets `key_version` to the current primary version on write; Phase 11's
    lazy re-encrypt bumps it alongside `encrypted_key` (see Step 4's UPDATE shape below). This
    note exists so a future migration/rotation tool does not read `key_version` before any phase
    actually maintains it.
- The master key, plaintext key, and ciphertext are **never logged, traced, or returned** —
  `crypto_service` enforces this (D-04).

## Crypto surface being operated

From `backend/services/crypto_service.py`:

- `encrypt_key(plaintext: str) -> str` — encrypt a new key under the current primary master key.
- `decrypt_key(ciphertext: str) -> str` — decrypt, trying each configured master key in order.
- `rotate_token(ciphertext: str) -> str` — re-encrypt an existing token under the current primary key.

## Rotation procedure

### Step 1 — Generate a NEW per-env master key

Generate a fresh key **for the target environment only**. Do not reuse another environment's value.

```bash
cd backend && venv/Scripts/python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

This prints a 44-character url-safe base64 string (32 raw bytes) — the exact format `Fernet(key)` expects.

### Step 2 — Set `KEY_ENCRYPTION_SECRET` to the comma-separated list, NEW KEY FIRST

Set the secret to `new,old` in the target environment's secret store:

- **Dev:** edit `.env` → `KEY_ENCRYPTION_SECRET="<new>,<old>"`
- **Prod:** edit `.env.prod` AND set the Fly secret:
  ```bash
  fly secrets set KEY_ENCRYPTION_SECRET="<new>,<old>"
  ```

The list order is load-bearing: `MultiFernet([Fernet(new), Fernet(old)])` encrypts with `new`
and can still decrypt rows written under `old`. **Never** reuse the dev key in prod (D-04).

### Step 3 — Deploy / restart so the backend reads the new list

Restart the backend process (or `fly deploy` for prod). Because `crypto_service` reads
`get_settings().key_encryption_secret` at call time, the new two-key `MultiFernet` is active
after restart. New encryptions immediately use the new primary key; existing rows still decrypt
via the old key in the list.

### Step 4 — Lazy re-encryption on read

During the rotation window, whenever a row is read and decrypted (Phase 11 per-request path):

1. `decrypt_key(row.encrypted_key)` — succeeds via the old key in the `MultiFernet` list.
2. If the row's `key_version` is behind the current primary version, call
   `rotate_token(row.encrypted_key)` to re-encrypt under the new primary key.
3. Write the re-encrypted token back with a bumped `key_version`. Intended UPDATE shape against
   `user_api_keys` (service-role client; the write path lands in the Phase 10/11 consumers):

   ```sql
   UPDATE user_api_keys
      SET encrypted_key = :rotated_token,
          key_version   = :new_key_version,
          updated_at    = now()
    WHERE user_id = :user_id;
   ```

Rows are migrated incrementally as users are active — no bulk migration job required.

### Step 5 — Drop the old key once all rows are re-encrypted

After every row has `key_version` at the new version (or after the rotation window closes and any
remaining stale rows are force-rotated), set `KEY_ENCRYPTION_SECRET` to the new key alone and
redeploy/restart:

- **Dev:** `.env` → `KEY_ENCRYPTION_SECRET="<new>"`
- **Prod:** `.env.prod` + `fly secrets set KEY_ENCRYPTION_SECRET="<new>"`

Once the old key is removed from the list, any token still encrypted under it will fail to decrypt,
so confirm migration is complete (e.g. `SELECT count(*) FROM user_api_keys WHERE key_version < :new_key_version;`
returns 0) before this step.

## Pitfall: cross-environment key reuse

Copying the dev `KEY_ENCRYPTION_SECRET` into `.env.prod` / Fly means one leaked key compromises
both environments, and rotating in one breaks the other. Always generate a **separate**
`Fernet.generate_key()` per environment (Step 1). The dev value never leaves `.env`; the prod
value is generated and set only in the prod secret store.

## Pitfall: Fernet key encoding mismatch

`KEY_ENCRYPTION_SECRET` entries must be url-safe base64 (the output of `Fernet.generate_key()`),
not raw 32-byte strings or hex — otherwise `Fernet(key)` raises
`ValueError: Fernet key must be 32 url-safe base64-encoded bytes`. Each entry is 44 characters.
