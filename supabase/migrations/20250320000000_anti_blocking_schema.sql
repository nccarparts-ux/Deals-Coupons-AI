-- Anti-blocking system schema for Deal Sniper AI Platform
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
    UNIQUE(user_agent_string)
);

CREATE INDEX idx_user_agents_success_rate ON public.user_agents (is_active, success_rate DESC);
CREATE INDEX idx_user_agents_browser_family ON public.user_agents (browser_family, is_active);

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
    UNIQUE(ip_address, port, protocol)
);

CREATE INDEX idx_proxies_success_rate ON public.proxies (is_active, is_working, success_rate DESC);
CREATE INDEX idx_proxies_country ON public.proxies (country, is_active, is_working);
CREATE INDEX idx_proxies_last_checked ON public.proxies (last_checked_at DESC);

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
    solved_at TIMESTAMP WITH TIME ZONE

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
('Mozilla/5.0 (Linux; Android 12; SM-T970) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36', 'Chrome', '120.0.0.0', 'Android', '12', 'tablet', 'manual')

-- Additional 50+ user agents would be added in a real implementation
-- This is a sample set to get started

ON CONFLICT (user_agent_string) DO NOTHING;