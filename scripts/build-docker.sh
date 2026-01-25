#!/bin/bash
# Build Docker image for ZephyrGate
# Supports multi-architecture builds for Docker Hub

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
IMAGE_NAME="${IMAGE_NAME:-zephyrgate}"
DOCKER_USERNAME="${DOCKER_USERNAME:-YOUR_USERNAME}"
VERSION="${VERSION:-latest}"
BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
VCS_REF=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Parse arguments
PUSH=false
MULTI_ARCH=false
PLATFORMS="linux/amd64"

while [[ $# -gt 0 ]]; do
    case $1 in
        --push)
            PUSH=true
            shift
            ;;
        --multi-arch)
            MULTI_ARCH=true
            PLATFORMS="linux/amd64,linux/arm64,linux/arm/v7"
            shift
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --username)
            DOCKER_USERNAME="$2"
            shift 2
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Full image name
FULL_IMAGE_NAME="${DOCKER_USERNAME}/${IMAGE_NAME}"

log_info "Building Docker image: ${FULL_IMAGE_NAME}:${VERSION}"
log_info "Build date: ${BUILD_DATE}"
log_info "VCS ref: ${VCS_REF}"
log_info "Platforms: ${PLATFORMS}"

# Check if buildx is available for multi-arch
if [[ "$MULTI_ARCH" == true ]]; then
    if ! docker buildx version >/dev/null 2>&1; then
        log_error "Docker buildx is required for multi-architecture builds"
        exit 1
    fi
    
    # Create builder if it doesn't exist
    if ! docker buildx inspect zephyr-builder >/dev/null 2>&1; then
        log_info "Creating buildx builder..."
        docker buildx create --name zephyr-builder --use
    else
        docker buildx use zephyr-builder
    fi
fi

# Build command
BUILD_CMD="docker"
if [[ "$MULTI_ARCH" == true ]]; then
    BUILD_CMD="docker buildx"
fi

# Build arguments
BUILD_ARGS=(
    --build-arg "BUILD_DATE=${BUILD_DATE}"
    --build-arg "VERSION=${VERSION}"
    --build-arg "VCS_REF=${VCS_REF}"
    --tag "${FULL_IMAGE_NAME}:${VERSION}"
    --tag "${FULL_IMAGE_NAME}:latest"
)

# Add platform for multi-arch
if [[ "$MULTI_ARCH" == true ]]; then
    BUILD_ARGS+=(--platform "${PLATFORMS}")
fi

# Add push flag if requested
if [[ "$PUSH" == true ]]; then
    if [[ "$MULTI_ARCH" == true ]]; then
        BUILD_ARGS+=(--push)
    fi
    log_info "Will push to Docker Hub after build"
fi

# Build the image
log_info "Building image..."
if [[ "$MULTI_ARCH" == true ]]; then
    $BUILD_CMD build "${BUILD_ARGS[@]}" .
else
    $BUILD_CMD build "${BUILD_ARGS[@]}" .
    
    # Push if requested (for single arch)
    if [[ "$PUSH" == true ]]; then
        log_info "Pushing image to Docker Hub..."
        docker push "${FULL_IMAGE_NAME}:${VERSION}"
        docker push "${FULL_IMAGE_NAME}:latest"
    fi
fi

log_info "Build complete!"
log_info "Image: ${FULL_IMAGE_NAME}:${VERSION}"

# Show image size
if [[ "$MULTI_ARCH" == false ]]; then
    IMAGE_SIZE=$(docker images "${FULL_IMAGE_NAME}:${VERSION}" --format "{{.Size}}")
    log_info "Image size: ${IMAGE_SIZE}"
fi

# Usage instructions
echo ""
log_info "To run the image:"
echo "  docker run -d -p 8080:8080 --device=/dev/ttyUSB0 ${FULL_IMAGE_NAME}:${VERSION}"
echo ""
log_info "To push to Docker Hub:"
echo "  docker push ${FULL_IMAGE_NAME}:${VERSION}"
echo "  docker push ${FULL_IMAGE_NAME}:latest"
