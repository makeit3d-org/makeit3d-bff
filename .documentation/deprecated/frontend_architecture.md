# MakeIt3D Frontend Architecture

## 1. High-Level Summary

The frontend is a Next.js application using the App Router architecture. It serves as the primary user interface for interacting with the MakeIt3D service. Users start on the Dashboard to initiate generation, view concepts and the final model on a dedicated Asset page, configure prints on a separate Print page, manage items in a Cart, and complete purchases via a Checkout page. It handles user authentication (Clerk), payment processing (Stripe), displaying generated assets, and managing orders. **Crucially, all communication with the external Python backend API is handled exclusively by Next.js server-side logic (Server Actions and Route Handlers) to maintain a strict client-server separation.** Client components interact with these server-side functions. The frontend leverages `shadcn/ui` and `lucide-react` for the user interface components and includes a 3D model viewer. **It includes a credit system where users spend credits for AI generation and can purchase more credits.**

## 2. Features

*   **User Authentication**: Sign-up, sign-in, profile management via Clerk.
*   **Landing Page (`/`)**: Marketing and entry point for new users.
*   **Main Layout**: Includes user icon (Clerk) and **Credit Balance display (`14 Credits [ + ]`)**. Clicking `[ + ]` opens the Buy Credits modal.
*   **Dashboard (`/dashboard`)**:
    *   **Input Mode Selection**: Tabs or similar UI to switch between "Text to Model" and "Image to Model" modes.
    *   **Text to Model Inputs** (Visible in Text mode):
        *   Prompt Box: Multi-line text area for user input.
        *   Style Selector: Grid of clickable image icons representing available `Style` options (fetched from DB).
    *   **Image to Model Inputs** (Visible in Image mode):
        *   Image Upload Area: Drag-and-drop zone or file input. *[Post-MVP: Consider allowing multiple image uploads.]*
        *   Prompt Box: Multi-line text area for user input (can augment the image).
        *   Style Selector: Grid of clickable image icons representing available `Style` options.
    *   **Generate Button**: A prominent button to initiate the generation process based on the current mode's inputs (prompt, optional image, selected style). Includes a visual indicator of the cost (**`1c` icon**).
    *   **Skip Concept Checkbox**: An option next to the Generate button (or nearby) allowing users to bypass the 2D concept generation step and attempt direct model generation.
    *   **Recent Activity**: Below the input controls, show a list of the user's most recent generated assets or orders.
    *   **Discovery Section (Public Assets Feed)**: Below Recent Activity, display a feed of public assets from the community, loading more automatically as the user scrolls down (infinite scroll).
*   **Asset Page (`/assets/[assetId]`)**: Dynamically displays the state of a specific generation job.
    *   **Concept View (Status: `CONCEPTS_GENERATED`)**: Shows the two generated 2D concept images. Includes buttons to "Regenerate Concepts" (if retries available) and "Generate 3D Model" (after selecting a concept). "Generate 3D Model" button includes cost indicator (**`1c` icon**, possibly marked as "Free" if it's the first attempt for this asset).
    *   **Model View (Status: `COMPLETED`)**: Shows the chosen concept alongside the final 3D model in an interactive viewer. Includes two primary action buttons:
        *   "Download Model": Adds the digital asset directly to the cart and navigates the user to the Cart Page.
        *   "3D Print + Download Model": Navigates the user to the Print Configuration Page.
        *   Includes a **"Regenerate Model"** button (costs 1 credit, uses the same input as the previous attempt).
    *   Displays loading/error states appropriately based on `Asset.status`.
*   **Buy Credits Modal**: Triggered from main layout. Displays available `CreditPurchaseOption` packages with amounts, prices, bonuses. Allows adding a package to the cart.
*   **Print Configuration Page (`/print/[assetId]`)**: Accessed from the Asset Page (Model View) via the "3D Print + Download Model" button.
    *   Allows user to configure print options: Technology, Material, Color, Surface Finish, Quantity, Remarks, **and Target Dimensions/Size**.
    *   Includes a dedicated section dynamically displaying the price breakdown.
    *   Includes an **"Add Configured Print to Cart"** button.
    *   Includes an **"Save and Exit"** or **"Save & Back to Workspace"** button (saves the current configuration as a `PrintJobConfig` and navigates to Workspace).
*   **Cart Page (`/cart`)**:
    *   Displays items added for purchase: digital assets (references `Asset`), configured prints (references `PrintJobConfig`), and/or credit packages (references `CreditPurchaseOption`).
    *   Allows adjusting quantities (for prints - by editing the associated `PrintJobConfig`?) or removing items.
    *   Shows subtotal and total price.
    *   Button to "Proceed to Checkout".
*   **Checkout Page (`/checkout`)**:
    *   Integrates with Stripe Elements for secure payment capture.
    *   Collects shipping address if physical prints are in the cart.
    *   Final order summary before payment button.
*   **Order Management Page (`/orders`)**:
    *   Lists past orders (digital assets and physical prints).
    *   Displays order status, tracking information (if applicable).
    *   Provides download links for purchased digital assets associated with each order.
*   **Account Page (`/account`)**: Manage Stripe payment method details, potentially other user settings.
*   **Workspace Page (`/workspace`)**: 
    *   Displays a scrollable list of the user's generation jobs (`Assets`).
    *   Each job entry shows a thumbnail (input image/placeholder), potentially the prompt/style used, and a clear **status indicator**. For actionable states, this indicator should suggest the next step (e.g., display "Select Concept" when status is `CONCEPTS_GENERATED`, "View Model" when status is `COMPLETED`, or "Error" when `FAILED`).
    *   Job entries are only clickable (navigating to `/assets/[assetId]`) when the status is `CONCEPTS_GENERATED` or `COMPLETED` (or potentially `FAILED` to view errors).
*   **Help Page (`/help`)**: A page containing guides and instructions for using the service, covering key workflows.

## 3. Architecture & Components

*   **Framework**: Next.js 14+ (App Router)
*   **Language**: TypeScript
*   **UI**: React, `shadcn/ui`, Tailwind CSS, `lucide-react`
*   **3D Viewer**: `react-three-fiber`, `@react-three/drei`
*   **State Management**: React Context API / Zustand (as needed for complex shared client-side state)
*   **Authentication**: Clerk (Middleware, frontend components, backend helpers)
*   **Payment**: Stripe SDK / React Stripe Elements (Client-side), Stripe Node SDK (Server-side)
*   **Data Fetching/Mutations**: Server Components (fetching), Route Handlers (API endpoints), Server Actions (mutations/forms). React Query (`@tanstack/react-query`) can be used for client-side caching/polling.
*   **API Communication**: Internal API client (`lib/server/api.ts`) **used exclusively by server-side code (Server Actions, Route Handlers)** to call the **two backend RunPod endpoints (Image Generation and Model Generation)**. For MVP, these calls will use RunPod's **synchronous `/runsync` operation**.

### Frontend/Server Separation (within Next.js)

*   **Client Components**: Render interactive UI, use hooks (`useState`, `useEffect`, etc., **and custom hooks from `/hooks/`**), handle user events. Located primarily in `apps/web/components/client/`. **Client components DO NOT directly call the Python backend.** They invoke Server Actions for mutations or fetch data from Route Handlers (or use data passed down from Server Components).
*   **Server Components**: Render static UI, fetch data directly (e.g., from Prisma), access server-only resources. Can call Server Actions internally or pass data to Client Components. Located primarily in `apps/web/components/server/`. Default component type in `apps/web/app/`. **Can call the Python backend via the internal API client (`lib/server/api.ts`) if needed for rendering, but this is typically delegated to Server Actions/Route Handlers.**
*   **Route Handlers (`apps/web/app/api/`)**: Build specific API endpoints callable by the client (e.g., for polling generation status, Stripe webhooks). **These server-side handlers CAN call the Python backend via `lib/server/api.ts`.** They are protected by Clerk authentication middleware and rate limiting.
*   **Server Actions (`apps/web/lib/server/actions/`)**: Handle form submissions and data mutations triggered from Client Components. Run exclusively on the server. **These server-side actions CAN call the Python backend via `lib/server/api.ts` and interact with Prisma.** They are protected by Clerk authentication checks and rate limiting.

### Key Directory Structure (`apps/web`) - Expanded

```
/app
|-- (auth)/                   # Clerk authentication routes
|   |-- sign-in/[[...sign-in]]/page.tsx
|   |-- sign-up/[[...sign-up]]/page.tsx
|   `-- layout.tsx
|-- (main)/                   # Authenticated user routes
|   |-- dashboard/            # Main generation UI
|   |   `-- page.tsx
|   |-- assets/               # Base route for assets (might list all or redirect)
|   |   |-- page.tsx          # Optional: List all assets here
|   |   `-- [assetId]/        # Dynamic route for specific asset
|   |       `-- page.tsx      # Handles Concept & Model View based on status
|   |-- orders/               # User's order history
|   |   |-- page.tsx          # List all orders
|   |   `-- [orderId]/page.tsx  # View specific order details
|   |-- print/[assetId]/      # Configure 3D print for an asset
|   |   `-- page.tsx
|   |-- cart/                 # Shopping Cart
|   |   `-- page.tsx
|   |-- checkout/             # Checkout Process
|   |   `-- page.tsx
|   |-- account/              # User account settings
|   |   `-- page.tsx
|   |-- help/                 # Instructions/How-To Guide
|   |   `-- page.tsx
|   |-- layout.tsx            # Main layout (navbar, sidebar), requires auth
|   `-- layout.tsx            # Main layout (navbar, sidebar), requires auth
|-- api/                      # API Route Handlers (Server-Side ONLY)
|   |-- stripe-webhook/       # Handles incoming Stripe events
|   |   `-- route.ts
|   |-- generation-status/[jobId]/ # Client polls this for status
|   |   `-- route.ts
|   `-- user/                 # Example: API route for user settings
|       `-- route.ts
|-- icon.svg                  # Favicon
|-- layout.tsx                # Root layout (Server Component: ClerkProvider, ThemeProvider)
`-- page.tsx                  # Landing Page
/components/
|-- client/                   # Client Components (interactive, hooks)
|   |-- dashboard-form.tsx
|   |-- asset-concept-view.tsx
|   |-- asset-model-view.tsx
|   |-- asset-viewer-3d.tsx    # The 3D viewer component itself
|   |-- print-configurator.tsx
|   |-- cart-item.tsx
|   |-- checkout-form.tsx
|   |-- dashboard-input-area.tsx
|   |-- dashboard-text-input.tsx
|   |-- dashboard-image-input.tsx
|   |-- style-selector.tsx
|   |-- credit-balance-display.tsx # Shows balance and [+] button in layout
|   |-- buy-credits-modal.tsx      # Modal for purchasing credits
|   |-- credit-option-card.tsx   # Displays a single credit purchase package
|   `-- ...
|-- server/                   # Server Components (data fetching, static rendering)
|   |-- asset-card-preview.tsx # For Dashboard/Discovery lists
|   |-- order-summary.tsx
|   |-- order-list-item.tsx
|   `-- ...
|-- ui/                       # shadcn/ui components (mostly Client, keep as is)
|-- icons/                    # Icon components (Server/Client safe)
/lib/
|-- server/                   # Server-Side ONLY modules
|   |-- actions/              # Server Actions
|   |   |-- generation.ts     # generateConcepts (now takes styleId), regenerate, generateModel
|   |   |-- print.ts          # AddPrintToCart (maybe handles price calc here or separate action)
|   |   |-- cart.ts           # AddDigitalToCart, AddPrintJobConfigToCart, UpdateCart, GetCart
|   |   |-- checkout.ts       # CreateStripeCheckoutSession, HandleStripeWebhook
|   |   |-- order.ts          # GetOrders, GetOrderDetails
|   |   |-- user.ts           # User settings actions
|   |   |-- asset.ts          # Actions related to assets (e.g., togglePublic)
|   |   |-- credits.ts        # FetchCreditOptions (maybe merged into cart/checkout)
|   |   `-- asset.ts          # Actions related to assets (e.g., togglePublic)
|   |-- api.ts                # Client for calling Python backend RunPod endpoints
|   |-- prisma.ts             # Prisma client instance
|   |-- stripe.ts             # Stripe client instance
|   `-- email.ts              # Email sending logic
|-- utils.ts                  # General utilities (Client/Server safe)
|-- constants.ts              # Shared constants (Client/Server safe)
|-- validation.ts             # Zod schemas for form/API validation (Client/Server safe)
/hooks/                       # Custom React hooks (Client-Side ONLY)
|-- use-asset-state.ts      # Manages polling and state for the asset page
|-- use-cart.ts             # Manages local cart state or interacts with server actions
|-- use-buy-credits-modal.ts # Manages modal visibility
`-- ...
/public/                      # Static assets (images, fonts)
/styles/                      # Global CSS
|-- globals.css
// Config files
next.config.js
postcss.config.js
tailwind.config.ts
tsconfig.json
.env.local                    # Environment variables (API keys, DB URL)
...                           # Other config files (eslint, prettier)
```

## 4. User & Sequence Flows (Revised Workflow)

*   **Authentication**: User interacts with Clerk components (Client) -> Clerk handles auth flow -> Server middleware/helpers verify session.

*   **Generation (Initiation)**:
    1.  **User Action (Dashboard Page - `/dashboard`)**: Selects Mode, provides input, selects Style.
    2.  **User Action (Dashboard Page)**: Optionally checks the "Skip Concept" checkbox.
    3.  **User Action (Dashboard Page)**: Clicks "Generate" (button shows `1c` cost).
    4.  **System Action (Client -> Server)**: Invokes `generateConceptsAction`, passing inputs, `styleId`, and `skipConcept` flag.
    5.  **System Action (Server)**: Action verifies credits (>= 1), deducts 1 credit.
        *   **If `skipConcept` is FALSE**: Calls **RunPod Image Generation Endpoint** (`/runsync`) with `operation: 'generate_concepts'`. **Waits for synchronous response.** Creates `Asset` with status `PENDING_CONCEPTS` before call, updates with concept URLs after response.
        *   **If `skipConcept` is TRUE**: Calls **RunPod Model Generation Endpoint** (`/runsync`) with `operation: 'generate_model'`. **Waits for synchronous response.** Creates `Asset` with status `GENERATING_MODEL` before call, updates with `normalized_model_url` after response.
    6.  **System Action (Server)**: Server Action receives the result (concept URLs or `normalized_model_url`) or error from the synchronous RunPod call. Updates the `Asset` status (`CONCEPTS_GENERATED` or `COMPLETED` / `FAILED`).
    7.  **System Action (Server -> Client)**: Server Action returns the asset ID (or error) to the client.
    8.  **System Action (Client)**: User likely stays on Dashboard or navigates to the **Workspace Page** (`/workspace`) to see the new job appear in the list with its initial status.

*   **Navigating Workspace & Viewing Asset**:
    1.  **User Action (Workspace Page - `/workspace`)**: User views the list of their generation jobs and statuses.
    2.  **System Action (Client - Workspace Page)**: Job list status updates via **client-side polling** of the status endpoint for active jobs (WebSockets/SSE are post-MVP).
    3.  **User Action (Workspace Page)**: User clicks on a job entry whose status is `CONCEPTS_GENERATED` or `COMPLETED`.
    4.  **System Action (Client)**: Navigates to the **Asset Page** (`/assets/[assetId]`).

*   **Generation (Concept View & Selection)**: (Occurs on Asset Page *after* navigating from Workspace, *only if concepts were generated*)
    1.  **System Action (Client - Asset Page)**: Page loads, fetches Asset data (status is `CONCEPTS_GENERATED`).
    2.  **System Action (Client - Asset Page)**: UI displays the two concepts (`components/client/asset-concept-view.tsx`).
    3.  **User Action (Asset Page)**: User reviews, clicks "Generate 3D Model".
    4.  **System Action (Client -> Server)**: Invokes `generateModelAction`.
    5.  **System Action (Server)**: Action checks credits/attempts, increments attempt count, updates `Asset` status to `GENERATING_MODEL`, calls **RunPod Model Generation Endpoint** (`/runsync`) with `operation: 'generate_model'` passing the selected `concept_image_url`. **Waits for synchronous response.**
    6.  **System Action (Server)**: Receives the `normalized_model_url` or error from the synchronous RunPod call. Updates the `Asset` status (`COMPLETED` / `FAILED`).
    7.  **System Action (Client - Asset Page)**: UI updates based on the action's success/failure. Status polling will eventually reflect the `COMPLETED`/`FAILED` state set by the server action.

*   **Generation (Model View & Next Steps)**: (Occurs on Asset Page *after* navigating from Workspace or after model generation completes while viewing)
    1.  **System Action (Client - Asset Page/Workspace)**: Status updates to `COMPLETED` (via polling/refresh).
    2.  **System Action (Client - Asset Page)**: If user is on the page, UI updates to show the model viewer and purchase buttons (`components/client/asset-model-view.tsx`).
    3.  (User clicks "Download Model" or "3D Print + Download Model" - flow continues as before)

*   **Buying Credits**:
    1.  **User Action (Main Layout)**: User clicks the `[ + ]` icon next to their credit balance.
    2.  **System Action (Client)**: The `Buy Credits Modal` opens (`components/client/buy-credits-modal.tsx`).
    3.  **System Action (Client)**: Modal fetches available `CreditPurchaseOption` data (via Server Component props or Server Action like `getCreditOptionsAction`).
    4.  **User Action (Buy Credits Modal)**: User selects a credit package and clicks "Add to Cart".
    5.  **System Action (Client -> Server)**: Invokes `addCreditsToCartAction` (`lib/server/actions/cart.ts`) with the chosen `CreditPurchaseOption` ID.
    6.  **System Action (Server)**: Action adds the credit package reference to the user's cart.
    7.  **System Action (Client)**: Modal closes, user is navigated to the **Cart Page** (`/cart`), or cart icon updates.

*   **Print Configuration & Cart/Checkout**: 
    1.  **User Action (Print Page - `/print/[assetId]`)**: User configures print options including **target dimensions/size**. Price breakdown updates.
    2.  **System Action (Client <-> Server)**: Price calculation Server Action (`calculatePriceAction`) queries DB.
    3.  **User Action (Print Page)**: User clicks **"Add Configured Print to Cart"**.
    4.  **System Action (Client -> Server)**: Invokes `savePrintConfigurationAction` (`lib/server/actions/print.ts` or `asset.ts`) which creates a `PrintJobConfig` record in the database with the current settings and calculated price.
    5.  **System Action (Server -> Client Response)**: Returns the ID of the newly created `PrintJobConfig`.
    6.  **System Action (Client -> Server)**: Invokes `addPrintJobConfigToCartAction` (`lib/server/actions/cart.ts`) passing the `printJobConfigId`.
    7.  **System Action (Server)**: Adds a reference to the `PrintJobConfig` to the user's cart representation.
    8.  **System Action (Client)**: User is navigated to the **Cart Page** (`/cart`) or shown confirmation.
    9.  **User Action (Print Page - Alternative)**: User clicks **"Save and Exit" / "Save & Back to Workspace"**.
    10. **System Action (Client -> Server)**: Invokes `savePrintConfigurationAction` to create/update a `PrintJobConfig` record with the current settings.
    11. **System Action (Client)**: User is navigated back to the Workspace Page (`/workspace`).

*   **Cart & Checkout**: 
    1.  **User Action (Cart Page - `/cart`)**: User reviews items (digital assets, configured prints referencing `PrintJobConfig`, credit packages).
    2.  **System Action (Client -> Server)**: Cart page fetches details for displayed items based on stored references (`Asset`, `PrintJobConfig`, `CreditPurchaseOption`).
    3.  **User Action (Cart Page)**: User clicks "Proceed to Checkout".
    4.  **System Action (Client)**: Navigates to **Checkout Page** (`/checkout`).
    5.  **User Action (Checkout Page)**: Enters payment/shipping.
    6.  **User Action (Checkout Page)**: Clicks "Place Order".
    7.  **System Action (Client -> Server)**: Invokes `createOrderFromCartAction`.
    8.  **System Action (Server)**: Action verifies payment via webhook. If successful:
        *   Creates `Order` record.
        *   Creates `OrderItem` records based on cart contents, linking to the appropriate `Asset` ID, `PrintJobConfig` ID, or `CreditPurchaseOption` ID.
        *   Updates status of relevant `PrintJobConfig` records to `ORDERED` and links them to the `OrderItem`.
        *   Grants purchased credits (if any).
        *   Clears cart.
        *   **Triggers Final Rescaling:** For each `OrderItem` linked to a `PrintJobConfig`, fetches the config, gets the associated `asset.normalized_model_url` (the *current* URL) and `printJobConfig.targetDimensions`. Calls the **RunPod Model Generation Endpoint** (`/runsync`) with `operation: 'rescale_model'`. **Waits for synchronous response.**
        *   **Receives Scaled Model URL**: Gets the `new_scaled_model_url` or error from the synchronous RunPod call.
        *   **Updates Asset**: Updates the associated `Asset` record in Prisma, setting `normalized_model_url` to the `new_scaled_model_url`.
        *   **Deletes Old Model**: Triggers the deletion of the *previous* model file from storage (using the URL stored before the update).
        *   **Triggers Email Sending**: Calls `sendPrintOrderEmailAction` passing the `new_scaled_model_url` and order details.
    9.  **System Action (Client)**: Redirected to order confirmation/Orders page.

*   **Order Viewing & Downloads**: 
    1.  **User Action (Orders Page - `/orders`)**: Navigates to page.
    2.  **User Action (Orders Page)**: Clicks order.
    3.  **System Action (Client - Order Detail Page)**: UI displays details. Download links provide the **current** `normalized_model_url` of the model (as generated initially).

## 5. Technical Considerations

*   **Strict Separation Enforcement**: Use tools like `server-only` and `client-only` packages.
*   **Rate Limiting**: Implement **on the server** (Server Actions, Route Handlers).
*   **Authentication**: Secure all **server-side logic**.
*   **Rescaling UI/UX**: Provide clear feedback during rescaling (loading states, validation). Decide if rescaling happens implicitly before checkout or explicitly via a user action.
*   **Error Handling**: Handle errors gracefully across client, server, and backend.
*   **Scalability**: Next.js serverless functions and Runpod backend scale independently.
*   **RunPod Communication (MVP)**: Server Actions will use **synchronous calls (`/runsync`)** to the RunPod endpoints. This simplifies frontend state management for MVP but means the Server Action duration is tied to the RunPod job duration. Long-running jobs exceeding timeouts might require switching to asynchronous calls (`/run` + `/status` polling) post-MVP.
*   **Large File Uploads/Downloads**: Use direct client-to-Supabase uploads/downloads with signed URLs generated by Server Actions.
*   **3D Viewer Performance**: Client-side concern.
*   **State Synchronization**: Polling via Route Handlers for MVP.
*   **Component Structure**: Maintain discipline in placing components in `client/` vs `server/` directories.
*   **Cart Management**: For MVP, the cart state will be managed **server-side**. Server Actions will handle adding/removing/updating items, interacting directly with the database (or potentially a server session linked to the user).
*   **Asset Page State**: The `/assets/[assetId]` page state management (`use-asset-state.ts`) needs to handle loading the asset data, polling for status updates during generation, displaying concepts/models appropriately, and managing loading/error states based on the `Asset.status`.
*   **Print Configuration State**: The state between the Print Page and adding to cart/checkout is now contained within the Print Page itself until the final action.
*   **Credit Logic**: Server Actions (`generateConceptsAction`, `generateModelAction`) must reliably check and deduct credits atomically (ideally within a transaction if possible with Prisma). Implement the "first model generation free" logic based on `Asset.modelGenerationAttempts`.
*   **Mixed Cart/Checkout**: Stripe checkout session creation needs to handle potentially mixed items (physical prints needing shipping, digital assets, credit packages). Credit packages map to specific Stripe Price IDs.
*   **Webhook Reliability**: The Stripe webhook handler is critical for granting credits and asset access after successful payment. Ensure it's robust and handles idempotency.
*   **UI Updates**: Credit balance display in the main layout should update automatically after generation actions or credit purchases (requires state management or re-fetching).
*   **Skip Concept Backend Logic**: The Model Generation Worker's `generate_model` operation handles initial inputs OR concept URLs, and includes normalization.
*   **Final Rescaling Trigger**: The Next.js server (likely within the webhook handler or a subsequent server action triggered by it) is responsible for orchestrating the post-payment call to the `rescale_model` backend operation before sending the print email.
*   **Normalized vs. Scaled URLs (Destructive Scaling)**: The `Asset.normalized_model_url` field will store the URL of the *most recently generated version* of the model. Initially, this is the normalized version. **After a print order checkout**, the rescaling process generates a new scaled model. The `Asset.normalized_model_url` will be **updated** to this new scaled URL, and the **previous model file (whether normalized or previously scaled) will be deleted from storage.** The `PrintJobConfig.targetDimensions` stores the dimensions used for a specific scaling operation. Consequence: Digital downloads will always provide the *latest* version (which might be scaled), not necessarily the original normalized version.
*   **Price Calculation**: Must accurately use the *target* dimensions/size selected by the user on the Print Configuration page.
*   **Workspace Page Updates**: Needs efficient fetching and status updating for the job list. For MVP, this will be implemented via **client-side polling** of the `/api/generation-status/[assetId]/route.ts` endpoint for active jobs. Server-sent events or WebSockets could be considered post-MVP if polling proves insufficient.
*   **Independent Scaling/Cost**: Separating the services allows scaling GPUs only for model generation and potentially using cheaper CPU instances for image generation. Error handling needs to consider failures in either service independently.
*   **Saving Print Configurations**: The creation of a `PrintJobConfig` record *before* adding to cart allows multiple distinct print configurations for the same base asset to exist simultaneously.

## 6. Implementation Tasks

### Setup & Core
- [ ] Initialize Monorepo (pnpm workspaces).
- [ ] Setup Next.js `apps/web` project (App Router, TypeScript).
- [ ] Setup Prisma `packages/db`.
- [ ] Configure Tailwind CSS & Shadcn/UI.
- [ ] Implement Root Layout (`/app/layout.tsx`) with ThemeProvider.
- [ ] Implement basic Landing Page (`/app/page.tsx`).
- [ ] Setup Clerk authentication (Provider, Middleware, Auth Routes `/app/(auth)/...`).
- [ ] Implement Main Authenticated Layout (`/app/(main)/layout.tsx`) with Navbar/Sidebar.
- [ ] Configure API Client (`lib/server/api.ts`) to handle two backend endpoint URLs.

### Dashboard
- [ ] Create Dashboard Page (`/app/(main)/dashboard/page.tsx`).
- [ ] Implement Input Mode Tabs (Text/Image).
- [ ] Implement Server Action/Component Logic to fetch active Styles from DB.
- [ ] Implement Style Selector Component (`components/client/style-selector.tsx`).
- [ ] Implement Text Input Component (`components/client/dashboard-text-input.tsx`).
- [ ] Implement Image Input Component (`components/client/dashboard-image-input.tsx`).
- [ ] Implement "Skip Concept" Checkbox UI.
- [ ] Integrate inputs, style selector, and skip checkbox into `dashboard-input-area.tsx`.
- [ ] Modify Server Action (`generateConceptsAction`) to accept and pass `styleId` and `skipConcept` flag, setting initial status appropriately.
- [ ] Modify Server Action (`generateConceptsAction`) to call the correct backend endpoint (Image Gen or Model Gen) based on `skipConcept` flag and deduct credits.
- [ ] Implement logic to display Recent Activity (fetching user's assets/orders).
- [ ] Implement Public Asset Feed (Infinite Scroll) on Dashboard.
- [ ] Implement Server Action (`getPublicAssetsAction` in `lib/server/actions/asset.ts`) for fetching paginated public assets.
- [ ] Implement Client Component (`components/client/public-asset-feed.tsx`) for infinite scroll logic.
- [ ] Integrate `public-asset-feed.tsx` into the Dashboard page.
- [ ] Ensure Asset Preview Component (`components/server/asset-card-preview.tsx` or similar) is used by the feed.

### Workspace & Asset Viewing
- [ ] Create Workspace Page (`/app/(main)/workspace/page.tsx`).
- [ ] Implement Job List component for Workspace page (fetches user Assets, displays clear status indicators like "Select Concept"/"View Model" based on `Asset.status`, handles conditional links).
- [ ] Implement status update mechanism for Workspace list via **polling** the status endpoint.
- [ ] Create dynamic Asset Page (`/app/(main)/assets/[assetId]/page.tsx`).
- [ ] Implement state management hook (`hooks/use-asset-state.ts`) for Asset Page polling/state.
- [ ] Implement API Route Handler for status polling (`/app/api/generation-status/[assetId]/route.ts`).
- [ ] Implement Concept View (`components/client/asset-concept-view.tsx`) on Asset Page.
- [ ] Implement Server Action (`regenerateConceptsAction`).
- [ ] Implement Server Action (`generateModelAction`) - Handles credit check/first free attempt logic & regeneration attempts.
- [ ] Implement 3D Model Viewer (`components/client/asset-viewer-3d.tsx`).
- [ ] Implement Model View (`components/client/asset-model-view.tsx`) on Asset Page.
- [ ] Implement Visibility Toggle UI on Asset Page.
- [ ] Implement Server Action (`toggleAssetVisibilityAction` in `lib/server/actions/asset.ts`).
- [ ] Implement "Download Model" button logic on Asset Page (adds Asset reference to cart).
- [ ] Implement "3D Print + Download Model" button logic on Asset Page (navigates to print config).
- [ ] Implement "Regenerate Model" button logic on Asset Page (Model View).

### Print Configuration
- [ ] Create Print Configuration Page (`/app/(main)/print/[assetId]/page.tsx`).
- [ ] Implement Print Config Form (`components/client/print-configurator.tsx`) including target dimension/size inputs.
- [ ] Implement Dynamic Price Calculation UI Section (using target size).
- [ ] Implement Server Action (`calculatePriceAction` in `lib/server/actions/print.ts`) - Fetches pricing models, calculates volume from target dimensions, returns estimated price.
- [ ] Implement Server Action (`savePrintConfigurationAction` in `lib/server/actions/print.ts`) to create `PrintJobConfig` record.
- [ ] Implement "Add Configured Print to Cart" button logic (calls `savePrintConfigurationAction` then `addPrintJobConfigToCartAction`).
- [ ] Implement "Save and Exit" / "Save & Back to Workspace" button logic (calls `savePrintConfigurationAction`, then navigates to Workspace).

### Cart & Checkout
- [ ] Implement Server Actions for Cart Management (`lib/server/actions/cart.ts`: `AddDigitalToCart`, `AddPrintJobConfigToCart`, `AddCreditsToCart`, `UpdateCart`, `GetCart`).
- [ ] Create Cart Page (`/app/(main)/cart/page.tsx`).
- [ ] Implement Cart Item Component (`components/client/cart-item.tsx`) distinguishing item types.
- [ ] Implement Cart Page logic (fetching full details for items, calculating totals, proceeding).
- [ ] Create Checkout Page (`/app/(main)/checkout/page.tsx`).
- [ ] Implement Checkout Form (`components/client/checkout-form.tsx`) with Stripe Elements & shipping address collection.
- [ ] Implement Server Action (`createStripeCheckoutSession` in `lib/server/actions/checkout.ts`).
- [ ] Implement Stripe Webhook Handler (`/app/api/stripe-webhook/route.ts`): Creates Order/OrderItems, updates `PrintJobConfig` status, grants credits, **triggers rescaling** for `PrintJobConfig` items, **updates Asset.normalized_model_url** with scaled URL, **triggers deletion of old model file**, **triggers email** with new scaled URL.
- [ ] Define and Implement Server Action/Logic for updating Asset URL and deleting old file (likely called from webhook handler).

### Orders
- [ ] Implement Server Actions for Orders (`lib/server/actions/order.ts`: `GetOrders`, `GetOrderDetails`).
- [ ] Create Order Management Page (`/app/(main)/orders/page.tsx`).
- [ ] Implement Order List Item Component (`components/server/order-list-item.tsx`).
- [ ] Create Order Detail Page (`/app/(main)/orders/[orderId]/page.tsx`).
- [ ] Implement logic for providing download links (for the *current* `normalized_model_url` on the Asset, which may be scaled) on Order Detail Page.
- [ ] Update Order Detail Page/Components to show target print dimensions from the associated `PrintJobConfig` (if applicable).

### Account & Misc
- [ ] Create Account Page (`/app/(main)/account/page.tsx`).
- [ ] Implement Stripe Customer Portal integration or payment method management.
- [ ] Implement Server Action/Module for sending print order emails (`lib/server/email.ts`).
- [ ] Implement Global Error Handling & Loading States.
- [ ] Setup Rate Limiting (`@upstash/ratelimit`) on relevant Server Actions/Route Handlers.
- [ ] Refine Styling & Ensure Responsiveness.

### Help / Instructions
- [ ] Create Help Page (`/app/(main)/help/page.tsx`).
- [ ] Implement static content sections for:
    - Generating a model (standard flow: input -> concepts -> model -> download/print).
    - Bypassing concept generation (skip concept flow).
    - Viewing and managing jobs via the Workspace page.
    - Viewing and using community models (from Dashboard Discovery section -> Asset Page -> Download/Print).

### Credits & Purchase Flow
- [ ] Implement Credit Balance display component (`components/client/credit-balance-display.tsx`) and integrate into layout.
- [ ] Implement Server Action/Component logic to fetch active Credit Purchase Options.
- [ ] Implement Buy Credits Modal (`components/client/buy-credits-modal.tsx`).
- [ ] Implement Credit Option Card (`components/client/credit-option-card.tsx`).
- [ ] Implement Hook (`hooks/use-buy-credits-modal.ts`) for modal state.
- [ ] Integrate `addCreditsToCartAction` into Buy Credits Modal flow.