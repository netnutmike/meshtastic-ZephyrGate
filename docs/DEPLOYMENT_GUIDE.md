# ZephyrGate Deployment Guide

## Table of Contents

1. [Deployment Overview](#deployment-overview)
2. [Docker Deployment](#docker-deployment)
3. [Manual Installation](#manual-installation)
4. [Production Deployment](#production-deployment)
5. [Cloud Deployment](#cloud-deployment)
6. [High Availability Setup](#high-availability-setup)
7. [Security Hardening](#security-hardening)
8. [Monitoring Setup](#monitoring-setup)
9. [Backup Configuration](#backup-configuration)
10. [Troubleshooting Deployment](#troubleshooting-deployment)

## Deployment Overview

### System Requirements

#### Minimum Requirements
- **CPU**: 2 cores, 1.5 GHz
- **RAM**: 2 GB
- **Storage**: 10 GB available space
- **Network**: 100 Mbps connection
- **OS**: Linux (Ubuntu 20.04+, CentOS 8+, Debian 11+)

#### Recommended Requirements
- **CPU**: 4 cores, 2.5 GHz
- **RAM**: 4 GB
- **Storage**: 50 GB SSD
- **Network**: 1 Gbps connection
- **OS**: Ubuntu 22.04 LTS or CentOS Stream 9

#### Hardware Compatibility
- **Meshtastic Devices**: All supported Meshtastic hardware
- **Serial Interfaces**: USB-to-serial adapters, built-in serial ports
- **Network Interfaces**: Ethernet, Wi-Fi
- **Storage**: Local disk, NFS, cloud storage

### Architecture Options

#### Single Node Deployment
- All services on one server
- Suitable for small networks (< 50 users)
- Easy to deploy and maintain
- Limited scalability

#### Multi-Service Deployment
- Services distributed across multiple containers/servers
- Better resource utilization
- Improved fault tolerance
- Suitable for medium networks (50-200 users)

#### High Availability Deployment
- Redundant services and data
- Load balancing and failover
- Suitable for large networks (200+ users)
- Maximum uptime requirements

## Docker Deployment

### Quick Start Deployment

#### 1. Prerequisites Installation

**Ubuntu/Debian:**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt install docker-compose-plugin

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

**CentOS/RHEL:**
```bash
# Install Docker
sudo yum install -y yum-utils
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo yum install docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Start Docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER
```

#### 2. Download and Configure

```bash
# Create application directory
mkdir -p /opt/zephyrgate
cd /opt/zephyrgate

# Download docker-compose.yml
wget https://raw.githubusercontent.com/your-repo/zephyrgate/main/docker-compose.yml

# Create environment file
cat > .env << EOF
# Application Configuration
ZEPHYR_APP_ENVIRONMENT=production
ZEPHYR_APP_LOG_LEVEL=INFO
ZEPHYR_APP_DEBUG=false

# Database Configuration
ZEPHYR_DATABASE_URL=sqlite:///data/zephyrgate.db

# Meshtastic Configuration
ZEPHYR_MESHTASTIC_INTERFACES_PRIMARY_TYPE=serial
ZEPHYR_MESHTASTIC_INTERFACES_PRIMARY_DEVICE=/dev/ttyUSB0

# Web Server Configuration
ZEPHYR_SERVER_HOST=0.0.0.0
ZEPHYR_SERVER_PORT=8080

# Security Configuration
ZEPHYR_SECURITY_SECRET_KEY=$(openssl rand -hex 32)
EOF
```

#### 3. Start Services

```bash
# Create required directories
mkdir -p data logs config

# Set permissions
sudo chown -R 1000:1000 data logs config

# Start services
docker compose up -d

# Check status
docker compose ps
docker compose logs -f
```

### Production Docker Configuration

#### docker-compose.prod.yml

```yaml
version: '3.8'

services:
  zephyrgate:
    image: zephyrgate:latest
    container_name: zephyrgate
    restart: unless-stopped
    
    environment:
      - ZEPHYR_APP_ENVIRONMENT=production
      - ZEPHYR_APP_LOG_LEVEL=INFO
      - ZEPHYR_DATABASE_URL=sqlite:///data/zephyrgate.db
      
    volumes:
      - ./data:/app/data:rw
      - ./config:/app/config:ro
      - ./logs:/app/logs:rw
      - /dev/ttyUSB0:/dev/ttyUSB0
      
    ports:
      - "127.0.0.1:8080:8080"
      
    devices:
      - "/dev/ttyUSB0:/dev/ttyUSB0"
      
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
      
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
        
    security_opt:
      - no-new-privileges:true
      
    cap_drop:
      - ALL
    cap_add:
      - CHOWN
      - SETGID
      - SETUID
      
  nginx:
    image: nginx:alpine
    container_name: zephyrgate-nginx
    restart: unless-stopped
    
    ports:
      - "80:80"
      - "443:443"
      
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
      
    depends_on:
      - zephyrgate
      
  redis:
    image: redis:alpine
    container_name: zephyrgate-redis
    restart: unless-stopped
    
    command: redis-server --appendonly yes --maxmemory 256mb --maxmemory-policy allkeys-lru
    
    volumes:
      - redis_data:/data
      
volumes:
  redis_data:
```

#### Nginx Configuration

```nginx
# nginx.conf
events {
    worker_connections 1024;
}

http {
    upstream zephyrgate {
        server zephyrgate:8080;
    }
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    
    server {
        listen 80;
        server_name your-domain.com;
        
        # Redirect HTTP to HTTPS
        return 301 https://$server_name$request_uri;
    }
    
    server {
        listen 443 ssl http2;
        server_name your-domain.com;
        
        # SSL Configuration
        ssl_certificate /etc/nginx/ssl/cert.pem;
        ssl_certificate_key /etc/nginx/ssl/key.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
        ssl_prefer_server_ciphers off;
        
        # Security Headers
        add_header X-Frame-Options DENY;
        add_header X-Content-Type-Options nosniff;
        add_header X-XSS-Protection "1; mode=block";
        add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload";
        
        # Proxy Configuration
        location / {
            proxy_pass http://zephyrgate;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # WebSocket support
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
        
        # API rate limiting
        location /api/ {
            limit_req zone=api burst=20 nodelay;
            proxy_pass http://zephyrgate;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        # Static files
        location /static/ {
            expires 1y;
            add_header Cache-Control "public, immutable";
            proxy_pass http://zephyrgate;
        }
    }
}
```

## Manual Installation

### System Preparation

#### 1. Create Application User

```bash
# Create dedicated user
sudo useradd -r -m -s /bin/bash zephyrgate
sudo mkdir -p /opt/zephyrgate
sudo chown zephyrgate:zephyrgate /opt/zephyrgate
```

#### 2. Install Dependencies

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv python3-dev \
    build-essential sqlite3 git curl wget \
    libffi-dev libssl-dev libudev-dev
```

**CentOS/RHEL:**
```bash
sudo yum groupinstall -y "Development Tools"
sudo yum install -y python3 python3-pip python3-devel \
    sqlite git curl wget openssl-devel libffi-devel systemd-devel
```

#### 3. Install Application

```bash
# Switch to application user
sudo -u zephyrgate -i

# Clone repository
cd /opt/zephyrgate
git clone https://github.com/your-repo/zephyrgate.git .

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Create configuration
cp config/config.template.yaml config/config.yaml
```

### Configuration Setup

#### 1. Basic Configuration

```yaml
# config/config.yaml
app:
  name: "ZephyrGate"
  environment: "production"
  debug: false
  log_level: "INFO"

server:
  host: "127.0.0.1"
  port: 8080
  workers: 4

database:
  url: "sqlite:///data/zephyrgate.db"
  auto_migrate: true

meshtastic:
  interfaces:
    primary:
      type: "serial"
      device: "/dev/ttyUSB0"
      baudrate: 921600

services:
  emergency:
    enabled: true
  bbs:
    enabled: true
  weather:
    enabled: true
  email:
    enabled: false  # Configure separately
  bot:
    enabled: true
  web:
    enabled: true
```

#### 2. Create Systemd Service

```bash
# Create service file
sudo tee /etc/systemd/system/zephyrgate.service > /dev/null << EOF
[Unit]
Description=ZephyrGate Meshtastic Gateway
Documentation=https://github.com/your-repo/zephyrgate
After=network.target network-online.target
Wants=network-online.target

[Service]
Type=simple
User=zephyrgate
Group=zephyrgate
WorkingDirectory=/opt/zephyrgate
Environment=PATH=/opt/zephyrgate/venv/bin
ExecStart=/opt/zephyrgate/venv/bin/python src/main.py
ExecReload=/bin/kill -HUP \$MAINPID
Restart=always
RestartSec=10
TimeoutStopSec=30

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/zephyrgate/data /opt/zephyrgate/logs
CapabilityBoundingSet=CAP_NET_BIND_SERVICE

# Resource limits
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable service
sudo systemctl daemon-reload
sudo systemctl enable zephyrgate
```

#### 3. Start and Verify

```bash
# Start service
sudo systemctl start zephyrgate

# Check status
sudo systemctl status zephyrgate

# View logs
sudo journalctl -u zephyrgate -f

# Test web interface
curl http://localhost:8080/health
```

## Production Deployment

### Load Balancer Configuration

#### HAProxy Configuration

```haproxy
# /etc/haproxy/haproxy.cfg
global
    daemon
    maxconn 4096
    log stdout local0
    
defaults
    mode http
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms
    option httplog
    
frontend zephyrgate_frontend
    bind *:80
    bind *:443 ssl crt /etc/ssl/certs/zephyrgate.pem
    redirect scheme https if !{ ssl_fc }
    
    # Security headers
    http-response set-header X-Frame-Options DENY
    http-response set-header X-Content-Type-Options nosniff
    
    default_backend zephyrgate_backend
    
backend zephyrgate_backend
    balance roundrobin
    option httpchk GET /health
    
    server zephyr1 192.168.1.10:8080 check
    server zephyr2 192.168.1.11:8080 check
    server zephyr3 192.168.1.12:8080 check
```

### Database Configuration

#### PostgreSQL Setup (for larger deployments)

```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib

# Create database and user
sudo -u postgres psql << EOF
CREATE DATABASE zephyrgate;
CREATE USER zephyrgate WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE zephyrgate TO zephyrgate;
\q
EOF

# Update configuration
# config/production.yaml
database:
  url: "postgresql://zephyrgate:secure_password@localhost/zephyrgate"
  pool_size: 20
  max_overflow: 30
```

#### Redis Configuration

```bash
# Install Redis
sudo apt install redis-server

# Configure Redis
sudo tee /etc/redis/redis.conf > /dev/null << EOF
bind 127.0.0.1
port 6379
maxmemory 512mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
EOF

# Start Redis
sudo systemctl start redis-server
sudo systemctl enable redis-server
```

### SSL Certificate Setup

#### Let's Encrypt with Certbot

```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

#### Self-Signed Certificate

```bash
# Generate certificate
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout /etc/ssl/private/zephyrgate.key \
    -out /etc/ssl/certs/zephyrgate.crt \
    -subj "/C=US/ST=State/L=City/O=Organization/CN=your-domain.com"
```

## Cloud Deployment

### AWS Deployment

#### EC2 Instance Setup

```bash
# Launch EC2 instance (t3.medium recommended)
aws ec2 run-instances \
    --image-id ami-0c02fb55956c7d316 \
    --instance-type t3.medium \
    --key-name your-key-pair \
    --security-group-ids sg-xxxxxxxxx \
    --subnet-id subnet-xxxxxxxxx \
    --user-data file://user-data.sh
```

#### User Data Script

```bash
#!/bin/bash
# user-data.sh
yum update -y
yum install -y docker git

# Start Docker
systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Deploy application
cd /opt
git clone https://github.com/your-repo/zephyrgate.git
cd zephyrgate
docker-compose up -d
```

#### RDS Database

```bash
# Create RDS instance
aws rds create-db-instance \
    --db-instance-identifier zephyrgate-db \
    --db-instance-class db.t3.micro \
    --engine postgres \
    --master-username zephyrgate \
    --master-user-password SecurePassword123 \
    --allocated-storage 20 \
    --vpc-security-group-ids sg-xxxxxxxxx
```

### Google Cloud Platform

#### Compute Engine Deployment

```bash
# Create instance
gcloud compute instances create zephyrgate-instance \
    --zone=us-central1-a \
    --machine-type=e2-medium \
    --image-family=ubuntu-2004-lts \
    --image-project=ubuntu-os-cloud \
    --boot-disk-size=50GB \
    --metadata-from-file startup-script=startup.sh
```

#### Cloud SQL Database

```bash
# Create Cloud SQL instance
gcloud sql instances create zephyrgate-db \
    --database-version=POSTGRES_13 \
    --tier=db-f1-micro \
    --region=us-central1

# Create database
gcloud sql databases create zephyrgate --instance=zephyrgate-db

# Create user
gcloud sql users create zephyrgate \
    --instance=zephyrgate-db \
    --password=SecurePassword123
```

### Azure Deployment

#### Container Instances

```bash
# Create resource group
az group create --name zephyrgate-rg --location eastus

# Create container instance
az container create \
    --resource-group zephyrgate-rg \
    --name zephyrgate \
    --image zephyrgate:latest \
    --cpu 2 \
    --memory 4 \
    --ports 8080 \
    --environment-variables \
        ZEPHYR_APP_ENVIRONMENT=production \
        ZEPHYR_DATABASE_URL=postgresql://user:pass@server/db
```

## High Availability Setup

### Multi-Node Configuration

#### Node 1 (Primary)

```yaml
# config/node1.yaml
app:
  node_id: "node1"
  role: "primary"
  
cluster:
  enabled: true
  nodes:
    - "node2.example.com:8081"
    - "node3.example.com:8081"
  
database:
  url: "postgresql://zephyrgate:password@db-cluster/zephyrgate"
  
redis:
  url: "redis://redis-cluster:6379/0"
```

#### Load Balancer Health Checks

```yaml
# Health check configuration
health_checks:
  enabled: true
  endpoint: "/health"
  interval: 30
  timeout: 10
  healthy_threshold: 2
  unhealthy_threshold: 3
```

### Database Clustering

#### PostgreSQL Streaming Replication

```bash
# Primary server configuration
# postgresql.conf
wal_level = replica
max_wal_senders = 3
wal_keep_segments = 64
archive_mode = on
archive_command = 'cp %p /var/lib/postgresql/archive/%f'

# pg_hba.conf
host replication replicator 192.168.1.0/24 md5
```

#### Redis Sentinel

```bash
# Sentinel configuration
# sentinel.conf
sentinel monitor mymaster 192.168.1.10 6379 2
sentinel down-after-milliseconds mymaster 5000
sentinel failover-timeout mymaster 10000
sentinel parallel-syncs mymaster 1
```

## Security Hardening

### System Security

#### Firewall Configuration

```bash
# UFW configuration
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

#### Fail2Ban Setup

```bash
# Install Fail2Ban
sudo apt install fail2ban

# Configure jail
sudo tee /etc/fail2ban/jail.local > /dev/null << EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
logpath = /var/log/auth.log

[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log
EOF

sudo systemctl restart fail2ban
```

### Application Security

#### Environment Variables

```bash
# Secure environment file
# .env.production
ZEPHYR_SECURITY_SECRET_KEY=$(openssl rand -hex 32)
ZEPHYR_DATABASE_PASSWORD=$(openssl rand -base64 32)
ZEPHYR_JWT_SECRET=$(openssl rand -hex 32)
```

#### File Permissions

```bash
# Set secure permissions
chmod 600 .env.production
chmod 700 data/
chmod 755 logs/
chown -R zephyrgate:zephyrgate /opt/zephyrgate
```

## Monitoring Setup

### Prometheus Configuration

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  
scrape_configs:
  - job_name: 'zephyrgate'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "ZephyrGate Monitoring",
    "panels": [
      {
        "title": "System Health",
        "type": "stat",
        "targets": [
          {
            "expr": "up{job=\"zephyrgate\"}"
          }
        ]
      },
      {
        "title": "Message Throughput",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(zephyr_messages_total[5m])"
          }
        ]
      }
    ]
  }
}
```

### Log Aggregation

#### ELK Stack Setup

```yaml
# docker-compose.elk.yml
version: '3.8'
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:7.15.0
    environment:
      - discovery.type=single-node
    ports:
      - "9200:9200"
      
  logstash:
    image: docker.elastic.co/logstash/logstash:7.15.0
    volumes:
      - ./logstash.conf:/usr/share/logstash/pipeline/logstash.conf
      
  kibana:
    image: docker.elastic.co/kibana/kibana:7.15.0
    ports:
      - "5601:5601"
    environment:
      - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
```

## Backup Configuration

### Automated Backup Script

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backup/zephyrgate"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Database backup
if [ "$DB_TYPE" = "postgresql" ]; then
    pg_dump -h localhost -U zephyrgate zephyrgate > "$BACKUP_DIR/db_$DATE.sql"
else
    sqlite3 /opt/zephyrgate/data/zephyrgate.db ".backup '$BACKUP_DIR/db_$DATE.sqlite'"
fi

# Configuration backup
tar -czf "$BACKUP_DIR/config_$DATE.tar.gz" -C /opt/zephyrgate config/

# Data backup
tar -czf "$BACKUP_DIR/data_$DATE.tar.gz" -C /opt/zephyrgate data/

# Cleanup old backups
find "$BACKUP_DIR" -name "*.sql" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.sqlite" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

# Upload to cloud storage (optional)
if [ -n "$AWS_S3_BUCKET" ]; then
    aws s3 sync "$BACKUP_DIR" "s3://$AWS_S3_BUCKET/zephyrgate-backups/"
fi
```

### Cron Job Setup

```bash
# Add to crontab
crontab -e

# Daily backup at 2 AM
0 2 * * * /opt/zephyrgate/scripts/backup.sh

# Weekly full backup
0 3 * * 0 /opt/zephyrgate/scripts/full-backup.sh
```

## Troubleshooting Deployment

### Common Issues

#### Port Conflicts

```bash
# Check port usage
sudo netstat -tlnp | grep :8080
sudo lsof -i :8080

# Change port in configuration
ZEPHYR_SERVER_PORT=8081
```

#### Permission Issues

```bash
# Fix file permissions
sudo chown -R zephyrgate:zephyrgate /opt/zephyrgate
sudo chmod -R 755 /opt/zephyrgate
sudo chmod 600 /opt/zephyrgate/.env
```

#### Database Connection Issues

```bash
# Test database connection
python3 -c "
import sqlite3
conn = sqlite3.connect('/opt/zephyrgate/data/zephyrgate.db')
print('Database connection successful')
conn.close()
"
```

#### Service Startup Issues

```bash
# Check service status
sudo systemctl status zephyrgate

# View detailed logs
sudo journalctl -u zephyrgate -n 50

# Test configuration
cd /opt/zephyrgate
source venv/bin/activate
python src/main.py --config-test
```

### Diagnostic Commands

```bash
# System diagnostics
df -h                    # Disk space
free -h                  # Memory usage
top                      # Process usage
netstat -tlnp           # Network ports

# Application diagnostics
docker compose logs      # Container logs
curl http://localhost:8080/health  # Health check
python src/main.py --status        # Application status
```

This deployment guide provides comprehensive instructions for deploying ZephyrGate in various environments, from simple single-node installations to complex high-availability setups. Choose the deployment method that best fits your requirements and infrastructure.