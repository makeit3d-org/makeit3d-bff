# MakeIt3D BFF API Developer Guide

**Version:** v1.1.0  
**Base URL:** `http://localhost:8000` (replace with your deployment URL)

## Overview

The MakeIt3D Backend-For-Frontend (BFF) API serves as an intermediary between your mobile app and external AI services. It handles:

- **2D Concept Generation** via OpenAI (image-to-image transformations)
- **3D Model Generation** via Tripo AI (text-to-model, image-to-model, sketch-to-model)
- **Asset Management** with Supabase Storage integration
- **Asynchronous Processing** with real-time status updates

## Core API Principles

### 1. Client-Generated Task IDs
Every generation request requires a unique `task_id` that you generate. This serves as the overall job identifier for tracking your workspace items.

```javascript
const taskId = `task-workspace-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
```

### 2. Asset Upload First
All binary inputs (images, sketches, models) must be uploaded to your Supabase Storage **before** calling generation endpoints. Then provide the full Supabase URL to the API.

### 3. Asynchronous Processing
Generation endpoints return a `celery_task_id` immediately. Use this to poll the status endpoint for real-time updates and final results.

### 4. Automatic Asset Management
The BFF automatically downloads temporary AI results and uploads them to your Supabase Storage, providing you with permanent URLs.

### 5. Database Integration
The BFF updates your Supabase tables (`concept_images`, `models`) with metadata, status, and final asset URLs.

---

## Authentication

Include your API key in requests:

```javascript
headers: {
  'X-API-Key': 'your-api-key',
  'Content-Type': 'application/json'
}
```

---

## Generation Endpoints

### 🎨 Image-to-Image Generation

Transform an input image into concept variations using AI.

**Endpoint:** `POST /generation/image-to-image`

**Request Body:**
```javascript
{
  "task_id": "task-workspace-abc123",           // Required: Your unique task ID
  "prompt": "A futuristic cityscape at dusk",  // Required: Description of desired output
  "input_image_asset_url": "https://[project].supabase.co/storage/v1/object/public/bucket/path/image.png", // Required: Full Supabase URL
  "style": "Impressionistic, vibrant colors",  // Optional: Style guidance
  "background": "transparent",                  // Optional: "transparent", "opaque", "auto" (default)
  "n": 2                                       // Optional: Number of images (1-4, default: 1)
}
```

**Response:**
```javascript
{
  "celery_task_id": "abc123xyz456"  // Use this to poll status
}
```

---

### 🔶 Text-to-Model Generation

Generate 3D models from text descriptions.

**Endpoint:** `POST /generation/text-to-model`

**Request Body:**
```javascript
{
  "task_id": "task-workspace-def456",                    // Required
  "prompt": "A violet cartoon flying elephant with big ears", // Required
  
  // Optional Tripo AI parameters:
  "style": "cartoon",                    // Style hint
  "texture": true,                       // Generate textures (default: true)
  "pbr": false,                         // Enable PBR texturing
  "texture_quality": "detailed",        // "standard" or "detailed"
  "model_version": "v2.5-20250123",    // Tripo model version
  "face_limit": 10000,                  // Max faces in output
  "auto_size": true                     // Auto-scale to real dimensions
}
```

---

### 📷 Image-to-Model Generation

Generate 3D models from images. Supports both single-view and multiview modes.

**Endpoint:** `POST /generation/image-to-model`

#### Single Image Mode (1 image)
Uses Tripo's standard `image_to_model` API:

```javascript
{
  "task_id": "task-workspace-ghi789",
  "input_image_asset_urls": [
    "https://[project].supabase.co/storage/v1/object/public/bucket/photo.png"
  ],
  "prompt": "Make it more detailed",  // Optional
  "texture_quality": "detailed"
}
```

#### Multiview Mode (2-4 images)
Uses Tripo's enhanced `multiview_to_model` API for higher quality results:

```javascript
{
  "task_id": "task-workspace-multiview-123",
  "input_image_asset_urls": [
    "https://[project].supabase.co/storage/v1/object/public/bucket/front.png",  // Required: Front view
    "https://[project].supabase.co/storage/v1/object/public/bucket/left.png",   // Optional: Left view  
    "https://[project].supabase.co/storage/v1/object/public/bucket/back.png",   // Optional: Back view
    "https://[project].supabase.co/storage/v1/object/public/bucket/right.png"   // Optional: Right view
  ],
  "prompt": "High quality 3D model",
  "texture_quality": "detailed",
  "pbr": true  // Recommended for multiview
}
```

**⚠️ Multiview Requirements:**
- Images must be in exact order: `[front, left, back, right]`
- Front view (position 0) is **required**
- Other views are optional but must maintain positional order
- Valid combinations: `[front]`, `[front, left]`, `[front, left, back]`, `[front, left, back, right]`

---

### ✏️ Sketch-to-Model Generation

Generate 3D models from hand-drawn sketches.

**Endpoint:** `POST /generation/sketch-to-model`

**Request Body:**
```javascript
{
  "task_id": "task-workspace-jkl012",
  "input_sketch_asset_url": "https://[project].supabase.co/storage/v1/object/public/bucket/sketch.png",
  "prompt": "Modern furniture piece",  // Optional
  "texture": true,
  "orientation": "align_image"         // "default" or "align_image"
}
```

---

### 🔧 Model Refinement

Refine and improve existing 3D models.

**Endpoint:** `POST /generation/refine-model`

**Request Body:**
```javascript
{
  "task_id": "task-workspace-mno345",
  "input_model_asset_url": "https://[project].supabase.co/storage/v1/object/public/bucket/model.glb",
  "prompt": "Make it look more weathered and ancient",
  "draft_model_task_id": "tripo_task_prev_abc",  // Optional: Previous Tripo task ID
  "texture_quality": "detailed",
  "pbr": true
}
```

---

## Status Polling

### 📊 Check Task Status

Poll for real-time updates on your generation tasks.

**Endpoint:** `GET /tasks/{celery_task_id}/status?service={service}`

**Parameters:**
- `celery_task_id`: The ID returned from generation endpoints
- `service`: Either `"openai"` (for image generation) or `"tripoai"` (for 3D models)

**Example:**
```javascript
const response = await fetch(`/tasks/abc123xyz456/status?service=tripoai`);
```

**Response States:**

#### ⏳ Pending
```javascript
{
  "task_id": "abc123xyz456",
  "status": "pending"
}
```

#### 🔄 Processing
```javascript
{
  "task_id": "abc123xyz456", 
  "status": "processing"
}
```

#### ✅ Complete
```javascript
{
  "task_id": "abc123xyz456",
  "status": "complete",
  "asset_url": "https://[project].supabase.co/storage/v1/object/public/generated/model.glb"
}
```

#### ❌ Failed
```javascript
{
  "task_id": "abc123xyz456",
  "status": "failed",
  "error": "AI service timed out"
}
```

---

## Implementation Examples

### Basic Image Generation Flow

```javascript
// 1. Upload your input image to Supabase first
const inputImageUrl = await uploadToSupabase(imageFile, taskId);

// 2. Start generation
const genResponse = await fetch('/generation/image-to-image', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    task_id: taskId,
    prompt: "Transform into cyberpunk style",
    input_image_asset_url: inputImageUrl,
    n: 3
  })
});

const { celery_task_id } = await genResponse.json();

// 3. Poll for completion
const pollStatus = async () => {
  const response = await fetch(`/tasks/${celery_task_id}/status?service=openai`);
  const status = await response.json();
  
  if (status.status === 'complete') return status.asset_url;
  if (status.status === 'failed') throw new Error(status.error);
  else {
    // Still processing, poll again
    setTimeout(pollStatus, 2000);
  }
};

await pollStatus();
```

### Multiview 3D Model Generation

```javascript
// 1. Upload all view images
const frontUrl = await uploadToSupabase(frontImage, `${taskId}/front.png`);
const leftUrl = await uploadToSupabase(leftImage, `${taskId}/left.png`);
const backUrl = await uploadToSupabase(backImage, `${taskId}/back.png`);
const rightUrl = await uploadToSupabase(rightImage, `${taskId}/right.png`);

// 2. Generate multiview model
const response = await fetch('/generation/image-to-model', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    task_id: taskId,
    input_image_asset_urls: [frontUrl, leftUrl, backUrl, rightUrl], // Exact order required
    prompt: "High-quality detailed model",
    texture_quality: "detailed",
    pbr: true
  })
});

const { celery_task_id } = await response.json();

// 3. Poll with longer timeout (multiview takes more time)
// ... polling logic with service=tripoai
```

---

## Response Codes

| Code | Meaning | Description |
|------|---------|-------------|
| `202` | Accepted | Task initiated successfully, use `celery_task_id` to poll |
| `400` | Bad Request | Invalid request format or parameters |
| `404` | Not Found | Task not found or still pending |
| `500` | Internal Error | Server error or AI service failure |

---

## Legacy Endpoint

### 📥 Download Image (Legacy)

**Note:** With the new architecture, you'll typically use Supabase URLs directly. This endpoint may be deprecated.

**Endpoint:** `GET /images/{bucket_name}/{file_path}`

**Example:** `GET /images/generated_assets_bucket/concepts/task_workspace_abc123/0.png`

---

## Tips for Frontend Integration

### 1. **Polling Strategy**
```javascript
const pollWithBackoff = async (celeryTaskId, service, maxAttempts = 30) => {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const response = await fetch(`/tasks/${celeryTaskId}/status?service=${service}`);
    const status = await response.json();
    
    if (status.status === 'complete') return status;
    if (status.status === 'failed') throw new Error(status.error);
    
    // Exponential backoff: 1s, 2s, 4s, then 5s intervals
    const delay = attempt < 3 ? Math.pow(2, attempt) * 1000 : 5000;
    await new Promise(resolve => setTimeout(resolve, delay));
  }
  throw new Error('Polling timeout');
};
```

### 2. **Error Handling**
```javascript
try {
  const result = await generateModel(taskId, prompt);
  updateUI(result.asset_url);
} catch (error) {
  if (error.message.includes('timeout')) {
    showError('Generation is taking longer than expected. Please try again.');
  } else {
    showError(`Generation failed: ${error.message}`);
  }
}
```

### 3. **Progress Indication**
- Show spinner for `pending` and `processing` states
- Display estimated time based on generation type:
  - Image generation: 10-30 seconds
  - Text-to-model: 60-120 seconds  
  - Image-to-model: 60-180 seconds
  - Multiview models: 120-300 seconds

### 4. **Asset URL Management**
- Store final `asset_url` values in your local database
- These URLs are permanent and can be used directly in your UI
- No need to re-download unless caching locally

---

This API provides a complete pipeline for AI-powered 3D content generation with robust asset management and real-time status updates. The asynchronous design ensures your frontend remains responsive during potentially long AI processing times. 