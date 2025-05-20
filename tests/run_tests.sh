#!/bin/bash

# Colors for better output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Display banner
echo -e "${BLUE}======================================${NC}"
echo -e "${GREEN}MakeIt3D Backend Test Runner${NC}"
echo -e "${BLUE}======================================${NC}"

# Check if docker-compose is running
if ! docker ps | grep -q "makeit3d-bff-backend"; then
    echo -e "${RED}Error: Docker containers are not running!${NC}"
    echo -e "${YELLOW}Please start the services with:${NC}"
    echo -e "${GREEN}docker-compose up -d${NC}"
    exit 1
fi

# Parse arguments
PYTEST_ARGS=""
TEST_PATH=""
SHOW_LOGS=false

# Process arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    -s|--show-logs)
      SHOW_LOGS=true
      shift
      ;;
    -v|--verbose)
      PYTEST_ARGS="$PYTEST_ARGS -v"
      shift
      ;;
    *)
      TEST_PATH="$1"
      shift
      ;;
  esac
done

# If no test path provided, use the default test file
if [ -z "$TEST_PATH" ]; then
    TEST_PATH="tests/test_endpoints.py"
    echo -e "${YELLOW}No test path specified, using default: ${TEST_PATH}${NC}"
fi

# Add logging flags if needed
if [ "$SHOW_LOGS" = true ]; then
    PYTEST_ARGS="$PYTEST_ARGS -s --log-cli-level=INFO"
    echo -e "${GREEN}Running with full logs enabled${NC}"
fi

echo -e "${BLUE}Running tests: ${TEST_PATH} ${PYTEST_ARGS}${NC}"
echo -e "${BLUE}======================================${NC}"

# Execute the test through docker-compose
docker-compose exec backend pytest $TEST_PATH $PYTEST_ARGS

# Capture exit code
EXIT_CODE=$?

# Display result
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ Tests passed successfully!${NC}"
else
    echo -e "${RED}✗ Tests failed with exit code: $EXIT_CODE${NC}"
fi

exit $EXIT_CODE 