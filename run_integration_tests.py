#!/usr/bin/env python3
"""
Integration Test Runner for ZephyrGate

Runs comprehensive integration tests including:
- System integration tests
- Performance and load tests
- Multi-service interaction tests
- End-to-end workflow tests
"""

import sys
import subprocess
import time
import argparse
from pathlib import Path


def run_command(cmd, description=""):
    """Run a command and return success status"""
    print(f"\n{'='*60}")
    print(f"Running: {description or cmd}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            check=True,
            capture_output=False,
            text=True
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n✅ SUCCESS: {description or cmd}")
        print(f"Duration: {duration:.2f} seconds")
        return True
        
    except subprocess.CalledProcessError as e:
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"\n❌ FAILED: {description or cmd}")
        print(f"Duration: {duration:.2f} seconds")
        print(f"Exit code: {e.returncode}")
        return False


def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="Run ZephyrGate integration tests")
    parser.add_argument(
        "--test-type",
        choices=["all", "integration", "performance", "system"],
        default="all",
        help="Type of tests to run"
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="Run with coverage reporting"
    )
    parser.add_argument(
        "--parallel",
        "-n",
        type=int,
        default=1,
        help="Number of parallel test processes"
    )
    
    args = parser.parse_args()
    
    # Ensure we're in the right directory
    project_root = Path(__file__).parent
    if not (project_root / "src").exists():
        print("❌ Error: Must run from project root directory")
        sys.exit(1)
    
    print("🚀 ZephyrGate Integration Test Runner")
    print(f"Project root: {project_root}")
    print(f"Test type: {args.test_type}")
    print(f"Verbose: {args.verbose}")
    print(f"Coverage: {args.coverage}")
    print(f"Parallel processes: {args.parallel}")
    
    # Build pytest command
    pytest_cmd = ["python", "-m", "pytest"]
    
    if args.verbose:
        pytest_cmd.append("-v")
    
    if args.parallel > 1:
        pytest_cmd.extend(["-n", str(args.parallel)])
    
    if args.coverage:
        pytest_cmd.extend([
            "--cov=src",
            "--cov-report=html",
            "--cov-report=term-missing"
        ])
    
    # Add test markers and paths based on test type
    test_commands = []
    
    if args.test_type in ["all", "system"]:
        # System integration tests
        cmd = pytest_cmd + [
            "tests/integration/test_system_integration.py",
            "-m", "not slow"
        ]
        test_commands.append((
            " ".join(cmd),
            "System Integration Tests"
        ))
    
    if args.test_type in ["all", "performance"]:
        # Performance tests
        cmd = pytest_cmd + [
            "tests/integration/test_performance_load.py",
            "-s"  # Show output for performance metrics
        ]
        test_commands.append((
            " ".join(cmd),
            "Performance and Load Tests"
        ))
    
    if args.test_type in ["all", "integration"]:
        # All existing integration tests
        cmd = pytest_cmd + [
            "tests/integration/",
            "--ignore=tests/integration/test_system_integration.py",
            "--ignore=tests/integration/test_performance_load.py"
        ]
        test_commands.append((
            " ".join(cmd),
            "Existing Integration Tests"
        ))
    
    # Run tests
    total_tests = len(test_commands)
    passed_tests = 0
    failed_tests = []
    
    start_time = time.time()
    
    for i, (cmd, description) in enumerate(test_commands, 1):
        print(f"\n🧪 Test Suite {i}/{total_tests}: {description}")
        
        if run_command(cmd, description):
            passed_tests += 1
        else:
            failed_tests.append(description)
    
    end_time = time.time()
    total_duration = end_time - start_time
    
    # Print summary
    print(f"\n{'='*60}")
    print("📊 TEST SUMMARY")
    print(f"{'='*60}")
    print(f"Total test suites: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {len(failed_tests)}")
    print(f"Total duration: {total_duration:.2f} seconds")
    
    if failed_tests:
        print(f"\n❌ Failed test suites:")
        for test in failed_tests:
            print(f"  - {test}")
        
        print(f"\n💡 Tips for debugging failures:")
        print("  - Run individual test files with -v for more details")
        print("  - Check test logs for specific error messages")
        print("  - Ensure all dependencies are installed")
        print("  - Verify test environment setup")
        
        sys.exit(1)
    else:
        print(f"\n🎉 All tests passed!")
        
        if args.coverage:
            print(f"\n📈 Coverage report generated in htmlcov/")
        
        sys.exit(0)


if __name__ == "__main__":
    main()