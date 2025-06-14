# Railway Deployment Guide for MakeIT3D BFF

This guide provides multiple ways to deploy the MakeIT3D BFF application to Railway with all required services (FastAPI, Redis, and Celery workers).

## Prerequisites

1. **Railway CLI**: Install the Railway CLI
   ```bash
   npm install -g @railway/cli
   ```

2. **Railway Account**: Login to Railway
   ```bash
   railway login
   ```

3. **Environment Variables**: Gather all required API keys and configuration values

## Method 1: Automated Shell Script (Recommended)

### Step 1: Prepare Environment Variables
```bash
# Copy the template and fill in your values
cp scripts/env.railway.template scripts/.env.railway.local

# Edit the file with your actual API keys and configuration
nano scripts/.env.railway.local
```

### Step 2: Run the Setup Script
```bash
# Make the script executable
chmod +x scripts/deploy-railway.sh

# Set your environment variables
export TRIPO_API_KEY="your_key_here"
export OPENAI_API_KEY="your_key_here"
export STABILITY_API_KEY="your_key_here"
export RECRAFT_API_KEY="your_key_here"
export REPLICATE_API_KEY="your_key_here"
export FLUX_API_KEY="your_key_here"
export SUPABASE_URL="your_supabase_url"
export SUPABASE_SERVICE_KEY="your_supabase_key"
export BFF_BASE_URL="https://your-domain.railway.app"
export GITHUB_REPO="your-username/your-repo"

# Run the setup script
./scripts/deploy-railway.sh
```

## Method 2: Python Script

### Step 1: Prepare Environment File
```bash
cp scripts/env.railway.template scripts/.env.railway.local
# Edit scripts/.env.railway.local with your values
```

### Step 2: Run Python Setup
```bash
python scripts/setup_railway.py
```

## Method 3: Manual Setup

### Step 1: Create Project and Add Redis
```bash
# Initialize Railway project
railway init --name "makeit3d-bff"

# Add Redis service
railway add --service redis

# Deploy main service
railway up
```

### Step 2: Create Celery Worker for Default Queue
```bash
# Create worker service
railway service create celery-worker-default
railway service use celery-worker-default

# Set environment variables
railway variables set \
    REDIS_URL='${{Redis.REDIS_URL}}' \
    TRIPO_API_KEY="your_tripo_key" \
    OPENAI_API_KEY="your_openai_key" \
    STABILITY_API_KEY="your_stability_key" \
    RECRAFT_API_KEY="your_recraft_key" \
    REPLICATE_API_KEY="your_replicate_key" \
    FLUX_API_KEY="your_flux_key" \
    SUPABASE_URL="your_supabase_url" \
    SUPABASE_SERVICE_KEY="your_supabase_key" \
    BFF_BASE_URL="your_domain"

# Set start command
railway service settings --start-command "celery -A celery_worker worker -Q default -l info --concurrency=2"

# Connect to GitHub and deploy
railway service connect --repo "your-username/your-repo"
railway up
```

### Step 3: Create Celery Worker for Tripo Queue
```bash
# Create Tripo worker service
railway service create celery-worker-tripo
railway service use celery-worker-tripo

# Set same environment variables as above
railway variables set \
    REDIS_URL='${{Redis.REDIS_URL}}' \
    # ... (same variables as default worker)

# Set start command for Tripo worker
railway service settings --start-command "celery -A celery_worker worker -Q tripo_other,tripo_refine -l info --concurrency=1"

# Connect and deploy
railway service connect --repo "your-username/your-repo"
railway up
```

### Step 4: Configure Main Service
```bash
# Switch to main service
railway service use makeit3d-bff

# Set environment variables for main service
railway variables set \
    REDIS_URL='${{Redis.REDIS_URL}}' \
    # ... (same variables as workers)

# Generate domain
railway domain generate
```

## Environment Variables Required

| Variable | Description | Example |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection URL | `${{Redis.REDIS_URL}}` |
| `TRIPO_API_KEY` | Tripo AI API key | `tripo_xxxxx` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-xxxxx` |
| `STABILITY_API_KEY` | Stability AI API key | `sk-xxxxx` |
| `RECRAFT_API_KEY` | Recraft API key | `xxxxx` |
| `REPLICATE_API_KEY` | Replicate API key | `r8_xxxxx` |
| `FLUX_API_KEY` | Flux API key | `xxxxx` |
| `SUPABASE_URL` | Supabase project URL | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Supabase service key | `eyJxxx` |
| `BFF_BASE_URL` | Your Railway domain | `https://xxx.railway.app` |

## Service Architecture

After deployment, you'll have these services:

```
┌─────────────────┐    ┌─────────────────┐
│   FastAPI App   │    │      Redis      │
│  (HTTP Server)  │◄──►│ (Broker/Backend)│
└─────────────────┘    └─────────────────┘
         │                       ▲
         │                       │
         ▼                       │
┌─────────────────┐    ┌─────────────────┐
│ celery-worker-  │    │ celery-worker-  │
│    default      │◄───┤     tripo       │
│  (Image Tasks)  │    │ (3D Model Tasks)│
└─────────────────┘    └─────────────────┘
```

## Verification

After deployment, test your setup:

```bash
# Test health endpoint
curl https://your-domain.railway.app/health

# Test image generation
curl -X POST "https://your-domain.railway.app/generate/text-to-image" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "test-123",
    "prompt": "a beautiful sunset",
    "provider": "recraft",
    "style": "realistic_image"
  }'

# Check task status
curl "https://your-domain.railway.app/tasks/TASK_ID/status?service=openai"
```

## Troubleshooting

### Common Issues

1. **Environment Variables Not Set**: Ensure all required environment variables are set for each service
2. **Redis Connection Failed**: Verify `REDIS_URL` is set to `${{Redis.REDIS_URL}}`
3. **Workers Not Processing**: Check worker service logs in Railway dashboard
4. **GitHub Connection Failed**: Ensure repository is accessible and connected

### Monitoring

- **Railway Dashboard**: Monitor service health and logs
- **Service Logs**: Check individual service logs for errors
- **Task Status**: Use the task status endpoint to monitor job processing

## Cost Optimization

- **Concurrency Settings**: Adjust `--concurrency` based on your needs
- **Service Scaling**: Scale down unused services
- **Sleep Settings**: Configure services to sleep when inactive

## Support

For issues with this deployment:
1. Check Railway service logs
2. Verify environment variables
3. Test individual service endpoints
4. Review Celery worker logs 