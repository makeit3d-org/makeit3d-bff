#!/usr/bin/env python3
"""
MakeIt3D Test Runner

This script provides a Python interface for running the MakeIt3D backend tests.
It offers more advanced options than the shell script version.
"""

import argparse
import subprocess
import sys
import os
import re
from typing import List, Optional

# ANSI color codes
class Colors:
    GREEN = '\033[0;32m'
    BLUE = '\033[0;34m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color

def print_colored(text: str, color: str) -> None:
    """Print text with color"""
    print(f"{color}{text}{Colors.NC}")

def print_banner() -> None:
    """Print the application banner"""
    print_colored("======================================", Colors.BLUE)
    print_colored("MakeIt3D Backend Test Runner (Python)", Colors.GREEN)
    print_colored("======================================", Colors.BLUE)

def check_docker_running() -> bool:
    """Check if the required Docker containers are running"""
    try:
        result = subprocess.run(
            ["docker", "ps"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        return "makeit3d-bff-backend" in result.stdout
    except subprocess.CalledProcessError:
        return False

def run_tests(
    test_path: str = "tests/test_endpoints.py", 
    show_logs: bool = False,
    verbose: bool = False,
    specific_test: Optional[str] = None,
    failfast: bool = False
) -> int:
    """Run the tests using docker-compose exec"""
    
    # Build pytest arguments
    pytest_args = []
    
    if verbose:
        pytest_args.append("-v")
    
    if failfast:
        pytest_args.append("--exitfirst")
    
    if show_logs:
        pytest_args.extend(["-s", "--log-cli-level=INFO"])
    
    # If a specific test is provided, append it to the test path
    if specific_test:
        # Check if the specific test includes :: already
        if "::" in test_path:
            print_colored("Warning: Both test path and specific test contain '::', using as provided", Colors.YELLOW)
            final_test_path = test_path
        else:
            final_test_path = f"{test_path}::{specific_test}"
    else:
        final_test_path = test_path
    
    # Build the full command with proper Python path
    cmd = ["docker-compose", "exec", "backend", "bash", "-c", f"cd / && PYTHONPATH=/app python -m pytest {final_test_path} {' '.join(pytest_args)}"]
    
    # Print the command being run
    print_colored(f"Running: {' '.join(cmd)}", Colors.BLUE)
    print_colored("======================================", Colors.BLUE)
    
    # Execute the command
    try:
        result = subprocess.run(cmd)
        return result.returncode
    except KeyboardInterrupt:
        print_colored("\nTest run interrupted by user", Colors.YELLOW)
        return 130  # Standard exit code for Ctrl+C

def list_available_tests(test_path: str = "/tests/test_endpoints.py") -> None:
    """List all available tests in the specified test path"""
    cmd = ["docker-compose", "exec", "backend", "bash", "-c", f"cd / && PYTHONPATH=/app python -m pytest {test_path} --collect-only -q"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print_colored(f"Error collecting tests:\n{result.stderr}", Colors.RED)
            return
        
        # Parse the output to extract test names
        test_lines = result.stdout.strip().split('\n')
        tests = []
        current_file = ""
        
        for line in test_lines:
            # Extract the file name if present
            if "::" in line and "/" in line:
                file_match = re.search(r'(/tests/test_[^:]+\.py)', line)
                if file_match:
                    new_file = file_match.group(1)
                    if new_file != current_file:
                        current_file = new_file
                        if tests:  # Add separator between files
                            tests.append(("separator", current_file))
                        else:
                            tests.append(("file_header", current_file))
            
            # Match test function names (assumes Python test naming conventions)
            match = re.search(r'::([a-zA-Z0-9_]+)(\s|$)', line)
            if match:
                tests.append(("test", match.group(1)))
        
        if tests:
            print_colored(f"Available tests in {test_path}:", Colors.BLUE)
            current_file_shown = ""
            for i, (test_type, test_name) in enumerate(tests):
                if test_type == "file_header":
                    print_colored(f"\n📁 {test_name}:", Colors.YELLOW)
                    current_file_shown = test_name
                elif test_type == "separator":
                    print_colored(f"\n📁 {test_name}:", Colors.YELLOW)
                    current_file_shown = test_name
                elif test_type == "test":
                    print_colored(f"  • {test_name}", Colors.CYAN)
        else:
            print_colored(f"No tests found in {test_path}", Colors.YELLOW)
            
    except Exception as e:
        print_colored(f"Error listing tests: {str(e)}", Colors.RED)

def list_all_test_files() -> None:
    """List all available test files in the tests directory"""
    cmd = ["docker-compose", "exec", "backend", "bash", "-c", "find /tests -name 'test_*.py' -type f | sort"]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print_colored(f"Error finding test files:\n{result.stderr}", Colors.RED)
            return
        
        test_files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]
        
        if test_files:
            print_colored("Available test files:", Colors.BLUE)
            for i, test_file in enumerate(test_files, 1):
                filename = test_file.split('/')[-1]
                print_colored(f"  {i}. {filename} ({test_file})", Colors.CYAN)
            print_colored("\nTo list tests in a specific file:", Colors.YELLOW)
            print_colored("  ./tests/run_tests.py -l <test_file_path>", Colors.GREEN)
            print_colored("\nTo run tests from a specific file:", Colors.YELLOW)
            print_colored("  ./tests/run_tests.py <test_file_path>", Colors.GREEN)
        else:
            print_colored("No test files found", Colors.YELLOW)
            
    except Exception as e:
        print_colored(f"Error listing test files: {str(e)}", Colors.RED)

def main() -> int:
    """Main entry point"""
    parser = argparse.ArgumentParser(description="MakeIt3D Backend Test Runner (Python)")
    parser.add_argument("-t", "--test", help="Specific test function to run")
    parser.add_argument("-l", "--list", action="store_true", help="List available tests")
    parser.add_argument("-a", "--all-files", action="store_true", help="List all available test files")
    parser.add_argument("-s", "--show-logs", action="store_true", help="Show logs during test execution")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("-f", "--fail-fast", action="store_true", help="Stop on first failure")
    parser.add_argument("test_file", nargs="?", default="/tests/test_endpoints.py", help="Test file to run (default: /tests/test_endpoints.py)")
    
    args = parser.parse_args()
    
    # Set test mode environment variable for Docker containers
    # This ensures all services (backend and celery workers) use test storage paths
    os.environ["TEST_ASSETS_MODE"] = "True"
    
    print_banner()
    
    # Check if Docker is running
    if not check_docker_running():
        print_colored("Error: Docker containers are not running!", Colors.RED)
        print_colored("Please start the services with:", Colors.YELLOW)
        print_colored("docker-compose up -d", Colors.GREEN)
        return 1
    
    # List all test files if requested
    if args.all_files:
        list_all_test_files()
        return 0
    
    # List tests if requested
    if args.list:
        list_available_tests(args.test_file)
        return 0
    
    # Run the tests
    return run_tests(
        test_path=args.test_file,
        show_logs=args.show_logs,
        verbose=args.verbose,
        specific_test=args.test,
        failfast=args.fail_fast
    )

if __name__ == "__main__":
    sys.exit(main()) 