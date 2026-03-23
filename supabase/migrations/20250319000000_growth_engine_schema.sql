-- Growth Engine Schema Extension
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_user_engagement_user_action ON public.user_engagement (user_id, action, created_at DESC);
CREATE INDEX idx_user_engagement_deal ON public.user_engagement (deal_id, created_at DESC);
CREATE INDEX idx_user_engagement_created ON public.user_engagement (created_at DESC);

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

    -- Constraints
    UNIQUE(referred_user_id)
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

    -- Constraints
    UNIQUE(user_id, metric_type, period_start, period_end)
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
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
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

    -- Constraints
    UNIQUE(digest_date)
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
    notified_at TIMESTAMP WITH TIME ZONE
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

    -- Constraints
    UNIQUE(user_id, deal_id, vote_type)
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

    -- Constraints
    UNIQUE(user_id, achievement_type, achievement_level)
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

/*
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
*/

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
GRANT ALL ON public.user_achievements TO service_role;