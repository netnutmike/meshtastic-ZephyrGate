# ZephyrGate Docker Quick Start

## One-Command Deployment

```bash
docker run -d \
  --name zephyrgate \
  -p 8080:8080 \
  -v zephyr_data:/app/data \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  --restart unless-stopped \
  YOUR_USERNAME/zephyrgate:latest
```

Then open: **http://localhost:8080**

## Docker Compose Deployment

```bash
# Download compose file
curl -O https://raw.githubusercontent.com/YOUR_REPO/zephyrgate/main/docker/docker-compose.simple.yml

# Start
docker-compose -f docker-compose.simple.yml up -d

# View logs
docker-compose logs -f
```

## Common Commands

```bash
# View logs
docker logs -f zephyrgate

# Stop
docker stop zephyrgate

# Start
docker start zephyrgate

# Restart
docker restart zephyrgate

# Update to latest
docker pull YOUR_USERNAME/zephyrgate:latest
docker stop zephyrgate
docker rm zephyrgate
# Run command again with latest image

# Remove
docker stop zephyrgate
docker rm zephyrgate
docker volume rm zephyr_data
```

## Find Your Device

```bash
# Linux
ls -la /dev/ttyUSB* /dev/ttyACM*

# macOS
ls -la /dev/cu.usbmodem*

# Then use in --device flag:
--device=/dev/ttyUSB0:/dev/ttyUSB0
```

## Environment Variables

```bash
docker run -d \
  -e TZ=America/New_York \
  -e ZEPHYR_LOG_LEVEL=DEBUG \
  -e ZEPHYR_DEBUG=true \
  YOUR_USERNAME/zephyrgate:latest
```

## Custom Configuration

```bash
# Create config directory
mkdir -p config

# Download template
curl -o config/config.yaml \
  https://raw.githubusercontent.com/YOUR_REPO/zephyrgate/main/config/config.template.yaml

# Edit config
nano config/config.yaml

# Run with custom config
docker run -d \
  -v $(pwd)/config:/app/config:ro \
  YOUR_USERNAME/zephyrgate:latest
```

## Troubleshooting

```bash
# Check if running
docker ps | grep zephyrgate

# View logs
docker logs zephyrgate --tail 100

# Check health
docker inspect zephyrgate | grep -A 10 Health

# Test from inside container
docker exec zephyrgate curl http://localhost:8080/health

# Restart
docker restart zephyrgate
```

## Full Documentation

- **Docker Guide**: [docs/DOCKER_DEPLOYMENT.md](docs/DOCKER_DEPLOYMENT.md)
- **Installation**: [docs/INSTALLATION.md](docs/INSTALLATION.md)
- **User Manual**: [docs/USER_MANUAL.md](docs/USER_MANUAL.md)
- **Admin Guide**: [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md)
