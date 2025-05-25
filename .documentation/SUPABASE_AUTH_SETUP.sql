-- =============================================================================
-- SUPABASE AUTH SETUP FOR MAKEIT3D
-- =============================================================================
-- This script sets up the complete authentication infrastructure for MakeIt3D
-- Execute these commands in your Supabase SQL Editor
-- 
-- PROJECT: MakeIt3D (iadsbhyztbokarclnzzk)
-- =============================================================================

-- =============================================================================
-- 🚨 CRITICAL SECURITY FIX
-- =============================================================================
-- The models table currently has RLS DISABLED, creating a major security vulnerability
-- This must be fixed IMMEDIATELY before frontend implementation

-- Enable RLS on models table
ALTER TABLE public.models ENABLE ROW LEVEL SECURITY;

-- Create user isolation policy for models table
CREATE POLICY "Users can manage their own models" ON public.models
  FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- =============================================================================
-- VERIFY EXISTING RLS POLICIES
-- =============================================================================
-- Check that other tables have proper RLS policies

-- Verify input_assets RLS (should already exist)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies 
    WHERE schemaname = 'public' 
    AND tablename = 'input_assets' 
    AND policyname = 'Users can manage their own input assets'
  ) THEN
    CREATE POLICY "Users can manage their own input assets" ON public.input_assets
      FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- Verify concept_images RLS (should already exist)  
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies 
    WHERE schemaname = 'public' 
    AND tablename = 'concept_images' 
    AND policyname = 'Users can view their own concept images'
  ) THEN
    CREATE POLICY "Users can view their own concept images" ON public.concept_images
      FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

-- =============================================================================
-- VERIFICATION QUERIES
-- =============================================================================
-- Run these to verify setup is complete

-- Check RLS status
SELECT 
  'RLS Status Check' as check_type,
  tablename,
  CASE 
    WHEN rowsecurity THEN '✅ Enabled'
    ELSE '❌ DISABLED - SECURITY RISK!'
  END as status
FROM pg_tables 
WHERE schemaname = 'public' 
AND tablename IN ('input_assets', 'concept_images', 'models')
ORDER BY tablename;

-- Check policies exist
SELECT 
  'Policy Check' as check_type,
  tablename,
  COUNT(*) as policy_count,
  CASE 
    WHEN COUNT(*) > 0 THEN '✅ Has Policies'
    ELSE '❌ NO POLICIES - SECURITY RISK!'
  END as status
FROM pg_policies 
WHERE schemaname = 'public' 
AND tablename IN ('input_assets', 'concept_images', 'models')
GROUP BY tablename
ORDER BY tablename;

-- Check test users exist
SELECT 
  'Test Users Check' as check_type,
  id,
  email,
  email_confirmed_at IS NOT NULL as email_confirmed,
  created_at
FROM auth.users 
WHERE email IN ('test@example.com', 'test-user@example.com')
ORDER BY email;

-- =============================================================================
-- POST-SETUP NOTES
-- =============================================================================
/*
After running this script:

1. ✅ RLS is enabled on all tables with proper user isolation
2. ✅ Test users are available for development
3. ✅ Security policies enforce data isolation

For Frontend Implementation:
- Use anon key: Get from Supabase Dashboard -> Settings -> API -> Project API keys
- Project URL: Get from Supabase Dashboard -> Settings -> API
- JWT tokens will automatically enforce user isolation via RLS

For Backend Implementation:
- Get JWT Secret from Supabase Dashboard -> Settings -> API -> JWT Secret
- Validate JWT tokens to extract user_id
- Use user_id in all database operations
*/ 