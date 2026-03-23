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
    captured_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_price_history_product_time ON price_history (product_id, captured_at DESC);

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
    reviewed_by UUID REFERENCES auth.users(id)
);

CREATE INDEX idx_deal_candidates_status_score ON public.deal_candidates (status, final_score DESC);
CREATE INDEX idx_deal_candidates_detected ON public.deal_candidates (detected_at DESC);

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
    last_updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_posted_deals_performance ON public.posted_deals (posted_at DESC, estimated_revenue DESC);

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
    UNIQUE(original_url, affiliate_program)
);

CREATE INDEX idx_affiliate_links_product ON public.affiliate_links (product_id);

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
    UNIQUE(retailer_id, code)
);

CREATE INDEX idx_coupon_codes_success_rate ON public.coupon_codes (retailer_id, success_rate DESC);

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
    UNIQUE(retailer_id, session_id)
);

CREATE INDEX idx_scraping_sessions_retailer_time ON public.scraping_sessions (retailer_id, started_at DESC);

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
    calculated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_performance_metrics_type_time ON public.performance_metrics (metric_type, period_end DESC);

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
    ON public.coupon_codes FOR EACH ROW EXECUTE FUNCTION public.update_coupon_success_rate();