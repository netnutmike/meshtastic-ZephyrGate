#!/bin/bash
# Multi-architecture Docker build script for ZephyrGate
# Builds images for AMD64, ARM64, and ARM/v7 architectures

set -e

# Configuration
IMAGE_NAME="zephyrgate"
VERSION=${VERSION:-"latest"}
REGISTRY=${REGISTRY:-""}
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
VCS_REF=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        log_error "Docker daemon is not running"
        exit 1
    fi
    
    # Check if buildx is available
    if ! docker buildx version &> /dev/null; then
        log_error "Docker buildx is not available. Please update Docker to a newer version."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Setup buildx builder
setup_builder() {
    log_info "Setting up multi-architecture builder..."
    
    # Create a new builder instance if it doesn't exist
    if ! docker buildx ls | grep -q "zephyr-builder"; then
        docker buildx create --name zephyr-builder --driver docker-container --bootstrap
        log_success "Created new buildx builder: zephyr-builder"
    else
        log_info "Using existing buildx builder: zephyr-builder"
    fi
    
    # Use the builder
    docker buildx use zephyr-builder
    
    # Inspect the builder to ensure it supports required platforms
    log_info "Inspecting builder capabilities..."
    docker buildx inspect --bootstrap
}

# Build multi-architecture images
build_images() {
    log_info "Building multi-architecture Docker images..."
    
    # Define target platforms
    PLATFORMS="linux/amd64,linux/arm64,linux/arm/v7"
    
    # Build image name with registry if provided
    if [ -n "$REGISTRY" ]; then
        FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}"
    else
        FULL_IMAGE_NAME="${IMAGE_NAME}"
    fi
    
    # Build arguments
    BUILD_ARGS=(
        --build-arg "BUILD_DATE=${BUILD_DATE}"
        --build-arg "VERSION=${VERSION}"
        --build-arg "VCS_REF=${VCS_REF}"
    )
    
    # Tags
    TAGS=(
        --tag "${FULL_IMAGE_NAME}:${VERSION}"
        --tag "${FULL_IMAGE_NAME}:latest"
    )
    
    log_info "Building for platforms: ${PLATFORMS}"
    log_info "Image name: ${FULL_IMAGE_NAME}"
    log_info "Version: ${VERSION}"
    log_info "Build date: ${BUILD_DATE}"
    log_info "VCS ref: ${VCS_REF}"
    
    # Execute the build
    docker buildx build \
        --platform "${PLATFORMS}" \
        "${BUILD_ARGS[@]}" \
        "${TAGS[@]}" \
        --push \
        .
    
    log_success "Multi-architecture build completed successfully"
}

# Build for local testing (single architecture)
build_local() {
    log_info "Building local image for testing..."
    
    # Detect current architecture
    ARCH=$(uname -m)
    case $ARCH in
        x86_64)
            PLATFORM="linux/amd64"
            ;;
        aarch64)
            PLATFORM="linux/arm64"
            ;;
        armv7l)
            PLATFORM="linux/arm/v7"
            ;;
        *)
            log_warning "Unknown architecture: $ARCH, defaulting to linux/amd64"
            PLATFORM="linux/amd64"
            ;;
    esac
    
    log_info "Building for platform: ${PLATFORM}"
    
    docker buildx build \
        --platform "${PLATFORM}" \
        --build-arg "BUILD_DATE=${BUILD_DATE}" \
        --build-arg "VERSION=${VERSION}" \
        --build-arg "VCS_REF=${VCS_REF}" \
        --tag "${IMAGE_NAME}:${VERSION}" \
        --tag "${IMAGE_NAME}:latest" \
        --load \
        .
    
    log_success "Local build completed successfully"
}

# Test the built image
test_image() {
    local image_name="$1"
    log_info "Testing image: ${image_name}"
    
    # Test if image can start and respond to health check
    container_id=$(docker run -d --rm \
        -e ZEPHYR_LOG_LEVEL=DEBUG \
        -e ZEPHYR_DATABASE_URL=sqlite:///tmp/test.db \
        "${image_name}")
    
    # Wait for container to start
    sleep 10
    
    # Check if container is still running
    if docker ps | grep -q "${container_id}"; then
        log_success "Container started successfully"
        
        # Test health endpoint
        if docker exec "${container_id}" curl -f http://localhost:8080/health; then
            log_success "Health check passed"
        else
            log_warning "Health check failed"
        fi
    else
        log_error "Container failed to start"
        docker logs "${container_id}"
    fi
    
    # Cleanup
    docker stop "${container_id}" || true
}

# Push images to registry
push_images() {
    if [ -z "$REGISTRY" ]; then
        log_warning "No registry specified, skipping push"
        return
    fi
    
    log_info "Pushing images to registry: ${REGISTRY}"
    
    # The images are already pushed during the buildx build with --push
    log_success "Images pushed successfully"
}

# Generate image manifest
generate_manifest() {
    log_info "Generating image manifest..."
    
    cat > image-manifest.json << EOF
{
  "name": "${IMAGE_NAME}",
  "version": "${VERSION}",
  "build_date": "${BUILD_DATE}",
  "vcs_ref": "${VCS_REF}",
  "platforms": [
    "linux/amd64",
    "linux/arm64",
    "linux/arm/v7"
  ],
  "registry": "${REGISTRY}",
  "tags": [
    "${VERSION}",
    "latest"
  ]
}
EOF
    
    log_success "Image manifest generated: image-manifest.json"
}

# Main function
main() {
    log_info "Starting ZephyrGate multi-architecture build"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --local)
                LOCAL_BUILD=true
                shift
                ;;
            --test)
                TEST_IMAGE=true
                shift
                ;;
            --version)
                VERSION="$2"
                shift 2
                ;;
            --registry)
                REGISTRY="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --local          Build for local architecture only"
                echo "  --test           Test the built image"
                echo "  --version VER    Set version tag (default: latest)"
                echo "  --registry REG   Set registry prefix"
                echo "  --help           Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Check prerequisites
    check_prerequisites
    
    if [ "$LOCAL_BUILD" = true ]; then
        # Local build for testing
        build_local
        
        if [ "$TEST_IMAGE" = true ]; then
            test_image "${IMAGE_NAME}:${VERSION}"
        fi
    else
        # Multi-architecture build
        setup_builder
        build_images
        generate_manifest
        
        if [ "$TEST_IMAGE" = true ]; then
            log_info "Testing multi-arch images requires pulling from registry"
            log_info "Use --local --test for local testing"
        fi
    fi
    
    log_success "Build process completed successfully!"
}

# Run main function with all arguments
main "$@"