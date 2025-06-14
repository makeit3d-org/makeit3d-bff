# MakeIt3D BFF API Developer Guide

**Version:** v2.0.0  
**Base URL:** `http://localhost:8000` (replace with your deployment URL)

## Index

1. [Overview](#overview)
2. [What's New in v2.0](#-whats-new-in-v20)
   - [Multi-Provider Support](#multi-provider-support)
   - [New Endpoints](#new-endpoints)
   - [Updated Endpoints](#updated-endpoints)
   - [Provider Selection](#provider-selection)
3. [Core API Principles](#core-api-principles)
   - [Provider Selection](#1-provider-selection)
   - [Client-Generated Task IDs](#2-client-generated-task-ids)
   - [Asset Upload First](#3-asset-upload-first)
   - [Asynchronous Processing](#4-asynchronous-processing)
   - [Automatic Asset Management](#5-automatic-asset-management)
   - [Database Integration](#6-database-integration)
4. [Authentication](#authentication)
   - [Getting JWT Tokens](#getting-jwt-tokens)
   - [Auth Error Responses](#auth-error-responses)
   - [Test Users](#test-users)
5. [Generation Endpoints](#generation-endpoints)
   - [🎨 Image-to-Image Generation](#-image-to-image-generation)
   - [🔶 Text-to-Image Generation](#-text-to-image-generation)
   - [🔶 Text-to-Model Generation](#-text-to-model-generation)
   - [📷 Image-to-Model Generation](#-image-to-model-generation)
   - [✏️ Sketch-to-Image Generation](#️-sketch-to-image-generation)
   - [🖼️ Background Removal](#️-background-removal)
   - [🎨 Search and Recolor](#-search-and-recolor)
   - [🔧 Model Refinement](#-model-refinement)
6. [Status Polling](#status-polling)
   - [📊 Check Task Status](#-check-task-status)
7. [Implementation Examples](#implementation-examples)
   - [Multi-Provider Image Generation](#multi-provider-image-generation)
   - [Background Removal with Fallback](#background-removal-with-fallback)
   - [Search and Recolor Implementation](#search-and-recolor-implementation)
   - [3D Model Generation with Multiple Providers](#3d-model-generation-with-multiple-providers)
8. [Response Codes](#response-codes)
9. [Provider-Specific Notes](#provider-specific-notes)
10. [Tips for Frontend Integration](#tips-for-frontend-integration)
    - [Provider Selection Strategy](#1-provider-selection-strategy)
    - [Polling Strategy with Provider Awareness](#2-polling-strategy-with-provider-awareness)
    - [Error Handling with Provider Context](#3-error-handling-with-provider-context)
    - [Progress Indication by Provider](#4-progress-indication-by-provider)

---

## Overview

The MakeIt3D Backend-For-Frontend (BFF) API serves as an intermediary between your mobile app and multiple AI services. It now supports **5 AI providers** across **8 endpoints** with unified parameter handling:

- **🎨 2D Image Generation** via OpenAI, Stability AI, Recraft, and Flux
- **🔶 3D Model Generation** via Tripo AI and Stability AI  
- **✏️ Sketch Processing** via Stability AI
- **🖼️ Background Removal** via Stability AI and Recraft
- **🎨 Object Recoloring** via Stability AI's Search and Recolor
- **🔧 Model Refinement** via Tripo AI
- **📦 Asset Management** with Supabase Storage integration
- **⚡ Asynchronous Processing** with real-time status updates

## 🆕 What's New in v2.0

### Multi-Provider Support
Each endpoint now supports multiple AI providers with provider-specific parameters:

| Endpoint | OpenAI | Tripo | Stability | Recraft | Flux |
|----------|--------|-------|-----------|---------|------|
| `/image-to-image` | ✅ | ❌ | ✅ | ✅ | ✅ |
| `/text-to-image` | ✅ | ❌ | ✅ | ✅ | ❌ |
| `/text-to-model` | ❌ | ✅ | ❌ | ❌ | ❌ |
| `/image-to-model` | ❌ | ✅ | ✅ | ❌ | ❌ |
| `/sketch-to-image` | ❌ | ❌ | ✅ | ❌ | ❌ |
| `/image-inpaint` | ❌ | ❌ | ❌ | ✅ | ❌ |
| `/remove-background` | ❌ | ❌ | ✅ | ✅ | ❌ |
| `/search-and-recolor` | ❌ | ❌ | ✅ | ❌ | ❌ |
| `/refine-model` | ❌ | ✅ | ❌ | ❌ | ❌ |

### New Endpoints
- **`/text-to-image`** - New 2D image generation from text using OpenAI, Stability, and Recraft
- **`/sketch-to-image`** - Generates 2D images from sketches using Stability AI
- **`/remove-background`** - Background removal functionality
- **`/search-and-recolor`** - Object segmentation and recoloring using Stability AI

### Updated Endpoints
- **`/text-to-model`** - Now exclusively for 3D model generation using Tripo AI only

### Provider Selection
All endpoints now require a `provider` field to specify which AI service to use.

## Core API Principles

### 1. Provider Selection
Every generation request must specify which AI provider to use:

```javascript
{
  "provider": "openai",  // Required: "openai", "stability", "recraft", "flux", or "tripo"
  "task_id": "task-workspace-abc123",
  // ... other parameters
}
```

### 2. Client-Generated Task IDs
Every generation request requires a unique `task_id` that you generate. This serves as the overall job identifier for tracking your workspace items.

```javascript
const taskId = `task-workspace-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
```

### 3. Asset Upload First
All binary inputs (images, sketches, models) must be uploaded to your Supabase Storage **before** calling generation endpoints. Then provide the full Supabase URL to the API.

### 4. Asynchronous Processing
Generation endpoints return a `celery_task_id` immediately. Use this to poll the status endpoint for real-time updates and final results.

### 5. Automatic Asset Management
The BFF automatically downloads temporary AI results and uploads them to your Supabase Storage, providing you with permanent URLs.

### 6. Database Integration
The BFF updates your Supabase tables (`concept_images`, `models`) with metadata, status, and final asset URLs.

---

## Authentication

**The API requires both an API key and a valid Supabase JWT token:**

```javascript
headers: {
  'X-API-Key': 'your-api-key',
  'Authorization': 'Bearer <supabase-jwt-token>',
  'Content-Type': 'application/json'
}
```

### Getting JWT Tokens

Obtain JWT tokens through Supabase Auth in your frontend:

```javascript
// In your React Native app with Supabase
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.EXPO_PUBLIC_SUPABASE_URL!,
  process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY!
);

// Login and get session
const { data: { session }, error } = await supabase.auth.signInWithPassword({
  email: 'user@example.com',
  password: 'password'
});

// Use session.access_token in Authorization header
const token = session?.access_token;
```

### Auth Error Responses

| Code | Response | Description |
|------|----------|-------------|
| `401` | `{"error": "unauthorized", "message": "Missing or invalid token"}` | No Authorization header or invalid JWT |
| `403` | `{"error": "forbidden", "message": "Access denied"}` | Valid token but insufficient permissions |

### Test Users

For development, you can use these existing test accounts:
- `test@example.com` (ID: `00000000-0000-4000-8000-000000000001`)  
- `test-user@example.com` (ID: `123e4567-e89b-12d3-a456-426614174000`)

---

## Generation Endpoints

### 🎨 Image-to-Image Generation

Transform an input image into concept variations using multiple AI providers.

**Endpoint:** `POST /generation/image-to-image`

#### OpenAI Provider
```javascript
{
  "task_id": "task-workspace-abc123",           // Required: Your unique task ID
  "provider": "openai",                         // Required: Provider selection
  "prompt": "A futuristic cityscape at dusk",  // Required: Description of desired output
  "input_image_asset_url": "https://[project].supabase.co/storage/v1/object/public/bucket/path/image.png", // Required: Full Supabase URL
  
  // OpenAI-specific parameters:
  "style": "vivid",                            // Optional: "vivid" or "natural"
  "background": "transparent",                  // Optional: "transparent", "opaque", "auto"
  "n": 2,                                      // Optional: Number of images (1-4, default: 1)
  "size": "1024x1024",                         // Optional: "1024x1024", "1792x1024", "1024x1792"
  "quality": "standard"                        // Optional: "standard" or "hd"
}
```

#### Stability AI Provider
```javascript
{
  "task_id": "task-workspace-def456",
  "provider": "stability",
  "prompt": "A futuristic cityscape at dusk",
  "input_image_asset_url": "https://...",
  
  // Stability-specific parameters:
  "style_preset": "3d-model",                  // Optional: Style preset
  "fidelity": 0.8,                            // Optional: 0.0-1.0, adherence to input
  "negative_prompt": "blurry, low quality",    // Optional: What to avoid
  "output_format": "png",                      // Optional: "png", "jpeg", "webp"
  "seed": 12345                               // Optional: Reproducibility seed
}
```

#### Recraft Provider
```javascript
{
  "task_id": "task-workspace-ghi789",
  "provider": "recraft",
  "prompt": "A futuristic cityscape at dusk",
  "input_image_asset_url": "https://...",
  
  // Recraft-specific parameters:
  "style": "realistic_image",                  // Optional: Style selection
  "substyle": "b_and_w",                      // Optional: Sub-style
  "strength": 0.3,                            // Optional: 0.0-1.0, transformation strength
  "negative_prompt": "cartoon, anime",         // Optional: What to avoid
  "n": 2,                                     // Optional: Number of images
  "model": "recraftv3",                       // Optional: Model version
  "response_format": "url",                   // Optional: "url" or "b64_json"
  "style_id": "custom_style_123"              // Optional: Custom style ID
}
```

#### Flux Provider
```javascript
{
  "task_id": "task-workspace-mno012",
  "provider": "flux",
  "prompt": "A futuristic cityscape at dusk",
  "input_image_asset_url": "https://...",
  
  // Flux-specific parameters:
  "aspect_ratio": "1:1",                      // Optional: "1:1", "16:9", "9:16", "21:9", "2:3", "3:2", "4:5", "5:4", "9:16", "16:9"
  "output_format": "png",                     // Optional: "png", "jpeg"
  "safety_tolerance": 2,                      // Optional: 0-6, higher = more permissive
  "prompt_upsampling": false                  // Optional: Enhance prompt automatically
}
```

**Response:**
```javascript
{
  "celery_task_id": "abc123xyz456"  // Use this to poll status
}
```

---

### 🔶 Text-to-Image Generation

Generate 2D images from text descriptions using multiple AI providers.

**Endpoint:** `POST /generation/text-to-image`

#### OpenAI Provider
```javascript
{
  "task_id": "task-workspace-def456",                    // Required
  "provider": "openai",                                  // Required
  "prompt": "A violet cartoon flying elephant with big ears", // Required
  
  // OpenAI-specific parameters:
  "style": "vivid",                           // Optional: "vivid" or "natural"
  "n": 1,                                     // Optional: Number of images (1-4)
  "size": "1024x1024",                        // Optional: Image dimensions
  "quality": "standard"                       // Optional: "standard" or "hd"
}
```

#### Stability AI Provider
```javascript
{
  "task_id": "task-workspace-ghi789",
  "provider": "stability",
  "prompt": "A violet cartoon flying elephant with big ears",
  
  // Stability-specific parameters:
  "style_preset": "fantasy-art",              // Optional: Style preset
  "aspect_ratio": "1:1",                      // Optional: "1:1", "16:9", "9:16", etc.
  "negative_prompt": "realistic, photo",       // Optional: What to avoid
  "output_format": "png",                     // Optional: "png", "jpeg", "webp"
  "seed": 42                                  // Optional: Reproducibility seed
}
```

#### Recraft Provider
```javascript
{
  "task_id": "task-workspace-jkl012",
  "provider": "recraft",
  "prompt": "A violet cartoon flying elephant with big ears",
  
  // Recraft-specific parameters:
  "style": "digital_illustration",            // Optional: Style selection
  "substyle": "hand_drawn",                   // Optional: Sub-style
  "n": 1,                                     // Optional: Number of images
  "model": "recraftv3",                       // Optional: Model version
  "response_format": "url",                   // Optional: "url" or "b64_json"
  "size": "1024x1024",                        // Optional: Image dimensions
  "style_id": "custom_style_456"              // Optional: Custom style ID
}
```

---

### 🔶 Text-to-Model Generation

Generate 3D models from text descriptions using Tripo AI.

**Endpoint:** `POST /generation/text-to-model`

**Note:** This endpoint generates 3D models and only supports Tripo AI.

#### Tripo AI Provider
```javascript
{
  "task_id": "task-workspace-xyz789",                    // Required
  "provider": "tripo",                                   // Required: Only "tripo" supported
  "prompt": "A medieval castle with tall towers",       // Required: Description of 3D model
  
  // Tripo-specific parameters:
  "style": "realistic",                       // Optional: Style selection
  "texture": true,                           // Optional: Generate textures (default: true)
  "pbr": false,                             // Optional: PBR texturing
  "model_version": "v2.5-20250123",        // Optional: Model version
  "face_limit": 10000,                      // Optional: Max faces in output model
  "auto_size": true,                        // Optional: Auto-scale to real-world dimensions
  "texture_quality": "standard"             // Optional: "standard" or "detailed"
}
```

**Response:**
```javascript
{
  "celery_task_id": "def456ghi789"  // Use this to poll status
}
```

---

### 📷 Image-to-Model Generation

Generate 3D models from images using Tripo AI or Stability AI.

**Endpoint:** `POST /generation/image-to-model`

#### Tripo AI Provider (Multiview Support)
```javascript
{
  "task_id": "task-workspace-ghi789",
  "provider": "tripo",                        // Required
  "input_image_asset_urls": [                 // Required: 1-4 images
    "https://[project].supabase.co/storage/v1/object/public/bucket/front.png",  // Front view (required)
    "https://[project].supabase.co/storage/v1/object/public/bucket/left.png",   // Left view (optional)
    "https://[project].supabase.co/storage/v1/object/public/bucket/back.png",   // Back view (optional)
    "https://[project].supabase.co/storage/v1/object/public/bucket/right.png"   // Right view (optional)
  ],
  "prompt": "Make it more detailed",          // Optional
  
  // Tripo-specific parameters:
  "texture": true,                            // Optional: Generate textures
  "pbr": false,                              // Optional: PBR texturing
  "texture_quality": "detailed",             // Optional: "standard" or "detailed"
  "model_version": "v2.5-20250123",         // Optional: Model version
  "face_limit": 10000,                       // Optional: Max faces
  "auto_size": true,                         // Optional: Auto-scale
  "orientation": "default"                   // Optional: "default" or "align_image"
}
```

#### Stability AI Provider (SPAR3D)
```javascript
{
  "task_id": "task-workspace-mno345",
  "provider": "stability",                    // Required
  "input_image_asset_urls": [                 // Required: Single image
    "https://[project].supabase.co/storage/v1/object/public/bucket/photo.png"
  ],
  "prompt": "High quality 3D model",         // Optional
  
  // Stability SPAR3D parameters:
  "texture_resolution": 1024,                // Optional: 512, 1024, 2048
  "remesh": "quad",                          // Optional: "none", "quad", "triangle"
  "foreground_ratio": 0.85,                  // Optional: 0.0-1.0
  "target_type": "vertex",                   // Optional: "vertex" or "face"
  "target_count": 10000,                     // Optional: Target count
  "guidance_scale": 3.0,                     // Optional: 1.0-10.0
  "seed": 12345                              // Optional: Reproducibility seed
}
```

---

### ✏️ Sketch-to-Image Generation

Generate 2D images from hand-drawn sketches using Stability AI.

**Endpoint:** `POST /generation/sketch-to-image`

```javascript
{
  "task_id": "task-workspace-jkl012",
  "provider": "stability",                    // Always "stability" for this endpoint
  "input_sketch_asset_url": "https://[project].supabase.co/storage/v1/object/public/bucket/sketch.png",
  "prompt": "Modern furniture piece",         // Required: Description
  
  // Stability Control Sketch parameters:
  "control_strength": 0.7,                   // Optional: 0.0-1.0, sketch adherence
  "style_preset": "photographic",           // Optional: Style preset
  "negative_prompt": "blurry, distorted",    // Optional: What to avoid
  "output_format": "png"                     // Optional: "png", "jpeg", "webp"
}
```

---

### 🖼️ Background Removal

Remove backgrounds from images using Stability AI or Recraft.

**Endpoint:** `POST /generation/remove-background`

#### Stability AI Provider
```javascript
{
  "task_id": "task-workspace-pqr678",
  "provider": "stability",                    // Required
  "input_image_asset_url": "https://[project].supabase.co/storage/v1/object/public/bucket/image.png",
  
  // Stability-specific parameters:
  "output_format": "png"                     // Optional: "png" (recommended for transparency)
}
```

#### Recraft Provider
```javascript
{
  "task_id": "task-workspace-stu901",
  "provider": "recraft",                      // Required
  "input_image_asset_url": "https://[project].supabase.co/storage/v1/object/public/bucket/image.png",
  
  // Recraft-specific parameters:
  "response_format": "url"                   // Optional: "url" or "b64_json"
}
```

---

### 🎨 Search and Recolor

Automatically segment and recolor specific objects in an image using Stability AI. This endpoint finds objects based on a description and changes their colors without requiring manual masks.

**Endpoint:** `POST /generation/search-and-recolor`

#### Stability AI Provider
```javascript
{
  "task_id": "task-workspace-xyz123",
  "provider": "stability",                    // Always "stability" for this endpoint
  "input_image_asset_url": "https://[project].supabase.co/storage/v1/object/public/bucket/image.png",
  "prompt": "light blue cat with dark blue stripes, maintaining the same pose and expression", // Required: Description of desired recoloring
  "select_prompt": "cat",                     // Required: What object to find and recolor
  
  // Stability Search and Recolor parameters:
  "negative_prompt": "blurry, low quality, distorted, orange, tan, brown", // Optional: What to avoid
  "grow_mask": 3,                            // Optional: 0-20, grows mask edges for smoother transitions (default: 3)
  "seed": 0,                                 // Optional: Reproducibility seed (0 for random)
  "output_format": "png",                    // Optional: "png", "jpeg", "webp" (default: "png")
  "style_preset": "photographic"             // Optional: Style preset (same options as other Stability endpoints)
}
```

**Key Features:**
- **Automatic Segmentation**: No manual mask required - just describe what to find
- **Precise Recoloring**: Changes only the specified object while preserving everything else
- **Smooth Transitions**: `grow_mask` parameter ensures natural edges around recolored areas
- **Style Control**: Optional style presets for consistent artistic output

**Use Cases:**
- Change clothing colors in fashion photos
- Recolor vehicles, furniture, or objects in product images
- Create color variations of characters or illustrations
- Brand color consistency across product lines

---

### 🔧 Model Refinement

Refine and improve existing 3D models using Tripo AI.

**Endpoint:** `POST /generation/refine-model`

```javascript
{
  "task_id": "task-workspace-mno345",
  "provider": "tripo",                        // Always "tripo" for this endpoint
  "input_model_asset_url": "https://[project].supabase.co/storage/v1/object/public/bucket/model.glb",
  "prompt": "Make it look more weathered and ancient",
  
  // Tripo refinement parameters:
  "draft_model_task_id": "tripo_task_prev_abc",  // Optional: Previous Tripo task ID
  "texture": true,                            // Optional: Generate textures
  "pbr": true,                               // Optional: PBR texturing
  "texture_quality": "detailed",             // Optional: "standard" or "detailed"
  "model_version": "v2.5-20250123",         // Optional: Model version
  "face_limit": 20000,                       // Optional: Max faces
  "auto_size": true                          // Optional: Auto-scale
}
```

---

## Status Polling

### 📊 Check Task Status

Poll for real-time updates on your generation tasks.

**Endpoint:** `GET /tasks/{celery_task_id}/status?service={service}`

**Parameters:**
- `celery_task_id`: The ID returned from generation endpoints
- `service`: Either `"openai"` or `"tripoai"` (Stability and Recraft tasks use OpenAI-style polling)

**Provider Service Mapping:**
- OpenAI tasks: `service=openai`
- Tripo AI tasks: `service=tripoai`  
- Stability AI tasks: `service=openai`
- Recraft tasks: `service=openai`
- Flux tasks: `service=openai`

**Example:**
```javascript
const response = await fetch(`/tasks/abc123xyz456/status?service=openai`, {
  headers: {
    'Authorization': `Bearer ${session.access_token}`,
    'X-API-Key': 'your-api-key'
  }
});
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
  "asset_url": "https://[project].supabase.co/storage/v1/object/public/generated/result.png"
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

### Multi-Provider Image Generation

```javascript
// Example: Try different providers for the same prompt
const providers = ['openai', 'stability', 'recraft'];
const results = [];

for (const provider of providers) {
  const taskId = `task-${provider}-${Date.now()}`;
  
  // Provider-specific parameters
  let providerParams = { task_id: taskId, provider, prompt: "Cyberpunk cityscape" };
  
  if (provider === 'openai') {
    providerParams = { ...providerParams, style: "vivid", n: 2 };
  } else if (provider === 'stability') {
    providerParams = { ...providerParams, style_preset: "neon-punk", output_format: "png" };
  } else if (provider === 'recraft') {
    providerParams = { ...providerParams, style: "digital_illustration", substyle: "cyberpunk" };
  }
  
  const response = await fetch('/generation/text-to-model', {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${session.access_token}`,
      'X-API-Key': 'your-api-key'
    },
    body: JSON.stringify(providerParams)
  });
  
  const { celery_task_id } = await response.json();
  results.push({ provider, taskId: celery_task_id });
}

// Poll all tasks
const finalResults = await Promise.all(
  results.map(({ provider, taskId }) => 
    pollStatus(taskId, provider === 'tripo' ? 'tripoai' : 'openai')
  )
);
```

### Background Removal with Fallback

```javascript
// Try Stability first, fallback to Recraft if needed
const removeBackground = async (imageUrl, taskId) => {
  try {
    // Try Stability AI first
    const stabilityResponse = await fetch('/generation/remove-background', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${session.access_token}`,
        'X-API-Key': 'your-api-key'
      },
      body: JSON.stringify({
        task_id: `${taskId}-stability`,
        provider: "stability",
        input_image_asset_url: imageUrl,
        output_format: "png"
      })
    });
    
    const { celery_task_id } = await stabilityResponse.json();
    return await pollStatus(celery_task_id, 'openai');
    
  } catch (error) {
    console.log('Stability failed, trying Recraft...', error);
    
    // Fallback to Recraft
    const recraftResponse = await fetch('/generation/remove-background', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${session.access_token}`,
        'X-API-Key': 'your-api-key'
      },
      body: JSON.stringify({
        task_id: `${taskId}-recraft`,
        provider: "recraft",
        input_image_asset_url: imageUrl,
        response_format: "url"
      })
    });
    
    const { celery_task_id } = await recraftResponse.json();
    return await pollStatus(celery_task_id, 'openai');
  }
};
```

### 3D Model Generation with Multiple Providers

```javascript
// Generate 3D model using both Tripo and Stability, compare results
const generate3DModel = async (imageUrl, taskId) => {
  const tripoTask = fetch('/generation/image-to-model', {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${session.access_token}`,
      'X-API-Key': 'your-api-key'
    },
    body: JSON.stringify({
      task_id: `${taskId}-tripo`,
      provider: "tripo",
      input_image_asset_urls: [imageUrl],
      texture_quality: "detailed",
      pbr: true
    })
  });
  
  const stabilityTask = fetch('/generation/image-to-model', {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${session.access_token}`,
      'X-API-Key': 'your-api-key'
    },
    body: JSON.stringify({
      task_id: `${taskId}-stability`,
      provider: "stability",
      input_image_asset_urls: [imageUrl],
      texture_resolution: 1024,
      remesh: "quad"
    })
  });
  
  const [tripoResponse, stabilityResponse] = await Promise.all([tripoTask, stabilityTask]);
  
  const tripoTaskId = (await tripoResponse.json()).celery_task_id;
  const stabilityTaskId = (await stabilityResponse.json()).celery_task_id;
  
  // Poll both tasks
  const [tripoResult, stabilityResult] = await Promise.all([
    pollStatus(tripoTaskId, 'tripoai'),
    pollStatus(stabilityTaskId, 'openai')
  ]);
  
  return {
    tripo: tripoResult.asset_url,
    stability: stabilityResult.asset_url
  };
};
```

### Search and Recolor Implementation

```javascript
// Advanced object recoloring with automatic segmentation
const recolorObject = async (imageUrl, taskId, objectDescription, newColors) => {
  const response = await fetch('/generation/search-and-recolor', {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${session.access_token}`,
      'X-API-Key': 'your-api-key'
    },
    body: JSON.stringify({
      task_id: `${taskId}-recolor`,
      provider: "stability",
      input_image_asset_url: imageUrl,
      prompt: `${objectDescription} with ${newColors}, maintaining the same pose and expression`,
      select_prompt: objectDescription,
      negative_prompt: "blurry, low quality, distorted",
      grow_mask: 3,
      output_format: "png",
      style_preset: "photographic"
    })
  });
  
  const { celery_task_id } = await response.json();
  return await pollStatus(celery_task_id, 'openai');
};

// Example usage: Recolor a car from red to blue
const result = await recolorObject(
  'https://project.supabase.co/storage/v1/object/public/bucket/red-car.png',
  'task-car-recolor-123',
  'car',
  'bright blue metallic paint'
);

// Example usage: Change shirt color from white to green
const shirtResult = await recolorObject(
  'https://project.supabase.co/storage/v1/object/public/bucket/person.png',
  'task-shirt-recolor-456', 
  'shirt',
  'forest green fabric'
);
```

---

## Response Codes

| Code | Meaning | Description |
|------|---------|-------------|
| `202` | Accepted | Task initiated successfully, use `celery_task_id` to poll |
| `400` | Bad Request | Invalid request format, parameters, or unsupported provider |
| `404` | Not Found | Task not found or still pending |
| `500` | Internal Error | Server error or AI service failure |

---

## Provider-Specific Notes

### OpenAI
- **Strengths**: High-quality image generation, reliable service
- **Limitations**: Limited style control, higher cost
- **Best for**: General image generation, professional quality

### Stability AI  
- **Strengths**: Fine-grained control, multiple output formats, 3D model generation, automatic object segmentation and recoloring
- **Limitations**: More complex parameter tuning
- **Best for**: Artistic styles, technical control, 3D models, precise object recoloring without manual masks

### Recraft
- **Strengths**: Consistent brand styles, custom style creation
- **Limitations**: Newer service, fewer model options
- **Best for**: Brand-consistent imagery, illustration styles

### Tripo AI
- **Strengths**: Specialized 3D generation, multiview support, model refinement
- **Limitations**: 3D models only, longer processing times
- **Best for**: High-quality 3D models, professional 3D workflows

### Flux
- **Strengths**: High-quality image transformations, advanced context understanding
- **Limitations**: Image-to-image only, no text-to-image support
- **Best for**: Professional image editing, context-aware transformations

---

## Tips for Frontend Integration

### 1. **Provider Selection Strategy**
```javascript
const selectProvider = (operation, requirements) => {
  if (operation === '3d-model') {
    return requirements.multiview ? 'tripo' : 'stability';
  }
  
  if (operation === 'image-generation') {
    if (requirements.style === 'professional') return 'openai';
    if (requirements.style === 'artistic') return 'stability';
    if (requirements.brand === 'consistent') return 'recraft';
  }
  
  return 'openai'; // Default fallback
};
```

### 2. **Polling Strategy with Provider Awareness**
```javascript
const pollWithBackoff = async (celeryTaskId, provider, maxAttempts = 30) => {
  const service = provider === 'tripo' ? 'tripoai' : 'openai';
  
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const response = await fetch(`/tasks/${celeryTaskId}/status?service=${service}`);
    const status = await response.json();
    
    if (status.status === 'complete') return status;
    if (status.status === 'failed') throw new Error(status.error);
    
    // Provider-specific delays
    const baseDelay = provider === 'tripo' ? 3000 : 1000; // Tripo takes longer
    const delay = attempt < 3 ? Math.pow(2, attempt) * baseDelay : baseDelay * 5;
    await new Promise(resolve => setTimeout(resolve, delay));
  }
  throw new Error('Polling timeout');
};
```

### 3. **Error Handling with Provider Context**
```javascript
try {
  const result = await generateWithProvider(taskId, prompt, provider);
  updateUI(result.asset_url);
} catch (error) {
  if (error.message.includes('Unsupported provider')) {
    showError(`${provider} doesn't support this operation. Try a different provider.`);
  } else if (error.message.includes('timeout')) {
    showError(`${provider} is taking longer than expected. Please try again.`);
  } else {
    showError(`${provider} generation failed: ${error.message}`);
  }
}
```

### 4. **Progress Indication by Provider**
- **OpenAI**: 10-30 seconds for images
- **Stability AI**: 15-45 seconds for images, 60-180 seconds for 3D models
- **Recraft**: 10-30 seconds for images
- **Tripo AI**: 60-300 seconds for 3D models (longer for multiview)

---

This updated API provides a comprehensive multi-provider pipeline for AI-powered content generation with unified parameter handling and robust provider selection. The new architecture ensures flexibility while maintaining backward compatibility and consistent response formats across all providers. 