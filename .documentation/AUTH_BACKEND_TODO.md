# Authentication Backend Implementation TODO

## Overview

Based on review of the MakeIt3D BFF documentation and codebase, **authentication using Supabase is currently not implemented** and is critical for MVP completion. The current system uses a hardcoded `TEST_USER_ID` throughout the application and lacks proper user authentication, authorization, and session management.

## Current State Analysis

### ❌ What's Missing for Auth
1. **No JWT validation** - BFF endpoints don't validate Supabase JWT tokens
2. **No user context extraction** - `TEST_USER_ID` hardcoded throughout `app/routers/generation.py`
3. **No auth middleware** - No FastAPI dependencies for protecting routes
4. **No auth configuration** - Missing JWT secret keys and validation settings
5. **No auth endpoints** - No login/logout/refresh token endpoints in BFF
6. **No auth testing** - Test suite doesn't cover authenticated scenarios
7. **No auth error handling** - No 401/403 responses for invalid tokens
8. **Incomplete RLS enforcement** - `models` table has RLS disabled, service role policies too broad

### ✅ What's Already in Place
- **Supabase client configuration** in `app/config.py` 
- **Database tables** (`input_assets`, `concept_images`, `models`) have `user_id` fields with foreign keys to `auth.users`
- **Supabase handler methods** accept optional `user_id` parameter
- **Frontend architecture docs** mention Supabase Auth integration
- **Test users exist** in auth.users table (including hardcoded TEST_USER_ID)
- **RLS policies partially configured**:
  - ✅ `input_assets`: RLS enabled with user isolation
  - ✅ `concept_images`: RLS enabled with user isolation  
  - ❌ `models`: RLS disabled (critical security gap)
- **Service role policies exist** but are overly permissive

## 🚨 IMMEDIATE SECURITY FIX REQUIRED

**Critical Security Vulnerability Detected**: The `models` table has Row Level Security (RLS) **DISABLED**, meaning any authenticated user can access all 3D models from all users. This must be fixed immediately:

```sql
-- Execute this ASAP in your Supabase SQL editor:
ALTER TABLE public.models ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage their own models" ON public.models
  FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
```

## Implementation Tasks

### 1. Core Authentication Setup

#### 1.1 Configuration Updates (`app/config.py`)
- [ ] Add JWT configuration settings:
  ```python
  # JWT & Auth Configuration  
  supabase_jwt_secret: str  # Get from Supabase Dashboard -> Settings -> API -> JWT Secret
  supabase_anon_key: str = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlhZHNiaHl6dGJva2FyY2xuenprIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDc1MjM4MDUsImV4cCI6MjA2MzA5OTgwNX0.HeTNAhHhCdOoadHJOUeyHEQxo9f5Ole6GxJqYCORS78"
  auth_required: bool = True # Toggle auth requirement (useful for testing)
  ```

#### 1.2 Create Auth Dependencies (`app/auth/`)
- [ ] Create `app/auth/` directory structure:
  ```
  app/auth/
  ├── __init__.py
  ├── dependencies.py  # FastAPI auth dependencies
  ├── jwt_handler.py   # JWT validation logic
  └── exceptions.py    # Auth-specific exceptions
  ```

- [ ] Implement JWT validation in `app/auth/jwt_handler.py`:
  - JWT token decoding and validation
  - User ID extraction from token
  - Token expiration checking
  - Error handling for invalid tokens

- [ ] Create auth dependencies in `app/auth/dependencies.py`:
  ```python
  async def get_current_user_id(authorization: str = Header(...)) -> str:
      # Extract Bearer token and validate JWT
      # Return user_id from token payload
      pass
  
  async def get_optional_user_id(authorization: str = Header(None)) -> str | None:
      # Optional auth for endpoints that work with/without auth
      pass
  ```

#### 1.3 Auth Middleware
- [ ] Create FastAPI middleware for auth logging/metrics
- [ ] Add CORS configuration for frontend auth flows

### 2. Update API Endpoints for Auth

#### 2.1 Router Updates (`app/routers/generation.py`)
- [ ] Remove hardcoded `TEST_USER_ID` constant
- [ ] Add auth dependency to all generation endpoints:
  ```python
  @router.post("/image-to-image", response_model=TaskIdResponse)
  async def generate_image_to_image_endpoint(
      request_data: ImageToImageRequest,
      user_id: str = Depends(get_current_user_id)  # Add this
  ):
  ```
- [ ] Replace all `user_id_from_auth = TEST_USER_ID` with injected `user_id`
- [ ] Update error responses to include proper 401/403 status codes

#### 2.2 Status Endpoint Updates (`app/routers/task_status.py`)
- [ ] Add auth to status polling endpoints
- [ ] Ensure users can only access their own task statuses
- [ ] Add user_id filtering in database queries

### 3. Database Security Integration

#### 3.1 Row Level Security (RLS) Critical Fixes
- [ ] **URGENT: Enable RLS on `models` table** (currently disabled, major security risk):
  ```sql
  ALTER TABLE public.models ENABLE ROW LEVEL SECURITY;
  ```
- [ ] **Create missing user policies for `models` table**:
  ```sql
  CREATE POLICY "Users can manage their own models" ON public.models
    FOR ALL USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
  ```
- [ ] **Review and tighten service role policies** (currently too broad):
  - Current policies allow service role full access to all records
  - Consider restricting to specific operations needed by BFF
- [ ] **Verify existing RLS policies** are working correctly:
  - ✅ `input_assets`: RLS enabled, user isolation working
  - ✅ `concept_images`: RLS enabled, user isolation working
  - ❌ `models`: RLS disabled - fix required
- [ ] Test RLS policies with both service key and user JWTs
- [ ] Document the security model in comments

#### 3.2 Supabase Handler Updates (`app/supabase_handler.py`)
- [ ] Update all database operations to properly use `user_id`
- [ ] Add user_id validation in create/update operations
- [ ] Ensure no database operations bypass user filtering
- [ ] Add logging for auth-related database operations

### 4. Auth Endpoints (Optional for MVP)

#### 4.1 Basic Auth Routes (`app/routers/auth.py`)
- [ ] Create auth router (if BFF needs to handle auth directly)
- [ ] Implement endpoints:
  - `POST /auth/refresh` - Refresh JWT tokens
  - `GET /auth/user` - Get current user profile
  - `POST /auth/logout` - Logout/invalidate tokens
- [ ] **Note**: Primary auth (login/signup) likely handled by frontend directly with Supabase

### 5. Testing Updates

#### 5.1 Test Infrastructure (`tests/`)
- [ ] Create auth test utilities in `tests/auth_helpers.py`:
  - Mock JWT token generation
  - Test user creation helpers
  - Auth header utilities
- [ ] Update test configuration:
  - Add test JWT secrets
  - Mock auth dependencies for testing
  - Test both authenticated and unauthenticated scenarios

#### 5.2 Test Coverage (`tests/test_endpoints.py`)
- [ ] Add auth test cases:
  - Valid JWT token access
  - Invalid/expired JWT token rejection (401)
  - Missing auth header rejection (401)
  - User isolation (can't access other user's data)
- [ ] Update existing tests to use proper auth headers
- [ ] Add auth-specific test scenarios
- [ ] Test RLS policy enforcement

#### 5.3 Test User Management
- [x] ✅ Test users already exist in Supabase:
  - `00000000-0000-4000-8000-000000000001` (test@example.com) - matches hardcoded TEST_USER_ID
  - `123e4567-e89b-12d3-a456-426614174000` (test-user@example.com) 
- [ ] Generate valid JWT tokens for test users using Supabase client
- [ ] Add test utilities for JWT token generation/validation
- [ ] Add cleanup for test auth data created during tests

### 6. Error Handling & Security

#### 6.1 Error Response Updates
- [ ] Standardize auth error responses:
  ```python
  {
    "error": "unauthorized",
    "message": "Invalid or expired token",
    "status_code": 401
  }
  ```
- [ ] Add rate limiting for auth endpoints
- [ ] Implement auth failure logging

#### 6.2 Security Hardening
- [ ] Add input validation for JWT tokens
- [ ] Implement token blacklisting (if needed)
- [ ] Add auth audit logging
- [ ] Configure secure headers for auth responses

### 7. Documentation Updates

#### 7.1 API Documentation (`makeit3d-api.md`)
- [ ] Add authentication section:
  - How to obtain JWT tokens
  - How to include Bearer tokens in requests
  - Auth error response formats
- [ ] Update all endpoint examples with auth headers
- [ ] Document auth requirements for each endpoint

#### 7.2 Architecture Documentation
- [ ] Update `bff_architecture.md` with auth flow details
- [ ] Document JWT validation process
- [ ] Add auth sequence diagrams
- [ ] Document RLS integration approach

### 8. Deployment & Configuration

#### 8.1 Environment Variables
- [ ] Add auth-related environment variables to deployment configs
- [ ] Document required Supabase JWT secrets
- [ ] Add auth configuration validation on startup

#### 8.2 Health Checks
- [ ] Add auth system health checks
- [ ] Verify JWT secret configuration on startup
- [ ] Test Supabase auth connectivity

## Priority for MVP

### 🔴 Critical (Blocking MVP)
1. **Enable RLS on `models` table** (major security vulnerability!)
2. JWT validation implementation (`app/auth/`)
3. Router auth dependency injection
4. Remove hardcoded `TEST_USER_ID`
5. Basic auth testing

### 🟡 Important (Pre-launch)
1. Fix overly permissive service role policies
2. Complete test coverage with real JWT tokens
3. Error handling standardization
4. Documentation updates

### 🟢 Nice to Have (Post-MVP)
1. Auth endpoints in BFF
2. Advanced auth logging
3. Token blacklisting
4. Auth audit trails

## Implementation Notes

1. **JWT Validation**: Use `python-jose[cryptography]` or `supabase` library for JWT handling
2. **Dependencies**: Leverage FastAPI's dependency injection for clean auth integration
3. **Testing**: Use existing test users and generate real JWT tokens via Supabase client
4. **RLS**: Fix critical `models` table vulnerability first, then verify other policies
5. **Security**: Your service role policies are currently too permissive - review after basic auth is working

## Specific to Your Supabase Setup

Based on analysis of your MakeIt3D project (`iadsbhyztbokarclnzzk`):

### Existing Infrastructure ✅
- **Project Status**: ACTIVE_HEALTHY in us-east-2
- **Database Version**: PostgreSQL 15.8.1.085  
- **Test Users**: Already exist with confirmed emails
- **Foreign Keys**: Properly configured between tables and auth.users
- **Anon Key**: Available for JWT validation

### Configuration Values for `.env`
```bash
# Add these to your .env file:
SUPABASE_PROJECT_ID=iadsbhyztbokarclnzzk
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlhZHNiaHl6dGJva2FyY2xuenprIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDc1MjM4MDUsImV4cCI6MjA2MzA5OTgwNX0.HeTNAhHhCdOoadHJOUeyHEQxo9f5Ole6GxJqYCORS78
SUPABASE_JWT_SECRET=# Get from Supabase Dashboard -> Settings -> API -> JWT Secret
```

### Your Current RLS Policies Summary
```sql
-- ✅ WORKING: input_assets
"Users can manage their own input assets" - user isolation ✓

-- ✅ WORKING: concept_images  
"Users can view their own concept images" - user isolation ✓

-- ❌ BROKEN: models (RLS DISABLED!)
NO user isolation policies - SECURITY VULNERABILITY
```

## Success Criteria

- [ ] All endpoints require valid JWT tokens (except health checks)
- [ ] Users can only access their own data
- [ ] Auth failures return proper 401/403 responses
- [ ] Test suite covers authenticated scenarios
- [ ] No hardcoded user IDs in production code
- [ ] Documentation reflects auth requirements
- [ ] RLS policies properly enforced 