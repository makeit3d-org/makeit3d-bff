# 3D Sculpter Backend Architecture - Prototype

## Overview

This document describes the backend architecture for the makeit3d app. The backend is responsible for mesh cleanup, remeshing, and color transfer, using Blender as the core processing engine. The service is built with Python (FastAPI), containerized with Docker, and designed for deployment on Railway or similar platforms.

## API Endpoints

### `POST /process/remesh`

- **Summary:** Cleans and remeshes an uploaded GLB model.
- **Request:**
    - **Content-Type:** `multipart/form-data`
    - **Parameters:**
        - `file`: File (required) - The `.glb` model file to process.
        - `voxel_size`: Float (optional, default: 0.1) - Controls the resolution/density of the Voxel Remesher. Smaller values result in higher density/detail.
- **Response:**
    - **Content-Type:** `model/gltf-binary`
    - **Body:** Binary `.glb` data of the cleaned and remeshed model.
- **Process:** Uses Blender to perform mesh cleanup and remeshing using the provided `voxel_size` (details in Core Processing Pipeline).

### `POST /process/transfer-colors`

- **Summary:** Transfers texture color from an original model to a sculpted model's vertex colors.
- **Request:**
    - **Content-Type:** `multipart/form-data`
    - **Parameters:**
        - `sculpted_mesh`: File (required) - The sculpted `.glb` model file.
        - `original_mesh`: File (required) - The original `.glb` model file (used for texture coordinates and source geometry).
        - `original_texture`: File (optional) - The texture file if not embedded in `original_mesh.glb`.
- **Response:**
    - **Content-Type:** `model/gltf-binary`
    - **Body:** Binary `.glb` data of the sculpted model with baked vertex colors.
- **Process:** Uses Blender's bake features to transfer the original texture color to the sculpted mesh's vertex colors (details in Core Processing Pipeline).

## Technology Stack

| Tool         | Purpose                                                      |
|--------------|--------------------------------------------------------------|
| Python 3.x   | Core backend language                                       |
| FastAPI      | Web API framework                                           |
| Docker       | Containerization for deployment                             |
| Blender      | Headless mesh processing (via Python API/scripts)           |
| Railway      | Cloud deployment platform (or similar, e.g., Render, Fly.io)|

## Core Processing Pipeline

### 1. Mesh Cleanup & Remeshing
- **Tool:** Blender (headless, via Python API)
- **Input:** `.glb` file (required), `voxel_size` (float, optional, default: 0.1)
- **Steps:**
    1. Receive `file` and optional `voxel_size` from the request.
    2. Load `.glb` into Blender.
    3. Determine the `voxel_size` to use (use provided value or default).
    4. Remove loose geometry (`bpy.ops.mesh.delete_loose()`).
    5. Select non-manifold edges (`bpy.ops.mesh.select_non_manifold()`) and potentially attempt basic repairs or report issues.
    6. Merge close vertices (`bpy.ops.mesh.remove_doubles()`).
    7. Apply Voxel Remesh modifier:
        - Add modifier: `mod = target_obj.modifiers.new(name="VoxelRemesh", type='VOXEL_REMESHER')`
        - Set voxel size: `mod.voxel_size = voxel_size_to_use`
        - Apply modifier: `bpy.context.view_layer.objects.active = target_obj` ; `bpy.ops.object.modifier_apply(modifier=mod.name)`
    8. Export cleaned `.glb`.
- **Output:** Cleaned and remeshed `.glb` file at the specified density.

### 2. Color Transfer (Texture to Vertex Color using Bake)
- **Tool:** Blender (Python API, using Bake functionality)
- **Steps:**
    1. Load the sculpted mesh (`target_obj`) and the original mesh with its texture (`source_obj`) into Blender.
    2. Ensure the `source_obj` has a material setup correctly using the provided texture image.
    3. Ensure the `target_obj` (sculpted mesh) has an active vertex color layer (e.g., `target_obj.data.vertex_colors.new(name='Color')`). Make this layer active for rendering/baking.
    4. Configure bake settings:
        - Set bake type to Diffuse: `bpy.context.scene.render.bake.bake_type = 'DIFFUSE'`
        - Disable contribution from direct/indirect light, only use color: `bpy.context.scene.render.bake.use_pass_direct = False`, `use_pass_indirect = False`, `use_pass_color = True`
        - Set the target to vertex colors: `bpy.context.scene.render.bake.target = 'VERTEX_COLORS'`
        - Use 'Selected to Active' method if mapping from original to sculpted: `bpy.context.scene.render.bake.use_selected_to_active = True`. Set appropriate `cage_extrusion` and `max_ray_distance`.
            - Select the `source_obj` (original), then the `target_obj` (sculpted), making it active.
    5. Execute the bake operation: `bpy.ops.object.bake(type='DIFFUSE', target='VERTEX_COLORS', use_selected_to_active=True)`
    6. Export the `target_obj` (sculpted mesh) as a `.glb` file, ensuring vertex colors (`COLOR_0`) are included.
- **Input:** Sculpted `.glb` file, original `.glb` file, original texture
- **Output:** `.glb` file of the sculpted mesh with vertex colors baked from the original texture.
- **Note:** This baking approach is significantly more efficient than manual looping and leverages Blender's core rendering capabilities.
## Deployment
- **Containerization:** All services run in Docker containers
- **Platform:** Deploy on Railway (or similar cloud platform)
- **Blender:** Installed in the Docker image, runs in headless mode (no GUI)
- **API:** Exposed via FastAPI, ready for secure public or private endpoints

---

### Backend Directory Structure (Python FastAPI + Blender)

```
/makeit3d-backend
|-- Dockerfile
|-- docker-compose.yml         # (optional, for local dev)
|-- requirements.txt           # Python dependencies
|-- README.md
|-- /app
|   |-- main.py                # FastAPI entrypoint
|   |-- api.py                 # API route definitions
|   |-- models.py              # Pydantic models/schemas
|   |-- config.py              # App/config settings
|   |-- /processing
|   |   |-- blender_remesh.py      # Blender remeshing script (invoked via subprocess or Blender API)
|   |   |-- blender_color_transfer.py # Blender color transfer script
|   |   |-- utils.py               # Shared mesh utilities
|   |-- /tasks                 # (optional) Async task queue workers (Celery, etc.)
|   |-- /static                # (optional) For serving static files/textures
|   |-- /tests                 # Unit/integration tests
|-- /scripts                   # Devops, migration, or Blender helper scripts
|-- .env                       # Environment variables (not committed)
```

---

## Implementation Tasks

- [ ] **Setup FastAPI & Docker Environment**
    - [ ] Initialize FastAPI project structure.
    - [ ] Create `Dockerfile` for the backend service.
    - [ ] Configure `requirements.txt` with FastAPI, Uvicorn, and Blender (as a Python module, otherwise system dependency).
- [ ] **Develop `/process/remesh` Endpoint**
    - [ ] Define Pydantic models for request/response.
    - [ ] Implement API route in `api.py`.
    - [ ] Create `blender_remesh.py` script:
        - [ ] Load `.glb`.
        - [ ] Implement mesh cleanup steps (loose geometry, non-manifold, remove doubles).
        - [ ] Implement Voxel Remesh modifier logic.
        - [ ] Export processed `.glb`.
    - [ ] Integrate Blender script execution (subprocess or direct API call) into the endpoint.
- [ ] **Develop `/process/transfer-colors` Endpoint**
    - [ ] Define Pydantic models for request/response.
    - [ ] Implement API route in `api.py`.
    - [ ] Create `blender_color_transfer.py` script:
        - [ ] Load sculpted and original `.glb` files.
        - [ ] Handle optional external texture.
        - [ ] Setup materials and vertex color layers.
        - [ ] Configure and execute Blender bake operation (Diffuse, Vertex Colors, Selected to Active).
        - [ ] Export `.glb` with vertex colors.
    - [ ] Integrate Blender script execution into the endpoint.
- [ ] **Core Utilities & Error Handling**
    - [ ] Implement utility functions for file handling in `processing/utils.py`.
    - [ ] Add robust error handling and logging in API endpoints and Blender scripts.
- [ ] **Testing**
    - [ ] Write unit tests for Blender scripts (mocking Blender's Python API if feasible, or using sample files).
    - [ ] Write integration tests for API endpoints using sample `.glb` files.
- [ ] **Deployment Preparation**
    - [ ] Ensure Blender runs headlessly in the Docker container.
    - [ ] Prepare configuration for Railway (or chosen platform).
    - [ ] Document deployment steps.