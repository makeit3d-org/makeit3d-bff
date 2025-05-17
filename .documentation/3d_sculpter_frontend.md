# 3D Sculpter Frontend Architecture - Prototype

## Overview

This document describes the architecture for a **Putty 3D clone** cross platform mobile app for iOS, Android and web. The app name is makeit3d. We will initially target web for prototyping, then move on to iOS, then Android. The app enables users to load, sculpt, compress, and upload 3D models in `.glb` format. Implementation is to be done in the two phases outlined in the task lists below. 


## Backend Interaction & Purpose

The frontend interacts with a backend service to offload computationally intensive mesh processing tasks. The backend provides:
- **Mesh Cleanup & Remeshing:** Ensures imported meshes are clean, manifold, and have optimal topology for sculpting. Triggered manually by the user before sculpting.
- **Color Transfer (Texture to Vertex Color):** Transfers color/texture information from the original model to the sculpted mesh's vertices. This is automatically triggered when the user switches from Sculpting Mode to Coloring Mode, preparing the mesh for client-side vertex painting.

**Endpoints Used:**
- `POST /process/remesh` — Uploads a `.glb` file for mesh cleanup and remeshing. Returns a cleaned `.glb` file. Triggered manually by the user.
- `POST /process/transfer-colors` — Uploads a sculpted `.glb`, original `.glb`, and texture (if not included in `.glb`). Returns a `.glb` with vertex colors, ready for client-side painting. Triggered automatically when entering Coloring Mode.

## Technology Stack

| Tool                  | Purpose                                      |
|-----------------------|----------------------------------------------|
| React Native          | Core framework for mobile UI                 |
| Expo                  | Toolkit for React Native development         |
| expo-gl               | OpenGL bindings for React Native (via Expo)  |
| three.js              | JavaScript 3D engine                         |
| react-three-fiber     | React renderer for three.js                  |
| @react-three/drei     | Helper components for R3F                    |

## User Journey & Workflow

1.  **Launch App**: User is presented with a model picker screen showing available stock `.glb` files and any user-uploaded `.glb` files.
2.  **Select or Upload Model**: User selects a `.glb` file from the list or uploads a new one.
3.  **Preview & Manual Remesh**: The selected model is immediately displayed in a preview/viewport. The user can manually trigger remeshing by pressing a "Remesh" button, which uploads the mesh to the backend for cleanup/remeshing (`POST /process/remesh`).
4.  **Enter Sculpting Mode**: Upon receiving the remeshed model from the backend, the app loads it into the editor, defaulting to Sculpting Mode.
5.  **Sculpt**: User uses sculpting tools (Add, Subtract, Smooth, Flatten, Move, Mirror). Changes are local and affect mesh geometry.
6.  **Switch to Coloring Mode**: User selects a "Coloring Mode" toggle/button.
    -   This action automatically triggers an upload of the current sculpted mesh and the original model/texture to the backend (`POST /process/transfer-colors`).
    -   The backend transfers color data from the original texture to the sculpted mesh's vertex colors.
    -   The app receives the `.glb` file now containing vertex colors.
7.  **Enter Coloring Mode**: The app loads the mesh (with vertex colors) into the editor, now in Coloring Mode.
8.  **Paint**: User uses a color brush tool (with adjustable size and a color palette/picker) to paint directly onto the model's vertex colors. All painting is done locally on the client-side.
9.  **Switch Modes (Optional)**: User can toggle back to Sculpting Mode. Vertex colors applied are retained. Further sculpting may require re-entering Coloring Mode (and thus re-triggering color transfer) if the topology changes significantly and original texture colors need to be re-projected onto the new geometry.
10. **Save/Export**: User can save the current project locally (this should save the mesh in its current state, including sculpts and any applied vertex colors) or export the final `.glb` file, which will include the sculpted shape and the vertex colors.

## UI Structure

-   **Model Picker Screen**: Displays a list of available stock `.glb` files and any user-uploaded `.glb` files. Allows user to select or upload a model.
-   **Model Preview Screen**: Shows the selected model in a viewport and provides a "Remesh" button to manually trigger remeshing.
-   **Editor Screen**:
    -   **Mode Toggle**: A clear UI element (e.g., tabs, a segmented control, or a toggle button) to switch between "Sculpting Mode" and "Coloring Mode".
    -   **3D Viewport**: Displays the 3D model (react-three-fiber).
    -   **Contextual Toolbar (changes based on mode)**:
        -   **Sculpting Mode Toolbar**: Contains tools like Add/Draw, Subtract, Smooth, Flatten, Move. Includes brush settings (size, strength) and Mirror mode toggle.
        -   **Coloring Mode Toolbar**: Contains the Color Brush tool. Includes brush settings (size) and a Color Palette/Picker for selecting paint colors.
    -   **Undo/Redo Buttons**: Should ideally function within the context of the current mode, though global undo/redo could be considered (might be more complex).
    -   **Save/Export Buttons**: To save the project or export the `.glb`.
-   **Project Management**: UI for local save/load of projects.

---

## Appendix: Repository Structure

### Frontend Directory Structure (React Native + Expo, Web/iOS/Android)

```
/makeit3d-frontend
|-- App.tsx
|-- app.json                # Expo/React Native config
|-- package.json
|-- babel.config.js
|-- tsconfig.json
|-- /src
|   |-- /assets             # Images, icons, fonts, sample models
|   |-- /components        # Reusable UI components
|   |   |-- /editor        # Sculpting tools, brush settings, 3D viewport
|   |   |-- /ui            # Buttons, modals, sliders, etc.
|   |   |-- /project       # Project save/load dialogs
|   |-- /screens           # App screens (Home, Editor, ProjectManager, etc.)
|   |-- /hooks             # Custom React hooks (e.g., useSculpting, useUndoRedo)
|   |-- /services          # API clients (backend, optional mesh compression, file I/O)
|   |-- /state             # Zustand or Redux stores, context providers
|   |-- /types             # TypeScript types/interfaces
|   |-- /utils             # Utility functions (math, mesh helpers, etc.)
|   |-- /navigation        # React Navigation setup
|   |-- /config            # App config, constants, environment
|-- /web                   # Web entry point (if using Expo for Web)
|-- README.md
```

---

## Implementation Tasks

### Phase 1: Core Sculpting Editor (Local Only, No Backend/Color)

- [ ] **Project Setup (React Native + Expo + Web)**
    - [ ] Initialize Expo project.
    - [ ] Setup `three.js`, `react-three-fiber`, `@react-three/drei`.
    - [ ] Basic navigation structure (`Model Picker` -> `Editor Screen`).
- [ ] **Model Loading & Display (Local)**
    - [ ] Implement `.glb` file picker/loader (use sample local `.glb` initially).
    - [ ] Display model in `react-three-fiber` viewport.
    - [ ] Basic camera controls (orbit, pan, zoom).
- [ ] **Sculpting Mode UI (Editor Screen)**
    - [ ] Static UI for Sculpting Mode (no mode switching yet).
    - [ ] Placeholder buttons for sculpt tools (Add, Subtract, Smooth, Flatten, Move).
    - [ ] Basic brush settings UI (size, strength) - non-functional initially.
- [ ] **Core Sculpting Logic (Client-Side)**
    - [ ] Implement raycasting for brush interaction with the mesh.
    - [ ] Develop basic "Add/Draw" sculpt tool (vertex displacement along normal).
    - [ ] Develop basic "Subtract" sculpt tool (vertex displacement inverse to normal).
    - [ ] Develop "Smooth" sculpt tool (Laplacian smoothing or similar).
    - [ ] (Optional Stretch) Implement "Flatten" and "Move" tools.
- [ ] **Basic Undo/Redo**
    - [ ] Implement a simple history stack for mesh state changes.
    - [ ] Add Undo/Redo buttons and functionality for sculpting operations.
- [ ] **Local Project Stub**
    - [ ] Placeholder for saving/loading sculpt (no actual persistence yet).

### Phase 2: Backend Integration, Coloring & Full Workflow

- [ ] **Backend Integration (`/process/remesh`)**
    - [ ] Implement API service client in `/services`.
    - [ ] Add "Remesh" button functionality on `Model Preview Screen` or `Editor Screen` to call backend.
    - [ ] Handle `.glb` upload and download for remeshing.
    - [ ] Update viewport with remeshed model.
- [ ] **Mode Switching (Sculpting/Coloring)**
    - [ ] Implement UI for switching between Sculpting and Coloring modes.
    - [ ] Adapt toolbar to show context-specific tools.
- [ ] **Backend Integration (`/process/transfer-colors`)**
    - [ ] Trigger `/process/transfer-colors` call when switching to Coloring Mode.
    - [ ] Handle upload of sculpted mesh and original mesh/texture.
    - [ ] Load resulting `.glb` with vertex colors.
- [ ] **Coloring Mode UI & Logic (Client-Side)**
    - [ ] Implement Color Brush tool.
    - [ ] Implement color palette/picker UI.
    - [ ] Allow painting directly on vertex colors (modifying `mesh.geometry.attributes.color`).
    - [ ] Brush settings for color (size).
- [ ] **Project Management (Local Save/Load)**
    - [ ] Implement local project saving (serialize current mesh state, including sculpts and vertex colors).
    - [ ] Implement local project loading.
- [ ] **Export `.glb`**
    - [ ] Implement functionality to export the current model (sculpted + vertex colors) as a `.glb` file.
- [ ] **Refinements & Polish**
    - [ ] Improve Undo/Redo to be mode-aware or handle global state carefully.
    - [ ] Add Mirror sculpting mode.
    - [ ] UI/UX polish based on testing.
    - [ ] Basic error handling for API calls.
- [ ] **Testing**
    - [ ] Test sculpting tools thoroughly.
    - [ ] Test coloring tools and vertex color persistence.
    - [ ] Test backend interactions for remeshing and color transfer.
    - [ ] Test file import/export.
