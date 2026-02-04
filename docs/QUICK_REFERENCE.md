# ZephyrGate Quick Reference

## Installation

```bash
# Easy install (recommended)
./install.sh

# Start ZephyrGate
./start.sh

# Stop ZephyrGate
./stop.sh
```

## System Service Commands

```bash
# Start service
sudo systemctl start zephyrgate

# Stop service
sudo systemctl stop zephyrgate

# Restart service
sudo systemctl restart zephyrgate

# Check status
sudo systemctl status zephyrgate

# View logs
sudo journalctl -u zephyrgate -f
```

## Configuration

**Main config file**: `config/config.yaml`

```bash
# Edit configuration
nano config/config.yaml

# Restart to apply changes
./stop.sh && ./start.sh
```

## Web Interface

**URL**: http://localhost:8080  
**Default credentials**: admin / admin

**Change password immediately after first login!**

## Common Commands (via Mesh)

### General
- `ping` - Test bot responsiveness
- `help` - Show available commands
- `help <command>` - Get help for specific command

### Bot Service
- `info <topic>` - Get information about a topic
- `history [count]` - View message history
- `games` - List available games
- `play <game>` - Start a game

### Emergency Service (Submenu)
**Quick Access:**
- `sos <message>` - Send emergency alert (always available)

**Emergency Menu:** `emergency`
- `emergency` - Show emergency menu
- `emergency status` - Check emergency status
- `emergency cancel` - Cancel your active SOS
- `emergency respond <id>` - Respond to an emergency
- `emergency incidents` - Enter incidents submenu

**Incidents Submenu:** `emergency incidents`
- `emergency incidents list` - List active incidents
- `emergency incidents view <id>` - View incident details
- `emergency incidents close <id>` - Close incident
- `emergency incidents history` - View past incidents
- `emergency incidents stats` - View statistics

### BBS Service (Submenu)
**Quick Access:**
- `read <id>` - Read bulletin
- `post <subject> <content>` - Post bulletin
- `directory` - View channel directory

**BBS Menu:** `bbs`
- `bbs` - Show BBS menu
- `bbs mail` - Enter mail submenu
- `bbs bulletins` - Enter bulletins submenu
- `bbs channels` - Enter channels submenu

**Mail Submenu:** `mail` or `bbs mail`
- `mail` - Show mail menu
- `mail list` - List your mail
- `mail read <id>` - Read mail
- `mail send` - Compose new mail
- `mail delete <id>` - Delete mail

**Bulletins Submenu:** `bbs bulletins`
- `bbs bulletins list` - List bulletins
- `bbs bulletins read <id>` - Read bulletin
- `bbs bulletins post` - Compose bulletin
- `bbs bulletins boards` - List boards
- `bbs bulletins board <name>` - Switch board

**Channels Submenu:** `bbs channels`
- `bbs channels list` - List channels
- `bbs channels info <id>` - Channel details
- `bbs channels search <term>` - Search channels

### Weather Service
- `wx [location]` - Current weather
- `weather [location]` - Detailed weather
- `forecast [days] [location]` - Weather forecast
- `alerts [location]` - Weather alerts

### Email Service
- `email send <to> <subject> <body>` - Send email
- `email check` - Check for new emails

### Asset Tracking (Submenu)
**Quick Access:**
- `locate [id]` - Locate asset (always available)

**Asset Menu:** `asset`
- `asset` - Show asset menu
- `asset list` - List all tracked assets
- `asset register <id> [name]` - Register asset
- `asset locate <id>` - Locate asset
- `asset status <id>` - Get asset status
- `asset update <id> <lat> <lon>` - Update location
- `asset tracking` - Enter tracking submenu
- `asset geofence` - Enter geofence submenu

**Tracking Submenu:** `asset tracking`
- `asset tracking start <id>` - Start tracking
- `asset tracking stop <id>` - Stop tracking
- `asset tracking history <id>` - View history
- `asset tracking active` - List active tracking
- `asset tracking stats` - View statistics

**Geofence Submenu:** `asset geofence`
- `asset geofence list` - List geofences
- `asset geofence create <name> <lat> <lon> <radius>` - Create geofence
- `asset geofence check <asset_id> <geofence_id>` - Check status
- `asset geofence alerts` - View alerts

### Menu Navigation
- `back` - Go to previous menu
- `main` - Return to top-level menu
- `quit` / `exit` - Exit menu system
- `help` - Show help for current menu

## Log Files

```bash
# View application logs
tail -f logs/zephyrgate.log

# View last 100 lines
tail -n 100 logs/zephyrgate.log

# Search logs
grep "ERROR" logs/zephyrgate.log
```

## Troubleshooting

### Serial Port Permission
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER
# Log out and back in
```

### Check Meshtastic Connection
```bash
# List USB devices
ls -l /dev/tty* | grep -E "(USB|ACM)"

# Check recent connections
dmesg | grep tty
```

### Reset Configuration
```bash
# Backup current config
cp config/config.yaml config/config.yaml.backup

# Run installer again
./install.sh
```

### Check Service Status
```bash
# If installed as service
sudo systemctl status zephyrgate

# View recent logs
sudo journalctl -u zephyrgate -n 50
```

## Plugin Management

### Enable/Disable Plugins

Edit `config/config.yaml`:

```yaml
plugins:
  enabled_plugins:
    - "bot_service"
    - "emergency_service"
    - "web_service"
    # Add or remove plugins here
```

### Available Plugins

- `bot_service` - Interactive bot with commands and games
- `emergency_service` - SOS and emergency response
- `bbs_service` - Bulletin board and mail system
- `weather_service` - Weather forecasts and alerts
- `email_service` - Email gateway
- `asset_service` - Asset tracking
- `web_service` - Web admin interface

## Backup and Restore

### Backup
```bash
# Backup database
cp data/zephyrgate.db data/zephyrgate.db.backup

# Backup configuration
cp config/config.yaml config/config.yaml.backup
```

### Restore
```bash
# Restore database
cp data/zephyrgate.db.backup data/zephyrgate.db

# Restore configuration
cp config/config.yaml.backup config/config.yaml

# Restart
./stop.sh && ./start.sh
```

## Update ZephyrGate

```bash
# Stop ZephyrGate
./stop.sh

# Pull latest changes
git pull

# Update dependencies
source .venv/bin/activate
pip install -r requirements.txt --upgrade

# Start ZephyrGate
./start.sh
```

## Performance Tips

### Raspberry Pi
```bash
# Check temperature
vcgencmd measure_temp

# Check memory
free -h

# Check disk space
df -h
```

### Reduce Log Size
Edit `config/config.yaml`:
```yaml
logging:
  level: "WARNING"  # Less verbose
  max_file_size: 5242880  # 5MB
  backup_count: 3  # Keep fewer backups
```

## Getting Help

- **Documentation**: [docs/](docs/)
- **Installation Guide**: [docs/INSTALLATION.md](docs/INSTALLATION.md)
- **User Manual**: [docs/USER_MANUAL.md](docs/USER_MANUAL.md)
- **Troubleshooting**: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- **GitHub Issues**: Report bugs and request features

## Important Files

| File/Directory | Purpose |
|----------------|---------|
| `config/config.yaml` | Main configuration file |
| `data/` | Database and persistent data |
| `logs/` | Application logs |
| `plugins/` | Plugin directory |
| `.venv/` | Python virtual environment |
| `install.sh` | Installation script |
| `start.sh` | Start script |
| `stop.sh` | Stop script |

## Security Checklist

- [ ] Change default admin password
- [ ] Review enabled plugins
- [ ] Configure firewall rules
- [ ] Set up regular backups
- [ ] Update system packages
- [ ] Review log files regularly
- [ ] Limit web interface access

## Support

Need help? Check these resources:

1. Read the [Installation Guide](docs/INSTALLATION.md)
2. Check [Troubleshooting Guide](docs/TROUBLESHOOTING.md)
3. Review logs: `tail -f logs/zephyrgate.log`
4. Search [GitHub Issues](https://github.com/your-repo/zephyrgate/issues)
5. Ask the community

---

**Quick tip**: Keep this file handy for reference! 📋
