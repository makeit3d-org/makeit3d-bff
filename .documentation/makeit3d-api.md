# MakeIt3D BFF API Developer Guide

**Version:** v1.0.0  
**Base URL:** `https://api.makeit3d.io`

## Index

1. [Overview](#overview)
2. [What's New in v3.0](#-whats-new-in-v30)
   - [Server-Managed Task IDs](#server-managed-task-ids)
   - [Simplified Request Format](#simplified-request-format)
   - [Enhanced Status Polling](#enhanced-status-polling)
3. [Core API Principles](#core-api-principles)
   - [Provider Selection](#1-provider-selection)
   - [Server-Generated Task IDs](#2-server-generated-task-ids)
   - [Asset Upload First](#3-asset-upload-first)
   - [Asynchronous Processing](#4-asynchronous-processing)
   - [Automatic Asset Management](#5-automatic-asset-management)
   - [Database Integration](#6-database-integration)
4. [Authentication](#authentication)
   - [Getting API Keys](#getting-api-keys)
   - [Auth Error Responses](#auth-error-responses)
   - [Test API Key](#test-api-key)
5. [Generation Endpoints](#generation-endpoints)
   - [🎨 Image-to-Image Generation](#-image-to-image-generation)
   - [🔶 Text-to-Image Generation](#-text-to-image-generation)
   - [🔶 Text-to-Model Generation](#-text-to-model-generation)
   - [📷 Image-to-Model Generation](#-image-to-model-generation)
   - [✏️ Sketch-to-Image Generation](#️-sketch-to-image-generation)
   - [🖼️ Background Removal](#️-background-removal)
   - [🎨 Search and Recolor](#-search-and-recolor)
   - [📈 Image Upscaling](#-image-upscaling)
   - [📉 Image Downscaling](#-image-downscaling)
   - [🔧 Model Refinement](#-model-refinement)
6. [Status Polling](#status-polling)
   - [📊 Check Task Status](#-check-task-status)
7. [Implementation Examples](#implementation-examples)
   - [Multi-Provider Image Generation](#multi-provider-image-generation)
   - [Background Removal with Fallback](#background-removal-with-fallback)
   - [Complete Workflow Example](#complete-workflow-example)
8. [Response Codes](#response-codes)
9. [Provider-Specific Notes](#provider-specific-notes)
10. [Tips for Frontend Integration](#tips-for-frontend-integration)

---

## Overview

The MakeIt3D Backend-For-Frontend (BFF) API serves as an intermediary between your application and multiple AI services. It now supports **5 AI providers** across **10 endpoints** with **server-managed task IDs**:

- **🎨 2D Image Generation** via OpenAI, Stability AI, Recraft, and Flux
- **🔶 3D Model Generation** via Tripo AI and Stability AI  
- **✏️ Sketch Processing** via Stability AI
- **🖼️ Background Removal** via Stability AI and Recraft
- **🎨 Object Recoloring** via Stability AI's Search and Recolor
- **📈 Image Upscaling** via Stability AI and Recraft AI
- **📉 Image Downscaling** via basic image processing
- **🔧 Model Refinement** via Tripo AI
- **📦 Asset Management** with Supabase Storage integration
- **⚡ Asynchronous Processing** with real-time status updates

## 🆕 What's New in v3.0

### Server-Managed Task IDs
**BREAKING CHANGE**: Clients no longer provide `task_id` in requests. The BFF now generates all task IDs automatically using the format:
```
{operation}-{timestamp}-{uuid8}

Examples:
- "remove-bg-1750625595-193ca577"
- "upscale-1750625602-eb3f0bc8"
- "text-to-image-1750625610-a1b2c3d4"
```

### Simplified Request Format
Request bodies are now cleaner without the `task_id` field:

**Before (v2.0):**
```javascript
{
  "task_id": "client-generated-id-123",  // ❌ No longer required
  "provider": "stability",
  "input_image_asset_url": "https://...",
  "prompt": "Make it blue"
}
```

**Now (v3.0):**
```javascript
{
  "provider": "stability",                // ✅ Still required
  "input_image_asset_url": "https://...", // ✅ Still required
  "prompt": "Make it blue"                // ✅ Still required
}
```

### Enhanced Status Polling
The status endpoint now auto-detects the service type, making the `service` parameter optional:

**Before:**
```javascript
GET /tasks/{task_id}/status?service=stability
```

**Now:**
```javascript
GET /tasks/{task_id}/status  // Auto-detects service type
```

### Multi-Provider Support
Each endpoint supports multiple AI providers with provider-specific parameters:

| Endpoint | OpenAI | Tripo | Stability | Recraft | Flux | Image Processing |
|----------|--------|-------|-----------|---------|------|------------------|
| `/text-to-image` | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ |
| `/image-to-image` | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ |
| `/text-to-model` | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| `/image-to-model` | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| `/sketch-to-image` | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| `/image-inpaint` | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| `/remove-background` | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| `/search-and-recolor` | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| `/upscale` | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| `/downscale` | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| `/refine-model` | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |

## Core API Principles

### 1. Provider Selection
Every generation request must specify which AI provider to use:

```javascript
{
  "provider": "stability",  // Required: "openai", "stability", "recraft", "flux", or "tripo"
  // ... other parameters
}
```

### 2. Server-Generated Task IDs
**The BFF automatically generates unique task IDs** for every request. Clients never provide task IDs.

**Workflow:**
1. Client submits request (no `task_id` field)
2. BFF generates task ID: `{operation}-{timestamp}-{uuid8}`
3. BFF returns the generated task ID
4. Client uses BFF-provided task ID for status polling

### 3. Asset Upload First
All binary inputs (images, sketches, models) must be uploaded to your Supabase Storage **before** calling generation endpoints. Then provide the full Supabase URL to the API.

### 4. Asynchronous Processing
Generation endpoints return a server-generated `task_id` immediately. Use this to poll the status endpoint for real-time updates and final results.

### 5. Automatic Asset Management
The BFF automatically downloads temporary AI results and uploads them to your Supabase Storage, providing you with permanent URLs.

### 6. Database Integration
The BFF updates your Supabase tables with metadata, status, and final asset URLs using the server-generated task IDs.

---

## Authentication

**The API requires an API key for authentication:**

```javascript
headers: {
  'X-API-Key': 'your-api-key',
  'Content-Type': 'application/json'
}
```

### Getting API Keys

API keys are obtained through the registration endpoint for approved applications and stores:

```javascript
// Register for an API key (requires shared secret)
const response = await fetch('https://api.makeit3d.io/auth/register', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    verification_secret: 'your-shared-secret',
    tenant_type: 'shopify', // or 'supabase_app', 'custom', 'development'
    tenant_identifier: 'your-store.myshopify.com',
    tenant_name: 'Your Store Name',
    metadata: {
      store_id: '12345',
      plan: 'basic'
    }
  })
});

const { api_key } = await response.json();
```

### API Key Types

| Tenant Type | Description | Identifier Format |
|-------------|-------------|-------------------|
| `shopify` | Shopify stores | `store-name.myshopify.com` |
| `supabase_app` | Supabase applications | `app-identifier` |
| `custom` | Custom integrations | `custom-identifier` |
| `development` | Development/testing | `dev-identifier` |

### Auth Error Responses

| Code | Response | Description |
|------|----------|-------------|
| `401` | `{"detail": "Missing API key"}` | No X-API-Key header provided |
| `401` | `{"detail": "Invalid or inactive API key"}` | Invalid or deactivated API key |
| `401` | `{"detail": "Invalid verification secret. Access denied."}` | Wrong secret for registration |
| `400` | `{"detail": "Shopify tenant_identifier must be a valid .myshopify.com domain"}` | Invalid Shopify domain format |

### Test API Key

For development and testing, you can use this test API key:
- **Test Key**: `makeit3d_test_sk_dev_001`
- **Tenant**: `dev_001` (development type)

---

## Authentication Endpoints

### 🔐 Register API Key

Register a new API key for your application or store.

**Endpoint:** `POST /auth/register`

**Note:** This endpoint requires a shared verification secret provided by MakeIT3D.

```javascript
{
  "verification_secret": "your-shared-secret",     // Required: Shared secret for verification
  "tenant_type": "shopify",                        // Required: "shopify", "supabase_app", "custom", "development"
  "tenant_identifier": "store.myshopify.com",     // Required: Unique identifier
  "tenant_name": "My Store",                       // Optional: Human readable name
  "metadata": {                                    // Optional: Additional information
    "store_id": "12345",
    "plan": "basic"
  }
}
```

**Response:**
```javascript
{
  "api_key": "makeit3d_live_sk_shopify_abc123def456",
  "tenant_id": "store.myshopify.com",
  "tenant_type": "shopify",
  "message": "API key successfully registered for shopify tenant: store.myshopify.com"
}
```

---

## Generation Endpoints

### 🎨 Image-to-Image Generation

Transform an input image into concept variations using multiple AI providers.

**Endpoint:** `POST /generate/image-to-image`

#### OpenAI Provider
```javascript
{
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
  "provider": "flux",
  "prompt": "A futuristic cityscape at dusk",
  "input_image_asset_url": "https://...",
  
  // Flux-specific parameters:
  "aspect_ratio": "1:1",                      // Optional: "1:1", "16:9", "9:16", "21:9", "2:3", "3:2", "4:5", "5:4"
  "output_format": "png",                     // Optional: "png", "jpeg"
  "safety_tolerance": 2,                      // Optional: 0-6, higher = more permissive
  "prompt_upsampling": false                  // Optional: Enhance prompt automatically
}
```

**Response:**
```javascript
{
  "task_id": "image-to-image-1750625610-a1b2c3d4"  // Server-generated task ID for polling
}
```

---

### 🔶 Text-to-Image Generation

Generate 2D images from text descriptions using multiple AI providers.

**Endpoint:** `POST /generate/text-to-image`

#### OpenAI Provider
```javascript
{
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

**Response:**
```javascript
{
  "task_id": "text-to-image-1750625615-e5f6g7h8"  // Server-generated task ID for polling
}
```

---

### 🔶 Text-to-Model Generation

Generate 3D models from text descriptions using Tripo AI.

**Endpoint:** `POST /generate/text-to-model`

**Note:** This endpoint generates 3D models and only supports Tripo AI.

#### Tripo AI Provider
```javascript
{
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
  "task_id": "text-to-model-1750625620-i9j0k1l2"  // Server-generated task ID for polling
}
```

---

### 📷 Image-to-Model Generation

Generate 3D models from images using Tripo AI or Stability AI.

**Endpoint:** `POST /generate/image-to-model`

#### Tripo AI Provider (Multiview Support)
```javascript
{
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

**Response:**
```javascript
{
  "task_id": "image-to-model-1750625625-m3n4o5p6"  // Server-generated task ID for polling
}
```

---

### ✏️ Sketch-to-Image Generation

Generate 2D images from hand-drawn sketches using Stability AI.

**Endpoint:** `POST /generate/sketch-to-image`

```javascript
{
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

**Response:**
```javascript
{
  "task_id": "sketch-to-image-1750625630-q7r8s9t0"  // Server-generated task ID for polling
}
```

---

### 🖼️ Background Removal

Remove backgrounds from images using Stability AI or Recraft.

**Endpoint:** `POST /generate/remove-background`

#### Stability AI Provider
```javascript
{
  "provider": "stability",                    // Required
  "input_image_asset_url": "https://[project].supabase.co/storage/v1/object/public/bucket/image.png",
  
  // Stability-specific parameters:
  "output_format": "png"                     // Optional: "png" (recommended for transparency)
}
```

#### Recraft Provider
```javascript
{
  "provider": "recraft",                      // Required
  "input_image_asset_url": "https://[project].supabase.co/storage/v1/object/public/bucket/image.png",
  
  // Recraft-specific parameters:
  "response_format": "url"                   // Optional: "url" or "b64_json"
}
```

**Response:**
```javascript
{
  "task_id": "remove-bg-1750625635-u1v2w3x4"  // Server-generated task ID for polling
}
```

---

### 🎨 Search and Recolor

Automatically segment and recolor specific objects in an image using Stability AI.

**Endpoint:** `POST /generate/search-and-recolor`

#### Stability AI Provider
```javascript
{
  "provider": "stability",                    // Always "stability" for this endpoint
  "input_image_asset_url": "https://[project].supabase.co/storage/v1/object/public/bucket/image.png",
  "prompt": "light blue cat with dark blue stripes, maintaining the same pose and expression", // Required: Description of desired recoloring
  "select_prompt": "cat",                     // Required: What object to find and recolor
  
  // Stability Search and Recolor parameters:
  "negative_prompt": "blurry, low quality, distorted, orange, tan, brown", // Optional: What to avoid
  "grow_mask": 3,                            // Optional: 0-20, grows mask edges for smoother transitions (default: 3)
  "seed": 0,                                 // Optional: Reproducibility seed (0 for random)
  "output_format": "png",                    // Optional: "png", "jpeg", "webp" (default: "png")
  "style_preset": "photographic"             // Optional: Style preset
}
```

**Response:**
```javascript
{
  "task_id": "search-recolor-1750625640-y5z6a7b8"  // Server-generated task ID for polling
}
```

---

### 📈 Image Upscaling

Enhance image resolution and quality using AI-powered upscaling.

**Endpoint:** `POST /generate/upscale`

#### Stability AI Provider
```javascript
{
  "provider": "stability",                    // Required: Provider selection
  "input_image_asset_url": "https://[project].supabase.co/storage/v1/object/public/bucket/image.png", // Required: Full Supabase URL
  
  // Stability-specific parameters:
  "model": "fast",                           // Optional: Model selection ("fast" is default and only option)
  "output_format": "png"                     // Optional: "png", "jpeg", "webp" (default: "png")
}
```

#### Recraft Provider
```javascript
{
  "provider": "recraft",                     // Required: Provider selection
  "input_image_asset_url": "https://[project].supabase.co/storage/v1/object/public/bucket/image.png", // Required: Full Supabase URL
  
  // Recraft-specific parameters:
  "model": "crisp",                          // Optional: Model selection ("crisp" is default and only option)
  "response_format": "url"                   // Optional: "url" or "b64_json" (default: "url")
}
```

**Response:**
```javascript
{
  "task_id": "upscale-1750625645-c9d0e1f2"  // Server-generated task ID for polling
}
```

---

### 📉 Image Downscaling

Reduce image file sizes to meet specific constraints while maintaining quality.

**Endpoint:** `POST /generate/downscale`

**Note:** This endpoint uses basic image processing (Pillow) rather than AI providers for fast, reliable file size reduction.

```javascript
{
  "input_image_asset_url": "https://[project].supabase.co/storage/v1/object/public/bucket/image.png", // Required: Full Supabase URL
  "max_size_mb": 0.5,                                   // Required: Target maximum file size in MB (0.1-20.0)
  "aspect_ratio_mode": "original",                      // Required: "original" or "square"
  "output_format": "original"                           // Optional: "original", "jpeg", "png" (default: "original")
}
```

**Parameters:**
- **`max_size_mb`**: Target maximum file size in megabytes (0.1 to 20.0 MB range)
- **`aspect_ratio_mode`**: 
  - `"original"`: Maintains original image proportions
  - `"square"`: Adds white padding to create a square image
- **`output_format`**: 
  - `"original"`: Keeps the same format as input
  - `"jpeg"`: Converts to JPEG (good for photos, smaller files)
  - `"png"`: Converts to PNG (good for graphics with transparency)

**Response:**
```javascript
{
  "task_id": "downscale-1750625650-g3h4i5j6"  // Server-generated task ID for polling
}
```

---

### 🔧 Model Refinement

Refine and improve existing 3D models using Tripo AI.

**Endpoint:** `POST /generate/refine-model`

```javascript
{
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

**Response:**
```javascript
{
  "task_id": "refine-model-1750625655-k7l8m9n0"  // Server-generated task ID for polling
}
```

---

## Status Polling

### 📊 Check Task Status

Poll for real-time updates on your generation tasks using the server-generated task ID.

**Endpoint:** `GET /tasks/{task_id}/status`

**Parameters:**
- `task_id`: The server-generated ID returned from generation endpoints
- `service`: Optional service hint (auto-detected if not provided)

**Example:**
```javascript
const response = await fetch(`https://api.makeit3d.io/tasks/remove-bg-1750625635-u1v2w3x4/status`, {
  headers: {
    'X-API-Key': 'your-api-key'
  }
});
```

**Response States:**

#### ⏳ Pending
```javascript
{
  "task_id": "remove-bg-1750625635-u1v2w3x4",
  "status": "pending"
}
```

#### 🔄 Processing
```javascript
{
  "task_id": "remove-bg-1750625635-u1v2w3x4", 
  "status": "processing",
  "progress": 75
}
```

#### ✅ Complete
```javascript
{
  "task_id": "remove-bg-1750625635-u1v2w3x4",
  "status": "complete",
  "asset_url": "https://[project].supabase.co/storage/v1/object/sign/images/remove-bg-1750625635-u1v2w3x4/result.png?token=..."
}
```

#### ❌ Failed
```javascript
{
  "task_id": "remove-bg-1750625635-u1v2w3x4",
  "status": "failed",
  "error": "AI service timed out"
}
```

---

## Implementation Examples

### Multi-Provider Image Generation

```javascript
const generateImage = async (prompt, provider = 'openai') => {
  // 1. Submit generation request (no task_id needed)
  const response = await fetch('https://api.makeit3d.io/generate/text-to-image', {
    method: 'POST',
    headers: {
      'X-API-Key': 'your-api-key',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      provider: provider,
      prompt: prompt,
      style: provider === 'openai' ? 'vivid' : undefined,
      style_preset: provider === 'stability' ? 'photographic' : undefined
    })
  });
  
  const { task_id } = await response.json();
  console.log(`Task submitted with ID: ${task_id}`);
  
  // 2. Poll for completion using server-generated task ID
  return await pollForCompletion(task_id);
};

const pollForCompletion = async (taskId, maxAttempts = 30) => {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const response = await fetch(`https://api.makeit3d.io/tasks/${taskId}/status`); // No service parameter needed
    const status = await response.json();
    
    if (status.status === 'complete') return status.asset_url;
    if (status.status === 'failed') throw new Error(status.error);
    
    // Progressive delay
    const delay = Math.min(1000 * Math.pow(1.5, attempt), 5000);
    await new Promise(resolve => setTimeout(resolve, delay));
  }
  throw new Error('Polling timeout');
};
```

### Background Removal with Fallback

```javascript
const removeBackground = async (imageUrl) => {
  const providers = ['stability', 'recraft'];
  
  for (const provider of providers) {
    try {
      const response = await fetch('https://api.makeit3d.io/generate/remove-background', {
        method: 'POST',
        headers: {
          'X-API-Key': 'your-api-key',
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          provider: provider,
          input_image_asset_url: imageUrl,
          output_format: 'png'
        })
      });
      
      const { task_id } = await response.json();
      const result = await pollForCompletion(task_id);
      
      console.log(`✅ Background removed using ${provider}`);
      return result;
      
    } catch (error) {
      console.log(`❌ ${provider} failed: ${error.message}`);
      if (provider === providers[providers.length - 1]) {
        throw new Error('All providers failed');
      }
    }
  }
};
```

### Complete Workflow Example

```javascript
const processImageWorkflow = async (originalImageUrl) => {
  try {
    // Step 1: Remove background
    console.log('🔄 Removing background...');
    const bgRemovedResponse = await fetch('https://api.makeit3d.io/generate/remove-background', {
      method: 'POST',
      headers: {
        'X-API-Key': 'your-api-key',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        provider: 'stability',
        input_image_asset_url: originalImageUrl
      })
    });
    
    const { task_id: bgTaskId } = await bgRemovedResponse.json();
    const bgRemovedUrl = await pollForCompletion(bgTaskId);
    console.log(`✅ Background removed: ${bgTaskId}`);
    
    // Step 2: Upscale the result
    console.log('🔄 Upscaling image...');
    const upscaleResponse = await fetch('https://api.makeit3d.io/generate/upscale', {
      method: 'POST',
      headers: {
        'X-API-Key': 'your-api-key',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        provider: 'stability',
        input_image_asset_url: bgRemovedUrl
      })
    });
    
    const { task_id: upscaleTaskId } = await upscaleResponse.json();
    const upscaledUrl = await pollForCompletion(upscaleTaskId);
    console.log(`✅ Image upscaled: ${upscaleTaskId}`);
    
    // Step 3: Optimize file size
    console.log('🔄 Optimizing file size...');
    const downscaleResponse = await fetch('https://api.makeit3d.io/generate/downscale', {
      method: 'POST',
      headers: {
        'X-API-Key': 'your-api-key',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        input_image_asset_url: upscaledUrl,
        max_size_mb: 0.5,
        aspect_ratio_mode: 'original',
        output_format: 'png'
      })
    });
    
    const { task_id: downscaleTaskId } = await downscaleResponse.json();
    const finalUrl = await pollForCompletion(downscaleTaskId);
    console.log(`✅ File optimized: ${downscaleTaskId}`);
    
    return {
      original: originalImageUrl,
      backgroundRemoved: bgRemovedUrl,
      upscaled: upscaledUrl,
      final: finalUrl
    };
    
  } catch (error) {
    console.error('❌ Workflow failed:', error.message);
    throw error;
  }
};
```

---

## Response Codes

| Code | Meaning | Description |
|------|---------|-------------|
| `200` | OK | Task initiated successfully, use returned `task_id` to poll |
| `400` | Bad Request | Invalid request format, parameters, or unsupported provider |
| `401` | Unauthorized | Invalid or missing API key |
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

### 1. **Server-Generated Task ID Handling**
```javascript
// Always use the task ID returned by the server
const submitJob = async (requestData) => {
  const response = await fetch('/generate/text-to-image', {
    method: 'POST',
    headers: {
      'X-API-Key': 'your-api-key',
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(requestData) // No task_id field needed
  });
  
  const { task_id } = await response.json(); // Use server-generated ID
  return task_id;
};
```

### 2. **Simplified Polling Strategy**
```javascript
const pollTaskStatus = async (taskId, maxAttempts = 30) => {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const response = await fetch(`/tasks/${taskId}/status`); // No service parameter needed
    const status = await response.json();
    
    if (status.status === 'complete') return status;
    if (status.status === 'failed') throw new Error(status.error);
    
    // Progressive delay
    const delay = Math.min(1000 * Math.pow(1.5, attempt), 5000);
    await new Promise(resolve => setTimeout(resolve, delay));
  }
  throw new Error('Polling timeout');
};
```

### 3. **Provider Selection Strategy**
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

### 4. **Progress Indication by Provider**
- **OpenAI**: 10-30 seconds for images
- **Stability AI**: 15-45 seconds for images, 60-180 seconds for 3D models, 10-20 seconds for upscaling
- **Recraft**: 10-30 seconds for images, 15-25 seconds for upscaling
- **Tripo AI**: 60-300 seconds for 3D models (longer for multiview)
- **Image Processing (Downscale)**: 1-3 seconds for basic processing

---

This updated API provides a streamlined experience with server-managed task IDs, simplified request formats, and enhanced auto-detection capabilities. The new architecture ensures better reliability and consistency while maintaining full provider flexibility and robust error handling. 