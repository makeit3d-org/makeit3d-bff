# MakeIT3D BFF API - cURL Commands Reference

**Base URL**: `https://api.makeit3d.io`

This document provides ready-to-use cURL commands for all MakeIT3D BFF API endpoints.

## 🔐 Authentication

All API requests require an API key in the `X-API-Key` header:

```bash
# Set your API key
export API_KEY="your-api-key-here"

# For testing, you can use the development API key:
export API_KEY="makeit3d_test_sk_dev_001"

# All requests should include this header:
-H "X-API-Key: $API_KEY"
```

## 🔐 Authentication Endpoints

### Register API Key
```bash
curl -X POST https://api.makeit3d.io/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "verification_secret": "your-shared-secret",
    "tenant_type": "shopify",
    "tenant_identifier": "your-store.myshopify.com",
    "tenant_name": "Your Store Name",
    "metadata": {
      "store_id": "12345",
      "plan": "basic"
    }
  }'
```

### Auth Health Check
```bash
curl https://api.makeit3d.io/auth/health
```

## 📊 System Endpoints

### Health Check
```bash
curl https://api.makeit3d.io/health
```

### API Information
```bash
curl https://api.makeit3d.io/
```

## 🖼️ Image Generation Endpoints

### 1. Text-to-Image

#### OpenAI DALL-E
```bash
curl -X POST https://api.makeit3d.io/generate/text-to-image \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "text-to-image-openai-001",
    "provider": "openai",
    "prompt": "A violet colored cartoon flying elephant with big flapping ears",
    "style": "vivid",
    "n": 1,
    "size": "1024x1024",
    "quality": "standard"
  }'
```

#### Stability AI
```bash
curl -X POST https://api.makeit3d.io/generate/text-to-image \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "text-to-image-stability-001",
    "provider": "stability",
    "prompt": "A majestic dragon flying over a fantasy castle at sunset",
    "style_preset": "fantasy-art",
    "aspect_ratio": "16:9",
    "output_format": "png",
    "negative_prompt": "blurry, low quality",
    "seed": 0
  }'
```

#### Recraft AI
```bash
curl -X POST https://api.makeit3d.io/generate/text-to-image \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "text-to-image-recraft-001",
    "provider": "recraft",
    "prompt": "A futuristic robot in a cyberpunk city with neon lights",
    "style": "digital_illustration",
    "substyle": "cyberpunk",
    "model": "recraftv3",
    "response_format": "url"
  }'
```

#### Flux AI
```bash
curl -X POST https://api.makeit3d.io/generate/text-to-image \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "text-to-image-flux-001",
    "provider": "flux",
    "prompt": "A serene mountain landscape with a crystal clear lake",
    "width": 1024,
    "height": 1024,
    "safety_tolerance": 2,
    "prompt_upsampling": false
  }'
```

### 2. Image-to-Image

#### OpenAI DALL-E
```bash
curl -X POST https://api.makeit3d.io/generate/image-to-image \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "image-to-image-openai-001",
    "provider": "openai",
    "input_image_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg",
    "prompt": "Transform this into a watercolor painting",
    "style": "vivid",
    "n": 1,
    "background": "transparent"
  }'
```

#### Stability AI
```bash
curl -X POST https://api.makeit3d.io/generate/image-to-image \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "image-to-image-stability-001",
    "provider": "stability",
    "input_image_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg",
    "prompt": "Make this image look like a vintage photograph",
    "style_preset": "photographic",
    "fidelity": 0.8,
    "negative_prompt": "modern, digital",
    "output_format": "png",
    "seed": 0
  }'
```

#### Recraft AI
```bash
curl -X POST https://api.makeit3d.io/generate/image-to-image \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "image-to-image-recraft-001",
    "provider": "recraft",
    "input_image_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg",
    "prompt": "Convert this to a cartoon style illustration",
    "substyle": "cartoon",
    "strength": 0.2,
    "model": "recraftv3",
    "response_format": "url"
  }'
```

#### Flux AI
```bash
curl -X POST https://api.makeit3d.io/generate/image-to-image \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "image-to-image-flux-001",
    "provider": "flux",
    "input_image_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg",
    "prompt": "Transform this into a sci-fi scene",
    "aspect_ratio": "1:1",
    "safety_tolerance": 2,
    "prompt_upsampling": false
  }'
```

### 3. Sketch-to-Image (Stability AI only)

```bash
curl -X POST https://api.makeit3d.io/generate/sketch-to-image \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "sketch-to-image-001",
    "input_sketch_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/sketch-cat.jpg",
    "prompt": "A realistic sports car based on this sketch",
    "control_strength": 0.8,
    "style_preset": "3d-model",
    "negative_prompt": "cartoon, unrealistic",
    "output_format": "png",
    "seed": 0
  }'
```

### 4. Remove Background

#### Stability AI
```bash
curl -X POST https://api.makeit3d.io/generate/remove-background \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "remove-bg-stability-001",
    "provider": "stability",
    "input_image_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg",
    "output_format": "png"
  }'
```

#### Recraft AI
```bash
curl -X POST https://api.makeit3d.io/generate/remove-background \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "remove-bg-recraft-001",
    "provider": "recraft",
    "input_image_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg",
    "response_format": "url"
  }'
```

### 5. Image Inpaint (Recraft AI only)

```bash
curl -X POST https://api.makeit3d.io/generate/image-inpaint \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "image-inpaint-001",
    "provider": "recraft",
    "input_image_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg",
    "input_mask_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/mask.jpg",
    "prompt": "A beautiful garden with flowers",
    "negative_prompt": "ugly, distorted",
    "n": 1,
    "style": "realistic_image",
    "substyle": "natural",
    "model": "recraftv3",
    "response_format": "url"
  }'
```

### 6. Search and Recolor (Stability AI only)

```bash
curl -X POST https://api.makeit3d.io/generate/search-and-recolor \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "search-recolor-001",
    "provider": "stability",
    "input_image_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg",
    "prompt": "Make it bright red with metallic finish",
    "select_prompt": "car",
    "negative_prompt": "dull, matte",
    "grow_mask": 3,
    "seed": 0,
    "output_format": "png",
    "style_preset": "photographic"
  }'
```

### 7. Upscale Images

#### Stability AI
```bash
curl -X POST https://api.makeit3d.io/generate/upscale \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "upscale-stability-001",
    "provider": "stability",
    "input_image_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg",
    "model": "fast",
    "output_format": "png"
  }'
```

#### Recraft AI
```bash
curl -X POST https://api.makeit3d.io/generate/upscale \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "upscale-recraft-001",
    "provider": "recraft",
    "input_image_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg",
    "model": "crisp",
    "response_format": "url"
  }'
```

### 8. Downscale Images (Basic Image Processing)

```bash
curl -X POST https://api.makeit3d.io/generate/downscale \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "downscale-001",
    "input_image_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg",
    "max_size_mb": 0.5,
    "aspect_ratio_mode": "original",
    "output_format": "original"
  }'
```

#### Downscale with Square Padding
```bash
curl -X POST https://api.makeit3d.io/generate/downscale \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "downscale-square-001",
    "input_image_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg",
    "max_size_mb": 1.0,
    "aspect_ratio_mode": "square",
    "output_format": "png"
  }'
```

#### Downscale with Format Conversion
```bash
curl -X POST https://api.makeit3d.io/generate/downscale \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "downscale-convert-001",
    "input_image_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg",
    "max_size_mb": 0.2,
    "aspect_ratio_mode": "original",
    "output_format": "jpeg"
  }'
```

## 🎯 3D Model Generation Endpoints

### 1. Text-to-Model (Tripo AI only)

```bash
curl -X POST https://api.makeit3d.io/generate/text-to-model \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "text-to-model-001",
    "provider": "tripo",
    "prompt": "A violet colored cartoon flying elephant with big flapping ears",
    "style": "cartoon",
    "texture": true,
    "pbr": false,
    "model_version": "v2.0-20240919",
    "face_limit": 10000,
    "auto_size": true,
    "texture_quality": "standard"
  }'
```

### 2. Image-to-Model

#### Tripo AI (Multi-view)
```bash
curl -X POST https://api.makeit3d.io/generate/image-to-model \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "image-to-model-tripo-001",
    "provider": "tripo",
    "input_image_asset_urls": [
      "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/front.jpg",
      "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/side.jpg"
    ],
    "prompt": "A detailed 3D model of this object",
    "style": "realistic",
    "texture": true,
    "pbr": true,
    "model_version": "v2.0-20240919",
    "face_limit": 20000,
    "auto_size": true,
    "texture_quality": "detailed",
    "orientation": "align_image"
  }'
```

#### Stability AI (Single image)
```bash
curl -X POST https://api.makeit3d.io/generate/image-to-model \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "image-to-model-stability-001",
    "provider": "stability",
    "input_image_asset_urls": [
      "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg"
    ],
    "texture_resolution": 2048,
    "remesh": "quad",
    "foreground_ratio": 1.3,
    "target_type": "none",
    "target_count": 10000,
    "guidance_scale": 6,
    "seed": 0
  }'
```

### 3. Refine Model (Tripo AI only)

```bash
curl -X POST https://api.makeit3d.io/generate/refine-model \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "refine-model-001",
    "provider": "tripo",
    "input_model_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-models/draft_model.glb",
    "prompt": "Make it more detailed and realistic with better textures",
    "draft_model_task_id": "previous-tripo-task-id",
    "texture": true,
    "pbr": true,
    "model_version": "v2.0-20240919",
    "face_limit": 30000,
    "auto_size": true,
    "texture_quality": "detailed"
  }'
```

## 📊 Task Status Polling

### Check Task Status

#### For Image Generation Tasks
```bash
# OpenAI tasks
curl -H "X-API-Key: $API_KEY" "https://api.makeit3d.io/tasks/your-celery-task-id/status?service=openai"

# Stability AI tasks
curl -H "X-API-Key: $API_KEY" "https://api.makeit3d.io/tasks/your-celery-task-id/status?service=stability"

# Recraft AI tasks
curl -H "X-API-Key: $API_KEY" "https://api.makeit3d.io/tasks/your-celery-task-id/status?service=recraft"

# Flux AI tasks
curl -H "X-API-Key: $API_KEY" "https://api.makeit3d.io/tasks/your-celery-task-id/status?service=flux"

# Upscale tasks (all providers)
curl -H "X-API-Key: $API_KEY" "https://api.makeit3d.io/tasks/your-celery-task-id/status?service=openai"

# Downscale tasks (image processing)
curl -H "X-API-Key: $API_KEY" "https://api.makeit3d.io/tasks/your-celery-task-id/status?service=openai"
```

#### For 3D Model Generation Tasks
```bash
# Tripo AI tasks
curl -H "X-API-Key: $API_KEY" "https://api.makeit3d.io/tasks/your-celery-task-id/status?service=tripoai"
```

### Example Status Response
```json
{
  "task_id": "celery-task-id-12345",
  "status": "complete",
  "asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-images/result.png",
  "progress": 100
}
```

## 🔄 Complete Workflow Example

### 1. Submit a Text-to-Image Request
```bash
RESPONSE=$(curl -s -X POST https://api.makeit3d.io/generate/text-to-image \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "workflow-example-001",
    "provider": "openai",
    "prompt": "A beautiful sunset over mountains",
    "style": "vivid",
    "n": 1,
    "size": "1024x1024"
  }')

echo "Response: $RESPONSE"
```

### 2. Extract Celery Task ID
```bash
CELERY_TASK_ID=$(echo $RESPONSE | jq -r '.celery_task_id')
echo "Celery Task ID: $CELERY_TASK_ID"
```

### 3. Poll for Completion
```bash
while true; do
  STATUS_RESPONSE=$(curl -s -H "X-API-Key: $API_KEY" "https://api.makeit3d.io/tasks/$CELERY_TASK_ID/status?service=openai")
  STATUS=$(echo $STATUS_RESPONSE | jq -r '.status')
  
  echo "Current status: $STATUS"
  
  if [ "$STATUS" = "complete" ]; then
    ASSET_URL=$(echo $STATUS_RESPONSE | jq -r '.asset_url')
    echo "✅ Task completed! Asset URL: $ASSET_URL"
    break
  elif [ "$STATUS" = "failed" ]; then
    ERROR=$(echo $STATUS_RESPONSE | jq -r '.error')
    echo "❌ Task failed: $ERROR"
    break
  fi
  
  sleep 2
done
```

### 4. Download the Result
```bash
if [ "$STATUS" = "complete" ]; then
  curl -o result.png "$ASSET_URL"
  echo "📥 Downloaded result to result.png"
fi
```

## 📝 Important Notes

### Task IDs
- **Always use unique `task_id`** values for each request
- Task IDs should be client-generated and meaningful
- Format suggestion: `{operation}-{provider}-{timestamp}` or `{operation}-{provider}-{uuid}`

### Input Asset URLs
- Must be valid Supabase storage URLs
- Images should be accessible (public or with proper permissions)
- Supported formats: JPG, PNG, WebP for images; GLB, OBJ for 3D models

### Rate Limiting
- Different endpoints have different rate limits
- OpenAI: 4 requests/minute
- Tripo Refine: 2 requests/minute  
- Tripo Other: 4 requests/minute
- Upscale: 4 requests/minute
- Downscale: 30 requests/minute (more permissive for basic image processing)

### Provider Capabilities

| Feature | OpenAI | Stability | Recraft | Flux | Tripo | Image Processing |
|---------|--------|-----------|---------|------|-------|------------------|
| Text-to-Image | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Image-to-Image | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Sketch-to-Image | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Remove Background | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Image Inpaint | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| Search & Recolor | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| Upscale | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| Downscale | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Text-to-Model | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| Image-to-Model | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Refine Model | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |

### Upscale vs Downscale
- **Upscale**: AI-powered enhancement using Stability AI or Recraft, increases image resolution and quality
- **Downscale**: Basic image processing using Pillow, reduces file size to meet size constraints

### Error Handling
- Always check the HTTP status code
- Parse JSON responses for error details
- Implement retry logic for network failures
- Handle rate limiting with exponential backoff

### Testing
- Use the health endpoint to verify API availability
- Start with simple text-to-image requests
- Test with small images first
- Monitor task status polling frequency to avoid rate limits

---

**API Version**: 1.0.0  
**Last Updated**: June 2025  
**Base URL**: https://api.makeit3d.io
