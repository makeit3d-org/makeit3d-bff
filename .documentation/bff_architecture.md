# BFF (Backend-for-Frontend) Architecture - Refactored

## Overview

This document describes the refactored architecture for the Backend-for-Frontend (BFF) service for the MakeIt3D app. The BFF acts as an intermediary between the mobile frontend and external AI services (Tripo AI, OpenAI). Its primary responsibilities are to securely manage API keys, abstract the complexities of external APIs, and provide a tailored API for the frontend client.

**Key Architectural Changes:**
1.  **Client-Managed `task_id`**: The client generates a unique `task_id` for each overall generation job/workspace item.
2.  **Supabase for Inputs**: The client uploads input assets (images, sketches) to its Supabase Storage and provides the Supabase URL of the asset to the BFF.
3.  **BFF Fetches Inputs**: The BFF fetches these input assets from the provided Supabase URLs.
4.  **BFF Manages Outputs to Supabase**: The BFF takes outputs from AI services (downloading from temporary AI URLs if necessary), uploads them to a configurable client Supabase Storage bucket (using a path structure like `{asset_type_plural}/{task_id}/{filename}`), and then creates/updates metadata records (including `status` and the final `asset_url`) in dedicated Supabase tables (`concept_images`, `models`).
5.  **Polling & Status**: The client polls `GET /tasks/{task_id}/status?service={service}` for real-time AI step status. The BFF provides the AI service's status and, upon completion of an AI step and BFF processing, the Supabase URL of the generated asset. The client also relies on querying the dedicated Supabase tables (`input_assets`, `concept_images`, `models`) for persisted state and asset locations.

The service is built with Python (FastAPI), containerized with Docker, and designed for deployment on platforms like Railway.

## API Endpoints (Refactored)

(Refer to `.documentation/makeit3d-api.md` for detailed OpenAPI v1.1.0 specification of request/response schemas.)

### `POST /generate/image-to-image`

- **Summary (Refactored):** Generates 2D concepts using OpenAI from a user-provided image URL (Supabase).
- **Request (Refactored):**
    - **Content-Type:** `application/json`
    - **Body:** Includes client-generated `task_id`, `prompt`, and `input_image_asset_url` (Supabase URL).
- **Process (Refactored):**
    1.  Receives `task_id`, `prompt`, `input_image_asset_url` (Supabase URL of the input image), and other parameters from the frontend.
    2.  BFF fetches the input image from the provided `input_image_asset_url` using its Supabase Handler.
    3.  Customizes the prompt for OpenAI based on the input style (if any).
    4.  BFF creates an initial record in the `concept_images` Supabase table for this `task_id` with status 'pending'.
    5.  Dispatches a Celery task (e.g., `generate_openai_image_task`) with necessary data (including the DB record ID).
    6.  BFF updates the `concept_images` record with the `celery_task_id` (as `ai_service_task_id`) and status 'processing'.
    7.  Returns a `TaskIdResponse` containing the `celery_task_id` to the frontend.
    8.  The Celery task, upon receiving results from OpenAI (e.g., base64 encoded images):
        *   Decodes and uploads each generated concept image to Supabase Storage (e.g., `[GENERATED_ASSETS_BUCKET_NAME]/concepts/{task_id}/{index}.png`).
        *   Updates the corresponding record(s) in the `concept_images` table with the new Supabase `asset_url`(s) and sets status to 'complete'.
    9.  Frontend polls `GET /tasks/{celery_task_id}/status?service=openai` using the received `celery_task_id` for OpenAI's direct processing status and final asset URLs.

### `POST /generate/text-to-model`

- **Summary (Refactored):** Initiates 3D model generation from text using Tripo AI.
- **Request (Refactored):**
    - **Content-Type:** `application/json`
    - **Body:** Includes client-generated `task_id`, `prompt`, and other Tripo AI parameters.
- **Process (Refactored):**
    1.  Receives `task_id`, `prompt`, and other parameters from the frontend.
    2.  BFF creates an initial record in the `models` Supabase table for this `task_id` with status 'pending', linking to the `user_id`.
    3.  Dispatches a Celery task (e.g., `generate_tripo_text_to_model_task`) with necessary data (including the DB record ID).
    4.  BFF updates the `models` record with the `celery_task_id` (as `ai_service_task_id`) and status 'processing'.
    5.  Returns a `TaskIdResponse` containing the `celery_task_id` to the frontend.
    6.  The Celery task calls Tripo AI's text-to-model endpoint and receives a Tripo AI task ID. It updates the `models` record with this `ai_provider_task_id` and status remains 'processing'.
    7.  Frontend polls `GET /tasks/{celery_task_id}/status?service=tripoai` using the received `celery_task_id`.
    8.  The `/tasks/{celery_task_id}/status` endpoint, when polled:
        *   Retrieves the Tripo AI task ID from the Celery task result (or the `models` table).
        *   Polls Tripo AI's status endpoint.
        *   When Tripo AI task completes:
            *   BFF (within the status endpoint logic) downloads the model from Tripo AI's temporary URL.
            *   BFF uploads the model to Supabase Storage (e.g., `[GENERATED_ASSETS_BUCKET_NAME]/models/{task_id}/model.glb`).
            *   BFF updates the corresponding record in the `models` table with the new Supabase `asset_url` and sets status to 'complete'.

### `POST /generate/image-to-model`

- **Summary (Refactored):** Initiates 3D model generation from image URL(s) (Supabase) using Tripo AI.
- **Request (Refactored):**
    - **Content-Type:** `application/json`
    - **Body:** Includes `task_id`, `input_image_asset_urls` (array of Supabase URLs), and other Tripo AI parameters.
- **Process (Refactored):**
    1.  Receives `task_id`, `input_image_asset_urls`, etc.
    2.  BFF fetches image(s) from the provided Supabase URL(s).
    3.  **Automatic Mode Selection:**
        - **Single Image (1 URL):** Uses Tripo's `image_to_model` API for single-view generation
        - **Multiview (2-4 URLs):** Uses Tripo's `multiview_to_model` API for enhanced quality
    4.  **Multiview Ordering:** For multiview mode, images must be provided in exact order: `[front, left, back, right]`
        - Front view (position 0) is REQUIRED and cannot be omitted
        - Other views are optional but must maintain positional order
        - Examples: `[front]`, `[front, left]`, `[front, left, back]`, `[front, left, back, right]`
    5.  BFF creates an initial record in the `models` table for this `task_id` with status 'pending'.
    6.  Dispatches a Celery task (e.g., `generate_tripo_image_to_model_task`) with fetched image data and DB record ID.
    7.  BFF updates the `models` record with the `celery_task_id` (as `ai_service_task_id`) and status 'processing'.
    8.  Returns a `TaskIdResponse` containing the `celery_task_id` to the frontend.
    9.  The Celery task calls Tripo AI's image-to-model or multiview-to-model endpoint based on image count.
    10. Handles polling (via `GET /tasks/{celery_task_id}/status?service=tripoai`), final asset download from Tripo, upload to Supabase Storage, and `models` table update as in `text-to-model`.

### `POST /generate/sketch-to-model`

- **Summary (Refactored):** Initiates 3D model generation from a sketch image URL (Supabase) using Tripo AI.
- **Request (Refactored):**
    - **Content-Type:** `application/json`
    - **Body:** Includes `task_id`, `input_sketch_asset_url` (Supabase URL), etc.
- **Process (Refactored):** Similar to `image-to-model`, but with a single sketch input URL.
    1. Fetch sketch from Supabase.
    2. Create initial record in `models` table with status 'pending'.
    3. Dispatch Celery task (`generate_tripo_sketch_to_model_task`).
    4. Update `models` record with `celery_task_id` and status 'processing'.
    5. Return `celery_task_id` to client.
    6. Celery task calls Tripo AI.
    7. Poll (via `GET /tasks/{celery_task_id}/status?service=tripoai`), download from Tripo, upload to Supabase Storage, update `models` table.

### `POST /generate/refine-model`

- **Summary (Refactored):** Initiates refinement of an existing 3D model using Tripo AI.
- **Request (Refactored):**
    - **Content-Type:** `application/json`
    - **Body:** Includes client's main workspace `task_id`, `input_model_asset_url` (Supabase URL of the model to refine), and `draft_model_task_id` (optional, Tripo's ID for a model previously generated by Tripo).
- **Process (Refactored):**
    1.  Receives `task_id`, `input_model_asset_url`, and other parameters.
    2.  BFF fetches the input model from `input_model_asset_url`.
    3.  BFF creates a new record in the `models` table for the refined model output with status 'pending'.
    4.  Dispatches a Celery task (e.g., `generate_tripo_refine_model_task`) with fetched model data and new DB record ID.
    5.  BFF updates the new `models` record with the `celery_task_id` (as `ai_service_task_id`) and status 'processing'.
    6.  Returns a `TaskIdResponse` containing the `celery_task_id` to the frontend.
    7.  The Celery task calls Tripo AI's refine endpoint.
    8.  Handles polling (via `GET /tasks/{celery_task_id}/status?service=tripoai`), final asset download from Tripo, upload to Supabase Storage, and `models` table update for the *new record* as in `text-to-model`.

### `GET /tasks/{celery_task_id}/status?service={service}`

- **Summary (Refactored):** Retrieves real-time status of a specific AI generation Celery task.
- **Request:** Path param `celery_task_id` (the Celery task ID), query param `service` (`openai` or `tripoai`).
- **Response (Refactored):**
    - **Body:** Normalized structure: `{ "task_id": "celery_task_id", "status": "pending|processing|complete|failed", "asset_url": string (Supabase URL if complete), "error": string (if failed) }`. (Matches `TaskStatusResponse` in OpenAPI)
- **Process (Refactored):**
    1.  Based on `service`, calls the appropriate AI service's status endpoint.
    2.  Normalizes the response.
    3.  If AI service step is complete, the BFF should have already processed the output (uploaded to Supabase Storage, updated respective metadata table). This endpoint returns the Supabase URL(s) for the asset(s) produced in *this specific step*.

## Technology Stack

| Tool                | Purpose                                                         |
|---------------------|-----------------------------------------------------------------|
| Python 3.x          | Core backend language                                          |
| FastAPI             | Web API framework                                               |
| httpx               | Asynchronous HTTP client for external APIs                      |
| Pydantic            | Data validation and settings management                         |
| **Supabase Python Client** | For interacting with Supabase Storage and Database             |
| Docker              | Containerization for deployment                                 |
| Railway             | Cloud deployment platform (or similar)                           |

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
        *   Uploads generated assets (concepts, models) to a configurable Supabase Storage bucket using the path structure: `[BUCKET_NAME]/{asset_type_plural}/{task_id}/{filename}` (e.g., `generated_assets_bucket/concepts/task_abc123/0.png`).
    *   **Database:**
        *   Creates and updates records in the `concept_images` and `models` Supabase tables.
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
        2. Creates initial record in `concept_images` or `models` table (status 'pending').
        3. Dispatches Celery task.
        4. Updates DB record with `celery_task_id` and status 'processing'.
        5. Returns `celery_task_id` to client.
    *   Client polls `GET /tasks/{celery_task_id}/status?service={service}` using the `celery_task_id`.
    *   **OpenAI Flow (within Celery task `generate_openai_image_task`):**
        1.  Celery task keeps DB record status as 'processing'.
        2.  Calls OpenAI.
        3.  Downloads/processes images.
        4.  Uploads images to Supabase Storage (via `supabase_handler`).
        5.  Updates its DB record in `concept_images` with final `asset_url`(s) and status 'complete' or 'failed'.
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
    *   BFF needs Supabase URL (`https://iadsbhyztbokarclnzzk.supabase.co`), service key, JWT secret for token validation
    *   Generated assets bucket name, and names of `concept_images` and `models` tables
    *   Anon key: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlhZHNiaHl6dGJva2FyY2xuenprIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDc1MjM4MDUsImV4cCI6MjA2MzA5OTgwNX0.HeTNAhHhCdOoadHJOUeyHEQxo9f5Ole6GxJqYCORS78`

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
|   |-- /schemas
|   |   |-- __init__.py
|   |   |-- generation_schemas.py
|   |-- config.py              # App settings, API keys, Supabase config
|   |-- /ai_clients
|   |   |-- __init__.py
|   |   |-- tripo_client.py
|   |   |-- openai_client.py
|   |-- supabase_handler.py    # NEW: Module for all Supabase interactions (Storage & DB)
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

### External API Mapping (Conceptual - for BFF to AI Service calls)

(Remains conceptually similar, but BFF now fetches inputs before calling these, and handles outputs by storing to Supabase, not just passing URLs.)

| BFF Endpoint Call Type | External Service | External API Call by BFF                     | BFF Output Handling                                       |
| :--------------------- | :--------------- | :------------------------------------------- | :-------------------------------------------------------- |
| Image-to-Image         | OpenAI           | Image Edit/Generate with fetched image data  | Upload concepts to Supabase Storage; record in `concept_images`. |
| Text-to-Model          | Tripo AI         | Text to Model endpoint                       | Upload model to Supabase Storage; record in `models`.      |
| Image-to-Model         | Tripo AI         | Image to Model with fetched image data(s)    | Upload model to Supabase Storage; record in `models`.      |
| Sketch-to-Model        | Tripo AI         | Image to Model with fetched sketch data      | Upload model to Supabase Storage; record in `models`.      |
| Refine-Model           | Tripo AI         | Refine Model endpoint                        | Upload refined model to Supabase Storage; record in `models`. |

(Polling status is separate via `GET /tasks/{task_id}/status` which calls respective AI service status endpoints.)

## Implementation Tasks
(Refer to `.documentation/API_REFACTOR.md` for the comprehensive checklist which details these changes.)