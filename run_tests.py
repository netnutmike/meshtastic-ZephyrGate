#!/usr/bin/env python3
"""
Test runner script for ZephyrGate.
Provides convenient commands for running different types of tests.
"""
import sys
import subprocess
import argparse
from pathlib import Path


def run_command(cmd, description):
    """Run a command and handle errors."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"Command: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=False)
        print(f"\n✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n❌ {description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print(f"\n❌ Command not found: {cmd[0]}")
        print("Make sure pytest is installed: pip install pytest")
        return False


def main():
    parser = argparse.ArgumentParser(description="ZephyrGate Test Runner")
    parser.add_argument("--unit", action="store_true", help="Run unit tests only")
    parser.add_argument("--integration", action="store_true", help="Run integration tests only")
    parser.add_argument("--coverage", action="store_true", help="Run tests with coverage report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--fast", action="store_true", help="Skip slow tests")
    parser.add_argument("--file", "-f", help="Run specific test file")
    parser.add_argument("--test", "-t", help="Run specific test function")
    parser.add_argument("--markers", "-m", help="Run tests with specific markers")
    parser.add_argument("--parallel", "-n", type=int, help="Run tests in parallel (requires pytest-xdist)")
    
    args = parser.parse_args()
    
    # Base pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add verbosity
    if args.verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")
    
    # Add coverage if requested
    if args.coverage:
        cmd.extend(["--cov=src", "--cov-report=term-missing", "--cov-report=html"])
    
    # Add parallel execution if requested
    if args.parallel:
        cmd.extend(["-n", str(args.parallel)])
    
    # Add test selection
    if args.unit:
        cmd.extend(["-m", "unit"])
        description = "Unit Tests"
    elif args.integration:
        cmd.extend(["-m", "integration"])
        description = "Integration Tests"
    elif args.markers:
        cmd.extend(["-m", args.markers])
        description = f"Tests with markers: {args.markers}"
    elif args.file:
        cmd.append(args.file)
        description = f"Tests in file: {args.file}"
    elif args.test:
        cmd.extend(["-k", args.test])
        description = f"Tests matching: {args.test}"
    else:
        description = "All Tests"
    
    # Skip slow tests if requested
    if args.fast:
        if "-m" in cmd:
            # Modify existing marker expression
            marker_index = cmd.index("-m") + 1
            cmd[marker_index] = f"({cmd[marker_index]}) and not slow"
        else:
            cmd.extend(["-m", "not slow"])
        description += " (excluding slow tests)"
    
    # Run the tests
    success = run_command(cmd, description)
    
    if success:
        print(f"\n🎉 All tests passed!")
        if args.coverage:
            print("\n📊 Coverage report generated in htmlcov/index.html")
    else:
        print(f"\n💥 Some tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()