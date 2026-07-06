-- Phase 15 — favorite models on user_preferences (MODEL-08, D-05).
-- ONE additive statement, no backfill, no destructive change to existing data:
-- a TEXT[] favorites column defaulting to the empty array, so existing rows and
-- brand-new users both resolve to "no favorites" without a backfill.
-- favorite_models is deliberately NOT a FK to model_cache (same deprecation-
-- tolerance rationale as default_model, D-06): a favorited model can be
-- deprecated and disappear from the cache while the user's starred slug must
-- persist as a plain string (the picker simply stops rendering it).
-- RLS: the own-row policies from migration 000032 apply to the WHOLE row, so
-- they cover this new column automatically — add NO policies here.
-- Each migration runs as one transaction (Supabase default).
-- Depends on: user_preferences (migration 000032).

ALTER TABLE user_preferences ADD COLUMN favorite_models TEXT[] NOT NULL DEFAULT '{}';
