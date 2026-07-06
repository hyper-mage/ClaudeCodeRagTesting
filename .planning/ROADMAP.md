**Requirements:** SEC-03 (dependency)
**Plans:** 2 plans

Plans:

- [x] 999.2-01-PLAN.md — Safe-by-default burn script + pure-logic unit tests (no spend) + greppable D-05a app-kill-switch test
- [x] 999.2-02-PLAN.md — Human-gated LIVE guardrail trip on the prod owner account + SEC-03 finding artifact (autonomous: false)

### Phase 15: Options UI Capstone + Demo Gating

**Goal:** Close out v1.2: key-gated model selection (picking a model with no key triggers OAuth connect), favorite/pin models, demo-fallback flag decision + non-dismissible demo banner (gated on the 999.2 SEC-03 PASS finding), and the picker polish the audit flagged — render popular marking (B-1/MODEL-03) and add catalog search (W-1/MODEL-01).
**Requirements**: KEY-05, MODEL-08, DEMO-01, DEMO-02, SEC-03 (+ audit fold-ins: MODEL-03 render seam, MODEL-01 search)
**Depends on:** Phase 14, Phase 999.2 (SEC-03 finding: .planning/phases/999.2-cost-guardrail-burn-script/999.2-SEC-03-FINDING.md)
**Plans:** 5/8 plans executed

Plans:
**Wave 1**

- [x] 15-01-PLAN.md — Migration 033 + schema fields + favorite_models roundtrip + demo_enabled in both status branches + [BLOCKING] dev db push (wave 1)
- [x] 15-02-PLAN.md — chat.py demo resolution: _demo_model_for free-guard + flag-gated use_demo override, SEC-03 killswitch tests pinned green (wave 1)
- [x] 15-03-PLAN.md — OAuthCallbackPage one-shot pending-selection resume + combined toasts + new page test file (wave 1)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 15-04-PLAN.md — Picker rebuild: hand-rolled fuzzy matcher, Favorites/Popular/All sections, Popular chip (B-1), search + combobox a11y migration (W-1) (wave 2)
- [x] 15-05-PLAN.md — useKeyGate shared gate + ConfirmDialog primary variant + both-surface wiring + stale-stash hygiene (KEY-05) (wave 2)

**Wave 3** *(blocked on Wave 2 completion)*

- [ ] 15-06-PLAN.md — Favorite star + optimistic whole-array PUT persistence + Shift+Enter (MODEL-08) (wave 3)
- [ ] 15-07-PLAN.md — Demo banner (locked copy, non-dismissible) + mode:"demo" signal read + [Use demo] 403 recovery wiring (wave 3)

**Wave 4** *(blocked on Wave 3 completion)*

- [ ] 15-08-PLAN.md — Human-gated prod deploy: migrations 029-033, LLM_API_KEY verify, DEMO_FALLBACK_ENABLED=true, live smoke (autonomous: false) (wave 4)
