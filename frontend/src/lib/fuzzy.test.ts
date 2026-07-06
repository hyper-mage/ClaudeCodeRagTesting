import { describe, it, expect } from 'vitest'
import { fuzzyScore, matchModel } from './fuzzy'

/**
 * Unit tests for the hand-rolled fuzzy matcher (D-08, zero new deps) — the UI-SPEC
 * LOCKED ranking the picker's search relies on (Plan 15-04 Task 1, MODEL-01):
 *
 *   - exact substring > match starting at a word boundary (/, -, ., space, :) >
 *     tighter subsequence gap span; earlier index wins within a substring tier
 *   - subsequence = typo tolerance: 'lama33' matches 'llama-3.3'
 *   - non-subsequence → null (row removed, never disabled)
 *   - case-insensitive; empty query → 0 (match-all)
 *   - matchModel = best of id/name; null name falls back to id-only; both null → null
 *
 * Ties are resolved by the CALLER sorting alphabetically by label — the scorer
 * bakes in no tie-breaking.
 */

describe('fuzzyScore — locked ranking tiers', () => {
  it('scores an exact substring above any subsequence match', () => {
    const substring = fuzzyScore('llama', 'meta/llama-3.3')
    // 'lab-llm-alpha-max' contains l-l-a-m-a only as a scattered subsequence.
    const subsequence = fuzzyScore('llama', 'lab-llm-alpha-max')
    expect(substring).not.toBeNull()
    expect(subsequence).not.toBeNull()
    expect(substring!).toBeGreaterThan(subsequence!)
  })

  it('scores a substring at a word boundary above a mid-word substring', () => {
    const atBoundary = fuzzyScore('llama', 'meta/llama-3.3') // preceded by '/'
    const midWord = fuzzyScore('llama', 'colossalllama') // preceded by 'l'
    expect(atBoundary!).toBeGreaterThan(midWord!)
  })

  it('treats query at index 0 as a boundary match', () => {
    const atStart = fuzzyScore('llama', 'llama-3.3')
    const afterSlash = fuzzyScore('llama', 'meta/llama-3.3')
    // Both are boundary-tier; the earlier index wins.
    expect(atStart!).toBeGreaterThan(afterSlash!)
  })

  it('prefers the earlier index within the same substring tier', () => {
    const earlier = fuzzyScore('llama', 'xllama') // mid-word, index 1
    const later = fuzzyScore('llama', 'xxllama') // mid-word, index 2
    expect(earlier!).toBeGreaterThan(later!)
  })

  it("matches 'lama33' against 'llama-3.3' as a subsequence (typo tolerance)", () => {
    const score = fuzzyScore('lama33', 'llama-3.3')
    expect(score).not.toBeNull()
    // Subsequence tier always ranks below the substring tier.
    expect(score!).toBeLessThan(fuzzyScore('llama', 'colossalllama')!)
  })

  it('scores a tighter subsequence span higher', () => {
    const tight = fuzzyScore('la', 'lxa') // span 3
    const loose = fuzzyScore('la', 'lxxa') // span 4
    expect(tight!).toBeGreaterThan(loose!)
  })

  it('returns null when the query is not a subsequence of the target', () => {
    expect(fuzzyScore('zzz', 'llama-3.3')).toBeNull()
    // Order matters: chars present but out of order are NOT a subsequence.
    expect(fuzzyScore('ba', 'ab')).toBeNull()
  })

  it('is case-insensitive', () => {
    expect(fuzzyScore('LLAMA', 'Llama-3.3')).toBe(fuzzyScore('llama', 'llama-3.3'))
    expect(fuzzyScore('LAMA33', 'LLAMA-3.3')).toBe(fuzzyScore('lama33', 'llama-3.3'))
  })

  it('returns 0 (match-all) for the empty query', () => {
    expect(fuzzyScore('', 'anything at all')).toBe(0)
    expect(fuzzyScore('', '')).toBe(0)
  })
})

describe('matchModel — best of id/name', () => {
  it('returns the max of the id and name scores', () => {
    // name 'Claude Paid' matches at index 0 (boundary) — beats the id's index-10 match.
    const best = matchModel('claude', 'anthropic/claude', 'Claude Paid')
    expect(best).toBe(fuzzyScore('claude', 'Claude Paid'))
    expect(best!).toBeGreaterThan(fuzzyScore('claude', 'anthropic/claude')!)
  })

  it('falls back to the id score when only the id matches', () => {
    expect(matchModel('anthropic', 'anthropic/claude', 'Claude Paid')).toBe(
      fuzzyScore('anthropic', 'anthropic/claude')
    )
  })

  it('falls back to the name score when only the name matches', () => {
    expect(matchModel('paid', 'anthropic/claude', 'Claude Paid')).toBe(
      fuzzyScore('paid', 'Claude Paid')
    )
  })

  it('handles a null name by scoring the id only', () => {
    expect(matchModel('llama', 'meta/llama-3.3', null)).toBe(
      fuzzyScore('llama', 'meta/llama-3.3')
    )
    expect(matchModel('zzz', 'meta/llama-3.3', null)).toBeNull()
  })

  it("matches 'lama33' against the id 'meta/llama-3.3' (subsequence over id)", () => {
    expect(matchModel('lama33', 'meta/llama-3.3', 'Llama 3.3 70B')).not.toBeNull()
  })

  it('returns null when neither the id nor the name matches', () => {
    expect(matchModel('zzz', 'anthropic/claude', 'Claude Paid')).toBeNull()
  })
})
