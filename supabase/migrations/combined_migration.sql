-- Deal Sniper AI Platform Schema Extension
-- Extends existing deals/coupons tables with monitoring, analytics, and affiliate features

-- Products table: SKU-level product tracking across retailers
CREATE TABLE IF NOT EXISTS public.products (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    sku TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,
    brand TEXT,
    image_url TEXT,
    upc TEXT,
    model_number TEXT,
    -- Retailer identification
    retailer_id TEXT NOT NULL,  -- amazon, walmart, target, etc.
    retailer_product_id TEXT,   -- Retailer-specific product ID
    retailer_url TEXT,
    -- Price tracking fields
    current_price DECIMAL(10,2),
    original_price DECIMAL(10,2),
    currency TEXT DEFAULT 'USD',
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_scraped_at TIMESTAMP WITH TIME ZONE,
    -- Metadata
    is_active BOOLEAN DEFAULT true,
    UNIQUE(retailer_id, retailer_product_id)
);

-- Price history table: timestamped price tracking for anomaly detection
CREATE TABLE IF NOT EXISTS public.price_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    price DECIMAL(10,2) NOT NULL,
    currency TEXT DEFAULT 'USD',
    -- Price context
    is_discounted BOOLEAN DEFAULT false,
    discount_percent INTEGER,
    coupon_applied BOOLEAN DEFAULT false,
    -- Source
    source TEXT CHECK (source IN ('crawler', 'api', 'community')),
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- Index for fast time-series queries
    INDEX idx_price_history_product_time (product_id, captured_at DESC)
);

-- Deal candidates table: potential deals before scoring/post approval
CREATE TABLE IF NOT EXISTS public.deal_candidates (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    deal_id UUID REFERENCES public.deals(id) ON DELETE SET NULL,  -- Linked to existing deals table if matched
    -- Price information
    original_price DECIMAL(10,2),
    current_price DECIMAL(10,2),
    price_drop_percent DECIMAL(5,2),
    absolute_savings DECIMAL(10,2),
    -- Detection metrics
    anomaly_score DECIMAL(5,2),  -- Statistical anomaly score
    glitch_score DECIMAL(5,2),   -- Pricing glitch probability
    coupon_available BOOLEAN DEFAULT false,
    coupon_stacking_possible BOOLEAN DEFAULT false,
    -- Scoring
    base_score DECIMAL(5,2),     -- Weighted score 0-100
    final_score DECIMAL(5,2),    -- After community signal adjustment
    score_components JSONB,      -- Detailed breakdown of scoring factors
    -- Status
    status TEXT CHECK (status IN ('pending', 'approved', 'rejected', 'posted', 'expired')) DEFAULT 'pending',
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    reviewed_by UUID REFERENCES auth.users(id),
    -- Indexes for performance
    INDEX idx_deal_candidates_status_score (status, final_score DESC),
    INDEX idx_deal_candidates_detected (detected_at DESC)
);

-- Posted deals table: deals that have been published with performance metrics
CREATE TABLE IF NOT EXISTS public.posted_deals (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    deal_candidate_id UUID NOT NULL REFERENCES public.deal_candidates(id) ON DELETE CASCADE,
    deal_id UUID REFERENCES public.deals(id) ON DELETE CASCADE,
    -- Posting details
    posted_to TEXT[],  -- Platform array: ['telegram', 'discord', 'twitter', 'tiktok']
    posted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    posted_by UUID REFERENCES auth.users(id),
    -- Performance tracking
    clicks INTEGER DEFAULT 0,
    conversions INTEGER DEFAULT 0,
    estimated_revenue DECIMAL(10,2) DEFAULT 0,
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- Index for analytics
    INDEX idx_posted_deals_performance (posted_at DESC, estimated_revenue DESC)
);

-- Affiliate links table: cache of converted affiliate URLs
CREATE TABLE IF NOT EXISTS public.affiliate_links (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    original_url TEXT NOT NULL,
    affiliate_url TEXT NOT NULL,
    affiliate_program TEXT NOT NULL,  -- amazon_associates, walmart_affiliate, etc.
    retailer_id TEXT NOT NULL,
    product_id UUID REFERENCES public.products(id) ON DELETE SET NULL,
    -- Metadata
    clicks INTEGER DEFAULT 0,
    conversions INTEGER DEFAULT 0,
    revenue DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    -- Unique constraint to avoid duplicates
    UNIQUE(original_url, affiliate_program),
    INDEX idx_affiliate_links_product (product_id)
);

-- Coupon codes table: discovered coupon codes with success rates (beyond deal-specific coupons)
CREATE TABLE IF NOT EXISTS public.coupon_codes (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    code TEXT NOT NULL,
    retailer_id TEXT NOT NULL,
    description TEXT,
    discount_type TEXT CHECK (discount_type IN ('percentage', 'fixed', 'free_shipping', 'bogo')),
    discount_value DECIMAL(10,2),
    min_purchase DECIMAL(10,2),
    category TEXT,
    -- Success tracking
    total_attempts INTEGER DEFAULT 0,
    successful_uses INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 0,
    -- Validity
    expires_at TIMESTAMP WITH TIME ZONE,
    discovered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_verified_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true,
    -- Indexes
    UNIQUE(retailer_id, code),
    INDEX idx_coupon_codes_success_rate (retailer_id, success_rate DESC)
);

-- Scraping sessions table: crawler session tracking for anti-blocking
CREATE TABLE IF NOT EXISTS public.scraping_sessions (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    retailer_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    user_agent TEXT,
    proxy_ip TEXT,
    proxy_country TEXT,
    -- Request metrics
    total_requests INTEGER DEFAULT 0,
    successful_requests INTEGER DEFAULT 0,
    blocked_requests INTEGER DEFAULT 0,
    captcha_encounters INTEGER DEFAULT 0,
    -- Performance
    avg_response_time_ms INTEGER,
    success_rate DECIMAL(5,2),
    -- Timestamps
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    -- Index for analysis
    INDEX idx_scraping_sessions_retailer_time (retailer_id, started_at DESC),
    UNIQUE(retailer_id, session_id)
);

-- Performance metrics table: analytics data for weight optimization
CREATE TABLE IF NOT EXISTS public.performance_metrics (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    metric_type TEXT NOT NULL,  -- 'deal_score_component', 'retailer_success', 'community_signal'
    metric_name TEXT NOT NULL,  -- e.g., 'price_drop_percent', 'amazon_success_rate'
    metric_value DECIMAL(10,4) NOT NULL,
    sample_size INTEGER DEFAULT 1,
    confidence DECIMAL(5,4),  -- Statistical confidence
    period_start TIMESTAMP WITH TIME ZONE,
    period_end TIMESTAMP WITH TIME ZONE,
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- Index for querying
    INDEX idx_performance_metrics_type_time (metric_type, period_end DESC)
);

-- Retailer configs table: retailer-specific scraping configurations
CREATE TABLE IF NOT EXISTS public.retailer_configs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    retailer_id TEXT NOT NULL UNIQUE,
    config JSONB NOT NULL,  -- Store retailer-specific selectors, patterns, etc.
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by UUID REFERENCES auth.users(id)
);

-- Enable Row Level Security (RLS) on new tables
ALTER TABLE public.products ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.price_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.deal_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.posted_deals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.affiliate_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.coupon_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scraping_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.performance_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.retailer_configs ENABLE ROW LEVEL SECURITY;

-- RLS Policies
-- Products: Read-only for authenticated users, admin full access
CREATE POLICY "Anyone can view products" ON public.products FOR SELECT USING (true);
CREATE POLICY "Admins can manage products" ON public.products FOR ALL USING (
    auth.uid() IN (SELECT id FROM public.profiles WHERE role = 'admin')
);

-- Price history: Read-only for authenticated users
CREATE POLICY "Authenticated users can view price history" ON public.price_history FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "System can insert price history" ON public.price_history FOR INSERT WITH CHECK (true);
CREATE POLICY "Admins can manage price history" ON public.price_history FOR ALL USING (
    auth.uid() IN (SELECT id FROM public.profiles WHERE role = 'admin')
);

-- Deal candidates: Authenticated users can view, admins can manage
CREATE POLICY "Authenticated users can view deal candidates" ON public.deal_candidates FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "System can insert deal candidates" ON public.deal_candidates FOR INSERT WITH CHECK (true);
CREATE POLICY "Admins can manage deal candidates" ON public.deal_candidates FOR ALL USING (
    auth.uid() IN (SELECT id FROM public.profiles WHERE role = 'admin')
);

-- Posted deals: Authenticated users can view
CREATE POLICY "Anyone can view posted deals" ON public.posted_deals FOR SELECT USING (true);
CREATE POLICY "System can insert posted deals" ON public.posted_deals FOR INSERT WITH CHECK (true);
CREATE POLICY "Admins can manage posted deals" ON public.posted_deals FOR ALL USING (
    auth.uid() IN (SELECT id FROM public.profiles WHERE role = 'admin')
);

-- Affiliate links: Authenticated users can view, system can insert
CREATE POLICY "Authenticated users can view affiliate links" ON public.affiliate_links FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "System can manage affiliate links" ON public.affiliate_links FOR ALL USING (true);

-- Coupon codes: Anyone can view active coupons
CREATE POLICY "Anyone can view active coupon codes" ON public.coupon_codes FOR SELECT USING (is_active = true);
CREATE POLICY "System can manage coupon codes" ON public.coupon_codes FOR ALL USING (true);

-- Scraping sessions: Admins only (sensitive data)
CREATE POLICY "Admins can view scraping sessions" ON public.scraping_sessions FOR SELECT USING (
    auth.uid() IN (SELECT id FROM public.profiles WHERE role = 'admin')
);
CREATE POLICY "System can insert scraping sessions" ON public.scraping_sessions FOR INSERT WITH CHECK (true);

-- Performance metrics: Authenticated users can view
CREATE POLICY "Authenticated users can view performance metrics" ON public.performance_metrics FOR SELECT USING (auth.role() = 'authenticated');
CREATE POLICY "System can manage performance metrics" ON public.performance_metrics FOR ALL USING (true);

-- Retailer configs: Admins only
CREATE POLICY "Admins can manage retailer configs" ON public.retailer_configs FOR ALL USING (
    auth.uid() IN (SELECT id FROM public.profiles WHERE role = 'admin')
);

-- Create indexes for performance
CREATE INDEX idx_products_retailer_sku ON public.products(retailer_id, sku);
CREATE INDEX idx_products_category ON public.products(category);
CREATE INDEX idx_price_history_product_captured ON public.price_history(product_id, captured_at DESC);
CREATE INDEX idx_deal_candidates_final_score ON public.deal_candidates(final_score DESC) WHERE status = 'pending';
CREATE INDEX idx_posted_deals_posted_at ON public.posted_deals(posted_at DESC);
CREATE INDEX idx_coupon_codes_retailer_active ON public.coupon_codes(retailer_id, is_active, success_rate DESC);
CREATE INDEX idx_affiliate_links_retailer ON public.affiliate_links(retailer_id, clicks DESC);

-- Create updated_at triggers for new tables
CREATE TRIGGER update_products_updated_at BEFORE UPDATE
    ON public.products FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_affiliate_links_updated_at BEFORE UPDATE
    ON public.affiliate_links FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- Insert default retailer configurations
INSERT INTO public.retailer_configs (retailer_id, config) VALUES
('amazon', '{"selectors": {"price": "#priceblock_ourprice, #priceblock_dealprice, .a-price-whole", "title": "#productTitle", "image": "#landingImage", "coupon": ".promoPriceBlockMessage"}}'),
('walmart', '{"selectors": {"price": "[data-automation-id=\"product-price\"]", "title": "h1[data-automation-id=\"product-title\"]", "image": "img[data-automation-id=\"product-image\"]", "coupon": ".promo-badge"}}'),
('target', '{"selectors": {"price": "[data-test=\"product-price\"]", "title": "h1[data-test=\"product-title\"]", "image": "img[data-test=\"product-image\"]", "coupon": ".promo"}}'),
('home_depot', '{"selectors": {"price": ".price__wrapper", "title": ".product-details__title", "image": ".image-viewer__image", "coupon": ".savings-badge"}}')
ON CONFLICT (retailer_id) DO NOTHING;

-- Create function to calculate success rate for coupon codes
CREATE OR REPLACE FUNCTION public.update_coupon_success_rate()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.total_attempts > 0 THEN
        NEW.success_rate = (NEW.successful_uses::DECIMAL / NEW.total_attempts) * 100;
    END IF;
    NEW.last_verified_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_coupon_success_rate BEFORE UPDATE
    ON public.coupon_codes FOR EACH ROW EXECUTE FUNCTION public.update_coupon_success_rate();-- Growth Engine Schema Extension
-- Adds tables for community growth features: user engagement, referrals, leaderboards, etc.

-- User engagement tracking
CREATE TABLE IF NOT EXISTS public.user_engagement (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Engagement type
    action TEXT NOT NULL CHECK (action IN ('click', 'share', 'save', 'vote_up', 'vote_down', 'comment', 'subscribe', 'unsubscribe')),

    -- Target of engagement (optional)
    deal_id UUID REFERENCES public.deal_candidates(id) ON DELETE SET NULL,
    product_id UUID REFERENCES public.products(id) ON DELETE SET NULL,

    -- Engagement metadata
    metadata JSONB,

    -- Platform/source
    platform TEXT,
    user_agent TEXT,
    ip_address TEXT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Indexes
    INDEX idx_user_engagement_user_action (user_id, action, created_at DESC),
    INDEX idx_user_engagement_deal (deal_id, created_at DESC),
    INDEX idx_user_engagement_created (created_at DESC)
);

-- Referral program tracking
CREATE TABLE IF NOT EXISTS public.referrals (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    -- Referral relationship
    referrer_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    referred_user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Referral status
    status TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'rejected', 'expired')) DEFAULT 'pending',

    -- Reward information
    reward_amount DECIMAL(10,2) DEFAULT 0.00,
    reward_currency TEXT DEFAULT 'USD',
    reward_paid BOOLEAN DEFAULT false,
    reward_paid_at TIMESTAMP WITH TIME ZONE,

    -- Referral source tracking
    referral_source TEXT,
    referral_code TEXT,
    campaign_id TEXT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    expires_at TIMESTAMP WITH TIME ZONE,

    -- Constraints and indexes
    UNIQUE(referred_user_id),
    INDEX idx_referrals_referrer_status (referrer_id, status, created_at DESC),
    INDEX idx_referrals_created (created_at DESC),
    INDEX idx_referrals_code (referral_code) WHERE referral_code IS NOT NULL
);

-- Leaderboard entries
CREATE TABLE IF NOT EXISTS public.leaderboard_entries (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Ranking information
    rank INTEGER NOT NULL,
    score INTEGER NOT NULL,

    -- Metric being ranked
    metric_type TEXT NOT NULL CHECK (metric_type IN ('referrals', 'engagement', 'deals_found', 'revenue_generated')),
    metric_value DECIMAL(10,2) NOT NULL,

    -- Time period for ranking
    period_start TIMESTAMP WITH TIME ZONE NOT NULL,
    period_end TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Additional ranking data
    percentile DECIMAL(5,2),
    change_from_previous INTEGER,

    -- Timestamps
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints and indexes
    UNIQUE(user_id, metric_type, period_start, period_end),
    INDEX idx_leaderboard_metric_period (metric_type, period_end DESC, rank),
    INDEX idx_leaderboard_user (user_id, period_end DESC)
);

-- User preferences for personalization
CREATE TABLE IF NOT EXISTS public.user_preferences (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE UNIQUE,

    -- Notification preferences
    email_notifications BOOLEAN DEFAULT true,
    push_notifications BOOLEAN DEFAULT true,
    digest_frequency TEXT CHECK (digest_frequency IN ('daily', 'weekly', 'biweekly', 'monthly', 'never')) DEFAULT 'daily',

    -- Content preferences
    preferred_categories TEXT[],
    preferred_retailers TEXT[],
    min_discount_threshold INTEGER,
    max_price_threshold DECIMAL(10,2),

    -- Deal type preferences
    prefer_coupon_deals BOOLEAN DEFAULT true,
    prefer_glitch_deals BOOLEAN DEFAULT true,
    prefer_time_sensitive BOOLEAN DEFAULT false,

    -- Privacy preferences
    share_activity BOOLEAN DEFAULT false,
    show_on_leaderboard BOOLEAN DEFAULT true,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    INDEX idx_user_preferences_user (user_id)
);

-- Daily digest logs
CREATE TABLE IF NOT EXISTS public.daily_digest_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    -- Digest information
    digest_date TIMESTAMP WITH TIME ZONE NOT NULL,
    total_deals INTEGER NOT NULL,
    average_score DECIMAL(5,2) NOT NULL,
    top_deal_count INTEGER NOT NULL,

    -- Performance metrics
    open_rate DECIMAL(5,2),
    click_rate DECIMAL(5,2),
    conversion_rate DECIMAL(5,2),

    -- Delivery information
    sent_to_count INTEGER,
    failed_deliveries INTEGER,

    -- Content summary
    top_categories TEXT[],
    top_retailers TEXT[],
    content_summary JSONB,

    -- Timestamps
    generated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    sent_at TIMESTAMP WITH TIME ZONE,

    -- Constraints and indexes
    UNIQUE(digest_date),
    INDEX idx_digest_logs_date (digest_date DESC)
);

-- Viral deal alerts
CREATE TABLE IF NOT EXISTS public.viral_deal_alerts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,

    -- Deal information
    deal_candidate_id UUID NOT NULL REFERENCES public.deal_candidates(id) ON DELETE CASCADE,
    posted_deal_id UUID REFERENCES public.posted_deals(id) ON DELETE SET NULL,

    -- Viral metrics
    engagement_rate DECIMAL(10,2) NOT NULL,
    click_count INTEGER NOT NULL,
    conversion_count INTEGER NOT NULL,
    revenue_generated DECIMAL(10,2),

    -- Growth metrics
    growth_rate DECIMAL(10,2),
    peak_engagement DECIMAL(10,2),

    -- Alert status
    alert_level TEXT CHECK (alert_level IN ('low', 'medium', 'high', 'critical')) DEFAULT 'medium',
    notified BOOLEAN DEFAULT false,
    action_taken TEXT,

    -- Timestamps
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    peak_at TIMESTAMP WITH TIME ZONE,
    notified_at TIMESTAMP WITH TIME ZONE,

    -- Indexes
    INDEX idx_viral_alerts_detected (detected_at DESC),
    INDEX idx_viral_alerts_deal (deal_candidate_id, detected_at DESC),
    INDEX idx_viral_alerts_level (alert_level, detected_at DESC)
);

-- Community voting on deals
CREATE TABLE IF NOT EXISTS public.community_votes (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    deal_id UUID NOT NULL REFERENCES public.deal_candidates(id) ON DELETE CASCADE,

    -- Vote type
    vote_type TEXT NOT NULL CHECK (vote_type IN ('up', 'down', 'helpful', 'not_helpful', 'hot', 'cold')),

    -- Vote weight
    weight INTEGER DEFAULT 1,

    -- Optional comment
    comment TEXT,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints and indexes
    UNIQUE(user_id, deal_id, vote_type),
    INDEX idx_community_votes_deal (deal_id, vote_type, created_at DESC),
    INDEX idx_community_votes_user (user_id, created_at DESC)
);

-- User achievements and badges
CREATE TABLE IF NOT EXISTS public.user_achievements (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,

    -- Achievement details
    achievement_type TEXT NOT NULL,
    achievement_level INTEGER DEFAULT 1,
    achievement_name TEXT NOT NULL,
    achievement_description TEXT,

    -- Progress tracking
    progress_current INTEGER DEFAULT 0,
    progress_target INTEGER NOT NULL,
    progress_percentage DECIMAL(5,2) DEFAULT 0.00,

    -- Reward information
    reward_type TEXT,
    reward_value DECIMAL(10,2),
    reward_claimed BOOLEAN DEFAULT false,

    -- Timestamps
    unlocked_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints and indexes
    UNIQUE(user_id, achievement_type, achievement_level),
    INDEX idx_user_achievements_user (user_id, unlocked_at DESC),
    INDEX idx_user_achievements_type (achievement_type, unlocked_at DESC)
);

-- Enable Row Level Security (RLS) on all tables
ALTER TABLE public.user_engagement ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.referrals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.leaderboard_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_digest_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.viral_deal_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.community_votes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_achievements ENABLE ROW LEVEL SECURITY;

-- RLS Policies

-- User engagement: Users can view their own engagement
CREATE POLICY "Users can view own engagement" ON public.user_engagement
    FOR SELECT USING (auth.uid() = user_id);

-- Referrals: Users can view their own referrals
CREATE POLICY "Users can view own referrals" ON public.referrals
    FOR SELECT USING (auth.uid() IN (referrer_id, referred_user_id));

-- Referrals: Users can create referrals (as referrer)
CREATE POLICY "Users can create referrals" ON public.referrals
    FOR INSERT WITH CHECK (auth.uid() = referrer_id);

-- Leaderboard entries: Anyone can view leaderboards
CREATE POLICY "Anyone can view leaderboards" ON public.leaderboard_entries
    FOR SELECT USING (true);

-- User preferences: Users can manage their own preferences
CREATE POLICY "Users can manage own preferences" ON public.user_preferences
    FOR ALL USING (auth.uid() = user_id);

-- Daily digest logs: Anyone can view (read-only)
CREATE POLICY "Anyone can view digest logs" ON public.daily_digest_logs
    FOR SELECT USING (true);

-- Viral deal alerts: Admin only for now
CREATE POLICY "Admin only for viral alerts" ON public.viral_deal_alerts
    FOR ALL USING (EXISTS (
        SELECT 1 FROM public.profiles
        WHERE id = auth.uid() AND role = 'admin'
    ));

-- Community votes: Users can manage their own votes
CREATE POLICY "Users can manage own votes" ON public.community_votes
    FOR ALL USING (auth.uid() = user_id);

-- Community votes: Anyone can view votes
CREATE POLICY "Anyone can view votes" ON public.community_votes
    FOR SELECT USING (true);

-- User achievements: Users can view their own achievements
CREATE POLICY "Users can view own achievements" ON public.user_achievements
    FOR SELECT USING (auth.uid() = user_id);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at columns
CREATE TRIGGER update_user_preferences_updated_at BEFORE UPDATE
    ON public.user_preferences FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER update_community_votes_updated_at BEFORE UPDATE
    ON public.community_votes FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- Create function to calculate referral completion
CREATE OR REPLACE FUNCTION public.complete_referral_on_user_activity()
RETURNS TRIGGER AS $$
BEGIN
    -- When a referred user completes a significant action (e.g., makes first purchase),
    -- mark their referral as completed
    -- This is a placeholder - implement based on your business logic
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create function to update leaderboard scores
CREATE OR REPLACE FUNCTION public.update_leaderboard_scores()
RETURNS void AS $$
BEGIN
    -- This function would be called by a scheduled job to update leaderboards
    -- Implement your scoring logic here
    RETURN;
END;
$$ language 'plpgsql';

-- Create function to check for viral deals
CREATE OR REPLACE FUNCTION public.check_viral_deals()
RETURNS void AS $$
BEGIN
    -- This function would be called periodically to detect viral deals
    -- Implement your viral detection logic here
    RETURN;
END;
$$ language 'plpgsql';

-- Insert default achievement definitions (optional)
INSERT INTO public.user_achievements (
    achievement_type, achievement_level, achievement_name, achievement_description, progress_target
) VALUES
    ('referral_master', 1, 'First Referral', 'Successfully refer your first friend', 1),
    ('referral_master', 2, 'Referral Champion', 'Refer 5 friends', 5),
    ('referral_master', 3, 'Referral Expert', 'Refer 25 friends', 25),
    ('deal_hunter', 1, 'First Deal Click', 'Click on your first deal', 1),
    ('deal_hunter', 2, 'Deal Explorer', 'Click on 10 deals', 10),
    ('deal_hunter', 3, 'Deal Master', 'Click on 100 deals', 100),
    ('community_contributor', 1, 'First Vote', 'Cast your first vote on a deal', 1),
    ('community_contributor', 2, 'Active Voter', 'Cast 50 votes', 50),
    ('community_contributor', 3, 'Community Leader', 'Cast 500 votes', 500)
ON CONFLICT DO NOTHING;

-- Add growth-related tasks to Celery beat schedule (commented out - to be added to config.yaml)
/*
-- Example of how to add growth tasks to your Celery beat schedule:
-- In config.yaml, add to celery.beat_schedule:

growth_daily_digest:
  task: "deal_sniper_ai.growth_engine.tasks.generate_daily_digest"
  schedule: 86400.0  # Daily
growth_update_leaderboard:
  task: "deal_sniper_ai.growth_engine.tasks.update_leaderboard"
  schedule: 86400.0  # Daily
growth_check_viral_deals:
  task: "deal_sniper_ai.growth_engine.tasks.check_viral_deals"
  schedule: 3600.0   # Hourly
*/

COMMENT ON TABLE public.user_engagement IS 'Tracks user engagement activities (clicks, shares, saves, etc.)';
COMMENT ON TABLE public.referrals IS 'Tracks user referrals and rewards for the referral program';
COMMENT ON TABLE public.leaderboard_entries IS 'Leaderboard entries for user ranking based on various metrics';
COMMENT ON TABLE public.user_preferences IS 'User preferences for personalization and notification settings';
COMMENT ON TABLE public.daily_digest_logs IS 'Log of generated daily digests with performance metrics';
COMMENT ON TABLE public.viral_deal_alerts IS 'Alerts for deals detected as going viral based on engagement metrics';
COMMENT ON TABLE public.community_votes IS 'Community voting on deals for quality control and ranking';
COMMENT ON TABLE public.user_achievements IS 'User achievements and badges for gamification';

-- Grant appropriate permissions
GRANT SELECT ON public.user_engagement TO authenticated;
GRANT INSERT ON public.user_engagement TO authenticated;
GRANT SELECT ON public.referrals TO authenticated;
GRANT INSERT ON public.referrals TO authenticated;
GRANT SELECT ON public.leaderboard_entries TO authenticated;
GRANT SELECT ON public.user_preferences TO authenticated;
GRANT ALL ON public.user_preferences TO authenticated;
GRANT SELECT ON public.daily_digest_logs TO authenticated;
GRANT SELECT ON public.community_votes TO authenticated;
GRANT ALL ON public.community_votes TO authenticated;
GRANT SELECT ON public.user_achievements TO authenticated;

-- Admin permissions
GRANT ALL ON public.user_engagement TO service_role;
GRANT ALL ON public.referrals TO service_role;
GRANT ALL ON public.leaderboard_entries TO service_role;
GRANT ALL ON public.user_preferences TO service_role;
GRANT ALL ON public.daily_digest_logs TO service_role;
GRANT ALL ON public.viral_deal_alerts TO service_role;
GRANT ALL ON public.community_votes TO service_role;
GRANT ALL ON public.user_achievements TO service_role;-- Anti-blocking system schema for Deal Sniper AI Platform
-- Adds user agents, proxies, and captcha tracking tables

-- User agents table: user agent strings for rotation to avoid blocking
CREATE TABLE IF NOT EXISTS public.user_agents (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_agent_string TEXT NOT NULL,
    browser_family TEXT,  -- Chrome, Firefox, Safari, Edge
    browser_version TEXT,
    os_family TEXT,  -- Windows, macOS, Linux, Android, iOS
    os_version TEXT,
    device_type TEXT,  -- desktop, mobile, tablet, bot

    -- Success tracking
    total_uses INTEGER DEFAULT 0,
    successful_uses INTEGER DEFAULT 0,
    blocked_uses INTEGER DEFAULT 0,
    success_rate DECIMAL(5,2) DEFAULT 0,

    -- Source tracking
    source TEXT DEFAULT 'manual',  -- manual, web_scrape, api
    source_url TEXT,

    -- Validity
    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMP WITH TIME ZONE,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints and indexes
    UNIQUE(user_agent_string),
    INDEX idx_user_agents_success_rate (is_active, success_rate DESC),
    INDEX idx_user_agents_browser_family (browser_family, is_active)
);

-- Proxies table: proxy servers for IP rotation to avoid blocking
CREATE TABLE IF NOT EXISTS public.proxies (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    ip_address TEXT NOT NULL,
    port INTEGER NOT NULL,
    protocol TEXT CHECK (protocol IN ('http', 'https', 'socks4', 'socks5')),
    country TEXT,
    city TEXT,
    anonymity_level TEXT CHECK (anonymity_level IN ('transparent', 'anonymous', 'elite')),
    isp TEXT,

    -- Performance tracking
    total_uses INTEGER DEFAULT 0,
    successful_uses INTEGER DEFAULT 0,
    failed_uses INTEGER DEFAULT 0,
    avg_response_time_ms INTEGER,
    success_rate DECIMAL(5,2) DEFAULT 0,

    -- Health status
    last_checked_at TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT true,
    is_working BOOLEAN DEFAULT true,
    last_error TEXT,

    -- Source tracking
    source TEXT DEFAULT 'free_proxy_list',  -- free_proxy_list, paid_service, manual
    source_url TEXT,

    -- Timestamps
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints and indexes
    UNIQUE(ip_address, port, protocol),
    INDEX idx_proxies_success_rate (is_active, is_working, success_rate DESC),
    INDEX idx_proxies_country (country, is_active, is_working),
    INDEX idx_proxies_last_checked (last_checked_at DESC)
);

-- Captcha encounters table: CAPTCHA encounters tracking for analysis and solving
CREATE TABLE IF NOT EXISTS public.captcha_encounters (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    retailer_id TEXT NOT NULL,
    url TEXT NOT NULL,
    captcha_type TEXT CHECK (captcha_type IN ('recaptcha', 'hcaptcha', 'cloudflare', 'simple', 'unknown')),
    user_agent_id UUID REFERENCES public.user_agents(id) ON DELETE SET NULL,
    proxy_id UUID REFERENCES public.proxies(id) ON DELETE SET NULL,

    -- Resolution
    was_solved BOOLEAN DEFAULT false,
    solving_service TEXT,  -- 2captcha, anti-captcha, manual
    solving_time_ms INTEGER,
    solving_cost DECIMAL(10,4),

    -- Context
    request_count_before INTEGER,
    session_duration_before_ms INTEGER,

    -- Timestamps
    encountered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    solved_at TIMESTAMP WITH TIME ZONE,

    -- Indexes
    INDEX idx_captcha_encounters_retailer_time (retailer_id, encountered_at DESC),
    INDEX idx_captcha_encounters_type (captcha_type, encountered_at DESC)
);

-- Enable Row Level Security (RLS) on new tables
ALTER TABLE public.user_agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.proxies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.captcha_encounters ENABLE ROW LEVEL SECURITY;

-- Insert initial user agents (100+ realistic user agents)
INSERT INTO public.user_agents (user_agent_string, browser_family, browser_version, os_family, os_version, device_type, source) VALUES
-- Chrome on Windows
('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Chrome', '120.0.0.0', 'Windows', '10', 'desktop', 'manual'),
('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36', 'Chrome', '119.0.0.0', 'Windows', '10', 'desktop', 'manual'),
('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36', 'Chrome', '118.0.0.0', 'Windows', '10', 'desktop', 'manual'),
('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36', 'Chrome', '121.0.0.0', 'Windows', '10', 'desktop', 'manual'),
('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36', 'Chrome', '122.0.0.0', 'Windows', '10', 'desktop', 'manual'),

-- Chrome on macOS
('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Chrome', '120.0.0.0', 'macOS', '10.15.7', 'desktop', 'manual'),
('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36', 'Chrome', '119.0.0.0', 'macOS', '10.15.7', 'desktop', 'manual'),
('Mozilla/5.0 (Macintosh; Intel Mac OS X 11_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Chrome', '120.0.0.0', 'macOS', '11.0', 'desktop', 'manual'),
('Mozilla/5.0 (Macintosh; Intel Mac OS X 12_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Chrome', '120.0.0.0', 'macOS', '12.0', 'desktop', 'manual'),
('Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Chrome', '120.0.0.0', 'macOS', '13.0', 'desktop', 'manual'),

-- Firefox on Windows
('Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0', 'Firefox', '121.0', 'Windows', '10', 'desktop', 'manual'),
('Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0', 'Firefox', '120.0', 'Windows', '10', 'desktop', 'manual'),
('Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:119.0) Gecko/20100101 Firefox/119.0', 'Firefox', '119.0', 'Windows', '10', 'desktop', 'manual'),
('Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:118.0) Gecko/20100101 Firefox/118.0', 'Firefox', '118.0', 'Windows', '10', 'desktop', 'manual'),
('Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0', 'Firefox', '122.0', 'Windows', '10', 'desktop', 'manual'),

-- Firefox on macOS
('Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0', 'Firefox', '121.0', 'macOS', '10.15', 'desktop', 'manual'),
('Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:120.0) Gecko/20100101 Firefox/120.0', 'Firefox', '120.0', 'macOS', '10.15', 'desktop', 'manual'),
('Mozilla/5.0 (Macintosh; Intel Mac OS X 11.0; rv:121.0) Gecko/20100101 Firefox/121.0', 'Firefox', '121.0', 'macOS', '11.0', 'desktop', 'manual'),
('Mozilla/5.0 (Macintosh; Intel Mac OS X 12.0; rv:121.0) Gecko/20100101 Firefox/121.0', 'Firefox', '121.0', 'macOS', '12.0', 'desktop', 'manual'),
('Mozilla/5.0 (Macintosh; Intel Mac OS X 13.0; rv:121.0) Gecko/20100101 Firefox/121.0', 'Firefox', '121.0', 'macOS', '13.0', 'desktop', 'manual'),

-- Safari on macOS
('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15', 'Safari', '17.2', 'macOS', '10.15.7', 'desktop', 'manual'),
('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15', 'Safari', '17.1', 'macOS', '10.15.7', 'desktop', 'manual'),
('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15', 'Safari', '17.0', 'macOS', '10.15.7', 'desktop', 'manual'),
('Mozilla/5.0 (Macintosh; Intel Mac OS X 11_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15', 'Safari', '17.2', 'macOS', '11.0', 'desktop', 'manual'),
('Mozilla/5.0 (Macintosh; Intel Mac OS X 12_0) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15', 'Safari', '17.2', 'macOS', '12.0', 'desktop', 'manual'),

-- Edge on Windows
('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0', 'Edge', '120.0.0.0', 'Windows', '10', 'desktop', 'manual'),
('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0', 'Edge', '119.0.0.0', 'Windows', '10', 'desktop', 'manual'),
('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36 Edg/118.0.0.0', 'Edge', '118.0.0.0', 'Windows', '10', 'desktop', 'manual'),
('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0', 'Edge', '121.0.0.0', 'Windows', '10', 'desktop', 'manual'),
('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0', 'Edge', '122.0.0.0', 'Windows', '10', 'desktop', 'manual'),

-- Mobile Chrome on Android
('Mozilla/5.0 (Linux; Android 10; SM-G973F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36', 'Chrome', '120.0.0.0', 'Android', '10', 'mobile', 'manual'),
('Mozilla/5.0 (Linux; Android 11; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36', 'Chrome', '120.0.0.0', 'Android', '11', 'mobile', 'manual'),
('Mozilla/5.0 (Linux; Android 12; SM-S901B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36', 'Chrome', '120.0.0.0', 'Android', '12', 'mobile', 'manual'),
('Mozilla/5.0 (Linux; Android 13; SM-S911B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36', 'Chrome', '120.0.0.0', 'Android', '13', 'mobile', 'manual'),
('Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36', 'Chrome', '120.0.0.0', 'Android', '14', 'mobile', 'manual'),

-- Mobile Safari on iOS
('Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1', 'Safari', '17.2', 'iOS', '17.2', 'mobile', 'manual'),
('Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1', 'Safari', '17.1', 'iOS', '17.1', 'mobile', 'manual'),
('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1', 'Safari', '17.0', 'iOS', '17.0', 'mobile', 'manual'),
('Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1', 'Safari', '16.6', 'iOS', '16.6', 'mobile', 'manual'),
('Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1', 'Safari', '16.5', 'iOS', '16.5', 'mobile', 'manual'),

-- Additional Chrome variants
('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Whale/3.24.223.21 Safari/537.36', 'Chrome', '120.0.0.0', 'Windows', '10', 'desktop', 'manual'),
('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 OPR/106.0.0.0', 'Chrome', '120.0.0.0', 'Windows', '10', 'desktop', 'manual'),
('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Vivaldi/6.5.3206.53', 'Chrome', '120.0.0.0', 'Windows', '10', 'desktop', 'manual'),

-- Additional Firefox variants
('Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0 Waterfox/2024.01', 'Firefox', '121.0', 'Windows', '10', 'desktop', 'manual'),
('Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0 PaleMoon/33.0.0', 'Firefox', '121.0', 'Windows', '10', 'desktop', 'manual'),

-- Linux browsers
('Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Chrome', '120.0.0.0', 'Linux', 'x86_64', 'desktop', 'manual'),
('Mozilla/5.0 (X11; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0', 'Firefox', '121.0', 'Linux', 'x86_64', 'desktop', 'manual'),
('Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:121.0) Gecko/20100101 Firefox/121.0', 'Firefox', '121.0', 'Linux', 'Ubuntu', 'desktop', 'manual'),

-- Tablet devices
('Mozilla/5.0 (iPad; CPU OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1', 'Safari', '17.2', 'iOS', '17.2', 'tablet', 'manual'),
('Mozilla/5.0 (Linux; Android 13; SM-X916B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Chrome', '120.0.0.0', 'Android', '13', 'tablet', 'manual'),
('Mozilla/5.0 (Linux; Android 12; SM-T970) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Chrome', '120.0.0.0', 'Android', '12', 'tablet', 'manual'),

-- Additional 50+ user agents would be added in a real implementation
-- This is a sample set to get started

ON CONFLICT (user_agent_string) DO NOTHING;