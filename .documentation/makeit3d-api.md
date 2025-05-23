openapi: 3.0.0
info:
  title: MakeIt3D BFF API
  version: v1.1.0
  description: |-
    Backend-For-Frontend (BFF) API for the MakeIt3D application.
    This API serves as an intermediary between the mobile frontend and external AI services (OpenAI for 2D concept generation, Tripo AI for 3D model generation).

    **Core Principles for API v1.1.0:**
    1.  All generation endpoints require a client-generated `task_id` (overall job ID) to be passed in the request body.
    2.  Inputs requiring binary data (images, sketches, models for refinement) must first be uploaded by the client to its Supabase Storage. The client then provides the full Supabase URL of this asset to the BFF.
    3.  All generation tasks are asynchronous. Endpoints that initiate an AI processing step will return a `celery_task_id` (Celery's task identifier).
    4.  The frontend should then poll the `GET /tasks/{celery_task_id}/status?service={service}` endpoint (where `service` is 'openai' or 'tripoai') to get real-time updates on the specific AI processing step and the final Supabase URL of the generated asset(s) for that step.
    5.  The BFF is responsible for handling AI service interactions, temporary asset downloads (e.g., from Tripo AI), placing final generated assets into the client's Supabase Storage, and updating metadata (including status and asset URLs) in the client's dedicated Supabase tables (`concept_images`, `models`).

servers:
  - url: http://localhost:8000 # Replace with your actual deployment URL
    description: Local development server

components:
  schemas:
    # Request Schemas
    ImageToImageRequest:
      type: object
      required:
        - task_id
        - prompt
        - input_image_asset_url
      properties:
        task_id:
          type: string
          description: Client-generated unique ID for the entire generation job/workspace item.
          example: "task_workspace_abc123"
        prompt:
          type: string
          description: A text description of the desired image(s).
          example: "A futuristic cityscape at dusk."
        input_image_asset_url:
          type: string
          format: url
          description: Full Supabase URL to the user-uploaded input image.
          example: "https://[project_ref].supabase.co/storage/v1/object/public/user_assets_bucket/task_workspace_abc123/source_image.png"
        style:
          type: string
          nullable: true
          description: An optional style hint for the generation.
          example: "Impressionistic, vibrant colors."
        background: 
          type: string
          nullable: true
          enum: ["transparent", "opaque", "auto"]
          default: "auto"
          description: Background setting for the generated image(s) (OpenAI).
        n:
          type: integer
          format: int32
          default: 1
          minimum: 1
          maximum: 4 # Adjusted based on typical OpenAI limits, DALL-E 2 edit was 1, DALL-E 3 generation is 1.
                     # Check actual OpenAI client capabilities. For now, 4 is a common max for some generation types.
          description: The number of images to generate.

    TextToModelRequest:
      type: object
      required:
        - task_id
        - prompt
      properties:
        task_id:
          type: string
          description: Client-generated unique ID for the entire generation job.
          example: "task_workspace_def456"
        prompt:
          type: string
          description: Text prompt for 3D model generation.
          example: "A violet colored cartoon flying elephant with big flapping ears"
        style:
          type: string
          nullable: true
          description: Optional style hint for Tripo AI.
        texture:
          type: boolean
          default: true
          description: Whether to generate textures for the model.
        pbr:
          type: boolean
          nullable: true
          description: Enable PBR texturing (Tripo AI). If true, texture is implied as true.
        model_version:
          type: string
          nullable: true
          description: Tripo AI model version (e.g., "v2.5-20250123").
        face_limit:
          type: integer
          nullable: true
          description: Limit the number of faces on the output model (Tripo AI).
        auto_size:
          type: boolean
          nullable: true
          description: Automatically scale the model to real-world dimensions (Tripo AI).
        texture_quality:
          type: string
          nullable: true
          enum: ["standard", "detailed"]
          description: Texture quality for Tripo AI.

    ImageToModelRequest: # Used for image-to-model and for generating model from a selected concept
      type: object
      required:
        - task_id
        - input_image_asset_urls
      properties:
        task_id:
          type: string
          description: Client-generated unique ID for the entire generation job.
          example: "task_workspace_ghi789"
        input_image_asset_urls:
          type: array
          items:
            type: string
            format: url
          description: |
            List of full Supabase URLs for input images.
            
            **Single Image Mode (1 image):** Uses Tripo's `image_to_model` API
            - Provide 1 image URL for single-view 3D model generation
            
            **Multiview Mode (2-4 images):** Uses Tripo's `multiview_to_model` API  
            - Images must be provided in exact order: [front, left, back, right]
            - Front view (position 0) is REQUIRED and cannot be omitted
            - Other views (left, back, right) are optional but must maintain position order
            - If you have fewer than 4 images, provide them in order starting with front
            - Examples:
              - 2 images: [front, left] 
              - 3 images: [front, left, back]
              - 4 images: [front, left, back, right]
          example: 
            - Single: ["https://[project_ref].supabase.co/storage/v1/object/public/user_inputs_bucket/task_workspace_ghi789/photo.png"]
            - Multiview: ["https://[project_ref].supabase.co/storage/v1/object/public/user_inputs_bucket/task_workspace_ghi789/front.png", "https://[project_ref].supabase.co/storage/v1/object/public/user_inputs_bucket/task_workspace_ghi789/left.png"]
        prompt:
          type: string
          nullable: true
          description: Optional text prompt to guide Tripo AI.
        style:
          type: string
          nullable: true
          description: Optional style hint for Tripo AI.
        texture:
          type: boolean
          default: true
        pbr:
          type: boolean
          nullable: true
        model_version:
          type: string
          nullable: true
        face_limit:
          type: integer
          nullable: true
        auto_size:
          type: boolean
          nullable: true
        texture_quality:
          type: string
          nullable: true
          enum: ["standard", "detailed"]
        orientation:
          type: string
          nullable: true
          enum: ["default", "align_image"]
          description: Model orientation for Tripo AI.

    SketchToModelRequest:
      type: object
      required:
        - task_id
        - input_sketch_asset_url
      properties:
        task_id:
          type: string
          description: Client-generated unique ID for the entire generation job.
          example: "task_workspace_jkl012"
        input_sketch_asset_url:
          type: string
          format: url
          description: Full Supabase URL to the user-uploaded sketch image.
          example: "https://[project_ref].supabase.co/storage/v1/object/public/user_inputs_bucket/task_workspace_jkl012/sketch.png"
        prompt:
          type: string
          nullable: true
        style:
          type: string
          nullable: true
        texture:
          type: boolean
          default: true
        pbr:
          type: boolean
          nullable: true
        model_version:
          type: string
          nullable: true
        face_limit:
          type: integer
          nullable: true
        auto_size:
          type: boolean
          nullable: true
        texture_quality:
          type: string
          nullable: true
          enum: ["standard", "detailed"]
        orientation:
          type: string
          nullable: true
          enum: ["default", "align_image"]

    RefineModelRequest:
      type: object
      required:
        - task_id
        - input_model_asset_url
      properties:
        task_id:
          type: string
          description: Client-generated unique ID for the entire workspace job/item this refinement belongs to.
          example: "task_workspace_mno345"
        input_model_asset_url:
          type: string
          format: url
          description: Full Supabase URL to the 3D model (e.g., .glb) that needs to be refined.
          example: "https://[project_ref].supabase.co/storage/v1/object/public/user_assets_bucket/task_workspace_mno345/model_to_refine.glb"
        prompt:
          type: string
          nullable: true
          description: Text prompt to guide the refinement process.
          example: "Make it look more weathered and ancient."
        draft_model_task_id:
          type: string
          nullable: true
          description: Optional. If the input model is already the result of a previous Tripo AI task, provide its Tripo task ID.
          example: "tripo_task_prev_abc"
        texture:
          type: boolean
          default: true
          description: Whether to generate/regenerate textures for the model.
        pbr:
          type: boolean
          nullable: true
          description: Enable PBR texturing (Tripo AI). If true, texture is implied as true.
        model_version:
          type: string
          nullable: true
          description: Tripo AI model version for refinement (e.g., "v2.5-20250123").
        face_limit:
          type: integer
          nullable: true
          description: Limit the number of faces on the output refined model (Tripo AI).
        auto_size:
          type: boolean
          nullable: true
          description: Automatically scale the refined model to real-world dimensions (Tripo AI).
        texture_quality:
          type: string
          nullable: true
          enum: ["standard", "detailed"]
          description: Texture quality for the refined model (Tripo AI).

    # Response Schemas
    TaskIdResponse:
      type: object
      required:
        - celery_task_id
      properties:
        celery_task_id:
          type: string
          description: The Celery task ID for the initiated asynchronous background task. The client uses this ID to poll the status endpoint.
          example: "abc123xyz456"

    TaskStatusResponse:
      type: object
      description: Response schema for the task status polling endpoint.
      required:
        - task_id # This is the Celery Task ID used in the polling request
        - status
      properties:
        task_id:
          type: string
          description: The Celery task ID of the job being polled (matches the {celery_task_id} path parameter).
          example: "abc123xyz456"
        status:
          type: string
          description: |
            Current status of the AI processing step.
            Possible values:
            - `pending`: Task is waiting to be processed or has been queued
            - `processing`: Task is currently being processed by the AI service
            - `complete`: Task has completed successfully and the asset is available at `asset_url`
            - `failed`: Task has failed with an error message in the `error` field
          example: "complete"
        asset_url:
          type: string
          format: url
          nullable: true
          description: Full Supabase URL to the generated asset. Only present if status is 'complete'.
          example: "https://[project_ref].supabase.co/storage/v1/object/public/generated_assets_bucket/concept_images/task_workspace_abc123/concept_image_0.png"
        error:
          type: string
          nullable: true
          description: Error message if the task failed.
          example: "AI service timed out."

    ErrorResponse:
      type: object
      properties:
        detail:
          type: string
          description: A human-readable error message.
        # For more complex error responses, you might add error codes, etc.

  securitySchemes:
    apiKey:
      type: apiKey
      in: header
      name: X-API-Key


paths:
  /generation/image-to-image:
    post:
      summary: Generate 2D concept images from an input image and prompt (async)
      tags:
        - Generation Endpoints
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ImageToImageRequest'
      responses:
        '202':
          description: Request accepted, AI image generation task initiated. Poll status endpoint with `celery_task_id`.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/TaskIdResponse'
        '400':
          description: Bad Request (e.g., validation error, invalid Supabase URL for input).
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '500':
          description: Internal Server Error (e.g., failed to dispatch Celery task).
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /generation/text-to-model:
    post:
      summary: Generate a 3D model from a text prompt (async)
      tags:
        - Generation Endpoints
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/TextToModelRequest'
      responses:
        '202':
          description: Request accepted, AI model generation task initiated. Poll status endpoint with `celery_task_id`.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/TaskIdResponse'
        '400':
          description: Bad Request.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '500':
          description: Internal Server Error.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /generation/image-to-model:
    post:
      summary: Generate a 3D model from input image(s) - Single or Multiview
      description: |
        This endpoint generates 3D models from input images and automatically selects the appropriate mode:
        
        **Single Image Mode (1 image):** 
        - Uses Tripo's `image_to_model` API for single-view generation
        - Provide 1 image URL in `input_image_asset_urls`
        
        **Multiview Mode (2-4 images):**
        - Uses Tripo's `multiview_to_model` API for higher quality multiview generation  
        - Images must be in exact order: [front, left, back, right]
        - Front view is REQUIRED (cannot be omitted)
        - Other views are optional but must maintain positional order
        - Examples: [front], [front, left], [front, left, back], [front, left, back, right]
        
        The client should upload all images to Supabase storage first and provide the URLs in the correct order.
      tags:
        - Generation Endpoints
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/ImageToModelRequest'
      responses:
        '202':
          description: Request accepted, AI model generation task initiated. Poll status endpoint with `celery_task_id`.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/TaskIdResponse'
        '400':
          description: Bad Request.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '500':
          description: Internal Server Error.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /generation/sketch-to-model:
    post:
      summary: Generate a 3D model from a user sketch (async)
      description: |
        The client should upload the sketch image to its Supabase storage first and provide the URL in `input_sketch_asset_url`.
      tags:
        - Generation Endpoints
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/SketchToModelRequest'
      responses:
        '202':
          description: Request accepted, AI model generation task initiated. Poll status endpoint with `celery_task_id`.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/TaskIdResponse'
        '400':
          description: Bad Request.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '500':
          description: Internal Server Error.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /generation/refine-model:
    post:
      summary: Refine an existing 3D model (async)
      description: |
        The client should upload the model to be refined to its Supabase storage first and provide the URL in `input_model_asset_url`.
      tags:
        - Generation Endpoints
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/RefineModelRequest'
      responses:
        '202':
          description: Request accepted, AI model refinement task initiated. Poll status endpoint with `celery_task_id`.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/TaskIdResponse'
        '400':
          description: Bad Request.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '500':
          description: Internal Server Error.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /tasks/{celery_task_id}/status:
    get:
      summary: Poll for the status of an AI generation task
      tags:
        - Task Status
      parameters:
        - name: celery_task_id
          in: path
          required: true
          description: The Celery task ID received from one of the generation endpoints.
          schema:
            type: string
          example: "abc123xyz456"
        - name: service
          in: query
          required: true
          description: Specifies which AI service's task status is being queried.
          schema:
            type: string
            enum: [openai, tripoai]
          example: "openai"
      responses:
        '200':
          description: Successfully retrieved task status.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/TaskStatusResponse'
        '400':
          description: Bad Request (e.g., invalid service parameter).
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '404':
          description: Task not found or Celery task result not yet available (still pending).
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '500':
          description: Internal Server Error (e.g., error fetching details from Supabase for a completed task).
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'

  /images/{bucket_name}/{file_path}: # This endpoint might become less relevant if client directly uses Supabase URLs from metadata tables.
                                    # Could be kept for specific BFF-brokered access or removed if client accesses storage directly.
                                    # For now, keeping it as it was, but its utility should be reassessed.
    get:
      summary: Download Generated Image (Potentially Legacy)
      description: |-
        Downloads a previously generated image (e.g., OpenAI concept) stored in Supabase.
        With the new architecture, clients might fetch directly from Supabase Storage using URLs obtained from metadata tables.
        This endpoint's relevance should be reviewed.
      operationId: downloadGeneratedImage
      parameters:
        - name: bucket_name
          in: path
          required: true
          description: The Supabase storage bucket name where the image is stored.
          schema:
            type: string
            example: "generated_assets_bucket" # Example updated bucket name
        - name: file_path # This should now be the full path within the bucket, e.g., concepts/task_id/0.png
          in: path
          required: true
          description: The full path to the image file within the bucket (e.g., concepts/task_workspace_abc123/0.png).
          schema:
            type: string
            example: "concepts/task_workspace_abc123/0.png"
      responses:
        '200':
          description: Successfully retrieved the image.
          content:
            image/png: {}
            image/jpeg: {}
            image/webp: {}
        '404':
          description: Image not found.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '500':
          description: Internal Server Error / Failed to download image.
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse' 