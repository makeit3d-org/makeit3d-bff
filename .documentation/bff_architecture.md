# BFF (Backend-for-Frontend) Architecture

## Overview

This document describes the architecture for the Backend-for-Frontend (BFF) service for the makeit3d app. The BFF acts as an intermediary between the mobile frontend and external AI services (Tripo AI, OpenAI). Its primary responsibilities are to securely manage API keys, abstract the complexities of external APIs, and provide a tailored API for the frontend client. **The BFF receives temporary URLs for generated assets from the AI services and passes them directly to the frontend; the frontend is responsible for downloading these assets and managing their storage.** The service is built with Python (FastAPI), containerized with Docker, and designed for deployment on platforms like Railway.

## API Endpoints

### `POST /generate/image-to-image`

- **Summary:** Generates 2D concepts from an input image and text prompt using OpenAI's image editing capabilities.
- **OpenAPI Reference:** [https://platform.openai.com/docs/api-reference/images/createEdit](https://platform.openai.com/docs/api-reference/images/createEdit)
- **Request:**
    - **Content-Type:** `multipart/form-data`
    - **Parameters:**
        - `image`: File (required) - The source image file (e.g., sketch or image from frontend).
        - `prompt`: String (required) - Text prompt to guide generation.
        - `style`: String (optional) - Style hint (used to customize prompt sent to OpenAI).
        - `n`: Integer (optional, default: 1) - The number of images to generate. Must be between 1 and 10.
        - **Note:** The OpenAI `createEdit` API supports transparency via a `mask` parameter, but this BFF endpoint currently does not include a mask parameter. Transparency in the output would depend on the input image's alpha channel if no mask is used.
- **Process:**
    1. Receives image file, prompt, style, and the desired number of images (`n`) from the frontend.
    2. Customizes the prompt for OpenAI based on the input style.
    3. Calls OpenAI's image `createEdit` endpoint with the image file, customized prompt, setting `model='gpt-image-1'`, the provided `n`, `size='1024x1024'` (Supported values: '1024x1024', '1024x1536', '1536x1024', 'auto'), and `response_format='b64_json'` (gpt-image-1 always returns b64_json).
    4. Receives base64 encoded image data for the generated images from OpenAI.
    5. Returns this base64 encoded image data to the frontend along with a task ID.
    8. Status polling for this task is handled via the `/tasks/{task_id}/status` endpoint, which will query OpenAI's response status if the task ID corresponds to an OpenAI job (though for synchronous APIs like this, status is immediately completed).

### `POST /generate/text-to-model`

- **Summary:** Initiates 3D model generation from a text prompt using Tripo AI's text-to-model endpoint.
- **Tripo API Reference:** [https://platform.tripo3d.ai/docs/generation](https://platform.tripo3d.ai/docs/generation)
- **Request:**
    - **Content-Type:** `application/json`
    - **Body:**
        ```json
        {
            "prompt": "string (required)",
            "style": "string (optional, used to customize prompt)",
            "texture": "boolean (optional, default: true)"
        }
        ```
- **Process:**
    1. Receives prompt, style, and texture preference from the frontend.
    2. Customizes the prompt for Tripo AI based on the input style.
    3. Calls Tripo AI's text-to-model endpoint with the customized prompt and the `texture` flag.
    4. Returns the Tripo AI task ID to the frontend. Frontend will poll `/tasks/{task_id}/status` for updates.

### `POST /generate/image-to-model`

- **Summary:** Initiates 3D model generation from multiple images (multiview) using Tripo AI's multiview-to-model endpoint.
- **Tripo API Reference:** [https://platform.tripo3d.ai/docs/generation](https://platform.tripo3d.ai/docs/generation)
- **Request:**
    - **Content-Type:** `application/json`
    - **Body:**
        ```json
        {
            "image_urls": "array of strings (required, URLs of images provided by frontend)",
            "prompt": "string (optional)",
            "style": "string (optional)",
            "texture": "boolean (optional, default: true)"
        }
        ```
- **Process:**
    1. Receives image URLs (provided by the frontend) for the multiple views.
    2. Passes the received image URLs to Tripo AI's multiview-to-model endpoint.
    3. Includes the `texture` flag in the Tripo AI call.
    4. Returns the Tripo AI task ID to the frontend. Frontend will poll `/tasks/{task_id}/status` for updates.

### `POST /generate/sketch-to-model`

- **Summary:** Initiates 3D model generation from a single sketch image using Tripo AI's image-to-model endpoint.
- **Tripo API Reference:** [https://platform.tripo3d.ai/docs/generation](https://platform.tripo3d.ai/docs/generation)
- **Request:**
    - **Content-Type:** `application/json`
    - **Body:**
        ```json
        {
            "image_url": "string (required, URL of sketch image provided by frontend)",
            "prompt": "string (optional)",
            "style": "string (optional)",
            "texture": "boolean (optional, default: true)"
        }
        ```
- **Process:**
    1. Receives the sketch image URL (provided by the frontend).
    2. Passes the received sketch image URL to Tripo AI's image-to-model endpoint.
    3. Includes the `texture` flag in the Tripo AI call.
    4. Returns the Tripo AI task ID to the frontend. Frontend will poll `/tasks/{task_id}/status` for updates.

### `POST /generate/refine-model`

- **Summary:** Initiates refinement of an existing 3D model using Tripo AI's refine endpoint.
- **Tripo API Reference:** [https://platform.tripo3d.ai/docs/generation](https://platform.tripo3d.ai/docs/generation)
- **Request:**
    - **Content-Type:** `application/json`
    - **Body:**
        ```json
        {
            "draft_model_task_id": "string (required, task ID of a draft model provided by frontend)"
        }
        ```
- **Process:**
    1. Receives the `draft_model_task_id` (provided by the frontend).
    2. Calls Tripo AI's refine endpoint, providing the `draft_model_task_id`.
    3. Returns the Tripo AI task ID to the frontend. Frontend will poll `/tasks/{task_id}/status` for updates.

### `GET /tasks/{task_id}/status`

- **Summary:** Retrieves the current status of a generation task by its ID, specifying whether it's a Tripo AI or OpenAI task.
- **Tripo Task Status:** [https://platform.tripo3d.ai/docs/task](https://platform.tripo3d.ai/docs/task)
- **OpenAI Response Status:** [https://platform.openai.com/docs/api-reference/docs/api-reference/images/get](https://platform.openai.com/docs/api-reference/docs/api-reference/images/get)
- **Request:**
    - Path parameter `task_id`: String (required) - The ID of the task obtained from a generation endpoint response.
    - Query parameter `service`: String (required) - Specifies the service that generated the task. Allowed values: `openai`, `tripo`.
- **Response:**
    - **Content-Type:** `application/json`
    - **Body:** Returns the status information for the specified task. The structure should be normalized for the frontend (e.g., `{ "status": "pending"|"processing"|"completed"|"failed", "progress": number, "result_url": string (Temporary URL) }`). `result_url` is included only on completion and is a temporary URL from the external API.
- **Process:**
    1. Receives the `task_id` and the `service` parameter from the frontend.
    2. Based on the `service` parameter, calls the appropriate status endpoint (`GET /v1/task/{task_id}` for Tripo AI, or `GET /v1/images/generations/{id}` for OpenAI).
    3. Normalizes the status response structure.
    4. If the task is complete and the external API provides a temporary download URL, include this temporary URL (`result_url`) in the normalized response.

## Technology Stack

| Tool         | Purpose                                                         |
|--------------|-----------------------------------------------------------------|
| Python 3.x   | Core backend language                                          |
| FastAPI      | Web API framework                                               |
| httpx        | Asynchronous HTTP client for calling external APIs. Handles passing URLs received from the frontend to AI services or receiving temporary URLs from AI services. |
| Pydantic     | Data validation and settings management                         |
| Docker       | Containerization for deployment                                 |
| Railway      | Cloud deployment platform (or similar)                           |

## Rate Limiting

The BFF implements per-client rate limiting on its API endpoints to ensure fair usage and protect backend services. These limits are configurable and enforced by `fastapi-limiter`.

- **OpenAI Endpoints (e.g., `/generate/image-to-image`):** Configured via `BFF_OPENAI_REQUESTS_PER_MINUTE` (e.g., 4 requests/minute/client).
  - *Reference OpenAI Limits:* [OpenAI Platform Limits](https://platform.openai.com/settings/organization/limits)
- **Tripo Refine Endpoint (e.g., `/generate/refine-model`):** Configured via `BFF_TRIPO_REFINE_REQUESTS_PER_MINUTE` (e.g., 6 requests/minute/client).
- **Other Tripo Endpoints (e.g., `/generate/text-to-model`):** Configured via `BFF_TRIPO_OTHER_REQUESTS_PER_MINUTE` (e.g., 12 requests/minute/client).
  - *Reference Tripo Limits:* [Tripo3D Generation Rate Limit](https://platform.tripo3d.ai/docs/limit#generation-rate-limit)

If a client exceeds these limits, the API will respond with an HTTP `429 Too Many Requests` error, including a `Retry-After` header indicating when the client can try again.

Backend Celery workers manage concurrency for Tripo tasks (10 for "other", 5 for "refine") and a task-level rate limit for OpenAI tasks (e.g., 5 tasks/minute globally) to align with external service capacities.

## Core Logic & Considerations

1.  **API Key Management:**
    *   Tripo AI, OpenAI, and other potential external service keys are stored securely as environment variables on the BFF server.
    *   FastAPI's `config.py` (using Pydantic's `BaseSettings`) will load these keys.
    *   Client applications never have access to these keys.

2.  **External API Interaction (`/ai_clients`):**
    *   `tripo_client.py`: Functions to interact with the Tripo AI API (authentication, job submission, status checks, model fetching, handling *input URLs provided by the frontend* and **returning temporary output URLs**).
    *   `openai_client.py`: Functions to interact with OpenAI API (e.g., DALL-E for concept generation, **returning temporary output URLs**).
    *   These clients will use `httpx` for making asynchronous HTTP requests.

3.  **Storage Interaction:**
    *   The BFF does not interact with persistent storage. It receives input URLs from the frontend and temporary output URLs from AI services.

4.  **Asynchronous Operations:**
    *   All routes involving calls to external services (Tripo AI, OpenAI) will be `async`.

5.  **File Handling:**
    *   Receiving input URLs (or potentially file streams if required by the AI API for direct upload) from the frontend.
    *   Passing input URLs (or file streams) to external AI services as required by their APIs.
    *   Handling temporary output URLs received from Tripo AI/OpenAI and passing them to the frontend.

6.  **Task Status Tracking (MVP Strategy):**
    *   Polling via `GET /tasks/{task_id}/status`.
    *   BFF polls appropriate external API (Tripo or OpenAI) and returns the temporary download URL upon completion in the normalized status response.
    *   Normalization of status response for the frontend.

7.  **Prompt Customization:**
    *   Logic within the BFF to tailor the text prompt sent to Tripo AI or OpenAI based on the user's selected style.

## Deployment
- **Containerization:** The BFF service runs in a Docker container.
- **Platform:** Deploy on Railway (or similar cloud platform).
- **Environment Variables:** API keys (Tripo, OpenAI) and other configurations are managed via environment variables.

---

### BFF Directory Structure (Python FastAPI)

```
/makeit3d-bff
|-- Dockerfile
|-- docker-compose.yml         # (optional, for local dev)
|-- requirements.txt           # Python dependencies (FastAPI, Uvicorn, httpx, Pydantic)
|-- README.md
|-- /app
|   |-- main.py                # FastAPI application entrypoint, middleware
|   |-- api.py                 # API route definitions (imports routers)
|   |-- /routers               # Directory for different API route modules
|   |   |-- generation.py      # Routes for /generate/*
|   |   |-- models.py          # Routes for /models/* and /tasks/*
|   |   |-- /schemas               # Pydantic schemas for request/response validation
|   |   |   |-- generation_schemas.py
|   |   |   |-- model_schemas.py
|   |   |   |-- task_schemas.py      # Schemas for task status responses
|   |   |-- config.py              # Application settings, API key loading (Pydantic BaseSettings)
|   |   |-- /ai_clients            # Clients for interacting with external AI services
|   |   |   |-- tripo_client.py    # Logic for Tripo AI communication
|   |   |   |-- openai_client.py   # Logic for OpenAI communication
|   |   |   |-- base_client.py     # (Optional) Base class for HTTP clients
|   |   |   `-- client_utils.py    # Utilities for AI clients
|   |   |-- /static                # (Optional) If BFF needs to serve any static assets
|   |   |-- /tests                 # Unit/integration tests
|   |   |   |-- /routers
|   |   |   |-- /ai_clients
|   |   |   |--/utils
|   |   |-- /file_handler        # Module for handling file data if AI services require uploads
|-- /scripts                   # Helper scripts
|-- .env                       # Environment variables (not committed to Git)
```

---

### External API Mapping

This section details how the BFF's generic endpoints map to the specific external API calls made to Tripo AI and OpenAI.

| BFF Endpoint                 | External Service | External API Endpoint/Method                 | Notes                                                                 |
| :--------------------------- | :--------------- | :------------------------------------------- | :-------------------------------------------------------------------- |
| `POST /generate/image-to-image`     | OpenAI           | Image Edit (`/v1/images/edits`)              | Uses `gpt-image-1`, provided `n` (1-10, default 1), `size=1024x1024` (Supported values: '1024x1024', '1024x1536', '1536x1024', 'auto'), returns `b64_json`.     |
| `POST /generate/text-to-model`     | Tripo AI         | Text to Model (`/v1/model/text-to-model`)    | Includes `texture` flag.                                          |
| `POST /generate/image-to-model`     | Tripo AI         | Multi-view to Model (`/v1/model/img-to-model-multiview`)| Accepts image URLs or file data. Includes `texture` flag.       |
| `POST /generate/sketch-to-model`     | Tripo AI         | Image to Model (`/v1/model/img-to-model`)    | Accepts sketch image URL or file data. Includes `texture` flag.    |
| `POST /generate/refine-model`     | Tripo AI         | Refine Model (`/v2/openapi/task` with `type: refine_model`)      | Accepts `draft_model_task_id` (provided by frontend). |
| `GET /tasks/{task_id}/status`     | Tripo AI / OpenAI| Tripo: `GET /v1/task/{task_id}`; OpenAI: `GET /v1/images/generations/{id}` | BFF determines service based on the provided `service` query parameter; returns temporary download URL on completion. |

## Implementation Tasks

- [ ] **Setup FastAPI & Docker Environment**
    - [ ] Initialize FastAPI project structure (`/app`, `main.py`, `config.py`).
    - [ ] Create `Dockerfile`.
    - [ ] Configure `requirements.txt` (FastAPI, Uvicorn, httpx, Pydantic).
- [ ] **Configure Environment Variables**
    - [ ] Document required environment variables (API keys for Tripo, OpenAI).
- [ ] **Implement AI Service Clients (`/app/ai_clients`)**
    - [ ] `openai_client.py`: Functions for concept generation (`createEdit`), polling status, and returning temporary URLs received from OpenAI.
    - [ ] `tripo_client.py`:
        - [ ] Authentication with Tripo AI.
        - [ ] Functions for submitting Text-to-Model, Image-to-Model (`image_to_model`), Multi-view-to-Model (`multiview_to_model`), Refine Model (`refine_model`) jobs. Include prompt customization logic.
        - [ ] Function for polling Tripo AI task status.
        - [ ] Handle passing *input URLs provided by the frontend* to Tripo AI.
        - [ ] Return temporary output URLs received from Tripo AI upon task completion. Ensure the `texture` parameter is handled correctly.
- [ ] **Develop API Endpoints (`/app/routers` & `/app/api.py`)**
    - [ ] Define Pydantic schemas in `/app/schemas/` for all request/response bodies, including task status responses.
    - [ ] `/generate/image-to-image`: Implement logic, integrate with `openai_client`. Handle receiving the image file from the frontend. The response should include the task ID and temporary URLs received from OpenAI.
    - [ ] `/generate/text-to-model`: Implement logic, integrate with `tripo_client`. Handle receiving the text prompt from the frontend. Response should include task ID.
    - [ ] `/generate/image-to-model`: Implement logic to receive image URLs from the frontend and pass them to `tripo_client` (`multiview_to_model`). Response should include task ID.
    - [ ] `/generate/sketch-to-model`: Implement logic to receive the sketch image URL from the frontend and pass it to `tripo_client` (`image_to_model`). Response should include task ID.
    - [ ] `/generate/refine-model`: Implement logic, integrate with `tripo_client`. Handle receiving the `draft_model_task_id` from the frontend. Response should include task ID.
    - [ ] `/tasks/{task_id}/status`: Implement logic to check status with either `tripo_client` or `openai_client` based on the provided `service` query parameter. If the task is complete, return the temporary download URL received from the external API in the normalized status response.
- [ ] **Error Handling & Logging**
    - [ ] Implement robust error handling across all layers.
    - [ ] Add structured logging.
- [ ] **Testing**
    - [ ] Write tests for all new components and endpoints.
- [ ] **Deployment**
    - [ ] Ensure Docker container builds.
    - [ ] Prepare configuration for deployment platform (Railway) for environment variables.
    - [ ] Document environment variable requirements (API keys for Tripo, OpenAI).
- [ ] **File Handling Module (`/app/file_handler`)**
    - [ ] (Removed as BFF does not handle file uploads beyond initial receipt from frontend)