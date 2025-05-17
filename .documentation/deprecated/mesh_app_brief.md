# Mesh Editing Mobile App Prototype - Architecture Brief

## 1. Overview

This project is to develop a **Putty 3D clone**—a mobile application for iOS and Android that allows users to import, sculpt, and export 3D models. The focus is on providing a core set of intuitive mesh sculpting tools with a responsive user experience, inspired by the usability of Putty3D.

## 2. Core Prototype Features

*   **Model Import**: Users can import 3D models in `.glb` format from their device.
*   **3D Viewport**: Display and navigate (rotate, pan, zoom) the imported 3D model.
*   **Sculpting System**:
    *   **Tools**:
        *   **Add/Draw Tool**: Increases volume by adding material, allowing users to build up forms.
        *   **Subtract Tool**: Removes material, useful for carving into the model (can be a mode of the Add/Draw tool or a separate tool).
        *   **Smooth Tool**: Softens transitions and blends areas for a polished look.
        *   **Flatten Tool**: Levels surfaces, aiding in creating planes or hard edges.
        *   **Move Tool**: Adjusts the mesh by pulling or pushing areas to reshape the model.
    *   **Brush Settings**: Adjustable brush size and strength for all applicable tools.
    *   **Mirror Mode**: Enables symmetrical sculpting, reflecting changes across a user-selectable axis (e.g., X, Y, or Z).
*   **Local Project Save/Load**: Save the current state of the edited model (geometry) locally on the device and reload it.
*   **Model Export**: Export the edited model as a `.glb` file, including sculpted geometry.
*   **Undo/Redo**: Basic undo/redo functionality for sculpt actions.

## 3. Technical Stack Overview

*   **Mobile Frontend**: React Native with Expo (TypeScript recommended).
    *   3D Rendering: `react-three-fiber` with `expo-gl`.
    *   State management solution (e.g., Zustand, Redux Toolkit, or React Context).

## 4. Scope of Work

The mobile application will provide the user interface and interactive tools for sculpting.

### Core Responsibilities:

1.  **User Interface (UI)**:
    *   Screen for importing models.
    *   Main editor screen with 3D viewport, toolbars for sculpting (reflecting the Add/Draw, Subtract, Smooth, Flatten, Move tools), and brush settings panels.
    *   UI control for toggling Mirror Mode and selecting the symmetry axis.
    *   File management UI for local save/load.
2.  **3D Viewport & Interaction**:
    *   Render `.glb` models using `react-three-fiber` and `expo-gl`.
    *   Implement camera controls (orbit, pan, zoom).
    *   Visually represent sculpting brush on the model surface, including a visual indicator for the symmetry plane if Mirror Mode is active.
3.  **Tool Logic (Client-Side)**:
    *   Manage active tool, brush settings.
    *   Implement client-side interaction logic for all sculpting tools. This includes applying deformations symmetrically if Mirror Mode is enabled.
    *   Manage undo/redo stack for local actions.
4.  **File Handling**:
    *   Import `.glb` files from device storage.
    *   Save current project state (including modified mesh) locally.
    *   Export final edited model as a `.glb` file to device storage.

## 5. Key Requirements & Considerations

*   **File Format**: `.glb` is the exclusive format for model import, export, and local save/load.
*   **User Experience**: The primary goal is a smooth and interactive experience for the sculpting tools. Minimize perceived latency.
*   **Performance**: The client-side rendering and tool interaction must be performant on target mobile devices.
*   **Modularity**: Aim for modular code to facilitate maintenance and potential future enhancements.

This brief outlines the core requirements for the prototype. Further details and clarifications will be provided as needed during development. 