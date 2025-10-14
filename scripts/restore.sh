#!/bin/bash
# ZephyrGate Restore Script
# Comprehensive restore solution for data, configuration, and system state

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_ROOT="${BACKUP_ROOT:-/backup/zephyrgate}"
RESTORE_TYPE="${RESTORE_TYPE:-full}"
DRY_RUN="${DRY_RUN:-false}"
FORCE_RESTORE="${FORCE_RESTORE:-false}"

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

# Check prerequisites
check_prerequisites() {
    log_info "Checking restore prerequisites..."
    
    # Check if required tools are available
    local missing_tools=()
    
    command -v tar >/dev/null 2>&1 || missing_tools+=("tar")
    command -v gzip >/dev/null 2>&1 || missing_tools+=("gzip")
    command -v sqlite3 >/dev/null 2>&1 || missing_tools+=("sqlite3")
    
    if [ ${#missing_tools[@]} -ne 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        exit 1
    fi
    
    # Check if running as appropriate user
    if [ "$EUID" -eq 0 ] && [ "$FORCE_RESTORE" != "true" ]; then
        log_warning "Running as root. Use --force to proceed or run as zephyrgate user"
        exit 1
    fi
    
    log_success "Prerequisites check completed"
}

# List available backups
list_backups() {
    log_info "Available backups:"
    
    if [ -d "$BACKUP_ROOT" ]; then
        find "$BACKUP_ROOT" -name "zephyrgate-backup-*.tar.gz*" -type f | \
            sort -r | \
            while read -r backup_file; do
                local backup_name=$(basename "$backup_file")
                local backup_size=$(du -h "$backup_file" | cut -f1)
                local backup_date=$(stat -c %y "$backup_file" | cut -d' ' -f1)
                echo "  $backup_name ($backup_size, $backup_date)"
            done
    else
        log_warning "Backup directory not found: $BACKUP_ROOT"
    fi
}

# Validate backup file
validate_backup() {
    local backup_file="$1"
    
    log_info "Validating backup file: $(basename "$backup_file")"
    
    if [ ! -f "$backup_file" ]; then
        log_error "Backup file not found: $backup_file"
        return 1
    fi
    
    # Check if file is encrypted
    if [[ "$backup_file" == *.gpg ]]; then
        log_info "Backup is encrypted, checking GPG availability..."
        if ! command -v gpg >/dev/null 2>&1; then
            log_error "GPG not available for decrypting backup"
            return 1
        fi
        
        # Test decryption (without actually decrypting)
        if ! gpg --list-packets "$backup_file" >/dev/null 2>&1; then
            log_error "Cannot decrypt backup file (wrong key or corrupted)"
            return 1
        fi
        
        log_success "Encrypted backup validation passed"
    else
        # Test archive integrity
        if ! tar -tzf "$backup_file" >/dev/null 2>&1; then
            log_error "Backup archive is corrupted or invalid"
            return 1
        fi
        
        log_success "Backup validation passed"
    fi
    
    return 0
}

# Extract backup
extract_backup() {
    local backup_file="$1"
    local extract_dir="$2"
    
    log_info "Extracting backup to: $extract_dir"
    
    mkdir -p "$extract_dir"
    
    if [[ "$backup_file" == *.gpg ]]; then
        # Decrypt and extract
        gpg --decrypt "$backup_file" | tar -xzf - -C "$extract_dir"
    else
        # Extract directly
        tar -xzf "$backup_file" -C "$extract_dir"
    fi
    
    log_success "Backup extracted successfully"
}

# Show backup manifest
show_manifest() {
    local backup_dir="$1"
    
    local manifest_file="$backup_dir/manifest.txt"
    
    if [ -f "$manifest_file" ]; then
        log_info "Backup manifest:"
        cat "$manifest_file"
    else
        log_warning "No manifest file found in backup"
    fi
}

# Stop ZephyrGate service
stop_service() {
    log_info "Stopping ZephyrGate service..."
    
    if systemctl is-active --quiet zephyrgate 2>/dev/null; then
        if [ "$DRY_RUN" = "false" ]; then
            systemctl stop zephyrgate
        fi
        log_success "ZephyrGate service stopped"
    else
        log_info "ZephyrGate service is not running"
    fi
}

# Start ZephyrGate service
start_service() {
    log_info "Starting ZephyrGate service..."
    
    if [ "$DRY_RUN" = "false" ]; then
        systemctl start zephyrgate
        
        # Wait for service to start
        sleep 5
        
        if systemctl is-active --quiet zephyrgate; then
            log_success "ZephyrGate service started successfully"
        else
            log_error "Failed to start ZephyrGate service"
            systemctl status zephyrgate
            return 1
        fi
    else
        log_info "DRY RUN: Would start ZephyrGate service"
    fi
}

# Backup current state before restore
backup_current_state() {
    log_info "Backing up current state before restore..."
    
    local pre_restore_backup="$APP_DIR/pre-restore-backup-$(date +%Y%m%d_%H%M%S)"
    
    if [ "$DRY_RUN" = "false" ]; then
        mkdir -p "$pre_restore_backup"
        
        # Backup current database
        if [ -f "$APP_DIR/data/zephyrgate.db" ]; then
            cp "$APP_DIR/data/zephyrgate.db" "$pre_restore_backup/"
        fi
        
        # Backup current configuration
        if [ -d "$APP_DIR/config" ]; then
            cp -r "$APP_DIR/config" "$pre_restore_backup/"
        fi
        
        log_success "Current state backed up to: $pre_restore_backup"
    else
        log_info "DRY RUN: Would backup current state to: $pre_restore_backup"
    fi
}

# Restore database
restore_database() {
    local backup_dir="$1"
    
    log_info "Restoring database..."
    
    local db_backup="$backup_dir/database/zephyrgate.sqlite"
    local target_db="$APP_DIR/data/zephyrgate.db"
    
    if [ -f "$db_backup" ]; then
        # Verify backup database integrity
        if sqlite3 "$db_backup" "PRAGMA integrity_check;" | grep -q "ok"; then
            log_success "Database backup integrity verified"
            
            if [ "$DRY_RUN" = "false" ]; then
                # Create target directory
                mkdir -p "$(dirname "$target_db")"
                
                # Restore database
                cp "$db_backup" "$target_db"
                
                # Set permissions
                chown zephyrgate:zephyrgate "$target_db" 2>/dev/null || true
                chmod 644 "$target_db"
                
                # Verify restored database
                if sqlite3 "$target_db" "PRAGMA integrity_check;" | grep -q "ok"; then
                    log_success "Database restored and verified"
                else
                    log_error "Restored database failed integrity check"
                    return 1
                fi
            else
                log_info "DRY RUN: Would restore database from $db_backup"
            fi
        else
            log_error "Database backup failed integrity check"
            return 1
        fi
    else
        log_warning "No database backup found in restore archive"
    fi
}

# Restore configuration
restore_config() {
    local backup_dir="$1"
    
    log_info "Restoring configuration..."
    
    local config_backup="$backup_dir/config/config.tar.gz"
    local target_config="$APP_DIR/config"
    
    if [ -f "$config_backup" ]; then
        if [ "$DRY_RUN" = "false" ]; then
            # Extract configuration
            tar -xzf "$config_backup" -C "$APP_DIR"
            
            # Set permissions
            chown -R zephyrgate:zephyrgate "$target_config" 2>/dev/null || true
            chmod -R 644 "$target_config"/*.yaml 2>/dev/null || true
            
            log_success "Configuration restored"
        else
            log_info "DRY RUN: Would restore configuration from $config_backup"
        fi
    else
        log_warning "No configuration backup found in restore archive"
    fi
}

# Restore application data
restore_data() {
    local backup_dir="$1"
    
    log_info "Restoring application data..."
    
    local data_backup="$backup_dir/data/data.tar.gz"
    local target_data="$APP_DIR/data"
    
    if [ -f "$data_backup" ]; then
        if [ "$DRY_RUN" = "false" ]; then
            # Extract data (excluding database which is handled separately)
            tar -xzf "$data_backup" -C "$APP_DIR" --exclude="data/zephyrgate.db"
            
            # Set permissions
            chown -R zephyrgate:zephyrgate "$target_data" 2>/dev/null || true
            
            log_success "Application data restored"
        else
            log_info "DRY RUN: Would restore application data from $data_backup"
        fi
    else
        log_warning "No application data backup found in restore archive"
    fi
}

# Restore system configuration
restore_system() {
    local backup_dir="$1"
    
    log_info "Restoring system configuration..."
    
    local system_backup="$backup_dir/system/system.tar.gz"
    
    if [ -f "$system_backup" ]; then
        if [ "$EUID" -ne 0 ]; then
            log_warning "System configuration restore requires root privileges"
            return 0
        fi
        
        if [ "$DRY_RUN" = "false" ]; then
            # Extract system configuration to temporary directory
            local temp_dir=$(mktemp -d)
            tar -xzf "$system_backup" -C "$temp_dir"
            
            # Restore systemd service
            if [ -f "$temp_dir/systemd/zephyrgate.service" ]; then
                cp "$temp_dir/systemd/zephyrgate.service" "/etc/systemd/system/"
                systemctl daemon-reload
                log_success "Systemd service restored"
            fi
            
            # Restore nginx configuration
            if [ -f "$temp_dir/nginx/zephyrgate" ]; then
                cp "$temp_dir/nginx/zephyrgate" "/etc/nginx/sites-available/"
                log_success "Nginx configuration restored"
            fi
            
            # Restore cron jobs
            if [ -f "$temp_dir/cron/zephyrgate" ]; then
                cp "$temp_dir/cron/zephyrgate" "/etc/cron.d/"
                log_success "Cron jobs restored"
            fi
            
            # Cleanup
            rm -rf "$temp_dir"
        else
            log_info "DRY RUN: Would restore system configuration from $system_backup"
        fi
    else
        log_warning "No system configuration backup found in restore archive"
    fi
}

# Verify restore
verify_restore() {
    log_info "Verifying restore..."
    
    local issues=0
    
    # Check database
    if [ -f "$APP_DIR/data/zephyrgate.db" ]; then
        if sqlite3 "$APP_DIR/data/zephyrgate.db" "PRAGMA integrity_check;" | grep -q "ok"; then
            log_success "Database integrity verified"
        else
            log_error "Database integrity check failed"
            issues=$((issues + 1))
        fi
    else
        log_warning "Database file not found"
        issues=$((issues + 1))
    fi
    
    # Check configuration
    if [ -d "$APP_DIR/config" ]; then
        log_success "Configuration directory exists"
    else
        log_error "Configuration directory not found"
        issues=$((issues + 1))
    fi
    
    # Check service (if not dry run)
    if [ "$DRY_RUN" = "false" ]; then
        if systemctl is-active --quiet zephyrgate 2>/dev/null; then
            log_success "ZephyrGate service is running"
        else
            log_warning "ZephyrGate service is not running"
        fi
    fi
    
    if [ $issues -eq 0 ]; then
        log_success "Restore verification completed successfully"
        return 0
    else
        log_error "Restore verification found $issues issues"
        return 1
    fi
}

# Full restore
full_restore() {
    local backup_file="$1"
    local extract_dir=$(mktemp -d)
    
    # Extract backup
    extract_backup "$backup_file" "$extract_dir"
    
    # Find the backup directory (handle nested structure)
    local backup_dir=$(find "$extract_dir" -name "manifest.txt" -type f | head -1 | xargs dirname)
    
    if [ -z "$backup_dir" ]; then
        log_error "Cannot find backup data in extracted archive"
        rm -rf "$extract_dir"
        return 1
    fi
    
    # Show manifest
    show_manifest "$backup_dir"
    
    # Confirm restore
    if [ "$FORCE_RESTORE" != "true" ] && [ "$DRY_RUN" != "true" ]; then
        echo
        read -p "Proceed with restore? This will overwrite current data (y/N): " confirm
        if [[ $confirm != [yY] ]]; then
            log_info "Restore cancelled by user"
            rm -rf "$extract_dir"
            return 0
        fi
    fi
    
    # Backup current state
    backup_current_state
    
    # Stop service
    stop_service
    
    # Restore components
    restore_database "$backup_dir"
    restore_config "$backup_dir"
    restore_data "$backup_dir"
    restore_system "$backup_dir"
    
    # Start service
    start_service
    
    # Verify restore
    verify_restore
    
    # Cleanup
    rm -rf "$extract_dir"
    
    log_success "Full restore completed successfully"
}

# Database-only restore
database_restore() {
    local backup_file="$1"
    local extract_dir=$(mktemp -d)
    
    # Extract backup
    extract_backup "$backup_file" "$extract_dir"
    
    # Find the backup directory
    local backup_dir=$(find "$extract_dir" -name "manifest.txt" -type f | head -1 | xargs dirname)
    
    if [ -z "$backup_dir" ]; then
        log_error "Cannot find backup data in extracted archive"
        rm -rf "$extract_dir"
        return 1
    fi
    
    # Backup current database
    if [ -f "$APP_DIR/data/zephyrgate.db" ]; then
        local db_backup="$APP_DIR/data/zephyrgate.db.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$APP_DIR/data/zephyrgate.db" "$db_backup"
        log_info "Current database backed up to: $db_backup"
    fi
    
    # Stop service
    stop_service
    
    # Restore database only
    restore_database "$backup_dir"
    
    # Start service
    start_service
    
    # Cleanup
    rm -rf "$extract_dir"
    
    log_success "Database restore completed successfully"
}

# Main function
main() {
    log_info "Starting ZephyrGate restore process"
    
    local backup_file=""
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --backup-file)
                backup_file="$2"
                shift 2
                ;;
            --type)
                RESTORE_TYPE="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --force)
                FORCE_RESTORE=true
                shift
                ;;
            --backup-root)
                BACKUP_ROOT="$2"
                shift 2
                ;;
            --list)
                list_backups
                exit 0
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --backup-file FILE       Backup file to restore from"
                echo "  --type TYPE              Restore type (full|database) [default: full]"
                echo "  --dry-run                Show what would be done without making changes"
                echo "  --force                  Skip confirmation prompts"
                echo "  --backup-root DIR        Backup root directory [default: /backup/zephyrgate]"
                echo "  --list                   List available backups"
                echo "  --help                   Show this help message"
                echo ""
                echo "Examples:"
                echo "  $0 --list"
                echo "  $0 --backup-file /backup/zephyrgate/zephyrgate-backup-20231201_120000.tar.gz"
                echo "  $0 --backup-file backup.tar.gz --type database --dry-run"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Check if backup file is specified
    if [ -z "$backup_file" ]; then
        log_error "No backup file specified. Use --backup-file or --list to see available backups"
        exit 1
    fi
    
    # Check prerequisites
    check_prerequisites
    
    # Validate backup file
    validate_backup "$backup_file"
    
    # Perform restore based on type
    case $RESTORE_TYPE in
        full)
            full_restore "$backup_file"
            ;;
        database)
            database_restore "$backup_file"
            ;;
        *)
            log_error "Unknown restore type: $RESTORE_TYPE"
            exit 1
            ;;
    esac
    
    log_success "Restore process completed successfully"
}

# Run main function with all arguments
main "$@"