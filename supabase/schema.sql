-- Supabase Postgres Database Schema Setup

-- 1. Create profiles table
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT,
    currency TEXT DEFAULT 'GBP',
    savings_goal NUMERIC DEFAULT 500.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 2. Create transactions table
CREATE TABLE IF NOT EXISTS transactions (
    id TEXT PRIMARY KEY, -- Original transaction ID or md5 hash of fields
    profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    description TEXT NOT NULL,
    merchant TEXT NOT NULL,
    amount NUMERIC NOT NULL, -- Positive = debit, Negative = credit
    currency TEXT NOT NULL,
    category TEXT NOT NULL,
    confidence TEXT CHECK (confidence IN ('high', 'medium', 'low')) NOT NULL,
    is_recurring BOOLEAN DEFAULT FALSE,
    flags TEXT[] DEFAULT '{}'::TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL
);

-- 3. Create briefings table
CREATE TABLE IF NOT EXISTS briefings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID REFERENCES profiles(id) ON DELETE CASCADE,
    month TEXT NOT NULL, -- Format YYYY-MM
    briefing_text TEXT NOT NULL, -- Markdown briefing content
    analysis JSONB NOT NULL, -- JSON breakdown including categories, savings rate, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now()) NOT NULL,
    UNIQUE(profile_id, month)
);

-- 4. Create development indexes
CREATE INDEX IF NOT EXISTS idx_transactions_profile_date ON transactions(profile_id, date);
CREATE INDEX IF NOT EXISTS idx_briefings_profile_month ON briefings(profile_id, month);

-- 5. Insert a default profile for local development / testing
-- Note: UUID '00000000-0000-0000-0000-000000000000' represents local mock profile
INSERT INTO profiles (id, email, currency, savings_goal)
VALUES ('00000000-0000-0000-0000-000000000000', 'default@example.com', 'GBP', 500.00)
ON CONFLICT (id) DO NOTHING;

-- 6. Enable Row Level Security (RLS)
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE briefings ENABLE ROW LEVEL SECURITY;

-- 7. Define Security Policies (Sandboxing users to their own Auth ID)

-- Profiles Policies
CREATE POLICY "Users can view their own profile" 
    ON profiles FOR SELECT 
    USING (auth.uid() = id);

CREATE POLICY "Users can update their own profile" 
    ON profiles FOR UPDATE 
    USING (auth.uid() = id);

CREATE POLICY "Users can insert their own profile" 
    ON profiles FOR INSERT 
    WITH CHECK (auth.uid() = id);

-- Transactions Policies
CREATE POLICY "Users can view their own transactions" 
    ON transactions FOR SELECT 
    USING (auth.uid() = profile_id);

CREATE POLICY "Users can insert their own transactions" 
    ON transactions FOR INSERT 
    WITH CHECK (auth.uid() = profile_id);

CREATE POLICY "Users can update their own transactions" 
    ON transactions FOR UPDATE 
    USING (auth.uid() = profile_id);

CREATE POLICY "Users can delete their own transactions" 
    ON transactions FOR DELETE 
    USING (auth.uid() = profile_id);

-- Briefings Policies
CREATE POLICY "Users can view their own briefings" 
    ON briefings FOR SELECT 
    USING (auth.uid() = profile_id);

CREATE POLICY "Users can manage their own briefings" 
    ON briefings FOR ALL 
    USING (auth.uid() = profile_id);

-- 8. Enable Bypass Policy for Local Developer Profile (Default UI bypass for testing)
-- This allows local development checks to pass without needing active Auth JWT sessions.
CREATE POLICY "Allow local default user profiles operations"
    ON profiles FOR ALL
    USING (id = '00000000-0000-0000-0000-000000000000');

CREATE POLICY "Allow local default transactions operations"
    ON transactions FOR ALL
    USING (profile_id = '00000000-0000-0000-0000-000000000000');

CREATE POLICY "Allow local default briefings operations"
    ON briefings FOR ALL
    USING (profile_id = '00000000-0000-0000-0000-000000000000');
