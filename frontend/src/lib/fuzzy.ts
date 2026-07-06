// Hand-rolled fuzzy matcher for the model picker search (D-08 — zero new deps).
//
// Ranking (UI-SPEC LOCKED): exact substring > match starting at a word boundary
// (/, -, ., space, :) > tighter subsequence gap span. Ties are alphabetical by
// label — resolved by the CALLER's sort, never baked into the scorer.
// Case-insensitive over id AND name. Conventions follow sibling lib/ files
// (api.ts, pkce.ts): named exports only, no default export, no React import,
// camelCase, 2-space indent, single quotes, no semicolons.

const BOUNDARY = /[\s/\-.:]/

/**
 * Score `target` against `query`. Returns:
 *   - substring tier: 10000 + 1000 boundary bonus - match index
 *   - subsequence tier: 1000 - (span - query.length) — tighter span scores higher
 *   - null when the query is not even a subsequence (row removed, never disabled)
 *   - 0 for the empty query (match-all)
 */
export function fuzzyScore(query: string, target: string): number | null {
  const q = query.toLowerCase()
  const t = target.toLowerCase()
  if (q.length === 0) return 0
  const sub = t.indexOf(q)
  if (sub >= 0) {
    const atBoundary = sub === 0 || BOUNDARY.test(t[sub - 1])
    return 10000 + (atBoundary ? 1000 : 0) - sub // substring tier; boundary + earlier wins
  }
  // Subsequence tier: query chars in order, gaps allowed (typo tolerance per spec:
  // 'lama33' matches 'llama-3.3').
  let ti = 0
  let first = -1
  let last = -1
  for (let qi = 0; qi < q.length; qi++) {
    ti = t.indexOf(q[qi], ti)
    if (ti === -1) return null // not a subsequence → no match, row removed
    if (first === -1) first = ti
    last = ti
    ti++
  }
  const span = last - first + 1
  return 1000 - (span - q.length) // tighter span scores higher
}

/** Per model: best of id/name; null name falls back to id-only; both null → null. */
export function matchModel(query: string, id: string, name: string | null): number | null {
  const a = fuzzyScore(query, id)
  const b = name ? fuzzyScore(query, name) : null
  if (a === null) return b
  if (b === null) return a
  return Math.max(a, b)
}
