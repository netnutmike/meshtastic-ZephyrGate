# ZephyrGate Docker Deployment Guide

Complete guide for deploying ZephyrGate using Docker and Docker Compose.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation Methods](#installation-methods)
3. [Configuration](#configuration)
4. [Device Access](#device-access)
5. [Docker Compose](#docker-compose)
6. [Production Deployment](#production-deployment)
7. [Updating](#updating)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

- Docker 20.10+ installed
- Docker Compose 2.0+ (optional but recommended)
- Meshtastic device connected via USB
- 512MB+ RAM available
- 1GB+ disk space

### Fastest Deployment

```bash
# Pull and run the image
docker run -d \
  --name zephyrgate \
  -p 8080:8080 \
  -v zephyr_data:/app/data \
  -v zephyr_logs:/app/logs \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  --restart unless-stopped \
  YOUR_USERNAME/zephyrgate:latest

# Access web interface
open http://localhost:8080
```

---

## Installation Methods

### Method 1: Docker Run (Simplest)

**Advantages:**
- Single command deployment
- No additional files needed
- Quick testing

**Command:**

```bash
docker run -d \
  --name zephyrgate \
  -p 8080:8080 \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -v $(pwd)/config:/app/config \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  -e TZ=America/New_York \
  -e ZEPHYR_LOG_LEVEL=INFO \
  --restart unless-stopped \
  YOUR_USERNAME/zephyrgate:latest
```

### Method 2: Docker Compose (Recommended)

**Advantages:**
- Easy configuration management
- Multi-container orchestration
- Simple updates and restarts

**Steps:**

```bash
# 1. Create project directory
mkdir zephyrgate && cd zephyrgate

# 2. Download docker-compose.yml
curl -O https://raw.githubusercontent.com/YOUR_REPO/zephyrgate/main/docker/docker-compose.simple.yml
mv docker-compose.simple.yml docker-compose.yml

# 3. Edit configuration (optional)
nano docker-compose.yml

# 4. Start services
docker-compose up -d

# 5. View logs
docker-compose logs -f
```

### Method 3: Build from Source

**Advantages:**
- Latest development version
- Custom modifications
- Full control

**Steps:**

```bash
# 1. Clone repository
git clone https://github.com/YOUR_REPO/zephyrgate.git
cd zephyrgate

# 2. Build image
docker build -t zephyrgate:local .

# 3. Run container
docker run -d \
  --name zephyrgate \
  -p 8080:8080 \
  -v $(pwd)/data:/app/data \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  zephyrgate:local
```

---

## Configuration

### Environment Variables

Configure ZephyrGate using environment variables:

```bash
docker run -d \
  --name zephyrgate \
  -e ZEPHYR_LOG_LEVEL=DEBUG \
  -e ZEPHYR_WEB_PORT=8080 \
  -e ZEPHYR_DEBUG=false \
  -e TZ=America/New_York \
  YOUR_USERNAME/zephyrgate:latest
```

**Available Variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `ZEPHYR_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARN, ERROR) |
| `ZEPHYR_WEB_PORT` | `8080` | Web interface port |
| `ZEPHYR_DEBUG` | `false` | Enable debug mode |
| `ZEPHYR_CONFIG_DIR` | `/app/config` | Configuration directory |
| `ZEPHYR_DATA_DIR` | `/app/data` | Data directory |
| `ZEPHYR_LOG_DIR` | `/app/logs` | Log directory |
| `TZ` | `UTC` | Timezone (e.g., America/New_York) |

### Configuration File

Mount a custom configuration file:

```bash
# Create config directory
mkdir -p config

# Download template
curl -o config/config.yaml \
  https://raw.githubusercontent.com/YOUR_REPO/zephyrgate/main/config/config.template.yaml

# Edit configuration
nano config/config.yaml

# Run with custom config
docker run -d \
  --name zephyrgate \
  -v $(pwd)/config:/app/config:ro \
  YOUR_USERNAME/zephyrgate:latest
```

### Plugin Configuration

Enable/disable plugins in `config/config.yaml`:

```yaml
plugins:
  enabled_plugins:
    - "bot_service"
    - "emergency_service"
    - "bbs_service"
    - "weather_service"
    - "email_service"
    - "asset_service"
    - "web_service"
```

---

## Device Access

### Finding Your Device

```bash
# List USB devices
ls -la /dev/ttyUSB* /dev/ttyACM*

# Common device paths:
# - /dev/ttyUSB0  (Most USB serial adapters)
# - /dev/ttyACM0  (Some Arduino-based devices)
# - /dev/cu.usbmodem* (macOS)
```

### Passing Device to Container

**Linux:**

```bash
docker run -d \
  --name zephyrgate \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  YOUR_USERNAME/zephyrgate:latest
```

**macOS:**

```bash
# Find device
ls -la /dev/cu.usbmodem*

# Pass to container
docker run -d \
  --name zephyrgate \
  --device=/dev/cu.usbmodem9070698283041:/dev/cu.usbmodem9070698283041 \
  YOUR_USERNAME/zephyrgate:latest
```

**Raspberry Pi:**

```bash
# Usually /dev/ttyUSB0 or /dev/ttyACM0
docker run -d \
  --name zephyrgate \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  --privileged \
  YOUR_USERNAME/zephyrgate:latest
```

### Device Permissions

If you get permission errors:

```bash
# Add user to dialout group (Linux)
sudo usermod -aG dialout $USER

# Or run with privileged mode (not recommended for production)
docker run -d --privileged YOUR_USERNAME/zephyrgate:latest
```

---

## Docker Compose

### Simple Configuration

**docker-compose.yml:**

```yaml
version: '3.8'

services:
  zephyrgate:
    image: YOUR_USERNAME/zephyrgate:latest
    container_name: zephyrgate
    restart: unless-stopped
    
    ports:
      - "8080:8080"
    
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./config:/app/config
    
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
    
    environment:
      - TZ=America/New_York
      - ZEPHYR_LOG_LEVEL=INFO
    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### Commands

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Restart services
docker-compose restart

# Update and restart
docker-compose pull
docker-compose up -d

# View status
docker-compose ps
```

### Advanced Configuration

**docker-compose.yml with Redis:**

```yaml
version: '3.8'

services:
  zephyrgate:
    image: YOUR_USERNAME/zephyrgate:latest
    container_name: zephyrgate
    restart: unless-stopped
    
    ports:
      - "8080:8080"
    
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
      - ./config:/app/config
    
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
    
    environment:
      - TZ=America/New_York
      - ZEPHYR_LOG_LEVEL=INFO
      - ZEPHYR_REDIS_URL=redis://redis:6379/0
    
    depends_on:
      - redis
    
    networks:
      - zephyr_network

  redis:
    image: redis:7-alpine
    container_name: zephyr_redis
    restart: unless-stopped
    
    command: redis-server --appendonly yes
    
    volumes:
      - redis_data:/data
    
    networks:
      - zephyr_network

volumes:
  redis_data:

networks:
  zephyr_network:
    driver: bridge
```

---

## Production Deployment

### Security Considerations

1. **Use specific version tags:**
   ```yaml
   image: YOUR_USERNAME/zephyrgate:1.0.0  # Not :latest
   ```

2. **Run as non-root:**
   ```yaml
   user: "1000:1000"
   ```

3. **Read-only root filesystem:**
   ```yaml
   read_only: true
   tmpfs:
     - /tmp
   ```

4. **Limit resources:**
   ```yaml
   deploy:
     resources:
       limits:
         memory: 512M
         cpus: '1.0'
   ```

5. **Use secrets for sensitive data:**
   ```yaml
   secrets:
     - db_password
     - api_key
   ```

### Production docker-compose.yml

```yaml
version: '3.8'

services:
  zephyrgate:
    image: YOUR_USERNAME/zephyrgate:1.0.0
    container_name: zephyrgate-prod
    restart: unless-stopped
    
    ports:
      - "127.0.0.1:8080:8080"  # Only localhost
    
    volumes:
      - /opt/zephyrgate/data:/app/data
      - /opt/zephyrgate/logs:/app/logs
      - /opt/zephyrgate/config:/app/config:ro
    
    devices:
      - /dev/ttyUSB0:/dev/ttyUSB0
    
    environment:
      - ZEPHYR_APP_ENVIRONMENT=production
      - ZEPHYR_DEBUG=false
      - ZEPHYR_LOG_LEVEL=INFO
      - TZ=America/New_York
    
    security_opt:
      - no-new-privileges:true
    
    user: "1000:1000"
    
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '1.0'
    
    logging:
      driver: "json-file"
      options:
        max-size: "50m"
        max-file: "5"
    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  nginx:
    image: nginx:alpine
    container_name: zephyr-nginx
    restart: unless-stopped
    
    ports:
      - "80:80"
      - "443:443"
    
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    
    depends_on:
      - zephyrgate
```

### Nginx Configuration

**nginx.conf:**

```nginx
events {
    worker_connections 1024;
}

http {
    upstream zephyrgate {
        server zephyrgate:8080;
    }

    server {
        listen 80;
        server_name your-domain.com;
        
        location / {
            return 301 https://$server_name$request_uri;
        }
    }

    server {
        listen 443 ssl http2;
        server_name your-domain.com;
        
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        
        location / {
            proxy_pass http://zephyrgate;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        location /ws {
            proxy_pass http://zephyrgate;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }
}
```

---

## Updating

### Update to Latest Version

```bash
# Using docker run
docker stop zephyrgate
docker rm zephyrgate
docker pull YOUR_USERNAME/zephyrgate:latest
docker run -d ... # Same command as before

# Using docker-compose
docker-compose pull
docker-compose up -d
```

### Update to Specific Version

```bash
# Pull specific version
docker pull YOUR_USERNAME/zephyrgate:1.0.0

# Update docker-compose.yml
image: YOUR_USERNAME/zephyrgate:1.0.0

# Restart
docker-compose up -d
```

### Backup Before Update

```bash
# Backup data
docker exec zephyrgate tar czf /tmp/backup.tar.gz /app/data
docker cp zephyrgate:/tmp/backup.tar.gz ./backup-$(date +%Y%m%d).tar.gz

# Or backup volumes
docker run --rm \
  -v zephyr_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/data-backup.tar.gz /data
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs zephyrgate

# Check if port is in use
sudo lsof -i :8080

# Check device permissions
ls -la /dev/ttyUSB0

# Run with debug mode
docker run -e ZEPHYR_DEBUG=true -e ZEPHYR_LOG_LEVEL=DEBUG ...
```

### Device Not Found

```bash
# List devices
ls -la /dev/tty*

# Check if device is passed correctly
docker inspect zephyrgate | grep -A 10 Devices

# Try privileged mode (temporary)
docker run --privileged ...
```

### Permission Denied

```bash
# Add user to dialout group
sudo usermod -aG dialout $USER

# Logout and login again
# Or use newgrp
newgrp dialout

# Check group membership
groups
```

### Container Keeps Restarting

```bash
# Check logs
docker logs zephyrgate --tail 100

# Check health status
docker inspect zephyrgate | grep -A 10 Health

# Disable health check temporarily
docker run --no-healthcheck ...
```

### High Memory Usage

```bash
# Check memory usage
docker stats zephyrgate

# Limit memory
docker run -m 512m ...

# Or in docker-compose.yml
deploy:
  resources:
    limits:
      memory: 512M
```

### Cannot Access Web Interface

```bash
# Check if container is running
docker ps | grep zephyrgate

# Check port mapping
docker port zephyrgate

# Test from inside container
docker exec zephyrgate curl http://localhost:8080/health

# Check firewall
sudo ufw status
sudo ufw allow 8080
```

### Database Errors

```bash
# Check database file
docker exec zephyrgate ls -la /app/data/

# Backup and reinitialize
docker exec zephyrgate mv /app/data/zephyrgate.db /app/data/zephyrgate.db.bak
docker restart zephyrgate
```

---

## Advanced Topics

### Multi-Architecture Support

ZephyrGate images support multiple architectures:

```bash
# Pull for your architecture automatically
docker pull YOUR_USERNAME/zephyrgate:latest

# Specific architecture
docker pull --platform linux/arm64 YOUR_USERNAME/zephyrgate:latest
docker pull --platform linux/amd64 YOUR_USERNAME/zephyrgate:latest
docker pull --platform linux/arm/v7 YOUR_USERNAME/zephyrgate:latest
```

### Custom Plugins

Mount custom plugins directory:

```bash
docker run -d \
  -v $(pwd)/custom-plugins:/app/plugins/custom \
  YOUR_USERNAME/zephyrgate:latest
```

### Development Mode

Run with live code reload:

```bash
docker run -d \
  -v $(pwd)/src:/app/src \
  -e ZEPHYR_DEBUG=true \
  -e ZEPHYR_LOG_LEVEL=DEBUG \
  YOUR_USERNAME/zephyrgate:latest
```

### Monitoring

Add Prometheus monitoring:

```yaml
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
```

---

## Support

- **Documentation**: https://github.com/YOUR_REPO/zephyrgate/tree/main/docs
- **Issues**: https://github.com/YOUR_REPO/zephyrgate/issues
- **Docker Hub**: https://hub.docker.com/r/YOUR_USERNAME/zephyrgate

---

**Last Updated**: 2026-01-25
