-- 005_social_expansion.sql
-- Extends existing tables for multi-platform publishing, A/B testing,
-- TikTok video output, SEO blog integration, and trend/viral scoring.
-- No new tables created. All ADD COLUMN IF NOT EXISTS — safe to run multiple times.

-- ── posted_deals ─────────────────────────────────────────────────────────────

ALTER TABLE public.posted_deals
    ADD COLUMN IF NOT EXISTS platform_copy      JSONB,   -- generated copy keyed by platform e.g. {"telegram": "...", "tiktok": "..."}
    ADD COLUMN IF NOT EXISTS persona_used       TEXT,    -- which of the 5 personas wrote the copy
    ADD COLUMN IF NOT EXISTS ab_variant         TEXT,    -- 'a' or 'b' for split testing
    ADD COLUMN IF NOT EXISTS tiktok_video_path  TEXT,    -- local path to generated .mp4 file
    ADD COLUMN IF NOT EXISTS blog_post_slug     TEXT;    -- links this deal to its SEO blog post

-- ── deal_candidates ──────────────────────────────────────────────────────────

ALTER TABLE public.deal_candidates
    ADD COLUMN IF NOT EXISTS trend_score        FLOAT,   -- score boost from Google Trends keyword match (0-100)
    ADD COLUMN IF NOT EXISTS viral_potential    FLOAT;   -- predicted shareability 1-10

-- ── performance_metrics ──────────────────────────────────────────────────────

ALTER TABLE public.performance_metrics
    ADD COLUMN IF NOT EXISTS platform           TEXT;    -- which platform this metric belongs to (telegram, tiktok, etc.)
