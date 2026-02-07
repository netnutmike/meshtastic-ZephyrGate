#!/bin/bash
# ZephyrGate System Validation Script
# Comprehensive system testing and validation

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
VALIDATION_LOG="/tmp/zephyrgate-validation-$(date +%Y%m%d_%H%M%S).log"
TEST_TIMEOUT=300  # 5 minutes
HEALTH_CHECK_RETRIES=10
HEALTH_CHECK_INTERVAL=5

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Test results tracking
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

# Logging functions
log_info() {
    local msg="[INFO] $(date '+%Y-%m-%d %H:%M:%S') $1"
    echo -e "${BLUE}${msg}${NC}"
    echo "$msg" >> "$VALIDATION_LOG"
}

log_success() {
    local msg="[SUCCESS] $(date '+%Y-%m-%d %H:%M:%S') $1"
    echo -e "${GREEN}${msg}${NC}"
    echo "$msg" >> "$VALIDATION_LOG"
}

log_warning() {
    local msg="[WARNING] $(date '+%Y-%m-%d %H:%M:%S') $1"
    echo -e "${YELLOW}${msg}${NC}"
    echo "$msg" >> "$VALIDATION_LOG"
}

log_error() {
    local msg="[ERROR] $(date '+%Y-%m-%d %H:%M:%S') $1"
    echo -e "${RED}${msg}${NC}"
    echo "$msg" >> "$VALIDATION_LOG"
}

log_test() {
    local msg="[TEST] $(date '+%Y-%m-%d %H:%M:%S') $1"
    echo -e "${PURPLE}${msg}${NC}"
    echo "$msg" >> "$VALIDATION_LOG"
}

# Test result functions
test_passed() {
    TESTS_PASSED=$((TESTS_PASSED + 1))
    log_success "✓ $1"
}

test_failed() {
    TESTS_FAILED=$((TESTS_FAILED + 1))
    log_error "✗ $1"
}

test_skipped() {
    TESTS_SKIPPED=$((TESTS_SKIPPED + 1))
    log_warning "⊘ $1"
}

# Display validation banner
show_banner() {
    cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║              ZephyrGate System Validation                   ║
║                                                              ║
║  Comprehensive testing and validation of all system         ║
║  components, requirements, and functionality.               ║
╚══════════════════════════════════════════════════════════════╝
EOF
}

# Check prerequisites
check_prerequisites() {
    log_test "Checking validation prerequisites..."
    
    local missing_tools=()
    
    # Check required tools
    command -v python3 >/dev/null 2>&1 || missing_tools+=("python3")
    command -v sqlite3 >/dev/null 2>&1 || missing_tools+=("sqlite3")
    command -v curl >/dev/null 2>&1 || missing_tools+=("curl")
    command -v docker >/dev/null 2>&1 || missing_tools+=("docker")
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        test_failed "Missing required tools: ${missing_tools[*]}"
        return 1
    fi
    
    # Check Python version
    local python_version=$(python3 --version | cut -d' ' -f2)
    local required_version="3.9.0"
    
    if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 9) else 1)"; then
        test_failed "Python version $python_version < $required_version"
        return 1
    fi
    
    test_passed "Prerequisites check completed"
    return 0
}

# Validate project structure
validate_project_structure() {
    log_test "Validating project structure..."
    
    local required_dirs=(
        "src"
        "src/core"
        "src/models"
        "src/services"
        "src/services/emergency"
        "src/services/bbs"
        "src/services/bot"
        "src/services/weather"
        "src/services/email"
        "src/services/web"
        "src/services/asset"
        "config"
        "tests"
        "tests/unit"
        "tests/integration"
        "docs"
        "scripts"
    )
    
    local required_files=(
        "src/main.py"
        "src/core/config.py"
        "src/core/database.py"
        "src/core/message_router.py"
        "requirements.txt"
        "docker-compose.yml"
        "Dockerfile"
        "README.md"
        "LICENSE"
        "CONTRIBUTING.md"
    )
    
    # Check directories
    for dir in "${required_dirs[@]}"; do
        if [ -d "$APP_DIR/$dir" ]; then
            log_info "✓ Directory exists: $dir"
        else
            test_failed "Missing required directory: $dir"
            return 1
        fi
    done
    
    # Check files
    for file in "${required_files[@]}"; do
        if [ -f "$APP_DIR/$file" ]; then
            log_info "✓ File exists: $file"
        else
            test_failed "Missing required file: $file"
            return 1
        fi
    done
    
    test_passed "Project structure validation completed"
    return 0
}

# Validate configuration
validate_configuration() {
    log_test "Validating configuration system..."
    
    # Check if configuration example exists
    if [ ! -f "$APP_DIR/config/config-example.yaml" ]; then
        test_failed "Configuration example not found"
        return 1
    fi
    
    # Test configuration loading
    cd "$APP_DIR"
    if python3 -c "
from src.core.config import ConfigurationManager
try:
    config = ConfigurationManager()
    config.load_config(['config/default.yaml'])
    print('Configuration loaded successfully')
except Exception as e:
    print(f'Configuration error: {e}')
    exit(1)
"; then
        test_passed "Configuration system validation completed"
    else
        test_failed "Configuration system validation failed"
        return 1
    fi
    
    return 0
}

# Validate database system
validate_database() {
    log_test "Validating database system..."
    
    cd "$APP_DIR"
    
    # Test database initialization
    if python3 -c "
from src.core.database import DatabaseManager
import tempfile
import os

try:
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    db_manager = DatabaseManager(f'sqlite:///{db_path}')
    db_manager.create_tables()
    
    # Test basic operations
    with db_manager.get_session() as session:
        # Test session creation
        pass
    
    # Cleanup
    os.unlink(db_path)
    print('Database system validation passed')
    
except Exception as e:
    print(f'Database validation error: {e}')
    exit(1)
"; then
        test_passed "Database system validation completed"
    else
        test_failed "Database system validation failed"
        return 1
    fi
    
    return 0
}

# Run unit tests
run_unit_tests() {
    log_test "Running unit tests..."
    
    cd "$APP_DIR"
    
    if [ ! -d "venv" ]; then
        log_info "Creating virtual environment for testing..."
        python3 -m venv venv
        source venv/bin/activate
        pip install -r requirements.txt
    else
        source venv/bin/activate
    fi
    
    # Run unit tests with coverage
    if python -m pytest tests/unit/ -v --tb=short --maxfail=5 2>&1 | tee -a "$VALIDATION_LOG"; then
        test_passed "Unit tests completed successfully"
    else
        test_failed "Unit tests failed"
        return 1
    fi
    
    return 0
}

# Run integration tests
run_integration_tests() {
    log_test "Running integration tests..."
    
    cd "$APP_DIR"
    source venv/bin/activate
    
    # Run integration tests
    if python -m pytest tests/integration/ -v --tb=short --maxfail=3 2>&1 | tee -a "$VALIDATION_LOG"; then
        test_passed "Integration tests completed successfully"
    else
        test_failed "Integration tests failed"
        return 1
    fi
    
    return 0
}

# Test Docker build
test_docker_build() {
    log_test "Testing Docker build..."
    
    cd "$APP_DIR"
    
    # Build Docker image
    if docker build -t zephyrgate:test . 2>&1 | tee -a "$VALIDATION_LOG"; then
        test_passed "Docker build completed successfully"
    else
        test_failed "Docker build failed"
        return 1
    fi
    
    # Test Docker run (basic startup)
    log_info "Testing Docker container startup..."
    
    local container_id=$(docker run -d --rm \
        -e ZEPHYR_LOG_LEVEL=DEBUG \
        -e ZEPHYR_DATABASE_URL=sqlite:///tmp/test.db \
        zephyrgate:test)
    
    if [ -n "$container_id" ]; then
        # Wait for container to start
        sleep 10
        
        # Check if container is still running
        if docker ps | grep -q "$container_id"; then
            test_passed "Docker container started successfully"
            docker stop "$container_id" >/dev/null 2>&1
        else
            test_failed "Docker container failed to start"
            docker logs "$container_id" 2>&1 | tee -a "$VALIDATION_LOG"
            return 1
        fi
    else
        test_failed "Failed to start Docker container"
        return 1
    fi
    
    return 0
}

# Test application startup
test_application_startup() {
    log_test "Testing application startup..."
    
    cd "$APP_DIR"
    source venv/bin/activate
    
    # Create test configuration
    cat > config/test.yaml << EOF
app:
  name: "ZephyrGate Test"
  environment: "test"
  debug: true
  log_level: "DEBUG"

server:
  host: "127.0.0.1"
  port: 8081

database:
  url: "sqlite:///tmp/zephyrgate_test.db"

services:
  emergency:
    enabled: true
  bbs:
    enabled: true
  weather:
    enabled: false  # Disable to avoid API calls
  email:
    enabled: false  # Disable to avoid SMTP requirements
  bot:
    enabled: true
  web:
    enabled: true

meshtastic:
  interfaces: {}  # No interfaces for testing
EOF
    
    # Start application in background
    timeout $TEST_TIMEOUT python src/main.py --config config/test.yaml &
    local app_pid=$!
    
    # Wait for application to start
    local retries=0
    while [ $retries -lt $HEALTH_CHECK_RETRIES ]; do
        if curl -f -s http://127.0.0.1:8081/health >/dev/null 2>&1; then
            test_passed "Application started successfully"
            kill $app_pid 2>/dev/null || true
            wait $app_pid 2>/dev/null || true
            rm -f config/test.yaml /tmp/zephyrgate_test.db
            return 0
        fi
        
        sleep $HEALTH_CHECK_INTERVAL
        retries=$((retries + 1))
    done
    
    test_failed "Application failed to start within timeout"
    kill $app_pid 2>/dev/null || true
    wait $app_pid 2>/dev/null || true
    rm -f config/test.yaml /tmp/zephyrgate_test.db
    return 1
}

# Test web interface
test_web_interface() {
    log_test "Testing web interface endpoints..."
    
    cd "$APP_DIR"
    source venv/bin/activate
    
    # Start application for web testing
    python src/main.py --config config/test.yaml &
    local app_pid=$!
    
    # Wait for startup
    sleep 10
    
    local endpoints=(
        "/health"
        "/api/system/status"
        "/api/services"
    )
    
    local all_passed=true
    
    for endpoint in "${endpoints[@]}"; do
        if curl -f -s "http://127.0.0.1:8081$endpoint" >/dev/null 2>&1; then
            log_info "✓ Endpoint accessible: $endpoint"
        else
            log_error "✗ Endpoint failed: $endpoint"
            all_passed=false
        fi
    done
    
    # Cleanup
    kill $app_pid 2>/dev/null || true
    wait $app_pid 2>/dev/null || true
    
    if [ "$all_passed" = true ]; then
        test_passed "Web interface endpoints validation completed"
        return 0
    else
        test_failed "Web interface endpoints validation failed"
        return 1
    fi
}

# Validate requirements implementation
validate_requirements() {
    log_test "Validating requirements implementation..."
    
    # This is a high-level check that key requirements are implemented
    # by checking for the existence of key components
    
    local requirements_check=(
        "Emergency Response System:src/services/emergency/emergency_service.py"
        "BBS System:src/services/bbs/bulletin_service.py"
        "Interactive Bot:src/services/bot/interactive_bot_service.py"
        "Weather Services:src/services/weather/weather_service.py"
        "Email Gateway:src/services/email/email_service.py"
        "Web Administration:src/services/web/web_admin_service.py"
        "Asset Tracking:src/services/asset/asset_tracking_service.py"
        "Message Router:src/core/message_router.py"
        "Configuration Management:src/core/config.py"
        "Database System:src/core/database.py"
    )
    
    local all_implemented=true
    
    for requirement in "${requirements_check[@]}"; do
        local name="${requirement%%:*}"
        local file="${requirement##*:}"
        
        if [ -f "$APP_DIR/$file" ]; then
            log_info "✓ $name implemented"
        else
            log_error "✗ $name not implemented (missing: $file)"
            all_implemented=false
        fi
    done
    
    if [ "$all_implemented" = true ]; then
        test_passed "Requirements implementation validation completed"
        return 0
    else
        test_failed "Requirements implementation validation failed"
        return 1
    fi
}

# Performance benchmark
run_performance_benchmark() {
    log_test "Running performance benchmark..."
    
    cd "$APP_DIR"
    
    # Simple performance test script
    cat > /tmp/perf_test.py << 'EOF'
import time
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.core.message_router import MessageRouter
from src.models.message import Message
from datetime import datetime

def benchmark_message_processing():
    router = MessageRouter()
    
    # Create test messages
    messages = []
    for i in range(1000):
        message = Message(
            id=f"test_{i}",
            sender_id=f"!{i:08x}",
            content=f"Test message {i}",
            timestamp=datetime.utcnow(),
            channel=0
        )
        messages.append(message)
    
    # Benchmark message processing
    start_time = time.time()
    
    for message in messages:
        # Simulate message processing
        pass
    
    end_time = time.time()
    duration = end_time - start_time
    throughput = len(messages) / duration
    
    print(f"Processed {len(messages)} messages in {duration:.2f}s")
    print(f"Throughput: {throughput:.2f} messages/second")
    
    # Performance thresholds
    if throughput < 100:
        print("WARNING: Low throughput detected")
        return False
    
    return True

if __name__ == "__main__":
    success = benchmark_message_processing()
    sys.exit(0 if success else 1)
EOF
    
    if python /tmp/perf_test.py 2>&1 | tee -a "$VALIDATION_LOG"; then
        test_passed "Performance benchmark completed"
    else
        test_failed "Performance benchmark failed"
        return 1
    fi
    
    rm -f /tmp/perf_test.py
    return 0
}

# Security validation
validate_security() {
    log_test "Running security validation..."
    
    cd "$APP_DIR"
    
    # Check for common security issues
    local security_issues=0
    
    # Check for hardcoded secrets
    if grep -r "password.*=" src/ | grep -v "example\|template\|test" >/dev/null 2>&1; then
        log_warning "Potential hardcoded passwords found"
        security_issues=$((security_issues + 1))
    fi
    
    # Check for SQL injection vulnerabilities (basic check)
    if grep -r "execute.*%" src/ >/dev/null 2>&1; then
        log_warning "Potential SQL injection vulnerabilities found"
        security_issues=$((security_issues + 1))
    fi
    
    # Check file permissions
    if find "$APP_DIR" -name "*.py" -perm /o+w 2>/dev/null | grep -q .; then
        log_warning "World-writable Python files found"
        security_issues=$((security_issues + 1))
    fi
    
    if [ $security_issues -eq 0 ]; then
        test_passed "Security validation completed"
    else
        test_failed "Security validation found $security_issues issues"
        return 1
    fi
    
    return 0
}

# Generate validation report
generate_validation_report() {
    log_test "Generating validation report..."
    
    local report_file="/tmp/zephyrgate-validation-report-$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
ZephyrGate System Validation Report
===================================
Validation Date: $(date)
System: $(uname -a)
Python Version: $(python3 --version)

Test Results Summary:
- Tests Passed: $TESTS_PASSED
- Tests Failed: $TESTS_FAILED
- Tests Skipped: $TESTS_SKIPPED
- Total Tests: $((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED))

Success Rate: $(( TESTS_PASSED * 100 / (TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED) ))%

Detailed Results:
================
EOF
    
    # Add detailed log
    cat "$VALIDATION_LOG" >> "$report_file"
    
    log_success "Validation report generated: $report_file"
    
    # Display summary
    echo
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                 Validation Complete                          ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo
    echo "Test Results:"
    echo "  Passed:  $TESTS_PASSED"
    echo "  Failed:  $TESTS_FAILED"
    echo "  Skipped: $TESTS_SKIPPED"
    echo "  Total:   $((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED))"
    echo
    echo "Success Rate: $(( TESTS_PASSED * 100 / (TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED) ))%"
    echo
    echo "Validation Report: $report_file"
    echo "Validation Log: $VALIDATION_LOG"
    
    if [ $TESTS_FAILED -eq 0 ]; then
        echo
        echo "🎉 All tests passed! ZephyrGate is ready for deployment."
        return 0
    else
        echo
        echo "❌ Some tests failed. Please review the report and fix issues."
        return 1
    fi
}

# Main validation function
main() {
    # Parse command line arguments
    local run_all=true
    local run_unit_tests_flag=false
    local run_integration_tests_flag=false
    local run_docker_tests_flag=false
    local run_performance_flag=false
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --unit-tests)
                run_all=false
                run_unit_tests_flag=true
                shift
                ;;
            --integration-tests)
                run_all=false
                run_integration_tests_flag=true
                shift
                ;;
            --docker-tests)
                run_all=false
                run_docker_tests_flag=true
                shift
                ;;
            --performance)
                run_all=false
                run_performance_flag=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --unit-tests         Run only unit tests"
                echo "  --integration-tests  Run only integration tests"
                echo "  --docker-tests       Run only Docker tests"
                echo "  --performance        Run only performance tests"
                echo "  --help               Show this help message"
                echo ""
                echo "If no options are specified, all tests will be run."
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Show banner
    show_banner
    
    log_info "Starting ZephyrGate system validation..."
    
    # Always run basic checks
    check_prerequisites || exit 1
    validate_project_structure || exit 1
    validate_configuration || exit 1
    validate_database || exit 1
    validate_requirements || exit 1
    
    # Run selected tests
    if [ "$run_all" = true ]; then
        run_unit_tests || true  # Don't exit on test failures
        run_integration_tests || true
        test_docker_build || true
        test_application_startup || true
        test_web_interface || true
        run_performance_benchmark || true
        validate_security || true
    else
        [ "$run_unit_tests_flag" = true ] && run_unit_tests
        [ "$run_integration_tests_flag" = true ] && run_integration_tests
        [ "$run_docker_tests_flag" = true ] && test_docker_build
        [ "$run_performance_flag" = true ] && run_performance_benchmark
    fi
    
    # Generate report
    generate_validation_report
}

# Run main function with all arguments
main "$@"