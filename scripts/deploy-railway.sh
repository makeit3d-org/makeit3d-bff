#!/bin/bash

# Railway Deployment Script for MakeIT3D BFF
# This script sets up the complete Railway project with all services

set -e  # Exit on any error

echo "🚀 Setting up MakeIT3D BFF on Railway..."

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI not found. Please install it first:"
    echo "npm install -g @railway/cli"
    exit 1
fi

# Check if user is logged in
if ! railway whoami &> /dev/null; then
    echo "❌ Please login to Railway first:"
    echo "railway login"
    exit 1
fi

# Create new Railway project
echo "📦 Creating new Railway project..."
railway init --name "makeit3d-bff"

# Get project ID for reference
PROJECT_ID=$(railway status --json | jq -r '.project.id')
echo "✅ Created project: $PROJECT_ID"

# Add Redis service
echo "🔴 Adding Redis service..."
railway add --service redis

# Add PostgreSQL (if needed)
# echo "🐘 Adding PostgreSQL service..."
# railway add --service postgresql

# Deploy main FastAPI service
echo "🐍 Deploying main FastAPI service..."
railway up

# Wait a moment for main service to be created
sleep 5

# Create Celery worker for default queue
echo "👷 Creating Celery worker for default queue..."
railway service create celery-worker-default
railway service use celery-worker-default

# Set environment variables for default worker
echo "🔧 Setting environment variables for default worker..."
railway variables set \
    REDIS_URL='${{Redis.REDIS_URL}}' \
    TRIPO_API_KEY="$TRIPO_API_KEY" \
    OPENAI_API_KEY="$OPENAI_API_KEY" \
    STABILITY_API_KEY="$STABILITY_API_KEY" \
    RECRAFT_API_KEY="$RECRAFT_API_KEY" \
    REPLICATE_API_KEY="$REPLICATE_API_KEY" \
    FLUX_API_KEY="$FLUX_API_KEY" \
    SUPABASE_URL="$SUPABASE_URL" \
    SUPABASE_SERVICE_KEY="$SUPABASE_SERVICE_KEY" \
    BFF_BASE_URL="$BFF_BASE_URL"

# Set custom start command for default worker
railway service settings --start-command "celery -A celery_worker worker -Q default -l info --concurrency=2"

# Connect to GitHub repo
railway service connect --repo "$GITHUB_REPO"

# Deploy default worker
railway up

# Create Celery worker for Tripo queue
echo "🎯 Creating Celery worker for Tripo queue..."
railway service create celery-worker-tripo
railway service use celery-worker-tripo

# Set environment variables for Tripo worker
echo "🔧 Setting environment variables for Tripo worker..."
railway variables set \
    REDIS_URL='${{Redis.REDIS_URL}}' \
    TRIPO_API_KEY="$TRIPO_API_KEY" \
    OPENAI_API_KEY="$OPENAI_API_KEY" \
    STABILITY_API_KEY="$STABILITY_API_KEY" \
    RECRAFT_API_KEY="$RECRAFT_API_KEY" \
    REPLICATE_API_KEY="$REPLICATE_API_KEY" \
    FLUX_API_KEY="$FLUX_API_KEY" \
    SUPABASE_URL="$SUPABASE_URL" \
    SUPABASE_SERVICE_KEY="$SUPABASE_SERVICE_KEY" \
    BFF_BASE_URL="$BFF_BASE_URL"

# Set custom start command for Tripo worker
railway service settings --start-command "celery -A celery_worker worker -Q tripo_other,tripo_refine -l info --concurrency=1"

# Connect to GitHub repo
railway service connect --repo "$GITHUB_REPO"

# Deploy Tripo worker
railway up

# Switch back to main service and set its environment variables
echo "🔧 Configuring main FastAPI service..."
railway service use makeit3d-bff

railway variables set \
    REDIS_URL='${{Redis.REDIS_URL}}' \
    TRIPO_API_KEY="$TRIPO_API_KEY" \
    OPENAI_API_KEY="$OPENAI_API_KEY" \
    STABILITY_API_KEY="$STABILITY_API_KEY" \
    RECRAFT_API_KEY="$RECRAFT_API_KEY" \
    REPLICATE_API_KEY="$REPLICATE_API_KEY" \
    FLUX_API_KEY="$FLUX_API_KEY" \
    SUPABASE_URL="$SUPABASE_URL" \
    SUPABASE_SERVICE_KEY="$SUPABASE_SERVICE_KEY" \
    BFF_BASE_URL="$BFF_BASE_URL"

# Generate domain for main service
echo "🌐 Generating domain for main service..."
railway domain generate

echo "✅ Railway deployment complete!"
echo ""
echo "📋 Services created:"
echo "  - makeit3d-bff (FastAPI main service)"
echo "  - Redis (message broker & backend)"
echo "  - celery-worker-default (image generation tasks)"
echo "  - celery-worker-tripo (3D model tasks)"
echo ""
echo "🔗 Check your Railway dashboard: https://railway.app/dashboard"
echo "🚀 Your API will be available at the generated domain" 