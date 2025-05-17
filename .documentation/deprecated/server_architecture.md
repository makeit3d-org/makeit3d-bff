# MakeIt3D Backend Worker Architecture (Split Services)

This document describes the two independent backend workers deployed on RunPod Serverless.

---

## Service 1: Image Generation Worker

### 1.1. High-Level Summary

This worker handles generating 2D concept images using OpenAI's API. It accepts text prompts or input images along with style information and returns URLs to the generated concepts. It runs as a RunPod Serverless worker, likely on CPU instances.

### 1.2. Features

*   **Concept Generation**: Processes jobs requesting 2D concept generation from text/image input and style info using OpenAI.
*   **Stateless Processing**: Each handler invocation is independent.

### 1.3. Architecture & Components

*   **Execution Environment**: RunPod Serverless (CPU likely sufficient)
*   **Core SDK**: `runpod` Python SDK
*   **Language**: Python
*   **AI Integration**: OpenAI Python Client
*   **Data Validation**: Pydantic
*   **Containerization**: Docker (`backend/image-generator/Dockerfile`)

### 1.4. Directory Structure (`backend/image-generator` - Example)

```
/app
|-- services/openai_service.py
|-- schemas/generation.py
/core/config.py
rp_handler.py         # Entry point for Image Generation worker
requirements.txt
Dockerfile
test_input.json
```

### 1.5. Serverless Endpoint Input/Output

*   **Endpoint URL:** `(RunPod Endpoint 1 URL)`
*   **Method:** `POST`
*   **Request Body Structure (Example):**
    ```json
    {
      "input": {
        "operation": "generate_concepts", // Only operation for this service
        "type": "text" | "image",
        "prompt": Optional[str],
        "image_url": Optional[str],
        "styleId": Optional[str]
      }
    }
    ```
*   **Success Response Body (Example):**
    ```json
    {
      "output": {
        "concept_urls": ["url1.jpg", "url2.jpg"]
      },
      "status": "COMPLETED", ...
    }
    ```
*   **Error Response Body (Example):** `{"error": "OpenAI API error...", "status": "FAILED", ...}`

### 1.6. Sequence Flow

1.  Next.js Server Action calls RunPod Endpoint 1 **using the `/runsync` operation**.
2.  RunPod starts worker, calls `handler(event)` in `rp_handler.py`.
3.  Handler validates input, calls `openai_service.generate_concepts(...)`.
4.  `openai_service` interacts with OpenAI API (using style info if needed).
5.  Handler receives concept URLs, formats output.
6.  Handler returns result to RunPod, which returns to Next.js.

### 1.7. Technical Considerations

*   Handler logic is simple (validation, call service, format output).
*   Dependencies: `runpod`, `openai`, `pydantic`.
*   **Statelessness & Data Handling**: Workers are stateless. They do **not** store input/output data (images, concepts) persistently. Inputs are received (e.g., via URLs or direct data), processed, and results (e.g., new concept image URLs) are returned. Any persistent storage happens externally (managed by the calling Next.js server).
*   **Concurrency & Queueing**: RunPod Serverless automatically scales workers up to the configured Maximum Concurrency limit. Requests exceeding this limit are automatically queued by RunPod and processed as workers become available.
*   **Environment Variables**: Use environment variables to securely configure secrets like the OpenAI API key.
*   **Cleanup**: Implement `runpod.serverless.utils.cleanup()` within the handler (e.g., in a `finally` block) to remove temporary files and ensure statelessness between jobs.
*   **Synchronous Calls**: For MVP simplicity, Next.js will call this endpoint using RunPod's `/runsync` operation. Be mindful of potential timeouts for longer-running tasks, which might necessitate switching to `/run` (async) post-MVP.
*   Error handling for OpenAI API calls.

### 1.8. Implementation Tasks

- [ ] Setup `backend/image-generator` project directory.
- [ ] Implement `rp_handler.py` for concept generation.
- [ ] Implement `openai_service.py`.
- [ ] Define Pydantic schemas.
- [ ] Create `Dockerfile` (CPU base image sufficient).
- [ ] Define `requirements.txt`.
- [ ] Create `test_input.json` for default local testing.
- [ ] Test locally using `python rp_handler.py` (with `test_input.json`) and the local API server (`--rp_serve_api` flag, sending requests to `/runsync`).
- [ ] Implement `runpod.serverless.utils.cleanup()` in handler.
- [ ] Build image (`--platform linux/amd64`), deploy to RunPod (Endpoint 1).

---

## Service 2: Model Generation Worker

### 2.1. High-Level Summary

This worker handles generating a 3D model from an input image, cleaning the mesh, **automatically normalizing it to a standard size**, and also performing on-demand rescaling for final print dimensions. It uses TRELLIS, MeshLab, and a rescaling library. It runs as a RunPod Serverless worker, requiring GPU instances.

### 2.2. Features

*   **3D Model Generation & Cleanup & Normalization**: Processes jobs taking an input image (+ optional style/prompt info) and producing a cleaned, **normalized** 3D model.
*   **Final Print Rescaling**: Processes jobs taking an existing (likely normalized) model URL and scaling parameters to produce a model at the final desired print dimensions.
*   **Stateless Processing**: Each handler invocation is independent.

### 2.3. Architecture & Components

*   **Execution Environment**: RunPod Serverless (GPU required)
*   **Core SDK**: `runpod` Python SDK
*   **Language**: Python
*   **AI/3D Integrations**: Microsoft TRELLIS, MeshLab, 3D Rescaling Library (e.g., `trimesh`).
*   **Data Validation**: Pydantic
*   **Containerization**: Docker (`backend/model-generator/Dockerfile`)

### 2.4. Directory Structure (`backend/model-generator` - Example)

```
/app
|-- services/model_processing_service.py
|-- schemas/generation.py
/core/config.py
/wrappers/
|-- trellis_wrapper.py
|-- meshlab_wrapper.py
|-- rescaler_wrapper.py
rp_handler.py         # Entry point for Model Generation worker
requirements.txt
Dockerfile
test_input.json
```

### 2.5. Serverless Endpoint Input/Output

*   **Endpoint URL:** `(RunPod Endpoint 2 URL)`
*   **Method:** `POST`
*   **Request Body Structure (Example):**
    ```json
    {
      "input": {
        "operation": "generate_model" | "rescale_model",
        // --- Payload specific to operation ---
        // For generate_model:
        "input_image_url": str, // Could be user image OR concept image
        "prompt": Optional[str], // Optional guiding prompt
        "styleId": Optional[str], // Optional style info
        // For rescale_model (Final Print Scaling):
        "model_url": str, // URL of the model to rescale (likely normalized)
        "scale_factor": Optional[float],
        "target_dimensions": Optional[dict] // Final print dimensions (e.g., {"x": 100, "y": 50, "z": 80, "unit": "mm"})
      }
    }
    ```
*   **Success Response Body (Example):**
    ```json
    {
      "output": {
        // For generate_model:
        // "normalized_model_url": "url_to_normalized_model.glb",
        // For rescale_model:
        // "rescaled_model_url": "url_to_final_print_scaled_model.glb"
      },
      "status": "COMPLETED", ...
    }
    ```
*   **Error Response Body (Example):** `{"error": "Rescaling failed...", "status": "FAILED", ...}`

### 2.6. Sequence Flow

1.  Next.js Server Action calls RunPod Endpoint 2 **using the `/runsync` operation**.
2.  RunPod starts GPU worker, calls `handler(event)`.
3.  Handler validates input, determines operation (`generate_model` or `rescale_model`).
4.  **If `generate_model`**: 
    *   Handler calls `model_processing_service.generate_clean_normalize(...)`.
    *   Service orchestrates `trellis_wrapper`, `meshlab_wrapper`, and **internal normalization** (using `rescaler_wrapper` or `meshlab_wrapper`).
    *   Handler receives **normalized** model URL, formats output.
5.  **If `rescale_model`**: 
    *   Handler calls `model_processing_service.rescale_for_print(...)`.
    *   Service uses `rescaler_wrapper` or `meshlab_wrapper` to apply final dimensions.
    *   Handler receives **final scaled** model URL, formats output.
6.  Handler returns result to RunPod, which returns to Next.js.

### 2.7. Technical Considerations

*   Handler logic involves dispatching to the service based on `operation`.
*   Dependencies: `runpod`, PyTorch/TRELLIS, MeshLab, `trimesh`, `pydantic`.
*   GPU requirement for worker configuration.
*   Model loading (TRELLIS) considerations for serverless environment.
*   **Statelessness & Data Handling**: Workers are stateless. They do **not** store input/output data (models) persistently. They receive inputs (e.g., image URLs, model URLs from external storage), process them (generating, cleaning, rescaling), and return results (e.g., new model URLs pointing to external storage). Temporary file handling during processing should use `runpod.serverless.utils.cleanup()`.
*   **Concurrency & Queueing**: RunPod Serverless automatically scales GPU workers up to the configured Maximum Concurrency limit. Requests exceeding this limit are automatically queued by RunPod and processed as workers become available.
*   **Environment Variables**: Use environment variables for any necessary secrets or configuration.
*   **Cleanup**: Implement `runpod.serverless.utils.cleanup()` within the handler (e.g., in a `finally` block) to remove temporary files (e.g., downloaded models, intermediate processing files) and ensure statelessness.
*   **Synchronous Calls**: For MVP simplicity, Next.js will call this endpoint using RunPod's `/runsync` operation. Model generation can be long; monitor execution times. If timeouts occur frequently, switching to `/run` (async) will be necessary post-MVP.
*   **Normalization Logic**: Define the standard normalization target (e.g., unit cube, specific max dimension) within the `model_processing_service`.
*   **Rescaling Logic**: Ensure the `rescale_model` operation correctly applies target dimensions or scale factors, potentially using metadata from the model if needed.
*   **Error Handling**: Robust error handling needed for all steps (generation, cleanup, normalization, final scaling).
*   **Interaction with Frontend on Scaling**: Note that the `rescale_model` operation returns the URL of the newly scaled model. The calling service (Next.js server) is responsible for updating the database record and deleting the previous model file from storage.

### 2.8. Implementation Tasks

- [ ] Setup `backend/model-generator` project directory.
- [ ] Implement `rp_handler.py` for model generation/rescaling dispatch.
- [ ] Implement `model_processing_service.py` with methods like `generate_clean_normalize` and `rescale_for_print`.
- [ ] Implement `trellis_wrapper.py`.
- [ ] Implement `meshlab_wrapper.py`.
- [ ] Implement `rescaler_wrapper.py` (handling normalization and final scaling).
- [ ] Define Pydantic schemas.
- [ ] Create `Dockerfile` (GPU base image, install all dependencies).
- [ ] Define `requirements.txt`.
- [ ] Create `test_input.json` (with examples for generate/rescale) for default local testing.
- [ ] Test locally using `python rp_handler.py` (with `test_input.json`) and the local API server (`--rp_serve_api` flag, sending requests to `/runsync`).
- [ ] Implement `runpod.serverless.utils.cleanup()` in handler.
- [ ] Build image (`--platform linux/amd64`), deploy to RunPod (Endpoint 2 - GPU). 