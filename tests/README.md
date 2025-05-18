# BFF Local Tests

This directory contains basic tests for the makeit3d BFF service endpoints. These tests are designed to be run against a locally running instance of the BFF.

## Prerequisites

*   Docker and Docker Compose installed and running on your machine.
*   Python 3.7+ and `pip` installed.
*   A local Python virtual environment (`.venv` recommended), created with a supported Python version (3.10, 3.11, or 3.12).
*   Access to your Tripo AI, OpenAI, and Supabase API keys, and Supabase URL, configured as environment variables in a `.env` file in the root directory (`.env` is already in `.gitignore`).

## Setup

1.  **Navigate to the BFF root directory:**
    ```bash
    cd /path/to/your/makeit3d-bff
    ```
    (Replace `/path/to/your/makeit3d-bff` with the actual path to your project).

2.  **Load your Python virtual environment:**
    ```bash
    source .venv/bin/activate
    ```
    (If you don't have a virtual environment, create one using a supported Python version like 3.10, 3.11, or 3.12 with `python3.x -m venv .venv` and then activate it. Replace `python3.x` with your desired supported version command).

3.  **Install test and application dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Ensure your `.env` file is configured:**
    Create a `.env` file in the root directory of the project if you haven't already, and add your API keys and Supabase details. For local testing, include:
    ```
    TRIPO_API_KEY=your_tripo_api_key
    OPENAI_API_KEY=your_openai_api_key
    SUPABASE_URL=your_supabase_url
    SUPABASE_SERVICE_KEY=your_supabase_service_key
    BFF_BASE_URL="http://localhost:8000"
    ```
    Replace the placeholder values with your actual credentials.

5.  **Update test placeholders:**
    Edit the `tests/test_endpoints.py` file.
    *   Replace placeholder image URLs (`https://example.com/...`) with actual publicly accessible image URLs for the `test_generate_image_to_model` and `test_generate_sketch_to_model` tests.
    *   Replace `YOUR_DRAFT_TASK_ID` in `test_generate_refine_model` with a task ID from a successfully generated *draft* model.
    *   Replace `YOUR_CONCEPT_IMAGE_URL` and `YOUR_CONCEPT_TASK_ID` in `test_generate_select_concept` with the URL and task ID from a successful `test_generate_image_to_image` run.
    *   Replace `YOUR_TRIPO_TASK_ID` in `test_get_task_status_tripo` with a task ID from any successful Tripo generation test.
    *   Replace `YOUR_OPENAI_TASK_ID` in `test_get_task_status_openai` with the dummy task ID returned by `test_generate_image_to_image` (or a real one if applicable in the future).

## Running the BFF Locally (Choose One)

You need the BFF server and Celery worker running locally to execute the tests against. Choose one of the following options:

### Option 1: Using Docker Compose (Recommended for Development)

This option uses Docker Compose to orchestrate the FastAPI backend, Celery worker, and Redis. The configuration in `docker-compose.yml` includes volume mounts, allowing for live code editing without rebuilding images.

1.  **Build and run the services:**
    In the BFF root directory, run:
    ```bash
    docker-compose up --build
    ```
    The `--build` flag ensures images are built if they don't exist or if there are changes to the Dockerfile or context. Omit `--build` on subsequent runs if you haven't changed the Dockerfile or dependencies.

    This command will start Redis, the Celery worker, and the FastAPI backend. The backend will be accessible at `http://localhost:8000`.

    Keep this terminal open. To stop the services later, press `Ctrl+C`.

### Option 2: Using Uvicorn and Celery (Direct Python Execution)

This option runs the BFF components directly in your local Python environment. You will need separate terminal windows for Uvicorn and the Celery worker.

1.  **Ensure your virtual environment is activated** in two separate terminal windows.

2.  **Run the FastAPI application in the first terminal:**
    ```bash
    uvicorn app.main:app --reload
    ```
    This will start the server, accessible at `http://127.0.0.1:8000`. The `--reload` flag provides hot-reloading.

3.  **Run the Celery worker in the second terminal:**
    ```bash
    celery -A app.celery_worker worker -l info -P eventlet -c 1
    ```
    This starts the worker that will process background tasks.

    Keep both terminals open and running.

## Running the Tests

Open a **new terminal** window (a third one if using Option 2), navigate to the BFF root directory (`/path/to/your/makeit3d-bff`), and activate your virtual environment (`source .venv/bin/activate`). Ensure the BFF services (backend and worker) are running using either the Docker Compose or Uvicorn/Celery method described above.

Then, use the `pytest` command to run the tests:

*   **Run all tests in the `tests/` directory:**
    ```bash
    pytest
    ```
*   **Run all tests in a specific file (e.g., `test_endpoints.py`):**
    ```bash
    pytest tests/test_endpoints.py
    ```
*   **Run a specific test function within a file (e.g., `test_generate_image_to_image` in `test_endpoints.py`):**
    ```bash
    pytest tests/test_endpoints.py::test_generate_image_to_image
    ```

Pytest will execute the specified tests. Watch the output for test progress and results. Any generated files (images or models) from successful tests will be downloaded to the `./tests/outputs/` directory. 