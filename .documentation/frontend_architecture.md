# Frontend Architecture: Mobile-First 3D Creation App

## 1. High-Level Summary

The frontend is a **mobile-first, cross-platform application** built using **React Native and Expo**. Its primary purpose for the **MVP (Minimum Viable Product)** is to allow users to **generate 3D models from various inputs (text, image, sketch, photo)** via a Backend-for-Frontend (BFF) that interacts with Tripo AI and OpenAI.

The app handles user authentication (e.g., Clerk) and is designed for intuitive mobile interaction, aiming for future web portability. E-commerce features are excluded.

## 2. Features

*   **User Authentication**: Sign-up, sign-in, profile management (e.g., Clerk React Native SDK).
*   **Creation Hub Screen**:
    *   Serves as the entry point for all model generation methods.
    *   Main UI section tabs:
        *   **Text-to-Model**: Input section for text prompt. Below this, a Style Selector (grid of clickable image icons, see Style Options section 3.1 for examples). Then, a "Generate Concept" checkbox, and finally a "Generate Model" button.
        *   **Image-to-Model**: Input section for image upload, optional text prompt. Below this, a Style Selector (grid of clickable image icons, see Style Options section 3.1 for examples). Then, a "Generate Concept" checkbox, and finally a "Generate Model" button.
        *   **Sketch-to-Model**: Input section for drawing canvas/upload. Below this, a Style Selector (grid of clickable image icons, see Style Options section 3.1 for examples). Then, a "Generate Concept" checkbox, and finally a "Generate Model" button.
        *   **Photo-to-Model**: Input section for image upload (single/multi-view). Below this, a Style Selector (grid of clickable image icons, see Style Options section 3.1 for examples). Finally, a "Generate Model" button.
    *   **Workspace Section**: Access to browse previously generated/saved models. Models currently being generated will appear here with a loading indicator and status updates (e.g., 'Generating Concepts', 'Generating Model').
    *   **Settings Section**: (Placeholder for future settings).
*   **Concept Selection Screen (New)**:
    *   Displayed if "Generate Concept" is checked for Text-to-Model, Image-to-Model, or Sketch-to-Model inputs.
    *   Shows 2D concepts from OpenAI, allows selection for 3D generation via Tripo AI.
*   **3D Viewer Screen (Basic Viewing)**:
    *   Renders the generated `.glb` model from Tripo AI (via BFF).
    *   Basic interaction (rotate, pan, zoom).
    *   Download button (to save the GLB locally).
*   **Loading/Processing Indicators**: For all BFF communications (Tripo AI, OpenAI).
*   **Local Project Management (Simple)**: Save/load generated models locally (as GLBs).
*   **Export & Sharing (Generated Models)**: Export `.glb` (as received from Tripo AI), render snapshot, share via OS dialog.
*   **Navigation**: Standard mobile app navigation.
*   **Account Screen**: Manage user profile.

## 3. Architecture & Components

*   **Framework**: React Native + Expo.
*   **Language**: TypeScript.
*   **UI Components**: React Native UI library (`react-native-paper`).
*   **3D Rendering (Viewing)**: `react-three-fiber` and `@react-three/drei` with `expo-gl` for model display.
*   **State Management**: Zustand, React Context API.
*   **Authentication**: Clerk (React Native SDK).
*   **Data Fetching & Client-Server State**: TanStack Query (React Query).

### Style Options
*   **Available Styles (represented by clickable image icons in the Style Selector)**: None, Cartoon, Simpson, Ghibli, South Park, Muppet, Action Figure, Wooden, Metallic, Claymation, Pixel Art, Abstract.

### API Communication (BFF Centric):
    *   Calls to a **Backend-for-Frontend (BFF)**: Securely houses Tripo AI and OpenAI API keys. Exposes endpoints for:
        *   Text-to-Model generation (Tripo AI, with styles, optional concept generation, `texture` flag).
        *   Image-to-Model generation (Tripo AI, with optional text, styles, optional concept generation, `texture` flag).
        *   Sketch-to-Model generation (Tripo AI, with styles, optional concept generation, `texture` flag).
        *   Photo-to-Model generation (Tripo AI, single/multi-view, `texture` flag).
        *   Image-to-image concept generation (OpenAI Image Generation API, based on user input and style).
### Sketching Canvas (for Sketch-to-Model
    * `react-native-skia` for optimal performance and native feel. It directly utilizes the Skia graphics engine, offering a more responsive and integrated drawing experience crucial for a mobile-first application.
    * Basic white canvas to allow the user to sketch in black. Marker size is fixed.

### Application Structure (Conceptual)
*`CreationHubScreen` is central, leading to `ConceptSelectionScreen` (if concepts are generated) or directly to `3DViewerScreen` for generated models.* By default, concept generation is checked, so the user must uncheck it if they want to bypass. 

## 4. Key Directory Structure (Example React Native/Expo Project)

```
/makeit3d-app-frontend  # Project root
|-- App.tsx                 # Main application component (moved to root)
|-- app.json                # Expo/React Native configuration
|-- package.json            # Project dependencies and scripts
|-- babel.config.js         # Babel compiler configuration
|-- tsconfig.json           # TypeScript configuration
|-- /src                    # Main source code directory
|   |-- /assets             # Static assets (images, fonts, initial models)
|   |-- /components         # Reusable UI components
|   |   |-- /creation       # Components for model generation flows
|   |   |   |-- TextToModelForm.tsx
|   |   |   |-- ImageToModelForm.tsx
|   |   |   |-- SketchToModelForm.tsx
|   |   |   |-- PhotoToModelForm.tsx
|   |   |   |-- StyleSelector.tsx
|   |   |   `-- SketchCanvas.tsx
|   |   |-- /editor         # Components for the 3D viewer
|   |   |   `-- ModelViewer.tsx # Core R3F scene for viewing
|   |   |-- /project        # Components for local project/model management
|   |   |-- /ui             # Generic UI elements (buttons, modals, etc.)
|   |   `-- /shared         # Components shared across multiple features
|   |-- /config             # Application configuration, constants, env vars (e.g., BFF base URL). API keys themselves are NEVER stored here; they reside securely on the BFF server.
|   |-- /hooks              # Custom React hooks
|   |-- /navigation         # Navigation setup (e.g., React Navigation)
|   |-- /screens            # Top-level screen components
|   |   |-- CreationHubScreen.tsx
|   |   |-- ConceptSelectionScreen.tsx
|   |   |-- EditorScreen.tsx      # For 3D model viewing and interaction
|   |   `-- AccountScreen.tsx
|   |-- /services           # API service clients
|   |   |-- bffService.ts     # For BFF communication
|   |   `-- authService.ts    # For authentication
|   |-- /state              # Global state management (Zustand, Context API)
|   |-- /styles             # Global styles, themes
|   |-- /types              # TypeScript type definitions
|   |-- /utils              # Utility functions
|-- /web                    # Entry point and configuration for Expo Web
|-- README.md               # Project README
...                         # Other project root files (e.g., .gitignore)
```
*(Other files remain similar to previous revision)*

## 5. User & Sequence Flows

*   **Authentication**: Unchanged.

*   **Model Generation & Preparation**:

    *   **Common Steps**:
        1.  **User Action (CreationHubScreen)**: Selects an X-to-Model tab, provides inputs (text, image, sketch, photo), selects a style from the Style Selector, optionally checks 'Generate Concept' (for Text, Image, Sketch), and clicks 'Generate Model'. **The application navigates the user to the Workspace Section within the Creation Hub Screen, where the new generation job appears with a loading status (e.g., 'Initializing...').**
        2.  **System Action (Client -> BFF)**: App sends generation request to BFF (status updates in Workspace, e.g., 'Sending to server...'). The BFF requests the generation from the appropriate AI service.
        3.  **System Action (BFF -> Tripo AI / OpenAI)**: BFF calls appropriate AI service(s) to initiate generation. (Workspace status updates reflect the AI service's progress, e.g., 'Generating Concepts' or 'Generating Model').

    *   **Flow A: Direct to 3D Model (e.g., Photo-to-Model, or Text/Image/Sketch-to-Model with 'Generate Concept' unchecked)**:
        4.  **AI Service -> BFF**: Tripo AI finishes generation and provides a temporary URL for the 3D model data (e.g., GLB URL).
        5.  **BFF -> Client**: Returns the temporary GLB URL to the client.
        6.  **Client Action**: Receives the temporary URL. **Downloads the GLB file from the temporary URL.** (Workspace status: 'Downloading Model...')
        7.  **Client Action**: **Uploads the downloaded GLB to Supabase Storage.** (Workspace status: 'Saving Model...')
        8.  **Client**: Displays the model from the local download (or Supabase URL) in `EditorScreen` (basic viewer). Model can be saved locally (if not already saved by the Supabase upload). **The Workspace Section updates to show the completed model, replacing the loading indicator and showing a thumbnail.**

    *   **Flow B: With 2D Concept Phase (e.g., Text/Image/Sketch-to-Model with 'Generate Concept' checked)**:
        4.  **BFF -> OpenAI Image Generation API**: Requests 2D concepts. (Workspace status: 'Generating Concepts')
        5.  **OpenAI -> BFF**: Returns concept image URLs.
        6.  **BFF -> Client**: Returns concept image URLs.
        7.  **Client**: Navigates to `ConceptSelectionScreen`. (Workspace status might indicate 'Awaiting Concept Selection')
        8.  **User Action (ConceptSelectionScreen)**: Selects a concept.
        9.  **Client -> BFF**: Sends selected concept for 3D model generation. (Workspace status: 'Sending to server...')
        10. **BFF -> Tripo AI**: Calls Tripo AI for 3D model from concept, initiating generation. (Workspace status: 'Generating Model')
        11. **Tripo AI -> BFF**: Tripo AI finishes generation and provides a temporary URL for the 3D model data.
        12. **BFF -> Client**: Returns the temporary GLB URL.
        13. **Client Action**: Receives the temporary URL. **Downloads the GLB file from the temporary URL.** (Workspace status: 'Downloading Model...')
        14. **Client Action**: **Uploads the downloaded GLB to Supabase Storage.** (Workspace status: 'Saving Model...')
        15. **Client**: Displays the model from the local download (or Supabase URL) in `EditorScreen` (basic viewer). Model can be saved locally (if not already saved by the Supabase upload). **The Workspace Section updates to show the completed model, replacing the loading indicator and showing a thumbnail.**

## 6. Technical Considerations

*   **Focus**: Ensuring the BFF handles all AI generation calls reliably.
*   **Performance on Mobile**: Efficiently handling GLB display.
*   **API Key Security**: BFF is critical for Tripo AI & OpenAI keys.
*   **Asynchronous Communication**: For all backend (BFF) calls.
*   **Tripo AI / OpenAI API Capabilities**: As previously noted.
*   *Other considerations from previous revision remain relevant.*

## 7. Frontend-BFF API Endpoints

The frontend communicates with the Backend-for-Frontend (BFF) using the following key endpoints. The BFF handles the interaction with external AI services (Tripo AI, OpenAI) and provides temporary URLs for assets, while the frontend handles downloading these assets and uploading them to Supabase Storage.

*   **POST /generate/image-to-image**: Initiates a 2D image concept generation process using OpenAI, typically for creating concepts. Includes input image, text prompt, and style.
*   **POST /generate/text-to-model**: Initiates a text-to-3D model generation process. Includes text prompt, style, and an option to generate 2D concepts first.
*   **POST /generate/image-to-model**: Initiates an image-to-3D model generation process. Includes input image, optional text prompt, style, and an option to generate 2D concepts first.
*   **POST /generate/sketch-to-model**: Initiates a sketch-to-3D model generation process. Includes sketch input, style, and an option to generate 2D concepts first.
*   **POST /generate/photo-to-model**: Initiates a photo-to-3D model generation process. Includes single or multi-view photo input and style.
*   **POST /generate/select-concept**: Sends a selected 2D concept (from the concept generation step) to the BFF to initiate the final 3D model generation.
*   **GET /status/{task_id}**: Polls the BFF for the status of a specific generation task. The BFF, in turn, polls the external AI services for their status.

## 8. Implementation Tasks (High-Level)

### Phase 1: Core App Setup & Generation Flows
*   [ ] Setup React Native + Expo project, Navigation, Clerk.
*   [ ] **BFF Development (Parallel)**: Endpoints for Text-to-Model (incl. optional concepts via OpenAI), Image-to-Model (incl. optional concepts via OpenAI), Sketch-to-Model (incl. optional concepts via OpenAI), Photo-to-Model (all via Tripo AI for 3D).
*   [ ] Implement `CreationHubScreen` with all generation forms/tabs.
*   [ ] Implement `StyleSelector` component.
*   [ ] Implement `ConceptSelectionScreen`.
*   [ ] Implement `EditorScreen` (Basic GLB viewer for `Mesh_A`).
*   [ ] Integrate all generation flows (Client -> BFF -> AI Services -> Client).
*   [ ] Implement local save/load, export, share for generated models.

### Phase 2: Polish & Refine
*   [ ] Refine UI/UX for all flows.
*   [ ] Comprehensive error handling.
*   [ ] Performance optimization.

---
*This document will evolve as development progresses and new technical decisions are made.*