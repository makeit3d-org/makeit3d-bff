# Frontend Architecture: Mobile-First 3D Creation App 

## 1. High-Level Summary

The frontend is a **mobile-first, cross-platform application** built using **React Native and Expo**. Its primary purpose for the **MVP (Minimum Viable Product)** is to allow users to **generate 3D models primarily from sketch input**, combined with text prompts and style selections, via a Backend-for-Frontend (BFF) that interacts with Tripo AI and OpenAI.

**Key Architectural Principles (aligned with BFF API v1.1.0):**
*   **Client-Generated `task_id`**: For each new generation job/workspace item, the client generates a unique `task_id`.
*   **Client Manages Supabase Records**: The client is responsible for creating and managing records in its own Supabase tables (`input_assets`, `concept_images`, `models`) to track the overall job and its associated assets.
*   **Inputs via Supabase**: For sketch inputs (and optional background images), the client uploads the asset(s) to its Supabase Storage first, creates a record in `input_assets` with the asset URL(s), and then provides this URL to the BFF.
*   **Polling & Status**: The client polls the BFF's `/tasks/{task_id}/status?service={service}` endpoint for real-time AI step status. Upon completion of an AI step by the BFF (which includes storing the asset in Supabase Storage and updating the respective metadata table like `models`), the client retrieves the final asset URL. The client primarily uses its own Supabase tables (`input_assets`, `concept_images`, `models`) as the source of truth for persisted asset locations and statuses.

The app handles user authentication (e.g., Supabase Auth) and is designed for intuitive mobile interaction.

## 2. Features

*   **User Authentication**: Sign-up, sign-in, profile management (using Supabase Auth). Supports email/password, and potentially OAuth providers (e.g., Google, Apple).
*   **Supabase Integration**: Client directly interacts with its Supabase instance for:
    *   Uploading sketch data (e.g., as SVG or points) and optional background images to Supabase Storage.
    *   Creating and managing records in `input_assets` and `models` tables (tracking `task_id`, prompts, styles, asset URLs, statuses). The `concept_images` table may be used if the live preview image is persisted.
*   **Home Screen**:
    *   **Main Navigation**: 
        *   Sketch to 3D (Primary Button)
        *   Sculpt Model (Button)
        *   Color Model (Button)
    *   **Sculpt Model Modal**: (Accessed via "Sculpt Model" button) Floating screen with options to load existing model (from workspace/public) or start from scratch (basic sphere).
    *   **Color Model Modal**: (Accessed via "Color Model" button) Floating screen with options to load existing model without texture for coloring workflow.
    *   **Your Workspace Section**: Mini previews prioritizing pending/processing models with status indicators, delete options, and "View All" button.
    *   **Explore Models Section**: Horizontal scroll of available stock models and community shared models (post-MVP).
*   **Sketch to 3D Screen**:
    *   User creates a sketch on a canvas, inputs an optional text prompt, selects a style, and can optionally upload a background image.
    *   A live concept preview is rendered in the control panel based on these inputs.
    *   Client generates `task_id`, creates record in `input_assets` (type: 'sketch', storing sketch data URL, background image URL if any, and prompt).
    *   **Style Options**: None, Ghibli, Simpson, South Park, Anime, Cartoon, Claymation, Muppet, Metal, Wood, Glass.
    *   **Layout (Tablet/Desktop)**:
        *   **Left Control Panel**: Contains "Background" upload, "Style" selector, "Prompt" input, and a "Preview" area showing the live updating single concept image.
        *   **Right Sketch Area**: Large "Sketch Canvas" for drawing, with an integrated "Generate 3D Model" button.
*   **Workspace Screen**: 
    *   Full view of all user models with infinite scrolling.
    *   Status indicators (pending, processing, complete).
    *   **Smart Model Navigation**: Clicking a model takes user to:
        *   Pending/Processing jobs → Sketch to 3D Screen (to continue/monitor).
        *   Complete jobs → 3D Sculpting Viewer.
*   **3D Sculpting Viewer**: Renders `.glb` models using Supabase URLs (from `models` table) and integrates with existing sculpting tools.
*   **Loading/Processing Indicators**: Real-time status updates for BFF calls (polling `/tasks/{task_id}/status`) and client-side Supabase operations.

## 3. Architecture & Components

*   **Framework**: React Native + Expo.
*   **Language**: TypeScript for new features, JavaScript for existing sculpting tools.
*   **UI Components**: Existing UI components, enhanced with new TypeScript components.
*   **Sketching**: `react-native-skia` for the sketching canvas and handling sketch data.
*   **3D Rendering**: `react-three-fiber`, `@react-three/drei`, `expo-gl`.
*   **State Management**: **Redux Toolkit** (extending existing store with new TypeScript slices for API features).
*   **Authentication**: Supabase Auth (via `@supabase/supabase-js` library). 
    *   Project: MakeIt3D (configured via environment variables)
    *   Anon Key: Configured via environment variables for JWT validation
    *   Utilizes AsyncStorage or SecureStore for session persistence
    *   JWT tokens sent to BFF via Authorization header
*   **Data Fetching & Client-Server State**: Redux Toolkit Query (RTK Query) for API calls, integrated with existing Redux store.
*   **Supabase Client Library**: For direct database and storage interaction.

### API Communication (BFF Centric - Refactored for Sketch):
    *   **Authentication**: Client includes JWT token in `Authorization: Bearer <token>` header for all BFF requests.
    *   Client generates `task_id` for each job.
    *   For sketch inputs: Client uploads sketch data (e.g., SVG) and optional background image to its Supabase Storage, creates a record in its `input_assets` table, then calls BFF with the `task_id` and the asset Supabase URLs.
    *   Calls BFF endpoint `/generate/sketch-to-image` with `task_id` and relevant parameters (including Supabase URLs for sketch and background image, plus text prompt).
    *   **Parallel Concept Generation**: Optionally calls `/generate/image-to-image` as a parallel call for quick iteration if the main sketch-to-image is slower.
    *   **User Isolation**: BFF validates JWT token and extracts `user_id` to ensure data isolation via RLS policies.
    *   Polls BFF `GET /tasks/{task_id}/status?service=tripo` (or relevant AI service for sketch) for real-time AI step status.
    *   BFF, upon completing an AI step, stores the output asset in Supabase Storage and updates the client's `models` table (including status and final asset URL).
    *   Client primarily queries its own Supabase tables (`input_assets`, `models`) to display persisted job status and asset URLs. The live concept preview might involve a separate, faster `/generate/image-to-image` style call for quick iteration if the main sketch-to-image is slower.

### Sketching Canvas (for Sketch-to-Image)
    * `react-native-skia`.

## 4.5. UI Design & Wireframes

For detailed UI wireframes, design specifications, and responsive layout information, see the dedicated UI design document: [`frontend_ui_sketch.md`](./frontend_ui_sketch.md)

This includes:
- Complete wireframes for all screens (Home, Sketch to 3D, Workspace, Modals)
- Responsive design specifications for different device sizes
- Component design specifications and interaction patterns
- Style selector layouts and generation options
- Accessibility considerations

## 4. Current Directory Structure & Integration Plan

**Current Structure (JavaScript-based sculpting tools with Redux):**
```
/makeit3d-frontend
|-- App.js                     # Main app entry point (existing)
|-- package.json               # Dependencies (existing, includes Redux Toolkit, react-native-skia)
|-- babel.config.js            # Babel config (existing)
|-- /assets                    # Static assets (existing)
|-- /src
|   |-- /components            # Reusable UI components (existing)
|   |   |-- /editor            # Sculpting editor components (existing JS)
|   |   |   |-- BrushVisual.js
|   |   |   |-- Model3D.js
|   |   |   |-- ModelViewer.js
|   |   |-- /ui                # Generic UI elements (existing)
|   |-- /config                # App configuration (existing)
|   |   |-- theme.js           # UI theme (existing)
|   |-- /features              # Feature modules (existing)
|   |   |-- /advanced-editor   # Advanced sculpting features (existing JS)
|   |   |   |-- /screens
|   |   |   |   |-- AdvancedEditorScreen.js
|   |   |   |-- /components
|   |-- /hooks                 # Custom React hooks (existing)
|   |-- /navigation            # Navigation setup (existing)
|   |   |-- AppNavigator.js
|   |-- /screens               # Top-level screens (existing)
|   |   |-- ModelPickerScreen.js  # Recently refactored with Redux integration
|   |-- /state                 # Redux state management (existing)
|   |   |-- store.js           # Redux store configuration (existing)
|   |   |-- slices/            # Redux slices (existing)
|   |   |   |-- appSlice.js    # Global app state (existing)
|   |   |   |-- editorSlice.js # Sculpting tools state (existing)
|   |   |   |-- modelSlice.js  # Current model state (existing)
|   |-- /utils                 # Utility functions (existing)
|   |   |-- UndoRedoManager.js # Recently improved (existing)
```

**New API Integration Structure (TypeScript additions extending Redux - Sketch Focus):**
```
/makeit3d-frontend
|-- /src
|   |-- /api                   # NEW: API service definitions (TypeScript)
|   |   |-- bffClient.ts       # Axios/fetch instance for BFF
|   |   |-- supabaseClient.ts  # Supabase JS client instance
|   |   |-- bffApi.ts          # RTK Query API slice for BFF endpoints
|   |   |-- supabaseApi.ts     # RTK Query API slice for Supabase operations
|   |-- /components
|   |   |-- /modals            # NEW: Modal components (TypeScript)
|   |   |   |-- SculptModelModal.tsx
|   |   |   |-- ColorModelModal.tsx
|   |   |-- /generation        # NEW: Model generation components (TypeScript)
|   |   |   |-- StyleSelector.tsx
|   |   |   |-- SketchCanvas.tsx        # NEW: react-native-skia based canvas
|   |   |   |-- BackgroundImagePicker.tsx # NEW: For sketch background
|   |   |   |-- LiveConceptPreview.tsx  # NEW: Displays updating concept image
|   |   |-- /shared            # NEW: Enhanced reusable components (TypeScript)
|   |   |   |-- ModelPicker.tsx # Extracted from existing ModelPickerScreen
|   |   |   |-- ModelCard.tsx   # Reusable model display component
|   |-- /features
|   |   |-- /model-generation  # NEW: Model generation feature (TypeScript)
|   |   |   |-- /components
|   |   |   |-- /hooks         # useAppSelector, useAppDispatch wrappers
|   |   |   |-- /screens
|   |   |   |   |-- HomeScreen.tsx
|   |   |   |   |-- SketchToModelScreen.tsx    # NEW
|   |   |   |   |-- WorkspaceScreen.tsx
|   |-- /hooks
|   |   |-- useSupabaseAuth.ts # NEW: Supabase auth hook
|   |   |-- useTypedSelector.ts # NEW: Typed Redux hooks
|   |-- /state                 # EXTENDED: Redux state management
|   |   |-- store.ts           # UPDATED: TypeScript store configuration
|   |   |-- rootReducer.ts     # UPDATED: Combined reducers with types
|   |   |-- slices/            # EXTENDED: Redux slices
|   |   |   |-- appSlice.js    # EXISTING: Global app state
|   |   |   |-- editorSlice.js # EXISTING: Sculpting tools state
|   |   |   |-- modelSlice.js  # EXISTING: Current model state
|   |   |   |-- generationSlice.ts # UPDATED: Model generation state (sketch focus)
|   |   |   |-- workspaceSlice.ts  # NEW: Workspace management state
|   |   |   |-- authSlice.ts   # NEW: Authentication state
|   |-- /types                 # NEW: TypeScript types
|   |   |-- api.ts             # BFF API types (sketch focus)
|   |   |-- supabase.ts        # Supabase table types
|   |   |-- redux.ts           # Redux state types
|   |   |-- domain.ts          # Core domain types (sketch focus)
|-- tsconfig.json              # NEW: TypeScript configuration
|-- .env                       # NEW: Environment variables
```

**Integration Strategy:**
- **Extend existing Redux store** - add new TypeScript slices alongside existing JavaScript slices.
- **Focus on `react-native-skia`** for `SketchCanvas.tsx`.
- **Reuse existing patterns** - leverage recent Redux refactoring for new components.
- **Keep existing sculpting tools in JavaScript**.
- **Add new TypeScript features for sketch-to-image**.
- **Extend existing navigation** - update `AppNavigator.js` to include `SketchToModelScreen.tsx`.
- **Shared state management** - unified Redux store.

## 5. User & Sequence Flows (Refactored for Sketch Focus)

**Home Screen Flow**:
1.  **User Action**: Opens app, sees Home Screen with main "Sketch to 3D" button, and secondary "Sculpt Model", "Color Model" buttons.
2.  **User Action**: Can either:
    *   Click "Sketch to 3D" → Navigate to Sketch to 3D Screen.
    *   Click "Sculpt Model" → Open Sculpt Model Modal.
    *   Click "Color Model" → Open Color Model Modal.
    *   Click on a model in Workspace section → Smart navigation based on status.
    *   Click "View All" in Workspace section → Navigate to full Workspace Screen.
    *   Click on model in Explore Models section → Load directly into relevant viewer/editor.

**Model Creation Flow (Sketch to 3D Screen)**:
1.  **User Action**: User is on the `SketchToModelScreen`.
    *   Optionally uploads a background image.
    *   Draws a sketch on the `SketchCanvas`.
    *   Optionally types a text prompt.
    *   Selects a style.
2.  **Client Action (Live Preview)**: As user interacts (sketches, types prompt, selects style), client sends data (sketch data, prompt, style, background image URL) to a BFF endpoint (e.g., `/generate/image-to-image` or a dedicated fast concept endpoint).
3.  **BFF**: Quickly generates a 2D concept image.
4.  **Client Action**: Displays the returned single concept image in the "Preview" area of the control panel, updating it live.
5.  **User Action**: When satisfied with the sketch and live concept preview, clicks "Generate 3D Model" button in the sketch area.
6.  **Client Action**: Generates a unique `task_id` for this 3D generation job.
7.  **Client Action**: Uploads the final sketch data (e.g., as SVG) and background image (if used) to its Supabase Storage. Gets the Supabase URL(s).
8.  **Client Action**: Creates a record in its `input_assets` Supabase table for this `task_id`, including prompt, style, input type ('sketch'), and the Supabase URL(s) of the sketch and background image. Sets initial status 'pending'.
9.  **Client -> BFF**: Calls BFF generation endpoint `/generate/sketch-to-image` with `task_id`, Supabase URL of sketch, Supabase URL of background image (if any), text prompt, and selected style.
10. **BFF**: (Internally) Creates/updates a record in its `models` table for this `task_id` with status 'processing'. Calls Tripo AI (or other relevant sketch-to-3D AI).
11. **Client**: Polls `GET /tasks/{task_id}/status?service=tripo` (or relevant service). Sketch screen shows status (e.g., 'Generating Model').
12. **BFF (on Tripo AI completion)**: Downloads model, uploads to client's Supabase Storage, updates the record in `models` table with the final Supabase `asset_url` and status 'complete'.
13. **Client (on seeing 'complete' status from polling or by observing `models` table)**: Retrieves the model's Supabase URL from the `models` table. Displays model in `SculptingViewerScreen`.

## 6. Technical Considerations

### Redux Integration Strategy

*   **Unified State Management**: Extend existing Redux store with new TypeScript slices.
*   **State Shape Extension (Sketch Focus)**:
    ```typescript
    interface RootState {
      app: AppState;           // existing (JS)
      editor: EditorState;     // existing (JS)
      model: ModelState;       // existing (JS)
      generation: GenerationState; // UPDATED (TS) - sketch focus
      workspace: WorkspaceState;   // NEW (TS)
      auth: AuthState;         // NEW (TS)
    }

    interface GenerationState {
      currentTaskId: string | null;
      generationType: 'sketch' | null; // Primarily 'sketch'
      inputData: {
        sketchDataUrl?: string;     // URL of persisted sketch (e.g., SVG on Supabase)
        rawSketchData?: any;        // Temporary raw data from skia canvas for live preview
        backgroundImageUrl?: string; // URL of background image on Supabase
        textPrompt?: string;
      };
      options: {
        style: StyleOption | null;
      };
      liveConceptPreviewUrl: string | null; // URL of the live updating concept image
      status: 'idle' | 'live_previewing' | 'uploading_inputs' | 'generating_3d' | 'polling' | 'complete' | 'error';
      error: string | null;
    }
    ```
*   **Component Reusability**: Extract model picker logic.
*   **Loading State Coordination**: Integrate new API polling states.

### API & Data Management

*   **RTK Query Integration**: Use for API calls.
*   **Client-Side Supabase Logic**: Handle Supabase operations.
*   **State Synchronization**: Ensure UI reflects state.
*   **Polling Strategy**: Implement polling.
*   **Live Concept Preview API**: May need a separate, fast BFF endpoint for the live concept image generation, distinct from the final sketch-to-3D model generation call.

## 7. Frontend-BFF API Endpoints (Summary - Sketch Perspective)

(Refer to `makeit3d-api.md` for full details, assuming it will be updated for sketch)
*   Client sends `task_id` and Supabase URLs for sketch and optional background image to:
    *   `POST /generate/sketch-to-image` (for final 3D model)
*   Client might send sketch data, prompt, style to a fast endpoint like:
    *   `POST /generate/concept-from-sketch` (or similar, for live preview image)
*   Client polls `GET /tasks/{task_id}/status?service={service}` for 3D model generation status.
*   Client uses its Supabase tables (`input_assets`, `models`) for persisted data.

## 8. Implementation Tasks (Structured for Sketch-to-3D)

### Phase 1: Foundation & Infrastructure Setup (Largely Same)

#### 1.1 Critical Security & Auth Setup
*   [ ] **CRITICAL: Execute RLS fix SQL**
*   [ ] Setup Supabase client
*   [ ] Setup Supabase Auth
*   [ ] Implement JWT token handling
*   [ ] Implement deep linking

#### 1.2 TypeScript & Development Environment
*   [ ] Add TypeScript configuration (`tsconfig.json`)
*   [ ] Install TypeScript, `react-native-skia`, Redux Toolkit Query
*   [ ] Install Supabase client library (`@supabase/supabase-js`)
*   [ ] Create TypeScript definitions for existing Redux slices

#### 1.3 Redux Store Extension & State Management (Sketch Focus)
*   [ ] Convert `store.js` to `store.ts`
*   [ ] Create `rootReducer.ts`
*   [ ] Update/Add slices: `generationSlice.ts` (sketch focus), `workspaceSlice.ts`, `authSlice.ts`
*   [ ] Create typed Redux hooks
*   [ ] Define sketch-focused state in `generationSlice.ts` (sketch data, background image, live concept URL)

#### 1.4 API Infrastructure (RTK Query)
*   [ ] Create `/src/api/` directory
*   [ ] Implement `supabaseClient.ts`, `bffClient.ts`
*   [ ] Create RTK Query API slices (`bffApi.ts`, `supabaseApi.ts`)
*   [ ] Define TypeScript types in `/src/types/` (sketch focus)

### Phase 2: Core UI Components & Sketch Functionality

#### 2.1 Authentication UI Components (Same)
*   [ ] Create UI components for login, sign-up, profile
*   [ ] Add auth state management, protected routes, error handling

#### 2.2 Component Extraction & Shared Components (Same)
*   [ ] Extract `ModelPicker.tsx`
*   [ ] Create `ModelCard.tsx`

#### 2.3 Sketch Generation Components
*   [ ] Create `/src/components/generation/SketchCanvas.tsx` using `react-native-skia`
    *   [ ] Implement drawing tools (pen, eraser, colors if applicable)
    *   [ ] Method to export sketch data (e.g., as SVG string or point data)
    *   [ ] Handle touch/stylus input
*   [ ] Create `/src/components/generation/StyleSelector.tsx` (if not already generic)
*   [ ] Create `/src/components/generation/BackgroundImagePicker.tsx`
*   [ ] Create `/src/components/generation/LiveConceptPreview.tsx` (displays single image)
*   [ ] Add text input component for prompt in Sketch to 3D screen control panel

### Phase 3: Sketch to 3D Screen Implementation

#### 3.1 Home Screen Implementation (Sketch Focus)
*   [ ] Create `/src/features/model-generation/screens/HomeScreen.tsx`
*   [ ] Implement main navigation: "Sketch to 3D", "Sculpt Model", "Color Model"
*   [ ] Ensure "Sketch to 3D" navigates to `SketchToModelScreen.tsx`
*   [ ] Create modals: `SculptModelModal.tsx`, `ColorModelModal.tsx`
*   [ ] Implement Workspace & Explore Models sections

#### 3.2 Sketch to 3D Screen
*   [ ] Create `/src/features/model-generation/screens/SketchToModelScreen.tsx`
*   [ ] Implement layout: Left control panel (Background, Style, Prompt, Live Preview), Right Sketch Canvas area.
*   [ ] Integrate `SketchCanvas.tsx` into the right area.
*   [ ] Integrate `BackgroundImagePicker.tsx` in control panel.
*   [ ] Integrate `StyleSelector.tsx` in control panel.
*   [ ] Implement prompt input in control panel.
*   [ ] Integrate `LiveConceptPreview.tsx` in control panel.
*   [ ] Implement "Generate 3D Model" button in sketch canvas area.
*   [ ] Connect control panel inputs (sketch data from canvas, background, prompt, style) to Redux state.

### Phase 4: Data Management & API Integration (Sketch Focus)

#### 4.1 Sketch Input Management
*   [ ] Implement Supabase Storage upload for sketch data (e.g., SVG) and background image via RTK Query.
*   [ ] Add progress indicators for uploads.
*   [ ] Update `input_assets` table with sketch & background image URL(s), prompt, style.

#### 4.2 Live Concept Preview API
*   [ ] Define BFF endpoint for fast concept generation from sketch data, prompt, style (e.g., `/generate/concept-from-sketch`).
*   [ ] Implement client-side calls to this endpoint as user modifies inputs.
*   [ ] Update `LiveConceptPreview.tsx` with the returned image URL.
*   [ ] Handle API errors for live preview.

#### 4.3 Sketch to 3D Model API
*   [ ] Implement client-side `task_id` generation for the 3D job.
*   [ ] Implement API call to `/generate/sketch-to-image` with `task_id`, sketch URL, background URL, prompt, style.
*   [ ] Create polling logic for 3D model generation status via RTK Query.
*   [ ] Handle API errors and retry logic for 3D generation.

#### 4.4 Other Screens & Workflows
*   [ ] Create `/src/features/model-generation/screens/WorkspaceScreen.tsx` (if not generic enough)
*   [ ] Implement full workspace view, filtering, pagination.

### Phase 5: Navigation & Integration (Sketch Focus)

#### 5.1 Navigation System
*   [ ] Update `AppNavigator.js` to include `SketchToModelScreen.tsx`.
*   [ ] Bridge `SketchToModelScreen.tsx` to existing sculpting tools.
*   [ ] Ensure seamless transition from sketch generation to sculpting.

#### 5.2 Cross-Feature Integration
*   [ ] Integrate sketch generation workflow with sculpting tools.
*   [ ] Ensure model loading from sketch generation to sculpting viewer.

### Phase 6: Testing & Validation (Sketch Focus)

#### 6.1 Core Functionality Testing
*   [ ] Test Sketch to 3D flow thoroughly.
    *   [ ] Test sketch canvas drawing and data export.
    *   [ ] Test background image upload.
    *   [ ] Test style selection.
    *   [ ] Test prompt input.
    *   [ ] Test live concept preview updates.
    *   [ ] Test 3D model generation from sketch.
*   [ ] Test modal workflows (Sculpt, Color).

#### 6.2 Integration Testing
*   [ ] Test with existing users.
*   [ ] Verify RLS policies.
*   [ ] Test auth flows.
*   [ ] Test BFF integration with JWT (for sketch endpoints).
*   [ ] Test transition to sculpting tools.

#### 6.3 UI/UX Testing
*   [ ] Test Sketch to 3D screen layout and controls on various devices.
*   [ ] Validate sketch canvas usability.
*   [ ] Test live concept preview responsiveness.
*   [ ] Test "Generate 3D Model" button states.

### Phase 7: Polish & Optimization (Largely Same, apply to Sketch)

#### 7.1 Performance Optimization
*   [ ] Optimize sketch data handling (e.g., debouncing for live preview API calls).
*   [ ] Optimize background image upload/compression.
*   [ ] Add caching where appropriate.
*   [ ] Optimize Redux updates.

#### 7.2 Error Handling & User Experience
*   [ ] Add comprehensive error messages for sketch flow.
*   [ ] Implement retry mechanisms.
*   [ ] Add clear loading states for live preview and 3D generation.
*   [ ] Implement offline handling for sketch saving if possible.

---
*This document reflects a focus on Sketch-to-3D functionality, based on BFF API v1.1.0 (assuming updates for sketch) and the agreed Supabase interaction model.*