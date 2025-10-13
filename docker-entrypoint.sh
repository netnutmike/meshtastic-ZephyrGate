#!/bin/bash
# Docker entrypoint script for ZephyrGate
# Handles initialization, configuration, and startup

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    if [[ "${ZEPHYR_DEBUG:-false}" == "true" ]]; then
        echo -e "${BLUE}[DEBUG]${NC} $1"
    fi
}

# Function to wait for service
wait_for_service() {
    local host=$1
    local port=$2
    local service_name=$3
    local timeout=${4:-30}
    
    log_info "Waiting for $service_name at $host:$port..."
    
    for i in $(seq 1 $timeout); do
        if nc -z "$host" "$port" 2>/dev/null; then
            log_info "$service_name is ready!"
            return 0
        fi
        sleep 1
    done
    
    log_error "$service_name is not available after ${timeout}s"
    return 1
}

# Function to check and create directories
ensure_directories() {
    local dirs=("$ZEPHYR_DATA_DIR" "$ZEPHYR_LOG_DIR" "$ZEPHYR_CONFIG_DIR")
    
    for dir in "${dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            log_info "Creating directory: $dir"
            mkdir -p "$dir"
        fi
        
        # Ensure proper permissions
        if [[ ! -w "$dir" ]]; then
            log_warn "Directory $dir is not writable"
        fi
    done
}

# Function to initialize configuration
init_config() {
    local config_file="$ZEPHYR_CONFIG_DIR/config.yaml"
    local template_file="$ZEPHYR_CONFIG_DIR/config.template.yaml"
    
    # Copy template if config doesn't exist
    if [[ ! -f "$config_file" && -f "$template_file" ]]; then
        log_info "Creating initial configuration from template"
        cp "$template_file" "$config_file"
    fi
    
    # Validate configuration exists
    if [[ ! -f "$config_file" ]]; then
        log_warn "No configuration file found at $config_file"
        log_info "Using default configuration"
    else
        log_info "Using configuration file: $config_file"
    fi
}

# Function to check system requirements
check_requirements() {
    log_info "Checking system requirements..."
    
    # Check Python version
    python_version=$(python --version 2>&1 | cut -d' ' -f2)
    log_debug "Python version: $python_version"
    
    # Check available memory
    if [[ -f /proc/meminfo ]]; then
        mem_total=$(grep MemTotal /proc/meminfo | awk '{print $2}')
        mem_total_mb=$((mem_total / 1024))
        log_debug "Available memory: ${mem_total_mb}MB"
        
        if [[ $mem_total_mb -lt 256 ]]; then
            log_warn "Low memory detected (${mem_total_mb}MB). Consider increasing container memory."
        fi
    fi
    
    # Check disk space
    disk_space=$(df -h "$ZEPHYR_DATA_DIR" | tail -1 | awk '{print $4}')
    log_debug "Available disk space: $disk_space"
}

# Function to setup device permissions
setup_device_permissions() {
    log_info "Setting up device permissions..."
    
    # Check for common Meshtastic device paths
    local device_paths=("/dev/ttyUSB0" "/dev/ttyACM0" "/dev/ttyUSB1" "/dev/ttyACM1")
    
    for device in "${device_paths[@]}"; do
        if [[ -e "$device" ]]; then
            log_info "Found device: $device"
            
            # Check if device is readable
            if [[ -r "$device" ]]; then
                log_debug "Device $device is readable"
            else
                log_warn "Device $device is not readable. Check permissions."
            fi
        fi
    done
    
    # List available USB devices for debugging
    if command -v lsusb >/dev/null 2>&1; then
        log_debug "USB devices:"
        lsusb | while read -r line; do
            log_debug "  $line"
        done
    fi
}

# Function to perform health check
health_check() {
    local max_attempts=30
    local attempt=1
    
    log_info "Performing health check..."
    
    while [[ $attempt -le $max_attempts ]]; do
        if curl -f -s "http://localhost:${ZEPHYR_WEB_PORT:-8080}/health" >/dev/null 2>&1; then
            log_info "Health check passed"
            return 0
        fi
        
        log_debug "Health check attempt $attempt/$max_attempts failed"
        sleep 2
        ((attempt++))
    done
    
    log_error "Health check failed after $max_attempts attempts"
    return 1
}

# Function to handle shutdown
shutdown_handler() {
    log_info "Received shutdown signal, stopping ZephyrGate..."
    
    # Send SIGTERM to the main process
    if [[ -n "$MAIN_PID" ]]; then
        kill -TERM "$MAIN_PID" 2>/dev/null || true
        
        # Wait for graceful shutdown
        local timeout=30
        while [[ $timeout -gt 0 ]] && kill -0 "$MAIN_PID" 2>/dev/null; do
            sleep 1
            ((timeout--))
        done
        
        # Force kill if still running
        if kill -0 "$MAIN_PID" 2>/dev/null; then
            log_warn "Forcing shutdown..."
            kill -KILL "$MAIN_PID" 2>/dev/null || true
        fi
    fi
    
    log_info "ZephyrGate stopped"
    exit 0
}

# Main execution
main() {
    log_info "Starting ZephyrGate Docker container..."
    log_info "Version: ${VERSION:-unknown}"
    log_info "Build date: ${BUILD_DATE:-unknown}"
    
    # Set up signal handlers
    trap shutdown_handler SIGTERM SIGINT
    
    # Environment setup
    export PYTHONPATH="/app/src:${PYTHONPATH:-}"
    export PYTHONUNBUFFERED=1
    
    # Check system requirements
    check_requirements
    
    # Ensure required directories exist
    ensure_directories
    
    # Initialize configuration
    init_config
    
    # Setup device permissions
    setup_device_permissions
    
    # Wait for dependencies
    if [[ "${WAIT_FOR_REDIS:-true}" == "true" ]]; then
        wait_for_service "redis" "6379" "Redis" 30 || log_warn "Redis not available, continuing without cache"
    fi
    
    # Start the application
    log_info "Starting ZephyrGate application..."
    log_info "Command: $*"
    
    # Execute the main command in background
    "$@" &
    MAIN_PID=$!
    
    # Wait for the application to start
    sleep 5
    
    # Perform initial health check (optional)
    if [[ "${SKIP_HEALTH_CHECK:-false}" != "true" ]]; then
        health_check || log_warn "Initial health check failed, but continuing..."
    fi
    
    # Wait for the main process
    wait $MAIN_PID
    exit_code=$?
    
    log_info "ZephyrGate exited with code $exit_code"
    exit $exit_code
}

# Execute main function with all arguments
main "$@"