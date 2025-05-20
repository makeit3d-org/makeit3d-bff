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
  3. test_generate_from_concept
  4. test_generate_image_to_model_texture
  5. test_generate_image_to_model_no_texture
  6. test_generate_sketch_to_model
  7. test_supabase_upload_and_metadata
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