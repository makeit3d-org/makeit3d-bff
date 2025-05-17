# BFF Local Tests

This directory contains basic tests for the makeit3d BFF service endpoints. These tests are designed to be run against a locally running instance of the BFF.

## Prerequisites

*   Docker installed and running on your machine (required only if using the Docker option).
*   Python 3.7+ and `pip` installed.
*   A local Python virtual environment (`.venv` recommended), created with a supported Python version (3.10, 3.11, or 3.12).
*   Access to your Tripo AI and OpenAI API keys, configured as environment variables.

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

4.  **Update test placeholders:**
    Edit the `tests/test_endpoints.py` file.
    *   Replace placeholder image URLs (`https://example.com/...`) with actual publicly accessible image URLs for the `test_generate_image_to_model` and `test_generate_sketch_to_model` tests.
    *   Replace `YOUR_DRAFT_TASK_ID` in `test_generate_refine_model` with a task ID from a successfully generated *draft* model.
    *   Replace `YOUR_CONCEPT_IMAGE_URL` and `YOUR_CONCEPT_TASK_ID` in `test_generate_select_concept` with the URL and task ID from a successful `test_generate_image_to_image` run.
    *   Replace `YOUR_TRIPO_TASK_ID` in `test_get_task_status_tripo` with a task ID from any successful Tripo generation test.
    *   Replace `YOUR_OPENAI_TASK_ID` in `test_get_task_status_openai` with the dummy task ID returned by `test_generate_image_to_image` (or a real one if applicable in the future).

## Running the BFF Locally (Choose One)

You need the BFF server running locally to execute the tests against. Choose one of the following options:

### Option 1: Using Docker

This option runs the BFF inside a Docker container, simulating a production-like environment.

1.  **Build the Docker image:**
    (You may have already done this, but repeat if necessary)
    ```bash
    docker build -t makeit3d-bff .
    ```

2.  **Run the Docker container:**
    Replace `YOUR_TRIPO_API_KEY` and `YOUR_OPENAI_API_KEY` with your actual API keys.
    ```bash
    docker run -d --name makeit3d-bff-instance -p 8000:8000 \
    -e TRIPO_API_KEY=YOUR_TRIPO_API_KEY \
    -e OPENAI_API_KEY=YOUR_OPENAI_API_KEY \
    makeit3d-bff
    ```
    Note the `-d` flag runs the container in detached mode. The server will be accessible at `http://127.0.0.1:8000`. You can check if it's running with `docker ps`. To stop it later, use `docker stop makeit3d-bff-instance`.

### Option 2: Using Uvicorn (Direct Python Execution)

This option runs the BFF directly in your local Python environment using uvicorn. This is often easier for development and debugging.

1.  **Ensure your virtual environment is activated:**
    ```bash
    source .venv/bin/activate
    ```

2.  **Run the FastAPI application:**
    ```bash
    uvicorn app.main:app --reload
    ```
    This will start the server, accessible at `http://127.0.0.1:8000`. The `--reload` flag will automatically restart the server when you make code changes. Keep this terminal open and running.

## Running the Tests

Open a **new terminal** window, navigate to the BFF root directory (`/path/to/your/makeit3d-bff`), and activate your virtual environment (`source .venv/bin/activate`). Ensure the BFF server is running using either the Docker or Uvicorn method described above.

Then, use the `pytest` command to run the tests:

*   **Run all tests in the `tests/` directory:**
    ```bash
    pytest
    ```
*   **Run all tests in a specific file (e.g., `test_endpoints.py`):**
    ```bash
    pytest tests/test_endpoints.py
    ```
*   **Run a specific test function within a file (e.g., `test_generate_text_to_model` in `test_endpoints.py`):**
    ```bash
    pytest tests/test_endpoints.py::test_generate_text_to_model
    ```

Pytest will execute the specified tests. Watch the output for test progress and results. Any generated files (images or models) from successful tests will be downloaded to the `./tests/outputs/` directory. 