-- ============================================================
-- Marketing System -- Run once in Supabase SQL Editor
-- ============================================================

-- Config (stores key/value pairs: telegram offset, latest PDF path, etc.)
CREATE TABLE IF NOT EXISTS config (
  id    BIGSERIAL PRIMARY KEY,
  key   TEXT UNIQUE NOT NULL,
  value TEXT
);

-- Deals (sourced from Telegram channel)
CREATE TABLE IF NOT EXISTS deals (
  id                TEXT PRIMARY KEY,
  title             TEXT,
  price             NUMERIC,
  original_price    NUMERIC,
  discount_pct      INT,
  amazon_url        TEXT,
  image_url         TEXT,
  category          TEXT,
  raw_text          TEXT,
  keywords          TEXT,
  slug              TEXT UNIQUE,
  fetched_at        TIMESTAMPTZ,
  content_written   BOOL DEFAULT false,
  email_sent        BOOL DEFAULT false,
  website_published BOOL DEFAULT false,
  social_queued     BOOL DEFAULT false,
  page_views        INT  DEFAULT 0,
  click_throughs    INT  DEFAULT 0
);

-- Email subscribers
CREATE TABLE IF NOT EXISTS subscribers (
  id           BIGSERIAL PRIMARY KEY,
  email        TEXT UNIQUE,
  first_name   TEXT,
  source       TEXT,
  referral_code TEXT UNIQUE,
  referred_by  BIGINT,
  confirmed    BOOL        DEFAULT false,
  confirmed_at TIMESTAMPTZ,
  joined_at    TIMESTAMPTZ DEFAULT now(),
  unsubscribed BOOL        DEFAULT false
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
  id          BIGSERIAL PRIMARY KEY,
  deal_slug   TEXT,
  keyword     TEXT,
  impressions INT     DEFAULT 0,
  clicks      INT     DEFAULT 0,
  avg_position NUMERIC,
  recorded_at TIMESTAMPTZ DEFAULT now()
);

-- Learning engine insights
CREATE TABLE IF NOT EXISTS learning_log (
  id          BIGSERIAL PRIMARY KEY,
  metric      TEXT,
  value       NUMERIC,
  context     JSONB,
  recorded_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_deals_content_written   ON deals (content_written);
CREATE INDEX IF NOT EXISTS idx_deals_website_published ON deals (website_published);
CREATE INDEX IF NOT EXISTS idx_deals_fetched_at        ON deals (fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_content_queue_deal_id   ON content_queue (deal_id, platform);
CREATE INDEX IF NOT EXISTS idx_email_log_subscriber    ON email_log (subscriber_id);
CREATE INDEX IF NOT EXISTS idx_learning_log_metric     ON learning_log (metric, recorded_at DESC);
