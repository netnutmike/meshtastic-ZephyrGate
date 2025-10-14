#!/bin/bash
# ZephyrGate Deployment Verification Script
# Verify deployment is working correctly in production environment

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_URL="${DEPLOYMENT_URL:-http://localhost:8080}"
VERIFICATION_LOG="/tmp/zephyrgate-deployment-verification-$(date +%Y%m%d_%H%M%S).log"
TIMEOUT=30
MAX_RETRIES=10
RETRY_INTERVAL=5

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test results tracking
CHECKS_PASSED=0
CHECKS_FAILED=0

# Logging functions
log_info() {
    local msg="[INFO] $(date '+%Y-%m-%d %H:%M:%S') $1"
    echo -e "${BLUE}${msg}${NC}"
    echo "$msg" >> "$VERIFICATION_LOG"
}

log_success() {
    local msg="[SUCCESS] $(date '+%Y-%m-%d %H:%M:%S') $1"
    echo -e "${GREEN}${msg}${NC}"
    echo "$msg" >> "$VERIFICATION_LOG"
}

log_warning() {
    local msg="[WARNING] $(date '+%Y-%m-%d %H:%M:%S') $1"
    echo -e "${YELLOW}${msg}${NC}"
    echo "$msg" >> "$VERIFICATION_LOG"
}

log_error() {
    local msg="[ERROR] $(date '+%Y-%m-%d %H:%M:%S') $1"
    echo -e "${RED}${msg}${NC}"
    echo "$msg" >> "$VERIFICATION_LOG"
}

# Check result functions
check_passed() {
    CHECKS_PASSED=$((CHECKS_PASSED + 1))
    log_success "✓ $1"
}

check_failed() {
    CHECKS_FAILED=$((CHECKS_FAILED + 1))
    log_error "✗ $1"
}

# Display verification banner
show_banner() {
    cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║            ZephyrGate Deployment Verification               ║
║                                                              ║
║  Verify that ZephyrGate deployment is working correctly     ║
║  in the production environment.                             ║
╚══════════════════════════════════════════════════════════════╝
EOF
}

# Wait for service to be ready
wait_for_service() {
    log_info "Waiting for ZephyrGate service to be ready..."
    
    local retries=0
    while [ $retries -lt $MAX_RETRIES ]; do
        if curl -f -s --max-time $TIMEOUT "$DEPLOYMENT_URL/health" >/dev/null 2>&1; then
            log_success "Service is ready"
            return 0
        fi
        
        log_info "Service not ready, waiting... (attempt $((retries + 1))/$MAX_RETRIES)"
        sleep $RETRY_INTERVAL
        retries=$((retries + 1))
    done
    
    log_error "Service failed to become ready within timeout"
    return 1
}

# Check basic connectivity
check_connectivity() {
    log_info "Checking basic connectivity..."
    
    if curl -f -s --max-time $TIMEOUT "$DEPLOYMENT_URL/health" >/dev/null 2>&1; then
        check_passed "Basic connectivity"
    else
        check_failed "Basic connectivity"
        return 1
    fi
    
    return 0
}

# Check health endpoint
check_health_endpoint() {
    log_info "Checking health endpoint..."
    
    local response=$(curl -s --max-time $TIMEOUT "$DEPLOYMENT_URL/health" 2>/dev/null)
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$DEPLOYMENT_URL/health" 2>/dev/null)
    
    if [ "$http_code" = "200" ]; then
        check_passed "Health endpoint returns 200 OK"
        
        # Check if response is valid JSON
        if echo "$response" | jq . >/dev/null 2>&1; then
            check_passed "Health endpoint returns valid JSON"
            
            # Check health status
            local status=$(echo "$response" | jq -r '.status' 2>/dev/null)
            if [ "$status" = "healthy" ]; then
                check_passed "System reports healthy status"
            else
                check_failed "System reports unhealthy status: $status"
            fi
        else
            check_failed "Health endpoint returns invalid JSON"
        fi
    else
        check_failed "Health endpoint returns HTTP $http_code"
        return 1
    fi
    
    return 0
}

# Check API endpoints
check_api_endpoints() {
    log_info "Checking API endpoints..."
    
    local endpoints=(
        "/api/system/status"
        "/api/services"
        "/api/emergency/incidents"
        "/api/bbs/bulletins"
    )
    
    for endpoint in "${endpoints[@]}"; do
        local http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$DEPLOYMENT_URL$endpoint" 2>/dev/null)
        
        if [ "$http_code" = "200" ] || [ "$http_code" = "401" ]; then
            # 401 is acceptable for protected endpoints
            check_passed "API endpoint accessible: $endpoint"
        else
            check_failed "API endpoint failed: $endpoint (HTTP $http_code)"
        fi
    done
}

# Check web interface
check_web_interface() {
    log_info "Checking web interface..."
    
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$DEPLOYMENT_URL/" 2>/dev/null)
    
    if [ "$http_code" = "200" ] || [ "$http_code" = "302" ] || [ "$http_code" = "401" ]; then
        check_passed "Web interface accessible"
    else
        check_failed "Web interface failed (HTTP $http_code)"
        return 1
    fi
    
    return 0
}

# Check service status
check_service_status() {
    log_info "Checking service status..."
    
    local response=$(curl -s --max-time $TIMEOUT "$DEPLOYMENT_URL/api/services" 2>/dev/null)
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$DEPLOYMENT_URL/api/services" 2>/dev/null)
    
    if [ "$http_code" = "200" ]; then
        check_passed "Services endpoint accessible"
        
        # Parse service status if JSON is valid
        if echo "$response" | jq . >/dev/null 2>&1; then
            local services=$(echo "$response" | jq -r '.services | keys[]' 2>/dev/null)
            
            if [ -n "$services" ]; then
                check_passed "Service information available"
                
                # Check individual services
                while IFS= read -r service; do
                    local service_status=$(echo "$response" | jq -r ".services.\"$service\".status" 2>/dev/null)
                    if [ "$service_status" = "running" ] || [ "$service_status" = "healthy" ]; then
                        log_info "✓ Service $service: $service_status"
                    else
                        log_warning "⚠ Service $service: $service_status"
                    fi
                done <<< "$services"
            else
                check_failed "No service information available"
            fi
        fi
    else
        check_failed "Services endpoint failed (HTTP $http_code)"
    fi
}

# Check database connectivity
check_database() {
    log_info "Checking database connectivity..."
    
    local response=$(curl -s --max-time $TIMEOUT "$DEPLOYMENT_URL/health/detailed" 2>/dev/null)
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$DEPLOYMENT_URL/health/detailed" 2>/dev/null)
    
    if [ "$http_code" = "200" ]; then
        if echo "$response" | jq . >/dev/null 2>&1; then
            local db_status=$(echo "$response" | jq -r '.database.status' 2>/dev/null)
            if [ "$db_status" = "healthy" ] || [ "$db_status" = "connected" ]; then
                check_passed "Database connectivity"
            else
                check_failed "Database connectivity: $db_status"
            fi
        else
            check_failed "Invalid response from detailed health endpoint"
        fi
    else
        log_warning "Detailed health endpoint not available (HTTP $http_code)"
    fi
}

# Check performance
check_performance() {
    log_info "Checking performance..."
    
    # Measure response time for health endpoint
    local start_time=$(date +%s%N)
    curl -f -s --max-time $TIMEOUT "$DEPLOYMENT_URL/health" >/dev/null 2>&1
    local end_time=$(date +%s%N)
    
    local response_time=$(( (end_time - start_time) / 1000000 ))  # Convert to milliseconds
    
    if [ $response_time -lt 1000 ]; then
        check_passed "Response time acceptable: ${response_time}ms"
    elif [ $response_time -lt 5000 ]; then
        log_warning "Response time slow: ${response_time}ms"
        check_passed "Response time within limits"
    else
        check_failed "Response time too slow: ${response_time}ms"
    fi
}

# Check security headers
check_security_headers() {
    log_info "Checking security headers..."
    
    local headers=$(curl -s -I --max-time $TIMEOUT "$DEPLOYMENT_URL/" 2>/dev/null)
    
    # Check for important security headers
    if echo "$headers" | grep -i "x-frame-options" >/dev/null; then
        check_passed "X-Frame-Options header present"
    else
        log_warning "X-Frame-Options header missing"
    fi
    
    if echo "$headers" | grep -i "x-content-type-options" >/dev/null; then
        check_passed "X-Content-Type-Options header present"
    else
        log_warning "X-Content-Type-Options header missing"
    fi
    
    if echo "$headers" | grep -i "strict-transport-security" >/dev/null; then
        check_passed "HSTS header present"
    else
        log_warning "HSTS header missing (may be expected for HTTP)"
    fi
}

# Check SSL/TLS (if HTTPS)
check_ssl() {
    if [[ $DEPLOYMENT_URL == https://* ]]; then
        log_info "Checking SSL/TLS configuration..."
        
        local domain=$(echo "$DEPLOYMENT_URL" | sed 's|https://||' | sed 's|/.*||')
        
        # Check SSL certificate
        if echo | openssl s_client -connect "$domain:443" -servername "$domain" 2>/dev/null | openssl x509 -noout -dates >/dev/null 2>&1; then
            check_passed "SSL certificate valid"
            
            # Check certificate expiration
            local expiry=$(echo | openssl s_client -connect "$domain:443" -servername "$domain" 2>/dev/null | openssl x509 -noout -enddate | cut -d= -f2)
            local expiry_epoch=$(date -d "$expiry" +%s 2>/dev/null || echo "0")
            local current_epoch=$(date +%s)
            local days_until_expiry=$(( (expiry_epoch - current_epoch) / 86400 ))
            
            if [ $days_until_expiry -gt 30 ]; then
                check_passed "SSL certificate expires in $days_until_expiry days"
            elif [ $days_until_expiry -gt 7 ]; then
                log_warning "SSL certificate expires in $days_until_expiry days"
            else
                check_failed "SSL certificate expires soon: $days_until_expiry days"
            fi
        else
            check_failed "SSL certificate validation failed"
        fi
    else
        log_info "Skipping SSL checks (HTTP deployment)"
    fi
}

# Check Docker deployment (if applicable)
check_docker_deployment() {
    log_info "Checking Docker deployment..."
    
    if command -v docker >/dev/null 2>&1; then
        # Check if ZephyrGate containers are running
        local containers=$(docker ps --filter "name=zephyr" --format "table {{.Names}}\t{{.Status}}" 2>/dev/null)
        
        if [ -n "$containers" ]; then
            check_passed "Docker containers found"
            echo "$containers" | while IFS= read -r line; do
                log_info "$line"
            done
            
            # Check container health
            local unhealthy=$(docker ps --filter "name=zephyr" --filter "health=unhealthy" -q 2>/dev/null)
            if [ -z "$unhealthy" ]; then
                check_passed "All containers healthy"
            else
                check_failed "Unhealthy containers detected"
            fi
        else
            log_info "No ZephyrGate Docker containers found (may be manual deployment)"
        fi
    else
        log_info "Docker not available for container checks"
    fi
}

# Check system resources
check_system_resources() {
    log_info "Checking system resources..."
    
    # This is a basic check - in production you might want more sophisticated monitoring
    local response=$(curl -s --max-time $TIMEOUT "$DEPLOYMENT_URL/api/system/status" 2>/dev/null)
    local http_code=$(curl -s -o /dev/null -w "%{http_code}" --max-time $TIMEOUT "$DEPLOYMENT_URL/api/system/status" 2>/dev/null)
    
    if [ "$http_code" = "200" ]; then
        if echo "$response" | jq . >/dev/null 2>&1; then
            local cpu_usage=$(echo "$response" | jq -r '.cpu_usage' 2>/dev/null)
            local memory_usage=$(echo "$response" | jq -r '.memory_usage' 2>/dev/null)
            local disk_usage=$(echo "$response" | jq -r '.disk_usage' 2>/dev/null)
            
            if [ "$cpu_usage" != "null" ] && [ "$cpu_usage" != "" ]; then
                if (( $(echo "$cpu_usage < 80" | bc -l 2>/dev/null || echo "1") )); then
                    check_passed "CPU usage acceptable: $cpu_usage%"
                else
                    log_warning "High CPU usage: $cpu_usage%"
                fi
            fi
            
            if [ "$memory_usage" != "null" ] && [ "$memory_usage" != "" ]; then
                if (( $(echo "$memory_usage < 85" | bc -l 2>/dev/null || echo "1") )); then
                    check_passed "Memory usage acceptable: $memory_usage%"
                else
                    log_warning "High memory usage: $memory_usage%"
                fi
            fi
            
            if [ "$disk_usage" != "null" ] && [ "$disk_usage" != "" ]; then
                if (( $(echo "$disk_usage < 90" | bc -l 2>/dev/null || echo "1") )); then
                    check_passed "Disk usage acceptable: $disk_usage%"
                else
                    log_warning "High disk usage: $disk_usage%"
                fi
            fi
        fi
    else
        log_info "System status endpoint not available"
    fi
}

# Generate verification report
generate_verification_report() {
    log_info "Generating verification report..."
    
    local report_file="/tmp/zephyrgate-deployment-report-$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
ZephyrGate Deployment Verification Report
=========================================
Verification Date: $(date)
Deployment URL: $DEPLOYMENT_URL
System: $(uname -a 2>/dev/null || echo "Unknown")

Verification Results Summary:
- Checks Passed: $CHECKS_PASSED
- Checks Failed: $CHECKS_FAILED
- Total Checks: $((CHECKS_PASSED + CHECKS_FAILED))

Success Rate: $(( CHECKS_PASSED * 100 / (CHECKS_PASSED + CHECKS_FAILED) ))%

Detailed Results:
================
EOF
    
    # Add detailed log
    cat "$VERIFICATION_LOG" >> "$report_file"
    
    log_success "Verification report generated: $report_file"
    
    # Display summary
    echo
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║              Deployment Verification Complete               ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo
    echo "Verification Results:"
    echo "  Passed: $CHECKS_PASSED"
    echo "  Failed: $CHECKS_FAILED"
    echo "  Total:  $((CHECKS_PASSED + CHECKS_FAILED))"
    echo
    echo "Success Rate: $(( CHECKS_PASSED * 100 / (CHECKS_PASSED + CHECKS_FAILED) ))%"
    echo
    echo "Deployment URL: $DEPLOYMENT_URL"
    echo "Verification Report: $report_file"
    echo "Verification Log: $VERIFICATION_LOG"
    
    if [ $CHECKS_FAILED -eq 0 ]; then
        echo
        echo "🎉 All checks passed! Deployment is working correctly."
        return 0
    else
        echo
        echo "❌ Some checks failed. Please review the report and address issues."
        return 1
    fi
}

# Main verification function
main() {
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --url)
                DEPLOYMENT_URL="$2"
                shift 2
                ;;
            --timeout)
                TIMEOUT="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --url URL        Deployment URL to verify [default: http://localhost:8080]"
                echo "  --timeout SEC    Request timeout in seconds [default: 30]"
                echo "  --help           Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0 --url https://zephyrgate.example.com"
                echo "  $0 --url http://localhost:8080 --timeout 60"
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
    
    log_info "Starting ZephyrGate deployment verification..."
    log_info "Target URL: $DEPLOYMENT_URL"
    
    # Wait for service to be ready
    wait_for_service || exit 1
    
    # Run verification checks
    check_connectivity || exit 1
    check_health_endpoint
    check_api_endpoints
    check_web_interface
    check_service_status
    check_database
    check_performance
    check_security_headers
    check_ssl
    check_docker_deployment
    check_system_resources
    
    # Generate report
    generate_verification_report
}

# Run main function with all arguments
main "$@"