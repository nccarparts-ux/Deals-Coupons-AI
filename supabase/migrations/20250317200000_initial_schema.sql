-- Initial schema for Deals-Coupons-AI
-- Creates basic tables for user profiles and deals

-- Enable UUID extension (must be in separate transaction)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create profiles table (extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS public.profiles (
  id UUID REFERENCES auth.users ON DELETE CASCADE PRIMARY KEY,
  email TEXT UNIQUE,
  full_name TEXT,
  avatar_url TEXT,
  role TEXT DEFAULT 'user' CHECK (role IN ('user', 'seller', 'admin')),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable Row Level Security (RLS)
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Create policies for profiles
-- Users can read their own profile
CREATE POLICY "Users can view own profile" ON public.profiles
  FOR SELECT USING (auth.uid() = id);

-- Users can update their own profile
CREATE POLICY "Users can update own profile" ON public.profiles
  FOR UPDATE USING (auth.uid() = id);

-- Create deals table (example structure)
CREATE TABLE IF NOT EXISTS public.deals (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT,
  original_price DECIMAL(10,2),
  discount_price DECIMAL(10,2),
  discount_percent INTEGER,
  category TEXT,
  tags TEXT[],
  image_url TEXT,
  seller_id UUID REFERENCES public.profiles(id),
  is_active BOOLEAN DEFAULT true,
  expires_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS for deals
ALTER TABLE public.deals ENABLE ROW LEVEL SECURITY;

-- Basic policies for deals
-- Anyone can view active deals
CREATE POLICY "Anyone can view active deals" ON public.deals
  FOR SELECT USING (is_active = true);

-- Sellers can manage their own deals
CREATE POLICY "Sellers can manage own deals" ON public.deals
  FOR ALL USING (auth.uid() = seller_id);

-- Create coupons table
CREATE TABLE IF NOT EXISTS public.coupons (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  code TEXT UNIQUE NOT NULL,
  deal_id UUID REFERENCES public.deals(id) ON DELETE CASCADE,
  discount_type TEXT CHECK (discount_type IN ('percentage', 'fixed', 'free_shipping')),
  discount_value DECIMAL(10,2),
  max_uses INTEGER,
  uses INTEGER DEFAULT 0,
  expires_at TIMESTAMP WITH TIME ZONE,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enable RLS for coupons
ALTER TABLE public.coupons ENABLE ROW LEVEL SECURITY;

-- Anyone can view active coupons
CREATE POLICY "Anyone can view active coupons" ON public.coupons
  FOR SELECT USING (is_active = true);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger for profiles updated_at
CREATE TRIGGER update_profiles_updated_at BEFORE UPDATE
  ON public.profiles FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- Create trigger for deals updated_at
CREATE TRIGGER update_deals_updated_at BEFORE UPDATE
  ON public.deals FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- Insert sample admin user (optional - update with actual user ID after signup)
-- INSERT INTO public.profiles (id, email, role)
-- VALUES ('00000000-0000-0000-0000-000000000000', 'admin@example.com', 'admin')
-- ON CONFLICT (id) DO NOTHING;