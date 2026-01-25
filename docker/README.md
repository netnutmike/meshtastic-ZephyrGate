# ZephyrGate Docker Image

[![Docker Pulls](https://img.shields.io/docker/pulls/YOUR_USERNAME/zephyrgate)](https://hub.docker.com/r/YOUR_USERNAME/zephyrgate)
[![Docker Image Size](https://img.shields.io/docker/image-size/YOUR_USERNAME/zephyrgate/latest)](https://hub.docker.com/r/YOUR_USERNAME/zephyrgate)
[![Docker Image Version](https://img.shields.io/docker/v/YOUR_USERNAME/zephyrgate?sort=semver)](https://hub.docker.com/r/YOUR_USERNAME/zephyrgate)

**ZephyrGate** is a comprehensive gateway service for Meshtastic networks, providing emergency response, bulletin board systems, weather services, email gateway, asset tracking, and more.

## Quick Start

### Using Docker Run

```bash
docker run -d \
  --name zephyrgate \
  -p 8080:8080 \
  -v zephyr_data:/app/data \
  -v zephyr_logs:/app/logs \
  -v zephyr_config:/app/config \
  --device=/dev/ttyUSB0:/dev/ttyUSB0 \
  YOUR_USERNAME/zephyrgate:latest
```

### Using Docker Compose

```bash
# Download docker-compose.yml
curl -O https://raw.githubusercontent.com/YOUR_REPO/zephyrgate/main/docker-compose.yml

# Start the service
docker-compose up -d
```

## Supported Architectures

- `linux/amd64` - x86_64 (Intel/AMD)
- `linux/arm64` - ARM 64-bit (Raspberry Pi 4, Apple Silicon)
- `linux/arm/v7` - ARM 32-bit (Raspberry Pi 3)

## Features

- 🚨 **Emergency Services** - SOS alerts and incident management
- 📋 **Bulletin Board System** - Public bulletins and private mail
- 🌤️ **Weather Services** - Current weather, forecasts, and alerts
- 📧 **Email Gateway** - Send and receive emails via mesh
- 📍 **Asset Tracking** - Track personnel and equipment
- 🤖 **Interactive Bot** - Commands and games
- 🌐 **Web Interface** - Admin panel for management
- 🔌 **Plugin System** - Extensible architecture

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ZEPHYR_LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARN, ERROR) |
| `ZEPHYR_WEB_PORT` | `8080` | Web interface port |
| `ZEPHYR_DEBUG` | `false` | Enable debug mode |
| `TZ` | `UTC` | Timezone |

## Volumes

| Path | Description |
|------|-------------|
| `/app/data` | Database and persistent data |
| `/app/logs` | Application logs |
| `/app/config` | Configuration files |

## Ports

| Port | Description |
|------|-------------|
| `8080` | Web interface and API |

## Device Access

For Meshtastic device connection, you need to pass through the USB device:

```bash
# Find your device
ls -la /dev/ttyUSB* /dev/ttyACM*

# Pass device to container
--device=/dev/ttyUSB0:/dev/ttyUSB0
```

## Configuration

Mount a custom configuration file:

```bash
docker run -d \
  --name zephyrgate \
  -v ./config.yaml:/app/config/config.yaml:ro \
  YOUR_USERNAME/zephyrgate:latest
```

## Health Check

The container includes a built-in health check:

```bash
docker inspect --format='{{.State.Health.Status}}' zephyrgate
```

## Documentation

- [Installation Guide](https://github.com/YOUR_REPO/zephyrgate/blob/main/docs/INSTALLATION.md)
- [User Manual](https://github.com/YOUR_REPO/zephyrgate/blob/main/docs/USER_MANUAL.md)
- [Admin Guide](https://github.com/YOUR_REPO/zephyrgate/blob/main/docs/ADMIN_GUIDE.md)
- [Plugin Development](https://github.com/YOUR_REPO/zephyrgate/blob/main/docs/PLUGIN_DEVELOPMENT.md)

## Support

- GitHub Issues: https://github.com/YOUR_REPO/zephyrgate/issues
- Documentation: https://github.com/YOUR_REPO/zephyrgate/tree/main/docs

## License

See [LICENSE](https://github.com/YOUR_REPO/zephyrgate/blob/main/LICENSE) file.
