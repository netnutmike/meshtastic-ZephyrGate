#!/bin/bash
# ZephyrGate Backup Script
# Comprehensive backup solution for data, configuration, and system state

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_ROOT="${BACKUP_ROOT:-/backup/zephyrgate}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
COMPRESSION_LEVEL="${COMPRESSION_LEVEL:-6}"
ENCRYPT_BACKUPS="${ENCRYPT_BACKUPS:-false}"
GPG_RECIPIENT="${GPG_RECIPIENT:-}"
S3_BUCKET="${S3_BUCKET:-}"
BACKUP_TYPE="${BACKUP_TYPE:-full}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') $1"
}

# Create backup directory structure
setup_backup_dirs() {
    local backup_date=$(date +%Y%m%d_%H%M%S)
    BACKUP_DIR="$BACKUP_ROOT/$backup_date"
    
    mkdir -p "$BACKUP_DIR"
    mkdir -p "$BACKUP_DIR/database"
    mkdir -p "$BACKUP_DIR/config"
    mkdir -p "$BACKUP_DIR/data"
    mkdir -p "$BACKUP_DIR/logs"
    mkdir -p "$BACKUP_DIR/system"
    
    log_info "Created backup directory: $BACKUP_DIR"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking backup prerequisites..."
    
    # Check if required tools are available
    local missing_tools=()
    
    command -v tar >/dev/null 2>&1 || missing_tools+=("tar")
    command -v gzip >/dev/null 2>&1 || missing_tools+=("gzip")
    command -v sqlite3 >/dev/null 2>&1 || missing_tools+=("sqlite3")
    
    if [ "$ENCRYPT_BACKUPS" = "true" ]; then
        command -v gpg >/dev/null 2>&1 || missing_tools+=("gpg")
        if [ -z "$GPG_RECIPIENT" ]; then
            log_error "GPG_RECIPIENT must be set when ENCRYPT_BACKUPS is true"
            exit 1
        fi
    fi
    
    if [ -n "$S3_BUCKET" ]; then
        command -v aws >/dev/null 2>&1 || missing_tools+=("aws")
    fi
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        exit 1
    fi
    
    # Check disk space
    local available_space=$(df "$BACKUP_ROOT" 2>/dev/null | awk 'NR==2 {print $4}' || echo "0")
    local required_space=1048576  # 1GB in KB
    
    if [ "$available_space" -lt "$required_space" ]; then
        log_warning "Low disk space available for backups: ${available_space}KB"
    fi
    
    log_success "Prerequisites check completed"
}

# Backup database
backup_database() {
    log_info "Backing up database..."
    
    local db_path="$APP_DIR/data/zephyrgate.db"
    local backup_file="$BACKUP_DIR/database/zephyrgate.sqlite"
    local sql_dump="$BACKUP_DIR/database/zephyrgate.sql"
    
    if [ -f "$db_path" ]; then
        # Create SQLite backup
        sqlite3 "$db_path" ".backup '$backup_file'"
        
        # Verify backup integrity
        if sqlite3 "$backup_file" "PRAGMA integrity_check;" | grep -q "ok"; then
            log_success "SQLite backup created and verified"
        else
            log_error "SQLite backup verification failed"
            return 1
        fi
        
        # Create SQL dump for portability
        sqlite3 "$db_path" .dump > "$sql_dump"
        
        # Compress SQL dump
        gzip -"$COMPRESSION_LEVEL" "$sql_dump"
        
        # Get database statistics
        local db_size=$(du -h "$db_path" | cut -f1)
        local backup_size=$(du -h "$backup_file" | cut -f1)
        
        echo "Database backup completed:" >> "$BACKUP_DIR/manifest.txt"
        echo "  Original size: $db_size" >> "$BACKUP_DIR/manifest.txt"
        echo "  Backup size: $backup_size" >> "$BACKUP_DIR/manifest.txt"
        echo "  Tables backed up:" >> "$BACKUP_DIR/manifest.txt"
        
        sqlite3 "$db_path" "SELECT name FROM sqlite_master WHERE type='table';" | \
            sed 's/^/    /' >> "$BACKUP_DIR/manifest.txt"
        
        log_success "Database backup completed (size: $backup_size)"
    else
        log_warning "Database file not found: $db_path"
    fi
}

# Backup configuration files
backup_config() {
    log_info "Backing up configuration..."
    
    local config_dir="$APP_DIR/config"
    local backup_file="$BACKUP_DIR/config/config.tar.gz"
    
    if [ -d "$config_dir" ]; then
        tar -czf "$backup_file" -C "$APP_DIR" config/ \
            --exclude="config/local.yaml" \
            --exclude="config/development.yaml" \
            --exclude="config/test.yaml"
        
        local config_size=$(du -h "$backup_file" | cut -f1)
        log_success "Configuration backup completed (size: $config_size)"
        
        echo "Configuration backup: $config_size" >> "$BACKUP_DIR/manifest.txt"
    else
        log_warning "Configuration directory not found: $config_dir"
    fi
}

# Backup application data
backup_data() {
    log_info "Backing up application data..."
    
    local data_dir="$APP_DIR/data"
    local backup_file="$BACKUP_DIR/data/data.tar.gz"
    
    if [ -d "$data_dir" ]; then
        tar -czf "$backup_file" -C "$APP_DIR" data/ \
            --exclude="data/zephyrgate.db" \
            --exclude="data/*.tmp" \
            --exclude="data/cache/*"
        
        local data_size=$(du -h "$backup_file" | cut -f1)
        log_success "Application data backup completed (size: $data_size)"
        
        echo "Application data backup: $data_size" >> "$BACKUP_DIR/manifest.txt"
    else
        log_warning "Data directory not found: $data_dir"
    fi
}

# Backup recent logs
backup_logs() {
    log_info "Backing up recent logs..."
    
    local logs_dir="$APP_DIR/logs"
    local backup_file="$BACKUP_DIR/logs/logs.tar.gz"
    
    if [ -d "$logs_dir" ]; then
        # Backup logs from the last 7 days
        find "$logs_dir" -name "*.log*" -mtime -7 -print0 | \
            tar -czf "$backup_file" --null -T -
        
        local logs_size=$(du -h "$backup_file" | cut -f1)
        log_success "Logs backup completed (size: $logs_size)"
        
        echo "Logs backup (last 7 days): $logs_size" >> "$BACKUP_DIR/manifest.txt"
    else
        log_warning "Logs directory not found: $logs_dir"
    fi
}

# Backup system configuration
backup_system() {
    log_info "Backing up system configuration..."
    
    local system_backup="$BACKUP_DIR/system/system.tar.gz"
    local temp_dir=$(mktemp -d)
    
    # Collect system files
    mkdir -p "$temp_dir/systemd"
    mkdir -p "$temp_dir/nginx"
    mkdir -p "$temp_dir/cron"
    
    # Systemd service files
    if [ -f "/etc/systemd/system/zephyrgate.service" ]; then
        cp "/etc/systemd/system/zephyrgate.service" "$temp_dir/systemd/"
    fi
    
    # Nginx configuration
    if [ -f "/etc/nginx/sites-available/zephyrgate" ]; then
        cp "/etc/nginx/sites-available/zephyrgate" "$temp_dir/nginx/"
    fi
    
    # Cron jobs
    if [ -f "/etc/cron.d/zephyrgate" ]; then
        cp "/etc/cron.d/zephyrgate" "$temp_dir/cron/"
    fi
    
    # Create system backup
    if [ "$(ls -A "$temp_dir")" ]; then
        tar -czf "$system_backup" -C "$temp_dir" .
        local system_size=$(du -h "$system_backup" | cut -f1)
        log_success "System configuration backup completed (size: $system_size)"
        
        echo "System configuration backup: $system_size" >> "$BACKUP_DIR/manifest.txt"
    else
        log_info "No system configuration files found to backup"
    fi
    
    # Cleanup
    rm -rf "$temp_dir"
}

# Create backup manifest
create_manifest() {
    log_info "Creating backup manifest..."
    
    local manifest_file="$BACKUP_DIR/manifest.txt"
    
    cat > "$manifest_file" << EOF
ZephyrGate Backup Manifest
==========================
Backup ID: $(basename "$BACKUP_DIR")
Created: $(date)
Type: $BACKUP_TYPE
Hostname: $(hostname)
ZephyrGate Version: $(cat "$APP_DIR/VERSION" 2>/dev/null || echo "unknown")

Backup Components:
EOF
    
    # Add component sizes
    if [ -f "$BACKUP_DIR/database/zephyrgate.sqlite" ]; then
        local db_size=$(du -h "$BACKUP_DIR/database/zephyrgate.sqlite" | cut -f1)
        echo "  Database: $db_size" >> "$manifest_file"
    fi
    
    if [ -f "$BACKUP_DIR/config/config.tar.gz" ]; then
        local config_size=$(du -h "$BACKUP_DIR/config/config.tar.gz" | cut -f1)
        echo "  Configuration: $config_size" >> "$manifest_file"
    fi
    
    if [ -f "$BACKUP_DIR/data/data.tar.gz" ]; then
        local data_size=$(du -h "$BACKUP_DIR/data/data.tar.gz" | cut -f1)
        echo "  Application Data: $data_size" >> "$manifest_file"
    fi
    
    if [ -f "$BACKUP_DIR/logs/logs.tar.gz" ]; then
        local logs_size=$(du -h "$BACKUP_DIR/logs/logs.tar.gz" | cut -f1)
        echo "  Logs: $logs_size" >> "$manifest_file"
    fi
    
    if [ -f "$BACKUP_DIR/system/system.tar.gz" ]; then
        local system_size=$(du -h "$BACKUP_DIR/system/system.tar.gz" | cut -f1)
        echo "  System Config: $system_size" >> "$manifest_file"
    fi
    
    # Total backup size
    local total_size=$(du -sh "$BACKUP_DIR" | cut -f1)
    echo "" >> "$manifest_file"
    echo "Total Backup Size: $total_size" >> "$manifest_file"
    
    log_success "Backup manifest created"
}

# Encrypt backup if requested
encrypt_backup() {
    if [ "$ENCRYPT_BACKUPS" != "true" ]; then
        return 0
    fi
    
    log_info "Encrypting backup..."
    
    local archive_name="zephyrgate-backup-$(basename "$BACKUP_DIR").tar.gz"
    local encrypted_name="${archive_name}.gpg"
    
    # Create compressed archive
    tar -czf "$BACKUP_ROOT/$archive_name" -C "$BACKUP_ROOT" "$(basename "$BACKUP_DIR")"
    
    # Encrypt the archive
    gpg --trust-model always --encrypt -r "$GPG_RECIPIENT" \
        --output "$BACKUP_ROOT/$encrypted_name" "$BACKUP_ROOT/$archive_name"
    
    # Remove unencrypted files
    rm -rf "$BACKUP_DIR"
    rm -f "$BACKUP_ROOT/$archive_name"
    
    log_success "Backup encrypted: $encrypted_name"
    FINAL_BACKUP_FILE="$BACKUP_ROOT/$encrypted_name"
}

# Compress backup
compress_backup() {
    if [ "$ENCRYPT_BACKUPS" = "true" ]; then
        return 0  # Already handled in encrypt_backup
    fi
    
    log_info "Compressing backup..."
    
    local archive_name="zephyrgate-backup-$(basename "$BACKUP_DIR").tar.gz"
    
    tar -czf "$BACKUP_ROOT/$archive_name" -C "$BACKUP_ROOT" "$(basename "$BACKUP_DIR")"
    
    # Remove uncompressed directory
    rm -rf "$BACKUP_DIR"
    
    log_success "Backup compressed: $archive_name"
    FINAL_BACKUP_FILE="$BACKUP_ROOT/$archive_name"
}

# Upload to cloud storage
upload_to_cloud() {
    if [ -z "$S3_BUCKET" ]; then
        return 0
    fi
    
    log_info "Uploading backup to S3..."
    
    local s3_key="zephyrgate-backups/$(basename "$FINAL_BACKUP_FILE")"
    
    if aws s3 cp "$FINAL_BACKUP_FILE" "s3://$S3_BUCKET/$s3_key"; then
        log_success "Backup uploaded to S3: s3://$S3_BUCKET/$s3_key"
    else
        log_error "Failed to upload backup to S3"
        return 1
    fi
}

# Cleanup old backups
cleanup_old_backups() {
    log_info "Cleaning up old backups..."
    
    # Local cleanup
    find "$BACKUP_ROOT" -name "zephyrgate-backup-*.tar.gz*" -mtime +$RETENTION_DAYS -delete
    
    local deleted_count=$(find "$BACKUP_ROOT" -name "zephyrgate-backup-*.tar.gz*" -mtime +$RETENTION_DAYS | wc -l)
    if [ "$deleted_count" -gt 0 ]; then
        log_info "Deleted $deleted_count old local backups"
    fi
    
    # S3 cleanup (if configured)
    if [ -n "$S3_BUCKET" ]; then
        local cutoff_date=$(date -d "$RETENTION_DAYS days ago" +%Y-%m-%d)
        aws s3 ls "s3://$S3_BUCKET/zephyrgate-backups/" | \
            awk '$1 < "'$cutoff_date'" {print $4}' | \
            while read -r file; do
                if [ -n "$file" ]; then
                    aws s3 rm "s3://$S3_BUCKET/zephyrgate-backups/$file"
                    log_info "Deleted old S3 backup: $file"
                fi
            done
    fi
    
    log_success "Cleanup completed"
}

# Incremental backup
incremental_backup() {
    log_info "Performing incremental backup..."
    
    local last_backup_file="$BACKUP_ROOT/.last_full_backup"
    
    if [ ! -f "$last_backup_file" ]; then
        log_warning "No previous full backup found, performing full backup"
        BACKUP_TYPE="full"
        full_backup
        return
    fi
    
    local last_backup_time=$(cat "$last_backup_file")
    log_info "Last full backup: $last_backup_time"
    
    # Find files changed since last backup
    local changed_files=$(mktemp)
    find "$APP_DIR" -newer "$last_backup_file" -type f > "$changed_files"
    
    if [ ! -s "$changed_files" ]; then
        log_info "No files changed since last backup"
        rm -f "$changed_files"
        return 0
    fi
    
    # Create incremental backup
    local incremental_name="zephyrgate-incremental-$(date +%Y%m%d_%H%M%S).tar.gz"
    tar -czf "$BACKUP_ROOT/$incremental_name" -T "$changed_files"
    
    log_success "Incremental backup created: $incremental_name"
    
    # Cleanup
    rm -f "$changed_files"
}

# Full backup
full_backup() {
    setup_backup_dirs
    
    backup_database
    backup_config
    backup_data
    backup_logs
    backup_system
    
    create_manifest
    
    if [ "$ENCRYPT_BACKUPS" = "true" ]; then
        encrypt_backup
    else
        compress_backup
    fi
    
    # Update last backup timestamp
    date > "$BACKUP_ROOT/.last_full_backup"
}

# Main function
main() {
    log_info "Starting ZephyrGate backup process"
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --type)
                BACKUP_TYPE="$2"
                shift 2
                ;;
            --encrypt)
                ENCRYPT_BACKUPS=true
                shift
                ;;
            --gpg-recipient)
                GPG_RECIPIENT="$2"
                shift 2
                ;;
            --s3-bucket)
                S3_BUCKET="$2"
                shift 2
                ;;
            --retention-days)
                RETENTION_DAYS="$2"
                shift 2
                ;;
            --backup-root)
                BACKUP_ROOT="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --type TYPE              Backup type (full|incremental) [default: full]"
                echo "  --encrypt                Encrypt backup with GPG"
                echo "  --gpg-recipient EMAIL    GPG recipient for encryption"
                echo "  --s3-bucket BUCKET       Upload to S3 bucket"
                echo "  --retention-days DAYS    Backup retention period [default: 30]"
                echo "  --backup-root DIR        Backup root directory [default: /backup/zephyrgate]"
                echo "  --help                   Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Create backup root directory
    mkdir -p "$BACKUP_ROOT"
    
    # Check prerequisites
    check_prerequisites
    
    # Perform backup based on type
    case $BACKUP_TYPE in
        full)
            full_backup
            ;;
        incremental)
            incremental_backup
            ;;
        *)
            log_error "Unknown backup type: $BACKUP_TYPE"
            exit 1
            ;;
    esac
    
    # Upload to cloud if configured
    if [ -n "$FINAL_BACKUP_FILE" ]; then
        upload_to_cloud
    fi
    
    # Cleanup old backups
    cleanup_old_backups
    
    log_success "Backup process completed successfully"
    
    if [ -n "$FINAL_BACKUP_FILE" ]; then
        local backup_size=$(du -h "$FINAL_BACKUP_FILE" | cut -f1)
        log_info "Final backup: $FINAL_BACKUP_FILE ($backup_size)"
    fi
}

# Run main function with all arguments
main "$@"