# Multi-stage Dockerfile for ZephyrGate
# Optimized for production deployment with minimal image size

# Build stage
FROM python:3.11-slim as builder

# Set build arguments
ARG BUILD_DATE
ARG VERSION=1.1.0
ARG VCS_REF

# Set labels
LABEL org.label-schema.build-date=$BUILD_DATE \
      org.label-schema.name="ZephyrGate" \
      org.label-schema.description="Unified Meshtastic Gateway Application" \
      org.label-schema.version=$VERSION \
      org.label-schema.vcs-ref=$VCS_REF \
      org.label-schema.schema-version="1.0"

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    pkg-config \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements and install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r /tmp/requirements.txt

# Production stage
FROM python:3.11-slim as production

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    # For Meshtastic serial connections
    udev \
    # For system monitoring
    procps \
    # For health checks
    curl \
    # For timezone support
    tzdata \
    # For Bluetooth LE support (optional)
    bluez \
    bluez-tools \
    # Clean up
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create application user
RUN groupadd -r zephyr && useradd -r -g zephyr -d /app -s /bin/bash zephyr

# Create application directories
WORKDIR /app
RUN mkdir -p /app/data /app/logs /app/config && \
    chown -R zephyr:zephyr /app

# Copy application code
COPY --chown=zephyr:zephyr src/ /app/src/
COPY --chown=zephyr:zephyr config/ /app/config/
COPY --chown=zephyr:zephyr docker-entrypoint.sh /app/
COPY --chown=zephyr:zephyr requirements.txt /app/

# Make entrypoint script executable
RUN chmod +x /app/docker-entrypoint.sh

# Set up Python path
ENV PYTHONPATH="/app/src:$PYTHONPATH"
ENV PYTHONUNBUFFERED=1

# Expose ports
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Switch to application user
USER zephyr

# Set default environment variables
ENV ZEPHYR_CONFIG_DIR="/app/config" \
    ZEPHYR_DATA_DIR="/app/data" \
    ZEPHYR_LOG_DIR="/app/logs" \
    ZEPHYR_LOG_LEVEL="INFO"

# Volume mounts for persistent data
VOLUME ["/app/data", "/app/logs", "/app/config"]

# Entry point
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python", "-m", "src.main"]