# ZephyrGate Maintenance and Backup Guide

## Table of Contents

1. [Maintenance Overview](#maintenance-overview)
2. [Daily Maintenance Tasks](#daily-maintenance-tasks)
3. [Weekly Maintenance Tasks](#weekly-maintenance-tasks)
4. [Monthly Maintenance Tasks](#monthly-maintenance-tasks)
5. [Backup Procedures](#backup-procedures)
6. [Recovery Procedures](#recovery-procedures)
7. [Database Maintenance](#database-maintenance)
8. [Log Management](#log-management)
9. [Performance Monitoring](#performance-monitoring)
10. [Security Updates](#security-updates)

## Maintenance Overview

### Maintenance Philosophy

ZephyrGate is designed for minimal maintenance overhead while ensuring reliable operation. This guide provides systematic procedures for:

- **Preventive Maintenance**: Regular tasks to prevent issues
- **Monitoring**: Continuous system health assessment
- **Backup and Recovery**: Data protection and disaster recovery
- **Performance Optimization**: Maintaining optimal system performance
- **Security**: Keeping the system secure and up-to-date

### Maintenance Schedule

| Frequency | Tasks | Duration | Downtime |
|-----------|-------|----------|----------|
| Daily | Health checks, log review | 15 minutes | None |
| Weekly | Performance analysis, cleanup | 30 minutes | None |
| Monthly | Updates, deep analysis | 1-2 hours | Minimal |
| Quarterly | Full system review | 2-4 hours | Planned |

## Daily Maintenance Tasks

### Automated Health Checks

#### System Health Monitoring

```bash
#!/bin/bash
# daily-health-check.sh

LOG_FILE="/var/log/zephyrgate/health-check.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$DATE] Starting daily health check" >> $LOG_FILE

# Check service status
if systemctl is-active --quiet zephyrgate; then
    echo "[$DATE] ✓ ZephyrGate service is running" >> $LOG_FILE
else
    echo "[$DATE] ✗ ZephyrGate service is not running" >> $LOG_FILE
    systemctl restart zephyrgate
fi

# Check web interface
if curl -f -s http://localhost:8080/health > /dev/null; then
    echo "[$DATE] ✓ Web interface is responding" >> $LOG_FILE
else
    echo "[$DATE] ✗ Web interface is not responding" >> $LOG_FILE
fi

# Check disk space
DISK_USAGE=$(df /opt/zephyrgate | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -lt 80 ]; then
    echo "[$DATE] ✓ Disk usage: ${DISK_USAGE}%" >> $LOG_FILE
else
    echo "[$DATE] ⚠ High disk usage: ${DISK_USAGE}%" >> $LOG_FILE
fi

# Check memory usage
MEMORY_USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
if [ $MEMORY_USAGE -lt 85 ]; then
    echo "[$DATE] ✓ Memory usage: ${MEMORY_USAGE}%" >> $LOG_FILE
else
    echo "[$DATE] ⚠ High memory usage: ${MEMORY_USAGE}%" >> $LOG_FILE
fi

# Check database integrity
if python3 /opt/zephyrgate/scripts/check-db.py; then
    echo "[$DATE] ✓ Database integrity check passed" >> $LOG_FILE
else
    echo "[$DATE] ✗ Database integrity check failed" >> $LOG_FILE
fi

echo "[$DATE] Daily health check completed" >> $LOG_FILE
```

#### Database Integrity Check

```python
#!/usr/bin/env python3
# check-db.py

import sqlite3
import sys
import os

def check_database_integrity():
    """Check SQLite database integrity"""
    db_path = "/opt/zephyrgate/data/zephyrgate.db"
    
    if not os.path.exists(db_path):
        print("Database file not found")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Run integrity check
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        
        if result[0] == "ok":
            print("Database integrity check passed")
            return True
        else:
            print(f"Database integrity check failed: {result[0]}")
            return False
            
    except Exception as e:
        print(f"Database check error: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    success = check_database_integrity()
    sys.exit(0 if success else 1)
```

### Log Review

#### Error Log Analysis

```bash
#!/bin/bash
# check-errors.sh

LOG_DIR="/opt/zephyrgate/logs"
ERROR_COUNT=$(grep -c "ERROR\|CRITICAL" $LOG_DIR/zephyrgate.log)

if [ $ERROR_COUNT -gt 0 ]; then
    echo "Found $ERROR_COUNT errors in logs:"
    grep "ERROR\|CRITICAL" $LOG_DIR/zephyrgate.log | tail -10
    
    # Send alert if too many errors
    if [ $ERROR_COUNT -gt 10 ]; then
        echo "High error count detected" | mail -s "ZephyrGate Alert" admin@example.com
    fi
fi
```

### Performance Metrics Collection

```bash
#!/bin/bash
# collect-metrics.sh

METRICS_FILE="/var/log/zephyrgate/metrics-$(date +%Y%m%d).log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# System metrics
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//')
MEMORY_USAGE=$(free | awk 'NR==2{printf "%.1f", $3*100/$2}')
DISK_USAGE=$(df /opt/zephyrgate | awk 'NR==2 {print $5}' | sed 's/%//')

# Application metrics
if curl -s http://localhost:8080/metrics > /tmp/app_metrics.txt; then
    MESSAGE_COUNT=$(grep "messages_processed_total" /tmp/app_metrics.txt | awk '{print $2}')
    ACTIVE_USERS=$(grep "active_users" /tmp/app_metrics.txt | awk '{print $2}')
else
    MESSAGE_COUNT="N/A"
    ACTIVE_USERS="N/A"
fi

# Log metrics
echo "$TIMESTAMP,CPU:$CPU_USAGE,Memory:$MEMORY_USAGE,Disk:$DISK_USAGE,Messages:$MESSAGE_COUNT,Users:$ACTIVE_USERS" >> $METRICS_FILE
```

## Weekly Maintenance Tasks

### Performance Analysis

#### Weekly Performance Report

```bash
#!/bin/bash
# weekly-report.sh

REPORT_FILE="/var/log/zephyrgate/weekly-report-$(date +%Y%m%d).txt"
START_DATE=$(date -d '7 days ago' '+%Y-%m-%d')
END_DATE=$(date '+%Y-%m-%d')

cat > $REPORT_FILE << EOF
ZephyrGate Weekly Performance Report
Generated: $(date)
Period: $START_DATE to $END_DATE

=== System Performance ===
EOF

# Analyze metrics from the past week
awk -F',' -v start="$START_DATE" -v end="$END_DATE" '
BEGIN {
    cpu_sum=0; mem_sum=0; disk_sum=0; msg_sum=0; count=0
}
$1 >= start && $1 <= end {
    gsub(/CPU:/, "", $2); cpu_sum += $2
    gsub(/Memory:/, "", $3); mem_sum += $3
    gsub(/Disk:/, "", $4); disk_sum += $4
    gsub(/Messages:/, "", $5); if($5 != "N/A") msg_sum += $5
    count++
}
END {
    if(count > 0) {
        printf "Average CPU Usage: %.1f%%\n", cpu_sum/count
        printf "Average Memory Usage: %.1f%%\n", mem_sum/count
        printf "Average Disk Usage: %.1f%%\n", disk_sum/count
        printf "Total Messages Processed: %d\n", msg_sum
        printf "Samples Collected: %d\n", count
    }
}' /var/log/zephyrgate/metrics-*.log >> $REPORT_FILE

# Check for errors
echo "" >> $REPORT_FILE
echo "=== Error Summary ===" >> $REPORT_FILE
ERROR_COUNT=$(grep -c "ERROR\|CRITICAL" /opt/zephyrgate/logs/zephyrgate.log)
echo "Total Errors This Week: $ERROR_COUNT" >> $REPORT_FILE

if [ $ERROR_COUNT -gt 0 ]; then
    echo "Recent Errors:" >> $REPORT_FILE
    grep "ERROR\|CRITICAL" /opt/zephyrgate/logs/zephyrgate.log | tail -5 >> $REPORT_FILE
fi

# Service uptime
echo "" >> $REPORT_FILE
echo "=== Service Uptime ===" >> $REPORT_FILE
systemctl show zephyrgate --property=ActiveEnterTimestamp >> $REPORT_FILE
```

### Log Rotation and Cleanup

```bash
#!/bin/bash
# log-cleanup.sh

LOG_DIR="/opt/zephyrgate/logs"
RETENTION_DAYS=30

# Rotate large log files
find $LOG_DIR -name "*.log" -size +100M -exec logrotate -f {} \;

# Compress old logs
find $LOG_DIR -name "*.log.*" -mtime +1 -exec gzip {} \;

# Remove old compressed logs
find $LOG_DIR -name "*.log.*.gz" -mtime +$RETENTION_DAYS -delete

# Clean up old metrics files
find /var/log/zephyrgate -name "metrics-*.log" -mtime +$RETENTION_DAYS -delete

# Clean up old reports
find /var/log/zephyrgate -name "*-report-*.txt" -mtime +90 -delete

echo "Log cleanup completed: $(date)"
```

### Database Optimization

```bash
#!/bin/bash
# optimize-database.sh

DB_PATH="/opt/zephyrgate/data/zephyrgate.db"
BACKUP_PATH="/opt/zephyrgate/data/backup/zephyrgate-$(date +%Y%m%d).db"

# Create backup before optimization
mkdir -p /opt/zephyrgate/data/backup
cp $DB_PATH $BACKUP_PATH

# Run database optimization
sqlite3 $DB_PATH << EOF
-- Analyze database statistics
ANALYZE;

-- Rebuild indexes
REINDEX;

-- Vacuum database to reclaim space
VACUUM;

-- Update statistics
ANALYZE;
EOF

echo "Database optimization completed: $(date)"
```

## Monthly Maintenance Tasks

### System Updates

#### Security Updates

```bash
#!/bin/bash
# security-updates.sh

# Update package lists
apt update

# List available security updates
apt list --upgradable | grep -i security

# Apply security updates (with confirmation)
apt upgrade -s | grep -i security
read -p "Apply security updates? (y/N): " confirm

if [[ $confirm == [yY] ]]; then
    apt upgrade
    
    # Check if reboot is required
    if [ -f /var/run/reboot-required ]; then
        echo "System reboot required after updates"
        echo "Schedule maintenance window for reboot"
    fi
fi
```

#### Application Updates

```bash
#!/bin/bash
# update-zephyrgate.sh

cd /opt/zephyrgate

# Backup current version
tar -czf backup/zephyrgate-backup-$(date +%Y%m%d).tar.gz \
    --exclude=data --exclude=logs --exclude=backup .

# Check for updates
git fetch origin
UPDATES=$(git log HEAD..origin/main --oneline)

if [ -n "$UPDATES" ]; then
    echo "Updates available:"
    echo "$UPDATES"
    
    read -p "Apply updates? (y/N): " confirm
    if [[ $confirm == [yY] ]]; then
        # Stop service
        systemctl stop zephyrgate
        
        # Apply updates
        git pull origin main
        
        # Update dependencies
        source venv/bin/activate
        pip install -r requirements.txt
        
        # Run migrations
        python src/main.py --migrate
        
        # Start service
        systemctl start zephyrgate
        
        # Verify service
        sleep 10
        if systemctl is-active --quiet zephyrgate; then
            echo "Update completed successfully"
        else
            echo "Update failed - check logs"
        fi
    fi
else
    echo "No updates available"
fi
```

### Comprehensive System Analysis

```bash
#!/bin/bash
# monthly-analysis.sh

REPORT_FILE="/var/log/zephyrgate/monthly-analysis-$(date +%Y%m).txt"

cat > $REPORT_FILE << EOF
ZephyrGate Monthly System Analysis
Generated: $(date)

=== System Information ===
Hostname: $(hostname)
OS: $(lsb_release -d | cut -f2)
Kernel: $(uname -r)
Uptime: $(uptime -p)

=== Disk Usage Analysis ===
EOF

df -h >> $REPORT_FILE

echo "" >> $REPORT_FILE
echo "=== Memory Usage Analysis ===" >> $REPORT_FILE
free -h >> $REPORT_FILE

echo "" >> $REPORT_FILE
echo "=== Service Status ===" >> $REPORT_FILE
systemctl status zephyrgate --no-pager >> $REPORT_FILE

echo "" >> $REPORT_FILE
echo "=== Database Statistics ===" >> $REPORT_FILE
sqlite3 /opt/zephyrgate/data/zephyrgate.db << EOF >> $REPORT_FILE
.headers on
.mode column
SELECT 
    name as table_name,
    (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=m.name) as record_count
FROM sqlite_master m WHERE type='table';
EOF

echo "" >> $REPORT_FILE
echo "=== Network Connectivity ===" >> $REPORT_FILE
ping -c 4 8.8.8.8 >> $REPORT_FILE 2>&1

echo "" >> $REPORT_FILE
echo "=== Security Status ===" >> $REPORT_FILE
last -n 10 >> $REPORT_FILE
```

## Backup Procedures

### Automated Backup System

#### Full System Backup

```bash
#!/bin/bash
# full-backup.sh

BACKUP_ROOT="/backup/zephyrgate"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/$DATE"
RETENTION_DAYS=30

# Create backup directory
mkdir -p $BACKUP_DIR

echo "Starting full backup: $(date)"

# Database backup
echo "Backing up database..."
sqlite3 /opt/zephyrgate/data/zephyrgate.db ".backup '$BACKUP_DIR/database.sqlite'"

# Configuration backup
echo "Backing up configuration..."
tar -czf $BACKUP_DIR/config.tar.gz -C /opt/zephyrgate config/

# Application data backup
echo "Backing up application data..."
tar -czf $BACKUP_DIR/data.tar.gz -C /opt/zephyrgate data/ --exclude=data/zephyrgate.db

# Logs backup (last 7 days)
echo "Backing up recent logs..."
find /opt/zephyrgate/logs -name "*.log*" -mtime -7 -exec tar -czf $BACKUP_DIR/logs.tar.gz {} +

# System configuration backup
echo "Backing up system configuration..."
tar -czf $BACKUP_DIR/system.tar.gz \
    /etc/systemd/system/zephyrgate.service \
    /etc/nginx/sites-available/zephyrgate \
    /etc/cron.d/zephyrgate 2>/dev/null

# Create backup manifest
cat > $BACKUP_DIR/manifest.txt << EOF
ZephyrGate Backup Manifest
Created: $(date)
Backup ID: $DATE
Components:
- database.sqlite (SQLite database)
- config.tar.gz (Application configuration)
- data.tar.gz (Application data files)
- logs.tar.gz (Recent log files)
- system.tar.gz (System configuration)

Backup Size: $(du -sh $BACKUP_DIR | cut -f1)
EOF

# Compress entire backup
cd $BACKUP_ROOT
tar -czf "zephyrgate-full-$DATE.tar.gz" $DATE/
rm -rf $DATE/

# Upload to cloud storage (if configured)
if [ -n "$AWS_S3_BUCKET" ]; then
    aws s3 cp "zephyrgate-full-$DATE.tar.gz" "s3://$AWS_S3_BUCKET/backups/"
fi

# Cleanup old backups
find $BACKUP_ROOT -name "zephyrgate-full-*.tar.gz" -mtime +$RETENTION_DAYS -delete

echo "Full backup completed: $(date)"
echo "Backup file: zephyrgate-full-$DATE.tar.gz"
```

#### Incremental Backup

```bash
#!/bin/bash
# incremental-backup.sh

BACKUP_ROOT="/backup/zephyrgate/incremental"
DATE=$(date +%Y%m%d_%H%M%S)
LAST_BACKUP_FILE="$BACKUP_ROOT/.last_backup"

# Create backup directory
mkdir -p $BACKUP_ROOT

# Find files changed since last backup
if [ -f $LAST_BACKUP_FILE ]; then
    LAST_BACKUP=$(cat $LAST_BACKUP_FILE)
    echo "Creating incremental backup since: $LAST_BACKUP"
    
    # Find changed files
    find /opt/zephyrgate -newer $LAST_BACKUP_FILE -type f > /tmp/changed_files.txt
    
    if [ -s /tmp/changed_files.txt ]; then
        # Create incremental backup
        tar -czf "$BACKUP_ROOT/incremental-$DATE.tar.gz" -T /tmp/changed_files.txt
        echo "Incremental backup created: incremental-$DATE.tar.gz"
    else
        echo "No files changed since last backup"
    fi
else
    echo "No previous backup found, creating full backup"
    /opt/zephyrgate/scripts/full-backup.sh
fi

# Update last backup timestamp
echo $DATE > $LAST_BACKUP_FILE
```

### Database-Specific Backup

```bash
#!/bin/bash
# backup-database.sh

DB_PATH="/opt/zephyrgate/data/zephyrgate.db"
BACKUP_DIR="/backup/zephyrgate/database"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

# SQLite backup with consistency check
sqlite3 $DB_PATH << EOF
.backup '$BACKUP_DIR/zephyrgate-$DATE.sqlite'
EOF

# Verify backup integrity
if sqlite3 "$BACKUP_DIR/zephyrgate-$DATE.sqlite" "PRAGMA integrity_check;" | grep -q "ok"; then
    echo "Database backup verified: zephyrgate-$DATE.sqlite"
    
    # Compress backup
    gzip "$BACKUP_DIR/zephyrgate-$DATE.sqlite"
    
    # Create SQL dump for portability
    sqlite3 $DB_PATH .dump | gzip > "$BACKUP_DIR/zephyrgate-$DATE.sql.gz"
    
else
    echo "Database backup verification failed"
    rm -f "$BACKUP_DIR/zephyrgate-$DATE.sqlite"
    exit 1
fi

# Cleanup old database backups (keep 14 days)
find $BACKUP_DIR -name "zephyrgate-*.sqlite.gz" -mtime +14 -delete
find $BACKUP_DIR -name "zephyrgate-*.sql.gz" -mtime +14 -delete
```

## Recovery Procedures

### Complete System Recovery

```bash
#!/bin/bash
# restore-system.sh

BACKUP_FILE="$1"
RESTORE_DIR="/opt/zephyrgate"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup-file>"
    echo "Available backups:"
    ls -la /backup/zephyrgate/zephyrgate-full-*.tar.gz
    exit 1
fi

echo "Starting system recovery from: $BACKUP_FILE"
read -p "This will overwrite current installation. Continue? (y/N): " confirm

if [[ $confirm != [yY] ]]; then
    echo "Recovery cancelled"
    exit 0
fi

# Stop services
systemctl stop zephyrgate

# Backup current state
if [ -d $RESTORE_DIR ]; then
    mv $RESTORE_DIR "$RESTORE_DIR.backup.$(date +%Y%m%d_%H%M%S)"
fi

# Extract backup
mkdir -p $RESTORE_DIR
cd /tmp
tar -xzf $BACKUP_FILE

# Find backup directory
BACKUP_DIR=$(tar -tzf $BACKUP_FILE | head -1 | cut -f1 -d'/')

# Restore database
if [ -f "$BACKUP_DIR/database.sqlite" ]; then
    mkdir -p $RESTORE_DIR/data
    cp "$BACKUP_DIR/database.sqlite" "$RESTORE_DIR/data/zephyrgate.db"
    echo "Database restored"
fi

# Restore configuration
if [ -f "$BACKUP_DIR/config.tar.gz" ]; then
    tar -xzf "$BACKUP_DIR/config.tar.gz" -C $RESTORE_DIR/
    echo "Configuration restored"
fi

# Restore data files
if [ -f "$BACKUP_DIR/data.tar.gz" ]; then
    tar -xzf "$BACKUP_DIR/data.tar.gz" -C $RESTORE_DIR/
    echo "Data files restored"
fi

# Restore system configuration
if [ -f "$BACKUP_DIR/system.tar.gz" ]; then
    tar -xzf "$BACKUP_DIR/system.tar.gz" -C /
    echo "System configuration restored"
fi

# Set permissions
chown -R zephyrgate:zephyrgate $RESTORE_DIR
chmod -R 755 $RESTORE_DIR
chmod 600 $RESTORE_DIR/config/*.yaml

# Start services
systemctl daemon-reload
systemctl start zephyrgate

# Verify recovery
sleep 10
if systemctl is-active --quiet zephyrgate; then
    echo "System recovery completed successfully"
    curl -f http://localhost:8080/health && echo "Web interface is responding"
else
    echo "System recovery failed - check logs"
    systemctl status zephyrgate
fi

# Cleanup
rm -rf /tmp/$BACKUP_DIR
```

### Database Recovery

```bash
#!/bin/bash
# restore-database.sh

BACKUP_FILE="$1"
DB_PATH="/opt/zephyrgate/data/zephyrgate.db"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <database-backup-file>"
    echo "Available database backups:"
    ls -la /backup/zephyrgate/database/
    exit 1
fi

echo "Restoring database from: $BACKUP_FILE"

# Stop service
systemctl stop zephyrgate

# Backup current database
if [ -f $DB_PATH ]; then
    cp $DB_PATH "$DB_PATH.backup.$(date +%Y%m%d_%H%M%S)"
    echo "Current database backed up"
fi

# Restore database
if [[ $BACKUP_FILE == *.gz ]]; then
    if [[ $BACKUP_FILE == *.sql.gz ]]; then
        # SQL dump restore
        zcat $BACKUP_FILE | sqlite3 $DB_PATH
    else
        # SQLite file restore
        zcat $BACKUP_FILE > $DB_PATH
    fi
else
    # Direct SQLite file
    cp $BACKUP_FILE $DB_PATH
fi

# Verify database integrity
if sqlite3 $DB_PATH "PRAGMA integrity_check;" | grep -q "ok"; then
    echo "Database integrity verified"
    
    # Set permissions
    chown zephyrgate:zephyrgate $DB_PATH
    chmod 644 $DB_PATH
    
    # Start service
    systemctl start zephyrgate
    
    # Verify service
    sleep 5
    if systemctl is-active --quiet zephyrgate; then
        echo "Database recovery completed successfully"
    else
        echo "Service failed to start after database recovery"
    fi
else
    echo "Database integrity check failed"
    exit 1
fi
```

## Database Maintenance

### Regular Database Tasks

```sql
-- database-maintenance.sql

-- Update table statistics
ANALYZE;

-- Rebuild all indexes
REINDEX;

-- Vacuum database to reclaim space
VACUUM;

-- Check foreign key constraints
PRAGMA foreign_key_check;

-- Update statistics again after vacuum
ANALYZE;
```

### Database Health Check

```python
#!/usr/bin/env python3
# database-health.py

import sqlite3
import os
import sys
from datetime import datetime, timedelta

def check_database_health():
    """Comprehensive database health check"""
    db_path = "/opt/zephyrgate/data/zephyrgate.db"
    
    if not os.path.exists(db_path):
        print("❌ Database file not found")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check integrity
        cursor.execute("PRAGMA integrity_check")
        integrity = cursor.fetchone()[0]
        if integrity == "ok":
            print("✅ Database integrity: OK")
        else:
            print(f"❌ Database integrity: {integrity}")
            return False
        
        # Check foreign keys
        cursor.execute("PRAGMA foreign_key_check")
        fk_violations = cursor.fetchall()
        if not fk_violations:
            print("✅ Foreign key constraints: OK")
        else:
            print(f"❌ Foreign key violations: {len(fk_violations)}")
        
        # Check database size
        cursor.execute("PRAGMA page_count")
        page_count = cursor.fetchone()[0]
        cursor.execute("PRAGMA page_size")
        page_size = cursor.fetchone()[0]
        db_size = (page_count * page_size) / (1024 * 1024)  # MB
        print(f"📊 Database size: {db_size:.2f} MB")
        
        # Check table statistics
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("\n📋 Table Statistics:")
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  {table_name}: {count} records")
        
        # Check recent activity
        cursor.execute("""
            SELECT COUNT(*) FROM users 
            WHERE last_seen > datetime('now', '-7 days')
        """)
        active_users = cursor.fetchone()[0]
        print(f"\n👥 Active users (last 7 days): {active_users}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database check error: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("ZephyrGate Database Health Check")
    print("=" * 40)
    success = check_database_health()
    sys.exit(0 if success else 1)
```

## Log Management

### Log Rotation Configuration

```bash
# /etc/logrotate.d/zephyrgate
/opt/zephyrgate/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 zephyrgate zephyrgate
    postrotate
        systemctl reload zephyrgate
    endscript
}
```

### Log Analysis Scripts

```bash
#!/bin/bash
# analyze-logs.sh

LOG_FILE="/opt/zephyrgate/logs/zephyrgate.log"
REPORT_FILE="/tmp/log-analysis-$(date +%Y%m%d).txt"

cat > $REPORT_FILE << EOF
ZephyrGate Log Analysis Report
Generated: $(date)

=== Error Summary ===
EOF

# Count errors by type
echo "Error counts by level:" >> $REPORT_FILE
grep -E "(ERROR|CRITICAL|WARNING)" $LOG_FILE | \
    awk '{print $3}' | sort | uniq -c | sort -nr >> $REPORT_FILE

echo "" >> $REPORT_FILE
echo "=== Recent Errors ===" >> $REPORT_FILE
grep -E "(ERROR|CRITICAL)" $LOG_FILE | tail -10 >> $REPORT_FILE

echo "" >> $REPORT_FILE
echo "=== Message Statistics ===" >> $REPORT_FILE
grep "message_received" $LOG_FILE | wc -l | \
    awk '{print "Messages received: " $1}' >> $REPORT_FILE

grep "message_sent" $LOG_FILE | wc -l | \
    awk '{print "Messages sent: " $1}' >> $REPORT_FILE

echo "" >> $REPORT_FILE
echo "=== Service Restarts ===" >> $REPORT_FILE
grep "Starting ZephyrGate" $LOG_FILE | \
    awk '{print $1 " " $2}' >> $REPORT_FILE

cat $REPORT_FILE
```

## Performance Monitoring

### System Resource Monitoring

```bash
#!/bin/bash
# monitor-resources.sh

THRESHOLD_CPU=80
THRESHOLD_MEMORY=85
THRESHOLD_DISK=90

# Check CPU usage
CPU_USAGE=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | sed 's/%us,//' | cut -d'%' -f1)
if (( $(echo "$CPU_USAGE > $THRESHOLD_CPU" | bc -l) )); then
    echo "⚠️  High CPU usage: ${CPU_USAGE}%"
fi

# Check memory usage
MEMORY_USAGE=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')
if [ $MEMORY_USAGE -gt $THRESHOLD_MEMORY ]; then
    echo "⚠️  High memory usage: ${MEMORY_USAGE}%"
fi

# Check disk usage
DISK_USAGE=$(df /opt/zephyrgate | awk 'NR==2 {print $5}' | sed 's/%//')
if [ $DISK_USAGE -gt $THRESHOLD_DISK ]; then
    echo "⚠️  High disk usage: ${DISK_USAGE}%"
fi

# Check service status
if ! systemctl is-active --quiet zephyrgate; then
    echo "❌ ZephyrGate service is not running"
fi

# Check network connectivity
if ! ping -c 1 8.8.8.8 > /dev/null 2>&1; then
    echo "⚠️  Network connectivity issue"
fi
```

### Application Performance Monitoring

```python
#!/usr/bin/env python3
# performance-monitor.py

import requests
import json
import time
from datetime import datetime

def check_application_performance():
    """Monitor application performance metrics"""
    
    try:
        # Check response time
        start_time = time.time()
        response = requests.get('http://localhost:8080/health', timeout=10)
        response_time = (time.time() - start_time) * 1000  # ms
        
        if response.status_code == 200:
            print(f"✅ Health check: OK ({response_time:.2f}ms)")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
        
        # Get metrics
        metrics_response = requests.get('http://localhost:8080/metrics', timeout=10)
        if metrics_response.status_code == 200:
            metrics = metrics_response.text
            
            # Parse key metrics
            for line in metrics.split('\n'):
                if 'messages_processed_total' in line:
                    value = line.split()[-1]
                    print(f"📊 Messages processed: {value}")
                elif 'active_users' in line:
                    value = line.split()[-1]
                    print(f"👥 Active users: {value}")
                elif 'response_time_seconds' in line:
                    value = float(line.split()[-1]) * 1000
                    print(f"⏱️  Average response time: {value:.2f}ms")
        
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Application not responding: {e}")
        return False
    except Exception as e:
        print(f"❌ Performance check error: {e}")
        return False

if __name__ == "__main__":
    print("ZephyrGate Performance Monitor")
    print("=" * 40)
    check_application_performance()
```

## Security Updates

### Security Patch Management

```bash
#!/bin/bash
# security-patches.sh

# Check for security updates
echo "Checking for security updates..."
apt list --upgradable 2>/dev/null | grep -i security

# Check for CVE notifications
if command -v lynis &> /dev/null; then
    echo "Running security audit..."
    lynis audit system --quick
fi

# Check file permissions
echo "Checking file permissions..."
find /opt/zephyrgate -type f -perm /o+w -exec ls -la {} \;

# Check for suspicious processes
echo "Checking processes..."
ps aux | grep -v grep | grep -E "(zephyrgate|python)"

# Check network connections
echo "Checking network connections..."
netstat -tlnp | grep :8080
```

### Automated Security Monitoring

```bash
#!/bin/bash
# security-monitor.sh

SECURITY_LOG="/var/log/zephyrgate/security.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

# Check for failed login attempts
FAILED_LOGINS=$(grep "authentication failed" /opt/zephyrgate/logs/zephyrgate.log | wc -l)
if [ $FAILED_LOGINS -gt 10 ]; then
    echo "[$DATE] WARNING: $FAILED_LOGINS failed login attempts detected" >> $SECURITY_LOG
fi

# Check for suspicious file changes
find /opt/zephyrgate/config -name "*.yaml" -mtime -1 -exec ls -la {} \; | \
    while read line; do
        echo "[$DATE] Config file modified: $line" >> $SECURITY_LOG
    done

# Check for unusual network activity
CONNECTIONS=$(netstat -tn | grep :8080 | wc -l)
if [ $CONNECTIONS -gt 50 ]; then
    echo "[$DATE] WARNING: High number of connections: $CONNECTIONS" >> $SECURITY_LOG
fi
```

This maintenance guide provides comprehensive procedures for keeping ZephyrGate running optimally. Regular execution of these maintenance tasks will ensure system reliability, performance, and security.