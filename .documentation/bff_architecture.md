# BFF (Backend-for-Frontend) Architecture - Refactored

## Overview

This document describes the refactored architecture for the Backend-for-Frontend (BFF) service for the MakeIt3D app. The BFF acts as an intermediary between the mobile frontend and external AI services (Tripo AI, OpenAI). Its primary responsibilities are to securely manage API keys, abstract the complexities of external APIs, and provide a tailored API for the frontend client.

**Key Architectural Changes:**
1.  **Client-Managed `task_id`**: The client generates a unique `task_id` for each overall generation job/workspace item.
2.  **Supabase for Inputs**: The client uploads input assets (images, sketches) to its Supabase Storage and provides the Supabase URL of the asset to the BFF.
3.  **BFF Fetches Inputs**: The BFF fetches these input assets from the provided Supabase URLs.
4.  **BFF Manages Outputs to Supabase**: The BFF takes outputs from AI services (downloading from temporary AI URLs if necessary), uploads them to a configurable client Supabase Storage bucket (using a path structure like `{asset_type_plural}/{task_id}/{filename}`), and then creates/updates metadata records (including `status` and the final `asset_url`) in dedicated Supabase tables (`images`, `models`).
5.  **User Authentication & Credits**: All requests require valid Supabase Auth JWT tokens. The BFF validates user sessions and manages credit deduction before AI operations using the integrated credit system (`user_credits`, `credit_transactions`, `operation_costs` tables).
6.  **Polling & Status**: The client polls `GET /tasks/{task_id}/status?service={service}` for real-time AI step status. The BFF provides the AI service's status and, upon completion of an AI step and BFF processing, the Supabase URL of the generated asset. The client also relies on querying the dedicated Supabase tables (`images`, `models`) for persisted state and asset locations.

The service is built with Python (FastAPI), containerized with Docker, and designed for deployment on platforms like Railway.

## API Endpoints (Multi-Provider Refactored)

(Refer to `.documentation/makeit3d-api.md` for detailed OpenAPI v1.1.0 specification of request/response schemas.)

### API Provider Mapping

| BFF Endpoint | Supported Providers | External API Endpoints |
|--------------|-------------------|----------------------|
| `/image-to-image` | OpenAI, Stability, Recraft | OpenAI: Image Edit/Generate<br/>Stability: Structure Control<br/>Recraft: Image-to-Image |
| `/text-to-image` | OpenAI, Stability, Recraft | OpenAI: Image Generation<br/>Stability: Image Core<br/>Recraft: Text-to-Image |
| `/text-to-model` | Tripo | Tripo: Text-to-Model |
| `/image-to-model` | Tripo, Stability | Tripo: Image to 3D, Stability: Image to 3D |
| `/sketch-to-image` | Stability | Stability: Sketch Control |
| `/refine-model` | Tripo | Tripo: Refine Model |
| `/remove-background` | Stability, Recraft | Stability: Remove Background, Recraft: Remove Background |
| `/search-and-recolor` | Stability | Stability: Search and Recolor |
| `/tasks/{id}/status` | Tripo, OpenAI | Tripo: Task Status<br/>OpenAI: Direct Response |
| `/image-inpaint` | Recraft | Recraft: Image Inpainting with Mask |

### `POST /generate/image-to-image`

- **Summary:** Generates 2D images from input image using specified AI provider.
- **Supported Providers:** `openai`, `stability`, `recraft`
- **Request:**
    - **Content-Type:** `application/json`
    - **Body:** Includes `task_id`, `provider`, `input_image_asset_url`, `prompt`, and provider-specific parameters.
- **Provider-Specific Parameters:**
    - **OpenAI:** `style`, `n`, `background`
    - **Stability:** `style_preset`, `fidelity`, `negative_prompt`, `output_format`, `seed`
    - **Recraft:** `style`, `substyle`, `strength`, `negative_prompt`, `n`, `model`, `response_format`

### `POST /generate/text-to-image`

- **Summary:** Generates 2D images from text using specified AI provider.
- **Supported Providers:** `openai`, `stability`, `recraft`
- **Request:**
    - **Content-Type:** `application/json`
    - **Body:** Includes `task_id`, `provider`, `prompt`, and provider-specific parameters.
- **Provider-Specific Parameters:**
    - **OpenAI:** `style`, `n`, `size`, `quality`
    - **Stability:** `style_preset`, `aspect_ratio`, `negative_prompt`, `output_format`, `seed`
    - **Recraft:** `style`, `substyle`, `n`, `model`, `response_format`, `size`

### `POST /generate/text-to-model`

- **Summary:** Generates 3D models from text using Tripo AI.
- **Supported Providers:** `tripo` (only)
- **Request:**
    - **Content-Type:** `application/json`
    - **Body:** Includes `task_id`, `provider`, `prompt`, and Tripo-specific parameters.
- **Provider-Specific Parameters:**
    - **Tripo:** `style`, `texture`, `pbr`, `model_version`, `face_limit`, `auto_size`, `texture_quality`

### `POST /generate/image-to-model`

- **Summary:** Generates 3D models from image(s) using specified AI provider.
- **Supported Providers:** `tripo`, `stability`
- **Request:**
    - **Content-Type:** `application/json`
    - **Body:** Includes `task_id`, `provider`, `input_image_asset_urls`, and provider-specific parameters.
- **Provider-Specific Parameters:**
    - **Tripo:** `prompt`, `style`, `texture`, `pbr`, `model_version`, `face_limit`, `auto_size`, `texture_quality`, `orientation`
    - **Stability:** `texture_resolution`, `remesh`, `foreground_ratio`, `target_type`, `target_count`, `guidance_scale`, `seed`

### `POST /generate/sketch-to-image`

- **Summary:** Generates 2D images from sketch using Stability AI.
- **Supported Providers:** `stability` (only)
- **Request:**
    - **Content-Type:** `application/json`
    - **Body:** Includes `task_id`, `input_sketch_asset_url`, `prompt`, and Stability-specific parameters.
- **Parameters:** `control_strength`, `style_preset`, `negative_prompt`, `output_format`, `seed`

### `POST /generate/refine-model`

- **Summary:** Refines existing 3D model using Tripo AI.
- **Supported Providers:** `tripo` (only)
- **Request:**
    - **Content-Type:** `application/json`
    - **Body:** Includes `task_id`, `input_model_asset_url`, `prompt`, and Tripo-specific parameters.
- **Parameters:** `draft_model_task_id`, `texture`, `pbr`, `model_version`, `face_limit`, `auto_size`, `texture_quality`

### `POST /generate/remove-background`

- **Summary:** Removes background from image using specified AI provider.
- **Supported Providers:** `stability`, `recraft`
- **Request:**
    - **Content-Type:** `application/json`
    - **Body:** Includes `task_id`, `provider`, `input_image_asset_url`, and provider-specific parameters.
- **Provider-Specific Parameters:**
    - **Stability:** `output_format`
    - **Recraft:** `response_format`

### `POST /generate/search-and-recolor`

- **Summary:** Automatically segments and recolors specific objects in an image using Stability AI.
- **Supported Providers:** `stability` (only)
- **Request:**
    - **Content-Type:** `application/json`
    - **Body:** Includes `task_id`, `input_image_asset_url`, `prompt`, `select_prompt`, and Stability-specific parameters.
- **Parameters:** `select_prompt`, `negative_prompt`, `grow_mask`, `seed`, `output_format`, `style_preset`

### `GET /tasks/{celery_task_id}/status?service={service}`

- **Summary:** Retrieves real-time status of a specific AI generation Celery task.
- **Supported Services:** `openai`, `tripoai`, `stability`, `recraft`
- **Request:** Path param `celery_task_id`, query param `service`.
- **Response:** Normalized structure with `task_id`, `status`, `asset_url`, `error`, `progress`.

## Technology Stack

| Tool                | Purpose                                                         |
|---------------------|-----------------------------------------------------------------|
| Python 3.x          | Core backend language                                          |
| FastAPI             | Web API framework                                               |
| httpx               | Asynchronous HTTP client for external APIs                      |
| Pydantic            | Data validation and settings management                         |
| **Supabase Python Client** | For interacting with Supabase Storage and Database             |
| **Celery**          | Asynchronous task queue for AI generation jobs                  |
| **Redis**           | Message broker for Celery and caching                          |
| Docker              | Containerization for deployment                                 |
| Railway             | Cloud deployment platform (or similar)                           |

## Credit System & User Management

### Authentication Requirements
- **JWT Validation**: All generation endpoints require valid Supabase Auth JWT tokens
- **User Context**: User ID extracted from JWT token for credit management and asset ownership
- **Session Management**: Token validation ensures secure user-scoped operations

### Credit Workflow
1. **Pre-Operation Check**: Before any AI generation, BFF checks user's available credits
2. **Cost Lookup**: Operation cost retrieved from `operation_costs` table using obfuscated operation keys
3. **Credit Deduction**: If sufficient credits available, amount is deducted atomically 
4. **Transaction Logging**: All credit movements logged in `credit_transactions` for audit trail
5. **AI Processing**: Only proceeds if credits successfully deducted
6. **Error Handling**: Credits refunded if AI operation fails

### Credit System Tables
- **`user_credits`**: Current balance, subscription tier, lifetime stats
- **`credit_transactions`**: Complete audit trail of all credit movements
- **`operation_costs`**: Configurable pricing with obfuscated provider names (provider_a, provider_b)

### Operation Keys (Obfuscated)
For security, operation keys in database use generic names:
- `text_to_image_core` (instead of `text_to_image_stability_core`)
- `image_to_3d` (instead of `image_to_3d_stability`)
- `text_to_image_v3` (instead of `text_to_image_recraft_v3`)

*Real provider mapping maintained in separate confidential documentation*

## Security & Provider Obfuscation

### Competitive Protection Strategy
To protect competitive advantage from external consultants and contractors:

1. **Database Obfuscation**: All provider references in database use generic names
   - `provider_a` = Stability AI  
   - `provider_b` = Recraft
   - Tripo operations completely removed from consultant-visible database

2. **Operation Key Sanitization**: All operation keys use generic names
   - Removes provider identifiers from all database-visible keys
   - Maintains functionality while hiding implementation details

3. **Documentation Separation**: 
   - Public documentation shows generic providers
   - Confidential documentation contains complete restoration instructions
   - Step-by-step SQL commands for reverting obfuscation when needed

4. **Code Protection**: AI client modules remain in BFF codebase (not accessible to frontend consultant)

This strategy ensures external frontend developers cannot identify actual AI providers or discover proprietary 3D generation capabilities while maintaining full system functionality.

## Rate Limiting

(No changes from previous version, still relevant.)

## Core Logic & Considerations (Refactored)

1.  **API Key Management:** Unchanged (secure environment variables).
2.  **External API Interaction (`/app/ai_clients`):**
    *   Clients (`tripo_client.py`, `openai_client.py`) accept prepared data (e.g., image bytes fetched by BFF) or parameters.
    *   They return raw AI service responses or temporary output URLs to the BFF's core logic.
    *   They do **not** interact directly with Supabase.
3.  **Supabase Interaction (New Module: `app/supabase_handler.py`):**
    *   **Storage:**
        *   Fetches input assets from client-provided Supabase URLs.
        *   Uploads generated assets (concepts, models) to a configurable Supabase Storage bucket using the path structure: `[BUCKET_NAME]/{asset_type_plural}/{task_id}/{filename}` (e.g., `generated_assets_bucket/images/task_abc123/0.png`).
    *   **Database:**
        *   Creates and updates records in the `images` and `models` Supabase tables.
        *   Manages the `status` field in these tables using simplified values: 'pending', 'processing', 'complete', 'failed'.
        *   Stores the final Supabase Storage `asset_url` in these tables.
4.  **Asynchronous Operations:** All routes involving external AI calls and Supabase I/O will be `async`.
5.  **File Handling (within BFF for AI outputs):**
    *   Receiving temporary output URLs/data from Tripo AI/OpenAI.
    *   Downloading/processing this data before uploading to Supabase Storage via `supabase_handler`.
6.  **Task Status Tracking & Flow:**
    *   Client initiates with `task_id` and input Supabase URL(s).
    *   BFF generation endpoint:
        1. Fetches input assets.
        2. Creates initial record in `images` or `models` table (status 'pending').
        3. Dispatches Celery task.
        4. Updates DB record with `celery_task_id` and status 'processing'.
        5. Returns `celery_task_id` to client.
    *   Client polls `GET /tasks/{celery_task_id}/status?service={service}` using the `celery_task_id`.
    *   **OpenAI Flow (within Celery task `generate_openai_image_task`):**
        1.  Celery task keeps DB record status as 'processing'.
        2.  Calls OpenAI.
        3.  Downloads/processes images.
        4.  Uploads images to Supabase Storage (via `supabase_handler`).
        5.  Updates its DB record in `images` with final `asset_url`(s) and status 'complete' or 'failed'.
    *   **TripoAI Flow (combination of Celery task and Status Endpoint logic):**
        1.  Celery task keeps DB record status as 'processing'.
        2.  Calls Tripo AI to initiate job, gets `ai_provider_task_id` (Tripo's internal ID).
        3.  Updates its DB record with `ai_provider_task_id` and status remains 'processing'.
        4.  The `/tasks/{celery_task_id}/status` endpoint, when polled by client:
            *   Retrieves `ai_provider_task_id` and `model_db_id` from the Celery task's result.
            *   Polls Tripo AI service using `ai_provider_task_id`.
            *   If Tripo AI job is complete:
                *   Downloads asset from Tripo's temporary URL.
                *   Uploads asset to Supabase Storage (via `supabase_handler`).
                *   Updates the `models` record (using `model_db_id`) with final `asset_url` and status 'complete'.
    *   The `/tasks/{celery_task_id}/status` response reflects the Celery task status, or the derived status from Tripo polling, and provides the final Supabase URL for the step once the BFF completes its processing (either in Celery task or status endpoint).
7.  **Prompt Customization:** Unchanged.
8.  **Configuration:**
    *   BFF needs Supabase URL, service key, JWT secret for token validation (all from environment variables)
    *   Generated assets bucket name, and names of `images` and `models` tables
    *   Anon key: Retrieved from Supabase Dashboard -> Settings -> API -> Project API keys

## Deployment
(No significant changes from previous version, Supabase credentials become more critical.)

---

### BFF Directory Structure (Python FastAPI) - Updated

```
/makeit3d-bff
|-- Dockerfile
|-- docker-compose.yml
|-- requirements.txt           # FastAPI, Uvicorn, httpx, Pydantic, supabase-py, celery, redis
|-- README.md
|-- /app
|   |-- __init__.py
|   |-- main.py                # Uvicorn entry point: `uvicorn app.main:app --reload`
|   |-- api.py                 # FastAPI app instantiation and router includes
|   |-- celery_worker.py       # Celery app definition and task imports
|   |-- /routers
|   |   |-- __init__.py
|   |   |-- generation.py
|   |   |-- task_status.py     # For /tasks/{celery_task_id}/status endpoint
|   |   |-- credits.py         # NEW: Credit management endpoints
|   |-- /schemas
|   |   |-- __init__.py
|   |   |-- generation_schemas.py
|   |   |-- credit_schemas.py   # NEW: Credit system schemas
|   |-- config.py              # App settings, API keys, Supabase config
|   |-- /ai_clients
|   |   |-- __init__.py
|   |   |-- tripo_client.py
|   |   |-- openai_client.py
|   |   |-- stability_client.py # AI client modules
|   |   |-- recraft_client.py
|   |-- supabase_handler.py    # Supabase interactions (Storage, DB, Credits)
|   |-- auth.py                # NEW: JWT validation and user context
|   |-- sync_state.py          # For sync_mode (if kept)
|   |-- limiter.py             # Rate limiter setup
|   |-- /tasks                 # Celery tasks
|   |   |-- __init__.py
|   |   |-- generation_tasks.py
|   |-- /tests
|   |   |-- __init__.py
|   |   |-- /routers
|   |   |-- /ai_clients
|   |   |-- /tasks
|   |   |-- test_supabase_handler.py
|-- .env
```

---

### External API Mapping (Multi-Provider)

| BFF Endpoint | Provider | External API Endpoint | BFF Output Handling |
|--------------|----------|----------------------|-------------------|
| **Image-to-Image** | OpenAI | Image Edit/Generate | Upload to `images` table |
| | Stability | Structure Control (`/v2beta/stable-image/control/style`) | Upload to `images` table |
| | Recraft | Image-to-Image (`/v1/images/imageToImage`) | Upload to `images` table |
| **Text-to-Image** | OpenAI | Image Generation | Upload to `images` table |
| | Stability | Image Core (`/v2beta/stable-image/generate/core`) | Upload to `images` table |
| | Recraft | Text-to-Image (`/v1/images/textToImage`) | Upload to `images` table |
| **Text-to-Model** | Tripo | Text-to-Model | Upload to `models` table |
| **Image-to-Model** | Tripo | Image to 3D | Upload to `models` table |
| | Stability | Image to 3D | Upload to `models` table |
| **Sketch-to-Image** | Stability | Sketch Control (`/v2beta/stable-image/control/sketch`) | Upload to `images` table |
| **Refine-Model** | Tripo | Refine Model | Upload to `models` table |
| **Remove-Background** | Stability | Remove Background (`/v2beta/stable-image/edit/remove-background`) | Upload to `images` table |
| | Recraft | Remove Background (`/v1/images/removeBackground`) | Upload to `images` table |
| **Search-and-Recolor** | Stability | Search and Recolor (`/v2beta/stable-image/edit/search-and-recolor`) | Upload to `images` table |
| **Image-Inpaint** | Recraft | Image Inpainting with Mask | Upload to `images` table |

**Status Polling:** `GET /tasks/{task_id}/status?service={provider}` calls respective AI service status endpoints for async operations (Tripo) or returns direct results for sync operations (OpenAI, Stability, Recraft).

## Implementation Tasks
(Refer to `.documentation/API_REFACTOR.md` for the comprehensive checklist which details these changes.)

## MVP Implementation Checklist

### 🔐 Authentication
- [ ] **JWT Middleware**: Implement JWT validation middleware for all generation endpoints
- [ ] **User Context**: Extract user_id from JWT tokens for database operations
- [ ] **Supabase Auth Integration**: Configure Supabase client with service key for backend operations
- [ ] **Error Handling**: Return proper 401/403 responses for invalid/missing tokens
- [ ] **User Initialization**: Auto-create user_credits record on first authenticated request

### 💳 Credit System
- [ ] **Credit Checking**: Implement pre-operation credit validation in all generation endpoints
- [ ] **Atomic Deduction**: Use database transactions for credit deduction + operation logging
- [ ] **Cost Configuration**: Ensure operation_costs table populated with current obfuscated pricing
- [ ] **Transaction Logging**: Log all credit movements with operation context in credit_transactions
- [ ] **Error Recovery**: Implement credit refund on AI operation failures
- [ ] **Credit Endpoints**: Add `/api/credits/balance` and `/api/credits/history` endpoints
- [ ] **Insufficient Credit Handling**: Return specific error codes when credits insufficient

### 🧪 Testing
- [ ] **Credit Integration Tests**: Add credit deduction verification to existing AI endpoint tests
- [ ] **Authentication Tests**: Test all endpoints with valid/invalid JWT tokens
- [ ] **Database Verification**: Add checks that images/models records created correctly
- [ ] **User Isolation**: Verify users can only access their own assets
- [ ] **Transaction Audit**: Test that all credit movements properly logged
- [ ] **Error Scenarios**: Test credit refunds on AI failures
- [ ] **Load Testing**: Verify credit system performance under concurrent requests

### 🚀 Railway Deployment
- [ ] **Environment Variables**: Configure all Supabase and AI provider credentials
- [ ] **Database Connection**: Ensure Railway can connect to Supabase database
- [ ] **Redis Setup**: Configure Redis service for Celery task queue
- [ ] **Celery Workers**: Deploy Celery worker containers alongside web service
- [ ] **Health Checks**: Add `/health` endpoint for Railway monitoring
- [ ] **Logging Configuration**: Set up structured logging for production debugging
- [ ] **Resource Limits**: Configure appropriate memory/CPU limits for containers
- [ ] **SSL/HTTPS**: Ensure secure connections for all external API calls
- [ ] **Monitoring**: Set up error tracking and performance monitoring
- [ ] **Backup Strategy**: Verify Supabase automated backups enabled

### 📋 Pre-Launch Verification
- [ ] **End-to-End Flow**: Test complete user journey (auth → credit check → AI generation → asset creation)
- [ ] **Rate Limiting**: Verify rate limits prevent abuse while allowing normal usage
- [ ] **Security Audit**: Confirm no sensitive provider information exposed in API responses
- [ ] **Performance Baseline**: Establish response time benchmarks for all endpoints
- [ ] **Error Monitoring**: Ensure all errors properly logged and traceable

### 🎯 Success Criteria
- ✅ All generation endpoints require valid authentication
- ✅ Credits properly deducted before AI operations
- ✅ Complete audit trail of all user operations
- ✅ Secure deployment with proper monitoring
- ✅ Frontend can integrate seamlessly with obfuscated provider system