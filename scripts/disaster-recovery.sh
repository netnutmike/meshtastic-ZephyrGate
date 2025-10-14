#!/bin/bash
# ZephyrGate Disaster Recovery Script
# Complete system recovery from catastrophic failure

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "$SCRIPT_DIR")"
RECOVERY_MODE="${RECOVERY_MODE:-interactive}"
BACKUP_SOURCE="${BACKUP_SOURCE:-local}"
S3_BUCKET="${S3_BUCKET:-}"
RECOVERY_LOG="/tmp/zephyrgate-recovery-$(date +%Y%m%d_%H%M%S).log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    local msg="[INFO] $(date '+%Y-%m-%d %H:%M:%S') $1"
    echo -e "${BLUE}${msg}${NC}"
    echo "$msg" >> "$RECOVERY_LOG"
}

log_success() {
    local msg="[SUCCESS] $(date '+%Y-%m-%d %H:%M:%S') $1"
    echo -e "${GREEN}${msg}${NC}"
    echo "$msg" >> "$RECOVERY_LOG"
}

log_warning() {
    local msg="[WARNING] $(date '+%Y-%m-%d %H:%M:%S') $1"
    echo -e "${YELLOW}${msg}${NC}"
    echo "$msg" >> "$RECOVERY_LOG"
}

log_error() {
    local msg="[ERROR] $(date '+%Y-%m-%d %H:%M:%S') $1"
    echo -e "${RED}${msg}${NC}"
    echo "$msg" >> "$RECOVERY_LOG"
}

log_step() {
    local msg="[STEP] $(date '+%Y-%m-%d %H:%M:%S') $1"
    echo -e "${PURPLE}${msg}${NC}"
    echo "$msg" >> "$RECOVERY_LOG"
}

# Display recovery banner
show_banner() {
    cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║                 ZephyrGate Disaster Recovery                 ║
║                                                              ║
║  This script will guide you through complete system         ║
║  recovery from catastrophic failure.                        ║
║                                                              ║
║  WARNING: This will completely rebuild the system!          ║
╚══════════════════════════════════════════════════════════════╝
EOF
}

# Assess system damage
assess_damage() {
    log_step "Assessing system damage..."
    
    local damage_score=0
    local issues=()
    
    # Check if ZephyrGate directory exists
    if [ ! -d "$APP_DIR" ]; then
        issues+=("Application directory missing")
        damage_score=$((damage_score + 3))
    fi
    
    # Check if database exists
    if [ ! -f "$APP_DIR/data/zephyrgate.db" ]; then
        issues+=("Database missing")
        damage_score=$((damage_score + 3))
    else
        # Check database integrity
        if ! sqlite3 "$APP_DIR/data/zephyrgate.db" "PRAGMA integrity_check;" | grep -q "ok"; then
            issues+=("Database corrupted")
            damage_score=$((damage_score + 2))
        fi
    fi
    
    # Check if configuration exists
    if [ ! -d "$APP_DIR/config" ]; then
        issues+=("Configuration missing")
        damage_score=$((damage_score + 2))
    fi
    
    # Check if service is installed
    if [ ! -f "/etc/systemd/system/zephyrgate.service" ]; then
        issues+=("System service not installed")
        damage_score=$((damage_score + 1))
    fi
    
    # Check if service is running
    if ! systemctl is-active --quiet zephyrgate 2>/dev/null; then
        issues+=("Service not running")
        damage_score=$((damage_score + 1))
    fi
    
    # Report damage assessment
    log_info "Damage assessment complete. Score: $damage_score/12"
    
    if [ ${#issues[@]} -gt 0 ]; then
        log_warning "Issues found:"
        for issue in "${issues[@]}"; do
            log_warning "  - $issue"
        done
    else
        log_success "No critical issues found"
    fi
    
    # Determine recovery strategy
    if [ $damage_score -ge 8 ]; then
        RECOVERY_STRATEGY="complete_rebuild"
        log_warning "Severe damage detected. Complete rebuild required."
    elif [ $damage_score -ge 4 ]; then
        RECOVERY_STRATEGY="partial_restore"
        log_warning "Moderate damage detected. Partial restore required."
    elif [ $damage_score -gt 0 ]; then
        RECOVERY_STRATEGY="repair"
        log_info "Minor damage detected. Repair possible."
    else
        RECOVERY_STRATEGY="none"
        log_success "System appears healthy. No recovery needed."
    fi
    
    echo "RECOVERY_STRATEGY=$RECOVERY_STRATEGY" >> "$RECOVERY_LOG"
}

# Find available backups
find_backups() {
    log_step "Searching for available backups..."
    
    local backups=()
    
    # Search local backups
    if [ -d "/backup/zephyrgate" ]; then
        while IFS= read -r -d '' backup; do
            backups+=("$backup")
        done < <(find /backup/zephyrgate -name "zephyrgate-backup-*.tar.gz*" -type f -print0 | sort -z -r)
    fi
    
    # Search S3 backups (if configured)
    if [ -n "$S3_BUCKET" ] && command -v aws >/dev/null 2>&1; then
        log_info "Searching S3 bucket: $S3_BUCKET"
        aws s3 ls "s3://$S3_BUCKET/zephyrgate-backups/" | \
            awk '{print $4}' | \
            grep "zephyrgate-backup-" | \
            while read -r s3_backup; do
                backups+=("s3://$S3_BUCKET/zephyrgate-backups/$s3_backup")
            done
    fi
    
    if [ ${#backups[@]} -eq 0 ]; then
        log_error "No backups found!"
        return 1
    fi
    
    log_success "Found ${#backups[@]} backup(s)"
    
    # Store backups for selection
    printf '%s\n' "${backups[@]}" > /tmp/available_backups.txt
}

# Select backup for recovery
select_backup() {
    log_step "Selecting backup for recovery..."
    
    if [ ! -f /tmp/available_backups.txt ]; then
        log_error "No backup list available"
        return 1
    fi
    
    local backups=()
    while IFS= read -r line; do
        backups+=("$line")
    done < /tmp/available_backups.txt
    
    if [ "$RECOVERY_MODE" = "interactive" ]; then
        echo "Available backups:"
        for i in "${!backups[@]}"; do
            local backup="${backups[$i]}"
            local backup_name=$(basename "$backup")
            local backup_date=""
            
            # Extract date from backup name
            if [[ $backup_name =~ zephyrgate-backup-([0-9]{8}_[0-9]{6}) ]]; then
                backup_date="${BASH_REMATCH[1]}"
                backup_date=$(date -d "${backup_date:0:8} ${backup_date:9:2}:${backup_date:11:2}:${backup_date:13:2}" '+%Y-%m-%d %H:%M:%S' 2>/dev/null || echo "Unknown")
            fi
            
            echo "  $((i+1)). $backup_name ($backup_date)"
        done
        
        echo
        read -p "Select backup number (1-${#backups[@]}): " selection
        
        if [[ $selection =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le ${#backups[@]} ]; then
            SELECTED_BACKUP="${backups[$((selection-1))]}"
        else
            log_error "Invalid selection"
            return 1
        fi
    else
        # Automatic mode - select most recent backup
        SELECTED_BACKUP="${backups[0]}"
    fi
    
    log_success "Selected backup: $(basename "$SELECTED_BACKUP")"
    echo "SELECTED_BACKUP=$SELECTED_BACKUP" >> "$RECOVERY_LOG"
}

# Download backup from S3 if needed
download_backup() {
    if [[ $SELECTED_BACKUP == s3://* ]]; then
        log_step "Downloading backup from S3..."
        
        local local_backup="/tmp/$(basename "$SELECTED_BACKUP")"
        
        if aws s3 cp "$SELECTED_BACKUP" "$local_backup"; then
            SELECTED_BACKUP="$local_backup"
            log_success "Backup downloaded to: $local_backup"
        else
            log_error "Failed to download backup from S3"
            return 1
        fi
    fi
}

# Stop all ZephyrGate processes
stop_all_processes() {
    log_step "Stopping all ZephyrGate processes..."
    
    # Stop systemd service
    if systemctl is-active --quiet zephyrgate 2>/dev/null; then
        systemctl stop zephyrgate
        log_info "Stopped systemd service"
    fi
    
    # Kill any remaining processes
    pkill -f "zephyrgate" || true
    pkill -f "python.*main.py" || true
    
    # Wait for processes to stop
    sleep 5
    
    log_success "All processes stopped"
}

# Create emergency backup of current state
emergency_backup() {
    log_step "Creating emergency backup of current state..."
    
    local emergency_dir="/tmp/zephyrgate-emergency-$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$emergency_dir"
    
    # Backup what we can
    if [ -f "$APP_DIR/data/zephyrgate.db" ]; then
        cp "$APP_DIR/data/zephyrgate.db" "$emergency_dir/" 2>/dev/null || true
    fi
    
    if [ -d "$APP_DIR/config" ]; then
        cp -r "$APP_DIR/config" "$emergency_dir/" 2>/dev/null || true
    fi
    
    if [ -d "$APP_DIR/logs" ]; then
        cp -r "$APP_DIR/logs" "$emergency_dir/" 2>/dev/null || true
    fi
    
    log_success "Emergency backup created: $emergency_dir"
    echo "EMERGENCY_BACKUP=$emergency_dir" >> "$RECOVERY_LOG"
}

# Complete system rebuild
complete_rebuild() {
    log_step "Performing complete system rebuild..."
    
    # Remove existing installation
    if [ -d "$APP_DIR" ]; then
        log_info "Removing existing installation..."
        rm -rf "$APP_DIR"
    fi
    
    # Create application directory structure
    log_info "Creating application directory structure..."
    mkdir -p "$APP_DIR"/{src,config,data,logs,scripts}
    
    # Create application user if it doesn't exist
    if ! id zephyrgate >/dev/null 2>&1; then
        log_info "Creating zephyrgate user..."
        useradd -r -m -s /bin/bash zephyrgate
    fi
    
    # Set ownership
    chown -R zephyrgate:zephyrgate "$APP_DIR"
    
    log_success "System rebuild preparation complete"
}

# Restore from backup
restore_from_backup() {
    log_step "Restoring from backup..."
    
    # Use the restore script
    local restore_script="$SCRIPT_DIR/restore.sh"
    
    if [ -f "$restore_script" ]; then
        "$restore_script" --backup-file "$SELECTED_BACKUP" --force
    else
        log_error "Restore script not found: $restore_script"
        return 1
    fi
    
    log_success "Restore from backup completed"
}

# Reinstall system service
reinstall_service() {
    log_step "Reinstalling system service..."
    
    # Create systemd service file
    cat > /etc/systemd/system/zephyrgate.service << 'EOF'
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
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=10
TimeoutStopSec=30

# Security settings
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/opt/zephyrgate/data /opt/zephyrgate/logs

[Install]
WantedBy=multi-user.target
EOF
    
    # Reload systemd and enable service
    systemctl daemon-reload
    systemctl enable zephyrgate
    
    log_success "System service reinstalled"
}

# Verify recovery
verify_recovery() {
    log_step "Verifying recovery..."
    
    local issues=0
    
    # Check application directory
    if [ -d "$APP_DIR" ]; then
        log_success "Application directory exists"
    else
        log_error "Application directory missing"
        issues=$((issues + 1))
    fi
    
    # Check database
    if [ -f "$APP_DIR/data/zephyrgate.db" ]; then
        if sqlite3 "$APP_DIR/data/zephyrgate.db" "PRAGMA integrity_check;" | grep -q "ok"; then
            log_success "Database integrity verified"
        else
            log_error "Database integrity check failed"
            issues=$((issues + 1))
        fi
    else
        log_error "Database file missing"
        issues=$((issues + 1))
    fi
    
    # Check configuration
    if [ -d "$APP_DIR/config" ]; then
        log_success "Configuration directory exists"
    else
        log_error "Configuration directory missing"
        issues=$((issues + 1))
    fi
    
    # Check service
    if systemctl is-enabled --quiet zephyrgate 2>/dev/null; then
        log_success "Service is enabled"
    else
        log_error "Service is not enabled"
        issues=$((issues + 1))
    fi
    
    # Start service and check
    log_info "Starting ZephyrGate service..."
    systemctl start zephyrgate
    
    sleep 10
    
    if systemctl is-active --quiet zephyrgate; then
        log_success "Service is running"
        
        # Test web interface
        if curl -f -s http://localhost:8080/health >/dev/null 2>&1; then
            log_success "Web interface is responding"
        else
            log_warning "Web interface is not responding"
            issues=$((issues + 1))
        fi
    else
        log_error "Service failed to start"
        systemctl status zephyrgate
        issues=$((issues + 1))
    fi
    
    if [ $issues -eq 0 ]; then
        log_success "Recovery verification completed successfully"
        return 0
    else
        log_error "Recovery verification found $issues issues"
        return 1
    fi
}

# Generate recovery report
generate_report() {
    log_step "Generating recovery report..."
    
    local report_file="/tmp/zephyrgate-recovery-report-$(date +%Y%m%d_%H%M%S).txt"
    
    cat > "$report_file" << EOF
ZephyrGate Disaster Recovery Report
===================================
Recovery Date: $(date)
Recovery Strategy: $RECOVERY_STRATEGY
Selected Backup: $(basename "$SELECTED_BACKUP" 2>/dev/null || echo "None")

System Status After Recovery:
EOF
    
    # Add system status
    echo "- Application Directory: $([ -d "$APP_DIR" ] && echo "OK" || echo "MISSING")" >> "$report_file"
    echo "- Database: $([ -f "$APP_DIR/data/zephyrgate.db" ] && echo "OK" || echo "MISSING")" >> "$report_file"
    echo "- Configuration: $([ -d "$APP_DIR/config" ] && echo "OK" || echo "MISSING")" >> "$report_file"
    echo "- Service Status: $(systemctl is-active zephyrgate 2>/dev/null || echo "INACTIVE")" >> "$report_file"
    
    # Add recovery log
    echo "" >> "$report_file"
    echo "Recovery Log:" >> "$report_file"
    echo "=============" >> "$report_file"
    cat "$RECOVERY_LOG" >> "$report_file"
    
    log_success "Recovery report generated: $report_file"
    
    # Display summary
    echo
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    Recovery Complete                         ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo
    echo "Recovery Report: $report_file"
    echo "Recovery Log: $RECOVERY_LOG"
    
    if [ -n "$EMERGENCY_BACKUP" ]; then
        echo "Emergency Backup: $EMERGENCY_BACKUP"
    fi
    
    echo
    echo "Next Steps:"
    echo "1. Review the recovery report and logs"
    echo "2. Test all system functionality"
    echo "3. Update configuration if needed"
    echo "4. Monitor system for stability"
    echo "5. Create a new backup once system is stable"
}

# Main recovery function
main() {
    # Check if running as root
    if [ "$EUID" -ne 0 ]; then
        log_error "Disaster recovery must be run as root"
        exit 1
    fi
    
    # Parse command line arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --auto)
                RECOVERY_MODE="automatic"
                shift
                ;;
            --backup-source)
                BACKUP_SOURCE="$2"
                shift 2
                ;;
            --s3-bucket)
                S3_BUCKET="$2"
                shift 2
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --auto               Run in automatic mode (no prompts)"
                echo "  --backup-source SRC  Backup source (local|s3) [default: local]"
                echo "  --s3-bucket BUCKET   S3 bucket for backups"
                echo "  --help               Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
    
    # Show banner
    show_banner
    
    # Confirm disaster recovery
    if [ "$RECOVERY_MODE" = "interactive" ]; then
        echo
        read -p "Are you sure you want to proceed with disaster recovery? (yes/NO): " confirm
        if [ "$confirm" != "yes" ]; then
            log_info "Disaster recovery cancelled"
            exit 0
        fi
    fi
    
    log_info "Starting disaster recovery process..."
    
    # Assess damage
    assess_damage
    
    # Skip recovery if not needed
    if [ "$RECOVERY_STRATEGY" = "none" ]; then
        log_success "No recovery needed. System is healthy."
        exit 0
    fi
    
    # Find available backups
    find_backups
    
    # Select backup
    select_backup
    
    # Download backup if from S3
    download_backup
    
    # Create emergency backup
    emergency_backup
    
    # Stop all processes
    stop_all_processes
    
    # Perform recovery based on strategy
    case $RECOVERY_STRATEGY in
        complete_rebuild)
            complete_rebuild
            restore_from_backup
            reinstall_service
            ;;
        partial_restore)
            restore_from_backup
            ;;
        repair)
            # For repair, we might just need to fix specific issues
            restore_from_backup
            ;;
    esac
    
    # Verify recovery
    verify_recovery
    
    # Generate report
    generate_report
    
    log_success "Disaster recovery completed successfully!"
}

# Run main function with all arguments
main "$@"