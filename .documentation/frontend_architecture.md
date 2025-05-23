# Frontend Architecture: Mobile-First 3D Creation App (Refactored API v1.1.0)

## 1. High-Level Summary

The frontend is a **mobile-first, cross-platform application** built using **React Native and Expo**. Its primary purpose for the **MVP (Minimum Viable Product)** is to allow users to **generate 3D models from various inputs (text, image, sketch, photo)** via a Backend-for-Frontend (BFF) that interacts with Tripo AI and OpenAI.

**Key Architectural Principles (aligned with BFF API v1.1.0):**
*   **Client-Generated `task_id`**: For each new generation job/workspace item, the client generates a unique `task_id`.
*   **Client Manages Supabase Records**: The client is responsible for creating and managing records in its own Supabase tables (`input_assets`, `concept_images`, `models`) to track the overall job and its associated assets.
*   **Inputs via Supabase**: For image/sketch inputs, the client uploads the asset to its Supabase Storage first, creates a record in `input_assets` with the asset URL, and then provides this URL to the BFF.
*   **Polling & Status**: The client polls the BFF's `/tasks/{task_id}/status?service={service}` endpoint for real-time AI step status. Upon completion of an AI step by the BFF (which includes storing the asset in Supabase Storage and updating the respective metadata table like `concept_images` or `models`), the client retrieves the final asset URL. The client primarily uses its own Supabase tables (`input_assets`, `concept_images`, `models`) as the source of truth for persisted asset locations and statuses.

The app handles user authentication (e.g., Supabase Auth) and is designed for intuitive mobile interaction.

## 2. Features

*   **User Authentication**: Sign-up, sign-in, profile management (using Supabase Auth). Supports email/password, and potentially OAuth providers (e.g., Google, Apple).
*   **Supabase Integration**: Client directly interacts with its Supabase instance for:
    *   Uploading input images/sketches to Supabase Storage.
    *   Creating and managing records in `input_assets`, `concept_images`, and `models` tables (tracking `task_id`, prompts, styles, asset URLs, statuses).
*   **Creation Hub Screen**:
    *   **Text-to-Model**: User inputs text prompt. Client generates `task_id`, creates record in `input_assets` (type: 'text_prompt'). Optionally, triggers concept generation first.
    *   **Image-to-Model**: User uploads image. Client uploads image to Supabase Storage, creates `task_id` and record in `input_assets` with the image's Supabase URL. Optionally, triggers concept generation.
    *   **Sketch-to-Model**: User draws/uploads sketch. Client uploads sketch to Supabase Storage, creates `task_id` and record in `input_assets` with the sketch's Supabase URL. Optionally, triggers concept generation.
    *   **Photo-to-Model**: User uploads photo(s). Client uploads to Supabase Storage, creates `task_id` and record(s) in `input_assets`.
    *   All flows: User selects style, options (e.g., "Generate Concept" checkbox).
    *   **Workspace Section**: Displays items based on `task_id` from client's Supabase tables (`input_assets`, `concept_images`, `models`). Shows status (read from these tables) and loading indicators.
*   **Concept Selection Screen**:
    *   If "Generate Concept" was chosen, this screen displays concepts for the active `task_id` (fetched from the client's `concept_images` table via their Supabase URLs).
    *   User selects a concept. Client notes the selected concept's Supabase URL for the next step.
*   **3D Viewer Screen**: Renders `.glb` models using their Supabase URLs (from `models` table).
*   **Loading/Processing Indicators**: For BFF calls (polling `/tasks/{task_id}/status`) and for client-side Supabase operations.
*   **Export & Sharing**: Export `.glb` (using Supabase URL), render snapshot.

## 3. Architecture & Components

*   **Framework**: React Native + Expo.
*   **Language**: TypeScript.
*   **UI Components**: `react-native-paper` (example).
*   **3D Rendering**: `react-three-fiber`, `@react-three/drei`, `expo-gl`.
*   **State Management**: Zustand, React Context API (managing `task_id` state, data from Supabase tables).
*   **Authentication**: Supabase Auth (via `@supabase/supabase-js` library). Utilizes AsyncStorage or SecureStore for session persistence.
*   **Data Fetching & Client-Server State**: TanStack Query (React Query) for interacting with both the BFF API and Supabase.
*   **Supabase Client Library**: For direct database and storage interaction.

### API Communication (BFF Centric - Refactored):
    *   Client generates `task_id` for each job.
    *   For image/sketch inputs: Client uploads to its Supabase Storage, creates a record in its `input_assets` table, then calls BFF with the `task_id` and the asset's Supabase URL.
    *   Calls BFF endpoints (e.g., `/generate/image-to-image`, `/generate/text-to-model`) with `task_id` and relevant parameters (including Supabase URLs for inputs).
    *   Polls BFF `GET /tasks/{task_id}/status?service={service}` for real-time AI step status.
    *   BFF, upon completing an AI step, stores the output asset in Supabase Storage and updates the client's `concept_images` or `models` table (including status and final asset URL).
    *   Client primarily queries its own Supabase tables (`input_assets`, `concept_images`, `models`) to display persisted job status and asset URLs.

### Sketching Canvas (for Sketch-to-Model)
    * `react-native-skia`.

## 4. Key Directory Structure (Example)

```
/makeit3d-app-frontend
|-- /assets                    # Static assets (images, fonts, etc.)
|   |-- /fonts
|   |-- /images
|-- /src
|   |-- /api                   # API service definitions and client instances
|   |   |-- bffClient.ts       # Axios or fetch instance for BFF, base URLs
|   |   |-- supabaseClient.ts  # Supabase JS client instance
|   |   |-- bffService.ts      # Typed functions for BFF endpoints (using bffClient)
|   |   |-- supabaseDbService.ts # Typed functions for Supabase DB interactions (CRUD for metadata tables)
|   |   |-- supabaseStorageService.ts # Typed functions for Supabase Storage interactions
|   |-- /components            # Reusable UI components
|   |   |-- /ui                # Generic, stateless UI elements (Button, Card, Input, etc.)
|   |   |-- /domain            # Feature-specific or domain-related components (e.g., CreationForm, ModelViewerControls, ConceptCard)
|   |   |-- /layout            # Layout components (e.g., MainLayout, AuthLayout)
|   |-- /config                # Application configuration
|   |   |-- env.ts             # Environment variables management
|   |   |-- theme.ts           # UI theme (e.g., for react-native-paper)
|   |   |-- navigationConfig.ts # Configuration for navigators
|   |-- /constants             # Application-wide constants (e.g., route names, event names)
|   |-- /contexts              # React Context API providers/consumers (if needed beyond Zustand)
|   |-- /features              # Optional: Modules for distinct application features (alternative to /domain in components and for grouping screens/hooks/state by feature)
|   |   |-- /auth
|   |   |   |-- /components
|   |   |   |-- /hooks
|   |   |   |-- /screens
|   |   |   |-- /state
|   |   |-- /taskGeneration
|   |   |   |-- /components
|   |   |   |-- /hooks         # e.g., useTaskManagement(), useConceptGeneration()
|   |   |   |-- /screens
|   |   |   |-- /state
|   |-- /hooks                 # Custom React hooks (globally applicable or not fitting into a specific feature/domain)
|   |   |-- useSupabaseAuth.ts # Hook for Supabase auth state and session management
|   |   |-- usePolling.ts      # Generic polling hook
|   |-- /lib                   # Wrappers or configurations for third-party libraries
|   |   |-- i18n.ts            # Internationalization setup
|   |   |-- queryClient.ts     # TanStack Query client instance and default options
|   |-- /navigation            # Navigation setup (React Navigation)
|   |   |-- AppNavigator.tsx
|   |   |-- AuthNavigator.tsx
|   |   |-- MainTabNavigator.tsx
|   |   |-- types.ts           # Navigation-specific types (screen params, etc.)
|   |-- /screens               # Top-level screen components (can be grouped by navigator or feature)
|   |   |-- /Auth
|   |   |   |-- SignInScreen.tsx
|   |   |   |-- SignUpScreen.tsx
|   |   |-- /Main
|   |   |   |-- CreationHubScreen.tsx
|   |   |   |-- ConceptSelectionScreen.tsx
|   |   |   |-- EditorScreen.tsx
|   |   |   |-- WorkspaceScreen.tsx
|   |-- /state                 # Global state management (Zustand stores)
|   |   |-- userStore.ts
|   |   |-- taskStore.ts       # For active task_id, job progress tracking
|   |   |-- uiStore.ts         # For global UI state (e.g., loading, modals)
|   |-- /styles                # Global styles, theme variables
|   |   |-- global.ts
|   |   |-- colors.ts
|   |   |-- typography.ts
|   |-- /types                 # Global TypeScript types and interfaces
|   |   |-- api.ts             # Types for BFF API requests/responses
|   |   |-- supabase.ts        # Types for Supabase table rows
|   |   |-- domain.ts          # Core domain types (Task, Asset, Concept, Model)
|   |-- /utils                 # Utility functions
|   |   |-- helpers.ts
|   |   |-- validators.ts
|   |   |-- formatters.ts
|   |-- App.tsx                # Main application entry point (registers navigators, providers, etc.)
|-- .env                       # Environment variables (ensure it's in .gitignore)
|-- babel.config.js
|-- metro.config.js
|-- package.json
|-- tsconfig.json
```

## 5. User & Sequence Flows (Refactored)

*   **Common Pre-steps**:
    1.  **User Action (Creation Hub)**: User initiates a generation type (Text, Image, Sketch, Photo), provides inputs, selects style.
    2.  **Client Action**: Generates a unique `task_id` for this entire job.
    3.  **Client Action (for image/sketch inputs)**: Uploads the image/sketch to its Supabase Storage. Gets the Supabase URL.
    4.  **Client Action**: Creates a record in its `input_assets` Supabase table for this `task_id`, including prompt, style, input type, and the Supabase URL of the uploaded asset (if applicable). Sets initial status 'pending'.
    5.  **Client Action**: Navigates to Workspace, showing the new job with `task_id` and status from `input_assets` table.

    *   **Flow A: Direct to 3D Model (e.g., Photo-to-Model, or Text/Image/Sketch-to-Model with 'Generate Concept' unchecked)**:
    6.  **Client -> BFF**: Calls appropriate BFF generation endpoint (e.g., `/generate/text-to-model`, `/generate/image-to-model`) with `task_id` and necessary parameters (including Supabase URL of input asset from `input_assets` if applicable).
    7.  **BFF**: (Internally) Creates/updates a record in its `models` table for this `task_id` with status 'processing'. Calls Tripo AI.
    8.  **Client**: Polls `GET /tasks/{task_id}/status?service=tripo`. Workspace shows status (e.g., 'Generating Model').
    9.  **BFF (on Tripo AI completion)**: Downloads model, uploads to client's Supabase Storage, updates the record in `models` table with the final Supabase `asset_url` and status 'complete'.
    10. **Client (on seeing 'complete' status from polling or by observing `models` table)**: Retrieves the model's Supabase URL from the `models` table. Displays model in `EditorScreen`.

    *   **Flow B: With 2D Concept Phase (e.g., Text/Image/Sketch-to-Model with 'Generate Concept' checked)**:
    6.  **Client -> BFF**: Calls `/generate/image-to-image` (or a similar concept endpoint) with `task_id` and parameters (including Supabase URL of input asset from `input_assets`).
    7.  **BFF**: (Internally) Creates record(s) in `concept_images` table for this `task_id` with status 'processing'. Calls OpenAI.
    8.  **Client**: Polls `GET /tasks/{task_id}/status?service=openai`. Workspace shows status (e.g., 'Generating Concepts').
    9.  **BFF (on OpenAI completion)**: Downloads concept(s), uploads to client's Supabase Storage, updates record(s) in `concept_images` table with final Supabase `asset_url`(s) and status 'complete'.
    10. **Client (on seeing 'complete' status)**: Fetches concept image URLs from its `concept_images` table. Navigates to `ConceptSelectionScreen`.
    11. **User Action (ConceptSelectionScreen)**: Selects a concept.
    12. **Client -> BFF**: Calls `/generate/image-to-model` with `task_id` and the Supabase URL of the *selected concept image* (from `concept_images` table) as `input_image_asset_urls`.
    13. **BFF**: (Internally) Creates/updates record in `models` table for this `task_id` with status 'processing' (linking to the chosen concept if schema supports it). Calls Tripo AI.
    14. **Client**: Polls `GET /tasks/{task_id}/status?service=tripo`. Workspace shows status (e.g., 'Generating Model').
    15. **BFF (on Tripo AI completion)**: Downloads model, uploads to client's Supabase Storage, updates the record in `models` table with final Supabase `asset_url` and status 'complete'.
    16. **Client (on seeing 'complete' status)**: Retrieves model URL from `models` table. Displays model in `EditorScreen`.

## 6. Technical Considerations

*   **Client-Side Supabase Logic**: Robust handling of Supabase operations (uploads, DB record creation/updates) with appropriate error handling and state management.
*   **State Synchronization**: Ensuring UI correctly reflects the state from the client's Supabase tables (`input_assets`, `concept_images`, `models`) and from BFF polling during active AI steps.
*   **API Rate Limiting & Client Behavior**: Unchanged from previous BFF considerations.
*   **BFF API Key Security**: Unchanged.
*   **Asynchronous Communication**: For all BFF calls and client-side Supabase operations.

## 7. Frontend-BFF API Endpoints (Summary - Client Perspective)

(Refer to `makeit3d-api.md` for full details)
*   Client sends `task_id` and Supabase URLs for inputs to endpoints like:
    *   `POST /generate/image-to-image`
    *   `POST /generate/text-to-model`
    *   `POST /generate/image-to-model` (also used for concept-to-model)
    *   `POST /generate/sketch-to-model`
    *   `POST /generate/refine-model`
*   Client polls `GET /tasks/{task_id}/status?service={service}` for real-time AI step status.
*   Client primarily uses its own Supabase tables (`input_assets`, `concept_images`, `models`) as the source of truth for persisted asset URLs and overall job status.

## 8. Implementation Tasks (High-Level - Frontend Focus)

*   [ ] Setup Supabase client, RLS policies for client tables.
*   [ ] Implement client-side logic for `task_id` generation.
*   [ ] Setup Supabase Auth: initialize client, configure auth providers (email/password, OAuth), manage session state.
*   [ ] Implement deep linking for Supabase Auth (OAuth, magic links).
*   [ ] Create UI components for login, sign-up, and profile management using Supabase Auth.
*   [ ] Implement Supabase Storage upload functionality for images/sketches.
*   [ ] Implement CRUD operations for `input_assets`, `concept_images`, `models` tables in Supabase via `supabaseDbService.ts` (from the updated directory structure).
*   [ ] Update `CreationHubScreen` forms to integrate Supabase uploads and `input_assets` record creation.
*   [ ] Update `bffService.ts` to call refactored BFF endpoints with `task_id` and Supabase asset URLs.
*   [ ] Implement polling logic for `GET /tasks/{task_id}/status` and update UI accordingly during active AI steps.
*   [ ] Ensure `ConceptSelectionScreen` and `EditorScreen` fetch asset URLs from the client's `concept_images` and `models` tables respectively.
*   [ ] Refine Workspace Section to display job status based on data from the client's three Supabase tables.

---
*This document reflects changes based on BFF API v1.1.0 and the agreed Supabase interaction model.*