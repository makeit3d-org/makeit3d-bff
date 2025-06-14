# Repository Structure Refactor: Organizing 3D Sculpting Features

## Overview
Refactor the makeit3d-frontend to better organize the existing 3D sculpting features into a cleaner feature-based structure with shared infrastructure.

## Key Changes

### 1. **Feature-Based Architecture**
- **Sculpt-3D Module**: Reorganized existing 3D editor (`features/sculpt-3d/`)
- **Shared Infrastructure**: Common components, state, and utilities (`shared/`)

### 2. **File Organization Changes**
- **Minimal 3D Disruption**: Keep existing 3D filenames and move to `features/sculpt-3d/`
- **Shared Infrastructure**: Move common components to `shared/` directory
- **Configuration Consolidation**: Environment, constants, and config in `shared/config/`

## Target Project Structure

> **File Operation Legend:**
> - **`# KEEP SAME NAME`** = Move existing file to new location without renaming (stays JavaScript)
> - **`# NEW`** = Create new file that doesn't exist yet
> - **`# MOVE FROM [path]`** = File currently exists at specified path and will be relocated
> - **`# EXTRACT FROM [file]`** = Content extracted from existing file into new file

```
src/
├── features/
│   └── sculpt-3d/                    # RENAMED from advanced-editor/
│       ├── screens/
│       │   └── AdvancedEditorScreen.js    # KEEP SAME NAME (move from features/advanced-editor/screens/)
│       ├── components/
│       │   ├── layout/
│       │   │   └── EditorLayout.js        # KEEP SAME NAME (move from features/advanced-editor/components/layout/)
│       │   ├── viewport/
│       │   │   ├── ModelViewer.js         # KEEP SAME NAME (move from src/components/editor/)
│       │   │   ├── Model3D.js             # KEEP SAME NAME (move from src/components/editor/)
│       │   │   └── BrushVisual.js         # KEEP SAME NAME (move from src/components/editor/)
│       │   └── tools/
│       │       ├── sculpting/
│       │       │   ├── ToolPalette.js     # KEEP SAME NAME (move from features/advanced-editor/components/tools/)
│       │       │   ├── BrushSettingsPanel.js  # KEEP SAME NAME (move from features/advanced-editor/components/tools/)
│       │       │   └── RemeshControls.js  # KEEP SAME NAME (move from features/advanced-editor/components/tools/)
│       │       ├── painting/
│       │       │   ├── ColorPalette.js    # KEEP SAME NAME (move from features/advanced-editor/components/tools/)
│       │       │   └── PaintBrushSettingsPanel.js  # KEEP SAME NAME (move from features/advanced-editor/components/tools/)
│       │       └── shared/
│       │           ├── ToolButton.js      # KEEP SAME NAME (move from features/advanced-editor/components/tools/)
│       │           └── SculptViewToggle.js # KEEP SAME NAME (move from features/advanced-editor/components/tools/)
│       ├── hooks/
│       │   ├── useSculptingSystem.js      # KEEP SAME NAME (move from src/hooks/)
│       │   └── useModelControls.js        # KEEP SAME NAME (move from src/hooks/)
│       ├── state/
│       │   ├── editorSlice.js             # KEEP SAME NAME - NO CONTENT CHANGES (move from src/state/slices/)
│       │   └── modelSlice.js              # KEEP SAME NAME - NO CONTENT CHANGES (move from src/state/slices/)
│       └── constants/
│           └── sculptTools.js             # EXTRACT FROM src/config/constants.js (3D-specific constants only)
│
├── shared/                                # Shared infrastructure (moved files only)
│   ├── components/
│   │   ├── ui/                            # MOVE ENTIRE DIRECTORY (keep all existing filenames and JavaScript)
│   │   └── layout/
│   │       └── RootLayout.js              # KEEP SAME NAME (move from src/components/layout/)
│   ├── hooks/
│   │   ├── useAppTheme.js                 # KEEP SAME NAME (move from src/hooks/)
│   │   ├── useResponsive.js               # KEEP SAME NAME (move from src/hooks/)
│   │   └── useCryptoPolyfill.js           # KEEP SAME NAME (move from src/hooks/)
│   ├── state/
│   │   ├── store.js                       # KEEP SAME NAME (move from src/state/)
│   │   ├── rootReducer.js                 # KEEP SAME NAME (move from src/state/)
│   │   └── appSlice.js                    # KEEP SAME NAME (move from src/state/slices/)
│   ├── utils/
│   │   └── UndoRedoManager.js             # KEEP SAME NAME (move from src/utils/)
│   ├── constants/
│   │   └── appConstants.js                # EXTRACT FROM src/config/constants.js (general app constants)
│   └── config/
│       └── theme.js                       # KEEP SAME NAME (move from src/config/)
│
├── screens/                               # KEEP EXISTING - for backward compatibility
│   └── ModelPickerScreen.js               # KEEP SAME NAME (existing file, no changes)
│
└── assets/                                # KEEP EXISTING - no changes
    ├── images/
    ├── fonts/
    └── models/
```

## Task List for Implementation

### 🔄 Phase 1: Project Structure Setup
- [ ] Create new directory structure under `src/features/sculpt-3d/`
- [ ] Create new directory structure under `src/shared/`
- [ ] Move existing 3D components to new feature structure (keep all filenames)
- [ ] Move shared components to `shared/` directory
- [ ] Extract 3D-specific constants from `src/config/constants.js` into `features/sculpt-3d/constants/sculptTools.js`
- [ ] Extract general app constants from `src/config/constants.js` into `shared/constants/appConstants.js`
- [ ] Update import paths in moved files

### 🧪 Phase 2: Testing & Validation
- [ ] Verify 3D editor still works after refactoring
- [ ] Test all existing 3D functionality
- [ ] Update any broken import paths
- [ ] Cross-platform testing (iOS/Android)

### Integration Notes
- **Preserve Existing**: All current 3D editor functionality moves to `src/features/sculpt-3d/` unchanged
- **No Content Changes**: State slices (`editorSlice.js`, `modelSlice.js`) move locations but content stays identical
- **Shared Infrastructure**: Common components, hooks, and utilities centralized in `shared/` directory
- **Import Path Updates**: Only change import statements to reflect new file locations