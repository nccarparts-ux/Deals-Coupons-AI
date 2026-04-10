-- ============================================================
-- Marketing System -- Run once in Supabase SQL Editor
-- Safe to re-run: uses IF NOT EXISTS / ADD COLUMN IF NOT EXISTS
-- ============================================================

-- Config (stores key/value pairs: telegram offset, latest PDF path, etc.)
CREATE TABLE IF NOT EXISTS config (
  id    BIGSERIAL PRIMARY KEY,
  key   TEXT UNIQUE NOT NULL,
  value TEXT
);

-- Deals table already exists from the main pipeline.
-- Add all marketing-system columns that may be missing.
ALTER TABLE deals ADD COLUMN IF NOT EXISTS price             NUMERIC;
ALTER TABLE deals ADD COLUMN IF NOT EXISTS discount_pct      INT;
ALTER TABLE deals ADD COLUMN IF NOT EXISTS amazon_url        TEXT;
ALTER TABLE deals ADD COLUMN IF NOT EXISTS raw_text          TEXT;
ALTER TABLE deals ADD COLUMN IF NOT EXISTS keywords          TEXT;
ALTER TABLE deals ADD COLUMN IF NOT EXISTS slug              TEXT;
ALTER TABLE deals ADD COLUMN IF NOT EXISTS fetched_at        TIMESTAMPTZ;
ALTER TABLE deals ADD COLUMN IF NOT EXISTS content_written   BOOL DEFAULT false;
ALTER TABLE deals ADD COLUMN IF NOT EXISTS email_sent        BOOL DEFAULT false;
ALTER TABLE deals ADD COLUMN IF NOT EXISTS website_published BOOL DEFAULT false;
ALTER TABLE deals ADD COLUMN IF NOT EXISTS social_queued     BOOL DEFAULT false;
ALTER TABLE deals ADD COLUMN IF NOT EXISTS page_views        INT  DEFAULT 0;
ALTER TABLE deals ADD COLUMN IF NOT EXISTS click_throughs    INT  DEFAULT 0;

-- Make slug unique if it isn't already (safe no-op if index exists)
CREATE UNIQUE INDEX IF NOT EXISTS idx_deals_slug ON deals (slug) WHERE slug IS NOT NULL;

-- Backfill fetched_at from created_at for existing rows
UPDATE deals SET fetched_at = created_at WHERE fetched_at IS NULL AND created_at IS NOT NULL;

-- Email subscribers
CREATE TABLE IF NOT EXISTS subscribers (
  id            BIGSERIAL PRIMARY KEY,
  email         TEXT UNIQUE,
  first_name    TEXT,
  source        TEXT,
  referral_code TEXT UNIQUE,
  referred_by   BIGINT,
  confirmed     BOOL        DEFAULT false,
  confirmed_at  TIMESTAMPTZ,
  joined_at     TIMESTAMPTZ DEFAULT now(),
  unsubscribed  BOOL        DEFAULT false
);

-- Content queue (AI-generated copy for each platform)
CREATE TABLE IF NOT EXISTS content_queue (
  id           BIGSERIAL PRIMARY KEY,
  deal_id      TEXT,
  platform     TEXT,
  content_text TEXT,
  hashtags     TEXT,
  status       TEXT        DEFAULT 'draft',
  created_at   TIMESTAMPTZ DEFAULT now(),
  used_at      TIMESTAMPTZ
);

-- Email send log
CREATE TABLE IF NOT EXISTS email_log (
  id            BIGSERIAL PRIMARY KEY,
  subscriber_id BIGINT,
  template_name TEXT,
  subject       TEXT,
  sent_at       TIMESTAMPTZ,
  status        TEXT
);

-- Referral link click tracking
CREATE TABLE IF NOT EXISTS referral_clicks (
  id            BIGSERIAL PRIMARY KEY,
  referral_code TEXT,
  clicked_at    TIMESTAMPTZ,
  converted     BOOL DEFAULT false
);

-- Google Search Console performance data
CREATE TABLE IF NOT EXISTS seo_performance (
  id           BIGSERIAL PRIMARY KEY,
  deal_slug    TEXT,
  keyword      TEXT,
  impressions  INT     DEFAULT 0,
  clicks       INT     DEFAULT 0,
  avg_position NUMERIC,
  recorded_at  TIMESTAMPTZ DEFAULT now()
);

-- Learning engine insights
CREATE TABLE IF NOT EXISTS learning_log (
  id          BIGSERIAL PRIMARY KEY,
  metric      TEXT,
  value       NUMERIC,
  context     JSONB,
  recorded_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_deals_content_written   ON deals (content_written);
CREATE INDEX IF NOT EXISTS idx_deals_website_published ON deals (website_published);
CREATE INDEX IF NOT EXISTS idx_deals_fetched_at        ON deals (fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_queue_deal_id   ON content_queue (deal_id, platform);
CREATE INDEX IF NOT EXISTS idx_email_log_subscriber    ON email_log (subscriber_id);
CREATE INDEX IF NOT EXISTS idx_learning_log_metric     ON learning_log (metric, recorded_at DESC);
