# Frontend UI Design: Mobile-First 3D Creation App

## 1. Overview

This document outlines the user interface design and wireframes for the mobile-first 3D creation app, focusing on the **Sketch-to-3D workflow**. The app is built using React Native and Expo with a responsive, cross-platform design approach.

## 2. Design Principles & Responsive Strategy

### Device Layout Strategy

**Responsive Design Approach:**
- **Tablets/Desktop (Landscape)**: Control panel on left, main sketch area on right (for Sketch to 3D screen).
- **Phones (Landscape)**: Similar to tablet layout with smaller/collapsible control panel.
- **Phones (Portrait)**: Stacked vertically - control panel on top, sketch area below.

### Responsive Breakpoints:
- **Mobile Portrait**: < 768px width, stacked layout.
- **Mobile Landscape**: 768px - 1024px width, side-by-side with smaller panel.
- **Tablet/Desktop**: > 1024px width, full side-by-side layout.

## 3. Complete UI Wireframes & Design Specifications

### 3.1 Home Screen Wireframes

#### Tablet/Desktop Layout (Landscape)
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Sketch3D Home                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────────────────────────┐ │
│ │                             Sketch to 3D                                │ │
│ └─────────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│ ┌──────────────────────────┐  ┌──────────────────────────┐                │
│ │                          │  │                          │                │
│ │      Sculpt Model        │  │       Color Model        │                │
│ │                          │  │                          │                │
│ └──────────────────────────┘  └──────────────────────────┘                │
├─────────────────────────────────────────────────────────────────────────────┤
│                              Your Workspace                                │
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ [View All] │
│ │ 🔄  │ │ ⚡  │ │ ✓   │ │ ✓   │ │ ✓   │ │ ✓   │ │ ✓   │ │ ✓   │           │
│ │Model│ │Model│ │Model│ │Model│ │Model│ │Model│ │Model│ │Model│           │
│ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘           │
├─────────────────────────────────────────────────────────────────────────────┤
│                             Explore Models                                 │
│ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ [Explore] │
│ │Stock│ │Stock│ │Stock│ │Stock│ │Stock│ │Stock│ │Stock│ │Stock│           │
│ │Model│ │Model│ │Model│ │Model│ │Model│ │Model│ │Model│ │Model│           │
│ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘ └─────┘           │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Phone Layout (Portrait)
```
┌─────────────────────────────┐
│        MakeIt3D Home        │
├─────────────────────────────┤
│ ┌─────────────────────────┐ │
│ │      Sketch to 3D       │ │
│ └─────────────────────────┘ │
│ ┌─────────────────────────┐ │
│ │      Sculpt Model       │ │
│ └─────────────────────────┘ │
│ ┌─────────────────────────┐ │
│ │       Color Model       │ │
│ └─────────────────────────┘ │
├─────────────────────────────┤
│      Your Workspace        │
│ ┌───┐ ┌───┐ ┌───┐ [View All]│
│ │🔄 │ │⚡ │ │✓  │          │
│ └───┘ └───┘ └───┘          │
│ ┌───┐ ┌───┐ ┌───┐          │
│ │✓  │ │✓  │ │✓  │          │
│ └───┘ └───┘ └───┘          │
├─────────────────────────────┤
│      Explore Models        │
│ ┌───┐ ┌───┐ ┌───┐ [Explore]│
│ │📦 │ │📦 │ │📦 │          │
│ └───┘ └───┘ └───┘          │
└─────────────────────────────┘
```

### 3.2 Sketch to 3D Screen Wireframes

#### Tablet/Desktop Layout (Landscape)
```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                             Sketch to 3D Creation                                │
├─────────────────────────┬───────────────────────────────────────────────────────────┤
│ CONTROL PANEL (Left)    │                    SKETCH AREA (Right)                   │
│                         │                                                           │
│ Background:             │                                                           │
│ ┌─────────────────────┐ │                                                           │
│ │ Upload Background   │ │                                                           │
│ │       Image         │ │                 S K E T C H   C A N V A S                 │
│ └─────────────────────┘ │                                                           │
│                         │                                                           │
│ Style:                  │                                                           │
│ ┌───┐ ┌───┐ ┌───┐ ... │                                                           │
│ │ 🎨│ │ 🎭│ │ 🗿│     │           (User draws here with touch/stylus)             │
│ └───┘ └───┘ └───┘     │                                                           │
│                         │                                                           │
│ Prompt:                 │                                                           │
│ ┌─────────────────────┐ │                                                           │
│ │ Add prompt here...  │ │                                                           │
│ └─────────────────────┘ │                                                           │
│                         │                                                           │
│ Preview:                │                                                           │
│ ┌─────────────────────┐ │                                                           │
│ │ Concept rendered    │ │                                                           │
│ │ here in real time   │ │                ┌───────────────────┐                    │
│ │ while user sketches │ │                │ Generate 3D Model │                    │
│ └─────────────────────┘ │                └───────────────────┘                    │
│                         │                                                           │
└─────────────────────────┴───────────────────────────────────────────────────────────┘
```

#### Phone Layout (Portrait) - Sketch to 3D
```
┌─────────────────────────────┐
│    Sketch to 3D Creation    │
├─────────────────────────────┤
│      CONTROL PANEL (Top)    │
│ Background: [Upload Btn]    │
│ Style: ┌───┐ ┌───┐ ...     │
│        │🎨 │ │🎭 │         │
│ Prompt:                     │
│ ┌─────────────────────────┐ │
│ │   Add prompt here...    │ │
│ └─────────────────────────┘ │
│ Preview:                    │
│ ┌─────────────────────────┐ │
│ │ [Live Concept Preview]  │ │
│ └─────────────────────────┘ │
├─────────────────────────────┤
│     SKETCH AREA (Bottom)    │
│ ┌─────────────────────────┐ │
│ │                         │ │
│ │     S K E T C H         │ │
│ │                         │ │
│ │       C A N V A S       │ │
│ │                         │ │
│ │  [Generate 3D Button]   │ │
│ └─────────────────────────┘ │
└─────────────────────────────┘
```

### 3.3 Workspace Screen Wireframes

#### Tablet/Desktop Layout (Landscape)
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Your Workspace                                │
├─────────────────┬───────────────────────────────────────────────────────────┤
│ CONTROL PANEL   │                    PREVIEW AREA                          │
│ (Filters etc.)  │                                                           │
│ Filter & Sort:  │ ┌───────────────────────────────────────────────────────┐ │
│ ┌─────────────┐ │ │                                                       │ │
│ │ All Models  │ │ │              Selected Model                           │ │
│ └─────────────┘ │ │                                                       │ │
│ ... (Filters)   │ │              [3D Preview]                             │ │
│                 │ │                                                       │ │
│ Search:         │ └───────────────────────────────────────────────────────┘ │
│ ┌─────────────┐ │                                                           │
│ │ Search...   │ │ Model Details & Actions                                   │
│ └─────────────┘ │ ...                                                       │
│                 │                                                           │
│ Your Models     │                                                           │
│ (Scrollable List)│                                                          │
│ ┌─────────────┐ │                                                           │
│ │ Model 1     │ │                                                           │
│ │ ✓ Complete  │ │                                                           │
│ │ (selected)  │ │                                                           │
│ └─────────────┘ │                                                           │
│ ...             │                                                           │
└─────────────────┴───────────────────────────────────────────────────────────┘
```

#### Phone Layout (Portrait)
```
┌─────────────────────────────┐
│       Your Workspace        │
├─────────────────────────────┤
│        CONTROL PANEL        │
│ Filter: [All ▼] Sort: [▼]   │
│ ┌─────────────────────────┐ │
│ │      Search...          │ │
│ └─────────────────────────┘ │
│ Models List (Scrollable):   │
│ ┌─────────────────────────┐ │
│ │ Model 1 - ✓ Complete    │ │
│ │ (selected)              │ │
│ └─────────────────────────┘ │
│ ...                         │
│ Actions: [Sculpt] [Delete]  │
├─────────────────────────────┤
│       PREVIEW AREA          │
│ ┌─────────────────────────┐ │
│ │                         │ │
│ │   Selected Model        │ │
│ │   [3D Preview]          │ │
│ └─────────────────────────┘ │
│ Details...                  │
└─────────────────────────────┘
```

### 3.4 Modal Wireframes

#### Sculpt Model Modal (Tablet/Desktop)
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Sculpt Model                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                       (Accessed from Home Screen)                         │
│                                                                             │
│ ┌─────────────────────┐ ┌─────────────────────┐ ┌─────────────────────┐     │
│ │                     │ │                     │ │                     │     │
│ │  Load from          │ │  Load from          │ │  Start from         │     │
│ │  Workspace          │ │  Public             │ │  Scratch            │     │
│ │                     │ │                     │ │                     │     │
│ │  [Your Models]      │ │  [Stock Models]     │ │  [Basic Sphere]     │     │
│ │                     │ │                     │ │                     │     │
│ └─────────────────────┘ └─────────────────────┘ └─────────────────────┘     │
│                                                                             │
│                              [Cancel]                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### Color Model Modal (Phone Portrait)
```
┌─────────────────────────────┐
│        Color Model          │
├─────────────────────────────┤
│ (Accessed from Home Screen) │
│                             │
│ ┌─────────────────────────┐ │
│ │                         │ │
│ │    Load from            │ │
│ │    Workspace            │ │
│ │                         │ │
│ │   [Your Models]         │ │
│ │   (No Texture)          │ │
│ │                         │ │
│ └─────────────────────────┘ │
│                             │
│ ┌─────────────────────────┐ │
│ │                         │ │
│ │    Load from            │ │
│ │    Public               │ │
│ │                         │ │
│ │   [Stock Models]        │ │
│ │   (No Texture)          │ │
│ │                         │ │
│ └─────────────────────────┘ │
│                             │
│        [Cancel]             │
└─────────────────────────────┘
```

## 4. Component Design Specifications

### 4.1 Control Panel Behavior (Sketch to 3D Screen)

- **Tablets/Desktop**: Fixed left panel (occupying approx. 30-35% of screen width, or a comfortable fixed width like 350-450px), main sketch area responsive. Contains controls for background image upload, style selection, text prompt, and a live preview of the generated concept.
- **Phones Landscape**: Collapsible left panel, swipe to show/hide.
- **Phones Portrait**: Stacked layout, control panel scrollable at top, sketch area below.

### 4.2 Preview Area Content (Control Panel)

- **Live Concept Preview**: Shows a single image that updates in (near) real-time as the user sketches, types a prompt, or selects a style. This image is the basis for the 3D model generation.
- **Processing States**: The live preview area might show progress indicators if concept generation is not instantaneous.

### 4.3 Style Selector Layout

**Style Grid (e.g., 3x2 + expandable):**
- Visible style options in a grid (e.g., 3 columns).
- Each style shows icon/preview and name.
- "..." or "More Styles" button to expand/scroll and show all available styles.
- Selected style highlighted.
- **Available Styles**: None, Ghibli, Simpson, South Park, Anime, Cartoon, Claymation, Muppet, Metal, Wood, Glass.

### 4.4 Generation Options

**Generate Button (Integrated into Sketch Canvas Area):**
- Shows cost (e.g., "10c" for credits).
- Disabled state if sketch is empty or other required inputs missing.
- Loading state during 3D model generation process.
- Success state transitions to the 3D Sculpting Viewer.

## 5. Navigation & User Flows

### 5.1 Home Screen Flow
1. **User Action**: Opens app, sees Home Screen with main "Sketch to 3D" button, and secondary "Sculpt Model", "Color Model" buttons.
2. **User Action**: Can either:
   - Click "Sketch to 3D" → Navigate to Sketch to 3D Screen.
   - Click "Sculpt Model" → Open Sculpt Model Modal.
   - Click "Color Model" → Open Color Model Modal.
   - Click on a model in Workspace section → Smart navigation based on status.
   - Click "View All" in Workspace section → Navigate to full Workspace Screen.
   - Click on model in Explore Models section → Load directly into relevant viewer/editor.

### 5.2 Sketch to 3D Workflow
1. **User Action**: User is on the Sketch to 3D Screen.
   - Optionally uploads a background image.
   - Draws a sketch on the canvas.
   - Optionally types a text prompt.
   - Selects a style.
2. **Live Preview**: As user interacts (sketches, types prompt, selects style), the concept preview updates in real-time.
3. **User Action**: When satisfied with the sketch and live concept preview, clicks "Generate 3D Model" button.
4. **Navigation**: Upon completion, transitions to 3D Sculpting Viewer to view and edit the generated model.

### 5.3 Smart Model Navigation
Clicking a model takes user to:
- **Pending/Processing jobs** → Sketch to 3D Screen (to continue/monitor).
- **Complete jobs** → 3D Sculpting Viewer.

## 6. UI Component Hierarchy

### 6.1 Home Screen Components
```
HomeScreen
├── Header
│   └── Title: "Sketch3D Home"
├── MainActions
│   ├── PrimaryButton: "Sketch to 3D"
│   ├── SecondaryButton: "Sculpt Model"
│   └── SecondaryButton: "Color Model"
├── WorkspaceSection
│   ├── SectionHeader: "Your Workspace"
│   ├── ModelGrid (horizontal scroll)
│   │   └── ModelCard[] (with status indicators)
│   └── ViewAllButton
└── ExploreSection
    ├── SectionHeader: "Explore Models"
    ├── ModelGrid (horizontal scroll)
    │   └── ModelCard[]
    └── ExploreButton
```

### 6.2 Sketch to 3D Screen Components
```
SketchToModelScreen
├── Header
├── ResponsiveLayout
│   ├── ControlPanel (Left/Top)
│   │   ├── BackgroundImagePicker
│   │   ├── StyleSelector
│   │   ├── PromptInput
│   │   └── LiveConceptPreview
│   └── SketchArea (Right/Bottom)
│       ├── SketchCanvas
│       └── GenerateButton
└── StatusIndicators
```

### 6.3 Workspace Screen Components
```
WorkspaceScreen
├── Header
├── ResponsiveLayout
│   ├── ControlPanel (Left/Top)
│   │   ├── FilterOptions
│   │   ├── SortOptions
│   │   ├── SearchInput
│   │   └── ModelList (scrollable)
│   │       └── ModelCard[]
│   └── PreviewArea (Right/Bottom)
│       ├── Model3DPreview
│       ├── ModelDetails
│       └── ActionButtons
└── LoadingIndicators
```

## 7. Responsive Design Details

### 7.1 Breakpoint Specifications
- **xs**: 0-479px (Phone Portrait)
- **sm**: 480-767px (Phone Landscape)
- **md**: 768-1023px (Tablet Portrait)
- **lg**: 1024-1439px (Tablet Landscape)
- **xl**: 1440px+ (Desktop)

### 7.2 Layout Adaptations

#### Sketch to 3D Screen Layouts
- **xs/sm**: Vertical stack (Control Panel → Sketch Area)
- **md+**: Horizontal split (Control Panel | Sketch Area)

#### Control Panel Adaptations
- **xs**: Full width, collapsible sections
- **sm**: Reduced width, icon + text
- **md+**: Fixed width (350-450px), full controls

#### Canvas Area Adaptations
- **xs**: Square aspect ratio, touch optimized
- **sm**: Landscape aspect ratio
- **md+**: Flexible size, stylus support

## 8. Interaction Patterns

### 8.1 Touch Interactions
- **Drawing**: Single finger draw, two finger pan/zoom
- **Style Selection**: Tap to select, visual feedback
- **Background Upload**: Tap to open picker, drag-and-drop on larger screens

### 8.2 Loading States
- **Live Preview**: Shimmer effect while generating
- **3D Generation**: Progress bar with status text
- **Upload**: Progress indicator with cancel option

### 8.3 Error States
- **Network Error**: Retry button with error message
- **Invalid Input**: Inline validation with guidance
- **Generation Failure**: Clear error message with support contact

## 9. Accessibility Considerations

### 9.1 Visual Accessibility
- High contrast mode support
- Scalable text (minimum 16px base)
- Color-blind friendly palette
- Clear focus indicators

### 9.2 Motor Accessibility
- Large touch targets (minimum 44px)
- Alternative input methods
- Gesture shortcuts
- Voice commands (future enhancement)

### 9.3 Cognitive Accessibility
- Clear visual hierarchy
- Consistent navigation patterns
- Progress indicators for long operations
- Undo/redo functionality

---

*This UI design document focuses specifically on the visual and interaction design aspects of the Sketch-to-3D mobile application, providing detailed wireframes and specifications for responsive implementation.* 