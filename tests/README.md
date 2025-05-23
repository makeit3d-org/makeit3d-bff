# MakeIt3D Backend Testing

This directory contains tests for the MakeIt3D Backend For Frontend (BFF) service.

## Running Tests

The `makeit3d-bff` project provides two convenient ways to run tests:

### 1. Bash Script Runner

For basic test execution, you can use the Bash script:

```bash
# Run all tests with default settings
./tests/run_tests.sh

# Run a specific test file
./tests/run_tests.sh tests/test_endpoints.py

# Run with logs enabled
./tests/run_tests.sh -s

# Run with verbose output
./tests/run_tests.sh -v

# Run a specific test with logs
./tests/run_tests.sh tests/test_endpoints.py::test_generate_image_to_image -s
```

### 2. Python Script Runner (More Advanced)

For more advanced test options, use the Python runner:

```bash
# Run all tests
./tests/run_tests.py

# List all available tests
./tests/run_tests.py -l

# Run a specific test
./tests/run_tests.py -t test_generate_image_to_image

# Run with logs enabled
./tests/run_tests.py -s

# Run with verbose output and fail fast
./tests/run_tests.py -v -f

# Run a specific test file with logs
./tests/run_tests.py path/to/test.py -s
```

## List Available Tests

To see all available tests in the project, use:

```bash
# List all tests in the default file (tests/test_endpoints.py)
./tests/run_tests.py -l

# List tests in a specific file
./tests/run_tests.py tests/other_test_file.py -l
```

This will display a numbered list of all test functions, making it easy to:
1. See what tests are available to run
2. Copy test names for running specific tests
3. Understand the test coverage

Example output:
```
Available tests in tests/test_endpoints.py:
  1. test_generate_image_to_image
  2. test_generate_text_to_model
  3. test_generate_image_to_model
  4. test_generate_multiview_to_model
  5. test_generate_sketch_to_model
  6. test_supabase_upload_and_metadata
```

### Manual Method (using docker-compose directly)

You can also run tests manually using docker-compose:

```bash
# Run all tests
docker-compose exec backend pytest tests/test_endpoints.py

# Run with logs enabled
docker-compose exec backend pytest tests/test_endpoints.py -s --log-cli-level=INFO

# Run a specific test
docker-compose exec backend pytest tests/test_endpoints.py::test_generate_image_to_image

# List available tests (collect only)
docker-compose exec backend pytest tests/test_endpoints.py --collect-only
```

## Test Structure

The tests in this project are organized as follows:

- **Unit Tests**: Test individual functions and components in isolation
- **Integration Tests**: Test the interaction between different components
- **End-to-End Tests**: Test the entire flow from API request to response

## Test Environment

The tests run inside the Docker container to ensure consistent execution environment. This means:

1. All dependencies are pre-installed in the container
2. The tests can access other services in the Docker network
3. Environment variables are properly set

## Test Timing Logs

Many of the tests include detailed timing logs to help diagnose performance issues. These logs measure:

- API response time
- Image download time
- Task processing time
- Total test execution time

To view these logs, run the tests with the `-s` flag (show logs).

## Adding New Tests

When adding new tests, follow these guidelines:

1. Use the existing test structure as a template
2. Include appropriate logging
3. Add timing measurements for performance-critical sections
4. Handle errors and clean up test resources
5. Document any special setup or teardown requirements

## Required Services

The tests require the following services to be running:

- Redis (for task queue and results)
- Backend FastAPI Service
- Celery Worker

These are all started automatically when you run `docker-compose up`.

## Environment Variables

The tests use the same environment variables as the main application. These are passed to the Docker containers via the `docker-compose.yml` file.

If you're running tests locally (not recommended), you'll need to set these variables yourself.

## Test Execution Flow Details

This section outlines the sequence of operations for each test in `test_endpoints.py`.

### `test_generate_image_to_image`

1.  Downloads a public JPG image.
2.  **Simulates client behavior**: Uploads this image to a test path in Supabase Storage using `supabase_client.upload_image_to_storage`.
3.  Constructs the Supabase URL for the uploaded image.
4.  Calls BFF `POST /generate/image-to-image` endpoint with a JSON payload containing a client-generated `task_id`, the `input_image_asset_url` (the Supabase URL), prompt, style, etc.
    *   *(BFF Internally)*: BFF fetches the input image from the provided `input_image_asset_url` (via `supabase_handler.fetch_asset_from_storage`), creates a record in `concept_images` table (status 'pending') via `supabase_handler.create_concept_image_record`. It dispatches a Celery task, then updates the `concept_images` record with the Celery task ID (as `ai_service_task_id`) and status 'processing'. The Celery task calls OpenAI, receives image data. The Celery task then uploads these to the client's Supabase Storage (`generated_assets_bucket/concepts/{client_task_id}/...`) via `supabase_handler.upload_asset_to_storage` and updates the `concept_images` table record to 'complete' with the Supabase `asset_url` via `supabase_handler.update_concept_image_record`.
5.  Receives a Celery `task_id` from the BFF.
6.  Polls BFF `GET /tasks/{celery_task_id}/status?service=openai` until status is 'complete'.
7.  Asserts the response contains `image_urls` in the `result` field (which are Supabase Storage URLs for the generated concepts).
8.  Downloads the generated concept image(s) from the returned Supabase URLs.

### `test_generate_text_to_model`

1.  Calls BFF `POST /generate/text-to-model` endpoint with a JSON payload containing a client-generated `task_id`, text prompt, and `texture_quality`.
    *   *(BFF Internally)*: BFF creates a record in `models` table (status 'pending') via `supabase_handler.create_model_record`. It dispatches a Celery task, then updates the `models` record with the Celery task ID (as `ai_service_task_id`) and status 'processing'. The Celery task calls Tripo AI, gets a Tripo task ID, and updates the `models` record with this `ai_provider_task_id` and status remains 'processing'.
2.  Receives a Celery `task_id` from the BFF.
3.  Polls BFF `GET /tasks/{celery_task_id}/status?service=tripo` until status is 'complete'.
    *   *(BFF Internally, within status endpoint for Tripo)*: When Tripo AI job is done, BFF downloads the model from Tripo's temporary URL, uploads it to client's Supabase Storage (`generated_assets_bucket/models/{client_task_id}/...`) via `supabase_handler.upload_asset_to_storage`, and updates the `models` table record to 'complete' with the new Supabase `asset_url` via `supabase_handler.update_model_record`.
4.  Asserts the response contains an `asset_url` (Supabase Storage URL for the model).
5.  Downloads the generated GLB model from the Supabase URL.

### `test_generate_image_to_model`

1.  Downloads a public image.
2.  **Simulates client behavior**: Uploads this image to a test path in Supabase Storage.
3.  Constructs the Supabase URL for the uploaded image.
4.  Calls BFF `POST /generate/image-to-model` endpoint with a JSON payload containing a client-generated `task_id`, `input_image_asset_urls` (list containing **one** Supabase URL for single-view mode), prompt, and `texture_quality`.
    *   *(BFF Internally)*: BFF fetches the image from the Supabase URL (via `supabase_handler.fetch_asset_from_storage`). Creates a record in `models` table (status 'pending') via `supabase_handler.create_model_record`. Dispatches Celery task, updates `models` record with Celery task ID and status 'processing'. Celery task calls Tripo AI's `image_to_model` endpoint (single-view), gets Tripo task ID, updates `models` record with `ai_provider_task_id` and status remains 'processing'.
5.  Receives a Celery `task_id` from the BFF.
6.  Polls BFF `GET /tasks/{celery_task_id}/status?service=tripo`.
    *   *(BFF Internally, Status Endpoint)*: Handles Tripo completion, download from Tripo, upload to client's Supabase Storage, and updates client's `models` table as in `test_generate_text_to_model`.
7.  Asserts the response contains an `asset_url` (Supabase URL for the model).
8.  Downloads the model from the Supabase URL.

### `test_generate_multiview_to_model`

1.  Downloads multiple public images for multiview testing.
2.  **Simulates client behavior**: Uploads these images to test paths in Supabase Storage with view-specific naming.
3.  Constructs Supabase URLs for all uploaded images in the required order: `[front, left, back, right]`.
4.  Calls BFF `POST /generate/image-to-model` endpoint with a JSON payload containing a client-generated `task_id`, `input_image_asset_urls` (list containing **multiple** Supabase URLs for multiview mode), prompt, and enhanced texture settings.
    *   *(BFF Internally)*: BFF automatically detects multiview mode (2+ images) and fetches all images from Supabase URLs. Creates a record in `models` table (status 'pending'). Dispatches Celery task that calls Tripo AI's `multiview_to_model` endpoint with properly ordered image data, gets Tripo task ID, updates `models` record.
    *   **Ordering Enforcement**: The API strictly enforces the view order `[front, left, back, right]` as per Tripo's specification. Front view (position 0) is required.
5.  Receives a Celery `task_id` from the BFF.
6.  Polls BFF `GET /tasks/{celery_task_id}/status?service=tripo` with extended timeout (multiview processing takes longer).
7.  Asserts the response contains an `asset_url` (Supabase URL for the enhanced multiview model).
8.  Downloads the generated multiview model from the Supabase URL.

### `test_generate_sketch_to_model`

1.  Downloads a public sketch image.
2.  **Simulates client behavior**: Uploads this sketch image to a test path in Supabase Storage.
3.  Constructs the Supabase URL for the uploaded sketch.
4.  Calls BFF `POST /generate/sketch-to-model` endpoint with a JSON payload containing a client-generated `task_id`, the `input_sketch_asset_url` (the Supabase URL), prompt, and `texture_quality`.
    *   *(BFF Internally)*: Fetches the sketch from the Supabase URL. Proceeds similar to `test_generate_image_to_model` for creating `models` record, Celery task, Tripo interaction, final upload to client's Supabase Storage, and updating client's `models` table.
5.  Receives a Celery `task_id` from BFF for the Tripo operation.
6.  Polls BFF `GET /tasks/{celery_task_id}/status?service=tripo`.
7.  Asserts the response contains an `asset_url` (Supabase URL for the model).
8.  Downloads the final 3D model from the Supabase URL.

### `test_supabase_upload_and_metadata`

*This test directly uses functions from `app.supabase_client.py` and does not interact with BFF endpoints. It tests direct Supabase operations.* 

1.  Downloads a public JPG image.
2.  Uploads the image to Supabase Storage (`test_uploads/...`) using `supabase_client.upload_image_to_storage`.
3.  Creates a metadata record in the `concept_images` Supabase table using `supabase_client.create_concept_image_record`, storing the image path and bucket name.
4.  Downloads the image directly from Supabase Storage using `supabase_client.download_image_from_storage`.
5.  Retrieves the metadata record from the `concept_images` table using `supabase_client.get_supabase_client().table(...).select(...).execute()` and verifies its contents. 