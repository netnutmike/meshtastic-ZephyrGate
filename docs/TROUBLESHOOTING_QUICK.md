# Quick Troubleshooting Guide

## Installation Issues

### "Permission denied" when running install.sh
```bash
chmod +x install.sh
./install.sh
```

### "Python 3.8+ required"
```bash
# Ubuntu/Debian
sudo apt-get install python3.9

# Or use deadsnakes PPA
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt-get update
sudo apt-get install python3.11
```

### "pip not found"
```bash
sudo apt-get install python3-pip
```

### "venv not found"
```bash
sudo apt-get install python3-venv
```

## Connection Issues

### "Permission denied" on serial port
```bash
# Add user to dialout group
sudo usermod -a -G dialout $USER

# Log out and back in, then verify
groups | grep dialout
```

### Can't find serial port
```bash
# List USB devices
ls -l /dev/tty* | grep -E "(USB|ACM)"

# Check recent connections
dmesg | tail -20 | grep tty

# Common ports:
# /dev/ttyUSB0 - USB serial
# /dev/ttyACM0 - USB CDC
# /dev/ttyAMA0 - Pi GPIO serial
```

### Meshtastic device not responding
1. Check USB cable (try different cable)
2. Check device is powered on
3. Try different USB port
4. Restart device
5. Check device with Meshtastic app first

## Runtime Issues

### ZephyrGate won't start
```bash
# Check logs
tail -f logs/zephyrgate.log

# Check config
nano config/config.yaml

# Verify virtual environment
source .venv/bin/activate
python --version
```

### "Port 8080 already in use"
```bash
# Find what's using the port
sudo lsof -i :8080

# Or change port in config
nano config/config.yaml
# Change web.port to 8081
```

### Web interface not accessible
```bash
# Check if service is running
sudo systemctl status zephyrgate

# Check firewall
sudo ufw status
sudo ufw allow 8080

# Try localhost first
curl http://localhost:8080
```

### High CPU usage
```bash
# Check what's running
top
# Press 'P' to sort by CPU

# Reduce logging
nano config/config.yaml
# Set log_level: "WARNING"

# Disable unused plugins
nano config/config.yaml
# Remove plugins from enabled_plugins
```

### High memory usage
```bash
# Check memory
free -h

# Restart service
sudo systemctl restart zephyrgate

# Reduce cache sizes in config
nano config/config.yaml
```

## Plugin Issues

### Plugin won't load
```bash
# Check plugin is enabled
nano config/config.yaml
# Verify plugin in enabled_plugins list

# Check plugin exists
ls -la plugins/

# Check logs for errors
grep "plugin_name" logs/zephyrgate.log
```

### Plugin crashes
```bash
# Check plugin logs
grep "ERROR.*plugin_name" logs/zephyrgate.log

# Disable problematic plugin
nano config/config.yaml
# Move plugin to disabled_plugins

# Restart
./stop.sh && ./start.sh
```

## Database Issues

### "Database locked"
```bash
# Stop ZephyrGate
./stop.sh

# Check for other processes
ps aux | grep zephyrgate

# Remove lock file if safe
rm data/zephyrgate.db-wal
rm data/zephyrgate.db-shm

# Restart
./start.sh
```

### Corrupted database
```bash
# Stop ZephyrGate
./stop.sh

# Backup current database
cp data/zephyrgate.db data/zephyrgate.db.corrupt

# Try to repair
sqlite3 data/zephyrgate.db "PRAGMA integrity_check;"

# If repair fails, restore from backup
cp data/zephyrgate.db.backup data/zephyrgate.db

# Restart
./start.sh
```

## Service Issues

### Service won't start
```bash
# Check service status
sudo systemctl status zephyrgate

# Check service logs
sudo journalctl -u zephyrgate -n 50

# Verify service file
cat /etc/systemd/system/zephyrgate.service

# Reload systemd
sudo systemctl daemon-reload
sudo systemctl restart zephyrgate
```

### Service starts but stops immediately
```bash
# Check logs
sudo journalctl -u zephyrgate -n 100

# Check permissions
ls -la /path/to/zephyrgate

# Verify paths in service file
sudo nano /etc/systemd/system/zephyrgate.service
```

## Update Issues

### Update fails
```bash
# Check git status
git status

# Stash local changes
git stash

# Pull updates
git pull

# Restore local changes
git stash pop

# Update dependencies
source .venv/bin/activate
pip install -r requirements.txt --upgrade
```

### Config conflicts after update
```bash
# Backup current config
cp config/config.yaml config/config.yaml.backup

# Check template for new options
diff config/config.yaml config/config.template.yaml

# Merge manually or regenerate
./install.sh
```

## Performance Issues

### Slow response times
```bash
# Check system resources
top
free -h
df -h

# Check message queue
grep "queue" logs/zephyrgate.log

# Reduce plugin count
nano config/config.yaml
```

### Messages not sending
```bash
# Check Meshtastic connection
grep "meshtastic" logs/zephyrgate.log

# Check message router
grep "router" logs/zephyrgate.log

# Test with simple ping
# Send "ping" from another device
```

## Log Analysis

### Find errors
```bash
grep "ERROR" logs/zephyrgate.log
```

### Find warnings
```bash
grep "WARNING" logs/zephyrgate.log
```

### Watch logs in real-time
```bash
tail -f logs/zephyrgate.log
```

### Search for specific plugin
```bash
grep "plugin_name" logs/zephyrgate.log
```

### Last 100 lines
```bash
tail -n 100 logs/zephyrgate.log
```

## Emergency Recovery

### Complete reset (keeps data)
```bash
# Stop ZephyrGate
./stop.sh

# Backup data
cp -r data data.backup
cp config/config.yaml config/config.yaml.backup

# Reinstall
./install.sh

# Restore data if needed
cp -r data.backup/* data/
```

### Factory reset (loses data)
```bash
# Stop ZephyrGate
./stop.sh

# Remove everything except source
rm -rf data logs .venv config/config.yaml

# Reinstall
./install.sh
```

## Getting More Help

### Check Documentation
- [Installation Guide](docs/INSTALLATION.md)
- [User Manual](docs/USER_MANUAL.md)
- [Admin Guide](docs/ADMIN_GUIDE.md)
- [Full Troubleshooting Guide](docs/TROUBLESHOOTING.md)

### Collect Debug Information
```bash
# System info
uname -a
python3 --version
pip3 --version

# ZephyrGate info
cat config/config.yaml
tail -n 100 logs/zephyrgate.log

# Service info (if applicable)
sudo systemctl status zephyrgate
sudo journalctl -u zephyrgate -n 50
```

### Report Issues
1. Check existing issues on GitHub
2. Collect debug information above
3. Create new issue with:
   - System information
   - Steps to reproduce
   - Error messages
   - Log excerpts

## Quick Commands Reference

```bash
# Start/Stop
./start.sh
./stop.sh

# Service control
sudo systemctl start zephyrgate
sudo systemctl stop zephyrgate
sudo systemctl restart zephyrgate
sudo systemctl status zephyrgate

# Logs
tail -f logs/zephyrgate.log
sudo journalctl -u zephyrgate -f

# Configuration
nano config/config.yaml

# Update
git pull
source .venv/bin/activate
pip install -r requirements.txt --upgrade
```

---

**Still stuck?** Check the [full troubleshooting guide](docs/TROUBLESHOOTING.md) or ask for help on GitHub Issues.
