#!/bin/bash
# Container health check script for ZephyrGate
# Used by Docker health checks and monitoring systems

set -e

# Configuration
HEALTH_URL="${HEALTH_URL:-http://localhost:8080/health}"
TIMEOUT="${TIMEOUT:-10}"
MAX_RETRIES="${MAX_RETRIES:-3}"
RETRY_DELAY="${RETRY_DELAY:-2}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "[INFO] $1" >&2
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1" >&2
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1" >&2
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

# Check if required tools are available
check_tools() {
    if ! command -v curl &> /dev/null; then
        log_error "curl is not available"
        exit 1
    fi
}

# Perform health check
health_check() {
    local retry_count=0
    
    while [ $retry_count -lt $MAX_RETRIES ]; do
        log_info "Performing health check (attempt $((retry_count + 1))/$MAX_RETRIES)..."
        
        # Perform the health check
        if curl -f -s --max-time "$TIMEOUT" "$HEALTH_URL" > /dev/null 2>&1; then
            log_success "Health check passed"
            return 0
        else
            retry_count=$((retry_count + 1))
            if [ $retry_count -lt $MAX_RETRIES ]; then
                log_warning "Health check failed, retrying in ${RETRY_DELAY}s..."
                sleep "$RETRY_DELAY"
            fi
        fi
    done
    
    log_error "Health check failed after $MAX_RETRIES attempts"
    return 1
}

# Detailed health check with JSON response
detailed_health_check() {
    local response
    local http_code
    
    log_info "Performing detailed health check..."
    
    # Get response with HTTP status code
    response=$(curl -s -w "%{http_code}" --max-time "$TIMEOUT" "$HEALTH_URL" 2>/dev/null)
    http_code="${response: -3}"
    response_body="${response%???}"
    
    case $http_code in
        200)
            log_success "HTTP 200 OK"
            if command -v jq &> /dev/null && echo "$response_body" | jq . &> /dev/null; then
                echo "$response_body" | jq .
            else
                echo "$response_body"
            fi
            return 0
            ;;
        503)
            log_error "HTTP 503 Service Unavailable"
            echo "$response_body"
            return 1
            ;;
        *)
            log_error "HTTP $http_code"
            echo "$response_body"
            return 1
            ;;
    esac
}

# Check database connectivity
check_database() {
    log_info "Checking database connectivity..."
    
    # This would be implemented based on the specific database check endpoint
    # For now, we'll use the general health endpoint
    if curl -f -s --max-time "$TIMEOUT" "${HEALTH_URL}/db" > /dev/null 2>&1; then
        log_success "Database connectivity OK"
        return 0
    else
        log_warning "Database connectivity check failed or not available"
        return 1
    fi
}

# Check service dependencies
check_dependencies() {
    log_info "Checking service dependencies..."
    
    local redis_ok=true
    local meshtastic_ok=true
    
    # Check Redis (if configured)
    if [ -n "$REDIS_URL" ]; then
        if curl -f -s --max-time "$TIMEOUT" "${HEALTH_URL}/redis" > /dev/null 2>&1; then
            log_success "Redis connectivity OK"
        else
            log_warning "Redis connectivity failed"
            redis_ok=false
        fi
    fi
    
    # Check Meshtastic interfaces
    if curl -f -s --max-time "$TIMEOUT" "${HEALTH_URL}/meshtastic" > /dev/null 2>&1; then
        log_success "Meshtastic interfaces OK"
    else
        log_warning "Meshtastic interfaces check failed"
        meshtastic_ok=false
    fi
    
    if [ "$redis_ok" = true ] && [ "$meshtastic_ok" = true ]; then
        return 0
    else
        return 1
    fi
}

# Main function
main() {
    local detailed=false
    local check_deps=false
    local check_db=false
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --detailed)
                detailed=true
                shift
                ;;
            --check-deps)
                check_deps=true
                shift
                ;;
            --check-db)
                check_db=true
                shift
                ;;
            --url)
                HEALTH_URL="$2"
                shift 2
                ;;
            --timeout)
                TIMEOUT="$2"
                shift 2
                ;;
            --retries)
                MAX_RETRIES="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --detailed       Show detailed health information"
                echo "  --check-deps     Check service dependencies"
                echo "  --check-db       Check database connectivity"
                echo "  --url URL        Health check URL (default: $HEALTH_URL)"
                echo "  --timeout SEC    Request timeout (default: $TIMEOUT)"
                echo "  --retries NUM    Max retries (default: $MAX_RETRIES)"
                echo "  --help           Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Check required tools
    check_tools
    
    # Perform health checks
    local exit_code=0
    
    if [ "$detailed" = true ]; then
        detailed_health_check || exit_code=1
    else
        health_check || exit_code=1
    fi
    
    if [ "$check_db" = true ]; then
        check_database || exit_code=1
    fi
    
    if [ "$check_deps" = true ]; then
        check_dependencies || exit_code=1
    fi
    
    exit $exit_code
}

# Run main function with all arguments
main "$@"