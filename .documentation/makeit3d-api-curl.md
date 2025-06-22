# MakeIT3D BFF API - cURL Commands Reference

**Base URL**: `https://api.makeit3d.io`

This document provides ready-to-use cURL commands for all MakeIT3D BFF API endpoints with **server-managed task IDs**.

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
    "provider": "openai",
    "prompt": "A violet colored cartoon flying elephant with big flapping ears",
    "style": "vivid",
    "n": 1,
    "size": "1024x1024",
    "quality": "standard"
  }'
```

**Response:**
```json
{
  "task_id": "text-to-image-1750625610-a1b2c3d4"
}
```

#### Stability AI
```bash
curl -X POST https://api.makeit3d.io/generate/text-to-image \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
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
    "provider": "openai",
    "input_image_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg",
    "prompt": "Transform this into a watercolor painting",
    "style": "vivid",
    "n": 1,
    "background": "transparent"
  }'
```

**Response:**
```json
{
  "task_id": "image-to-image-1750625615-e5f6g7h8"
}
```

#### Stability AI
```bash
curl -X POST https://api.makeit3d.io/generate/image-to-image \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
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
    "provider": "stability",
    "input_sketch_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/sketch-cat.jpg",
    "prompt": "A realistic sports car based on this sketch",
    "control_strength": 0.8,
    "style_preset": "3d-model",
    "negative_prompt": "cartoon, unrealistic",
    "output_format": "png",
    "seed": 0
  }'
```

**Response:**
```json
{
  "task_id": "sketch-to-image-1750625620-i9j0k1l2"
}
```

### 4. Remove Background

#### Stability AI
```bash
curl -X POST https://api.makeit3d.io/generate/remove-background \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "stability",
    "input_image_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg",
    "output_format": "png"
  }'
```

**Response:**
```json
{
  "task_id": "remove-bg-1750625625-m3n4o5p6"
}
```

#### Recraft AI
```bash
curl -X POST https://api.makeit3d.io/generate/remove-background \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
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

**Response:**
```json
{
  "task_id": "image-inpaint-1750625630-q7r8s9t0"
}
```

### 6. Search and Recolor (Stability AI only)

```bash
curl -X POST https://api.makeit3d.io/generate/search-and-recolor \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
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

**Response:**
```json
{
  "task_id": "search-recolor-1750625635-u1v2w3x4"
}
```

### 7. Upscale Images

#### Stability AI
```bash
curl -X POST https://api.makeit3d.io/generate/upscale \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "stability",
    "input_image_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg",
    "model": "fast",
    "output_format": "png"
  }'
```

**Response:**
```json
{
  "task_id": "upscale-1750625640-y5z6a7b8"
}
```

#### Recraft AI
```bash
curl -X POST https://api.makeit3d.io/generate/upscale \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
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
    "input_image_asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg",
    "max_size_mb": 0.5,
    "aspect_ratio_mode": "original",
    "output_format": "original"
  }'
```

**Response:**
```json
{
  "task_id": "downscale-1750625645-c9d0e1f2"
}
```

#### Downscale with Square Padding
```bash
curl -X POST https://api.makeit3d.io/generate/downscale \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
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

**Response:**
```json
{
  "task_id": "text-to-model-1750625650-g3h4i5j6"
}
```

### 2. Image-to-Model

#### Tripo AI (Multi-view)
```bash
curl -X POST https://api.makeit3d.io/generate/image-to-model \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
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

**Response:**
```json
{
  "task_id": "image-to-model-1750625655-k7l8m9n0"
}
```

#### Stability AI (Single image)
```bash
curl -X POST https://api.makeit3d.io/generate/image-to-model \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
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

**Response:**
```json
{
  "task_id": "refine-model-1750625700-o1p2q3r4"
}
```

## 📊 Task Status Polling

### Check Task Status

All task status requests use the same endpoint with auto-detection:

```bash
# Check status using server-generated task ID (auto-detects service type)
curl -H "X-API-Key: $API_KEY" "https://api.makeit3d.io/tasks/remove-bg-1750625625-m3n4o5p6/status"
```

### Example Status Responses

#### Pending
```json
{
  "task_id": "remove-bg-1750625625-m3n4o5p6",
  "status": "pending"
}
```

#### Processing
```json
{
  "task_id": "remove-bg-1750625625-m3n4o5p6",
  "status": "processing",
  "progress": 75
}
```

#### Complete
```json
{
  "task_id": "remove-bg-1750625625-m3n4o5p6",
  "status": "complete",
  "asset_url": "https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/sign/images/remove-bg-1750625625-m3n4o5p6/result.png?token=..."
}
```

#### Failed
```json
{
  "task_id": "remove-bg-1750625625-m3n4o5p6",
  "status": "failed",
  "error": "AI service timed out"
}
```

## 🔄 Complete Workflow Example

### 1. Submit a Text-to-Image Request
```bash
RESPONSE=$(curl -s -X POST https://api.makeit3d.io/generate/text-to-image \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "prompt": "A beautiful sunset over mountains",
    "style": "vivid",
    "n": 1,
    "size": "1024x1024"
  }')

echo "Response: $RESPONSE"
```

### 2. Extract Server-Generated Task ID
```bash
TASK_ID=$(echo $RESPONSE | jq -r '.task_id')
echo "Server-Generated Task ID: $TASK_ID"
```

### 3. Poll for Completion
```bash
while true; do
  STATUS_RESPONSE=$(curl -s -H "X-API-Key: $API_KEY" "https://api.makeit3d.io/tasks/$TASK_ID/status")
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

## 🔄 Multi-Step Workflow Example

### Background Removal → Upscale → Downscale Pipeline
```bash
#!/bin/bash

# Configuration
API_KEY="makeit3d_test_sk_dev_001"
INPUT_IMAGE="https://ftnkfcuhjmmedmoekvwg.supabase.co/storage/v1/object/public/makeit3d-public/portrait-boy.jpg"

# Function to poll for completion
poll_task() {
  local task_id=$1
  local max_attempts=60
  local attempt=0
  
  while [ $attempt -lt $max_attempts ]; do
    response=$(curl -s -H "X-API-Key: $API_KEY" "https://api.makeit3d.io/tasks/$task_id/status")
    status=$(echo $response | jq -r '.status')
    
    echo "[$task_id] Status: $status"
    
    if [ "$status" = "complete" ]; then
      echo $response | jq -r '.asset_url'
      return 0
    elif [ "$status" = "failed" ]; then
      echo "Task failed: $(echo $response | jq -r '.error')"
      return 1
    fi
    
    sleep 2
    ((attempt++))
  done
  
  echo "Timeout waiting for task completion"
  return 1
}

# Step 1: Remove Background
echo "🔄 Step 1: Removing background..."
bg_response=$(curl -s -X POST https://api.makeit3d.io/generate/remove-background \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"provider\": \"stability\",
    \"input_image_asset_url\": \"$INPUT_IMAGE\",
    \"output_format\": \"png\"
  }")

bg_task_id=$(echo $bg_response | jq -r '.task_id')
echo "✅ Background removal task ID: $bg_task_id"

bg_result_url=$(poll_task $bg_task_id)
if [ $? -ne 0 ]; then
  echo "❌ Background removal failed"
  exit 1
fi
echo "✅ Background removed: $bg_result_url"

# Step 2: Upscale
echo "🔄 Step 2: Upscaling image..."
upscale_response=$(curl -s -X POST https://api.makeit3d.io/generate/upscale \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"provider\": \"stability\",
    \"input_image_asset_url\": \"$bg_result_url\",
    \"model\": \"fast\",
    \"output_format\": \"png\"
  }")

upscale_task_id=$(echo $upscale_response | jq -r '.task_id')
echo "✅ Upscale task ID: $upscale_task_id"

upscale_result_url=$(poll_task $upscale_task_id)
if [ $? -ne 0 ]; then
  echo "❌ Upscaling failed"
  exit 1
fi
echo "✅ Image upscaled: $upscale_result_url"

# Step 3: Downscale for optimization
echo "🔄 Step 3: Optimizing file size..."
downscale_response=$(curl -s -X POST https://api.makeit3d.io/generate/downscale \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"input_image_asset_url\": \"$upscale_result_url\",
    \"max_size_mb\": 0.5,
    \"aspect_ratio_mode\": \"original\",
    \"output_format\": \"png\"
  }")

downscale_task_id=$(echo $downscale_response | jq -r '.task_id')
echo "✅ Downscale task ID: $downscale_task_id"

final_result_url=$(poll_task $downscale_task_id)
if [ $? -ne 0 ]; then
  echo "❌ Downscaling failed"
  exit 1
fi
echo "✅ File optimized: $final_result_url"

# Summary
echo ""
echo "🎉 Workflow Complete!"
echo "📥 Original: $INPUT_IMAGE"
echo "📥 Background Removed: $bg_result_url"
echo "📥 Upscaled: $upscale_result_url"
echo "📥 Final Optimized: $final_result_url"
```

## 📝 Important Notes

### Server-Managed Task IDs
- **Never provide `task_id`** in request bodies
- **Always use server-generated task IDs** for status polling
- Task ID format: `{operation}-{timestamp}-{uuid8}`
- Examples: `remove-bg-1750625625-m3n4o5p6`, `upscale-1750625640-y5z6a7b8`

### Input Asset URLs
- Must be valid Supabase storage URLs
- Images should be accessible (public or with proper permissions)
- Supported formats: JPG, PNG, WebP for images; GLB, OBJ for 3D models

### Auto-Detection Features
- **Service Type**: Status endpoint auto-detects service type (no `service` parameter needed)
- **Provider Capabilities**: API validates provider support for each endpoint
- **Error Handling**: Clear error messages for unsupported provider/endpoint combinations

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

**API Version**: 3.0.0  
**Last Updated**: January 2025  
**Base URL**: https://api.makeit3d.io
