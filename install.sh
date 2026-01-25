#!/bin/bash
#
# ZephyrGate Installation Script
# Simple, interactive installer for Raspberry Pi and Unix systems
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Check if running as root
check_root() {
    if [ "$EUID" -eq 0 ]; then 
        print_warning "Please do not run this script as root"
        print_info "Run as a regular user: ./install.sh"
        exit 1
    fi
}

# Detect OS
detect_os() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    elif type lsb_release >/dev/null 2>&1; then
        OS=$(lsb_release -si)
        VER=$(lsb_release -sr)
    elif [ -f /etc/lsb-release ]; then
        . /etc/lsb-release
        OS=$DISTRIB_ID
        VER=$DISTRIB_RELEASE
    else
        OS=$(uname -s)
        VER=$(uname -r)
    fi
    
    print_info "Detected OS: $OS $VER"
}

# Check system requirements
check_requirements() {
    print_header "Checking System Requirements"
    
    local missing_deps=()
    
    # Check Python 3.8+
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
        
        if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 8 ]; then
            print_success "Python $PYTHON_VERSION found"
        else
            print_error "Python 3.8+ required (found $PYTHON_VERSION)"
            missing_deps+=("python3.8+")
        fi
    else
        print_error "Python 3 not found"
        missing_deps+=("python3")
    fi
    
    # Check pip
    if command -v pip3 &> /dev/null; then
        print_success "pip3 found"
    else
        print_warning "pip3 not found"
        missing_deps+=("python3-pip")
    fi
    
    # Check git
    if command -v git &> /dev/null; then
        print_success "git found"
    else
        print_warning "git not found (optional)"
    fi
    
    # Check for virtual environment support
    if python3 -m venv --help &> /dev/null; then
        print_success "Python venv support found"
    else
        print_warning "Python venv not found"
        missing_deps+=("python3-venv")
    fi
    
    # If missing dependencies, offer to install
    if [ ${#missing_deps[@]} -gt 0 ]; then
        echo ""
        print_warning "Missing dependencies: ${missing_deps[*]}"
        echo ""
        read -p "Would you like to install missing dependencies? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            install_dependencies "${missing_deps[@]}"
        else
            print_error "Cannot continue without required dependencies"
            exit 1
        fi
    fi
}

# Install dependencies based on OS
install_dependencies() {
    local deps=("$@")
    
    print_info "Installing dependencies..."
    
    if [[ "$OS" == *"Debian"* ]] || [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Raspbian"* ]]; then
        sudo apt-get update
        sudo apt-get install -y python3 python3-pip python3-venv git
    elif [[ "$OS" == *"Fedora"* ]] || [[ "$OS" == *"Red Hat"* ]] || [[ "$OS" == *"CentOS"* ]]; then
        sudo dnf install -y python3 python3-pip python3-virtualenv git
    elif [[ "$OS" == *"Arch"* ]]; then
        sudo pacman -S --noconfirm python python-pip python-virtualenv git
    else
        print_error "Unsupported OS for automatic dependency installation"
        print_info "Please install: python3, python3-pip, python3-venv, git"
        exit 1
    fi
    
    print_success "Dependencies installed"
}

# Create virtual environment
setup_venv() {
    print_header "Setting Up Python Virtual Environment"
    
    if [ -d ".venv" ]; then
        print_warning "Virtual environment already exists"
        read -p "Recreate it? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf .venv
        else
            print_info "Using existing virtual environment"
            return
        fi
    fi
    
    print_info "Creating virtual environment..."
    python3 -m venv .venv
    print_success "Virtual environment created"
    
    print_info "Activating virtual environment..."
    source .venv/bin/activate
    
    print_info "Upgrading pip..."
    pip install --upgrade pip
    
    print_info "Installing Python dependencies..."
    pip install -r requirements.txt
    
    print_success "Python dependencies installed"
}

# Configure Meshtastic interface
configure_meshtastic() {
    print_header "Meshtastic Interface Configuration"
    
    echo "ZephyrGate needs to connect to your Meshtastic device."
    echo ""
    echo "Connection types:"
    echo "  1) Serial (USB cable)"
    echo "  2) TCP (Network connection)"
    echo "  3) Skip (configure manually later)"
    echo ""
    
    read -p "Select connection type [1-3]: " connection_type
    
    case $connection_type in
        1)
            configure_serial
            ;;
        2)
            configure_tcp
            ;;
        3)
            print_info "Skipping Meshtastic configuration"
            print_info "Edit config/config.yaml manually to configure"
            ;;
        *)
            print_warning "Invalid selection, skipping configuration"
            ;;
    esac
}

# Configure serial connection
configure_serial() {
    print_info "Detecting serial ports..."
    
    # List available serial ports
    if [ -d "/dev" ]; then
        echo ""
        echo "Available serial ports:"
        ls -1 /dev/tty* 2>/dev/null | grep -E "(USB|ACM)" || echo "  No USB serial ports found"
        echo ""
    fi
    
    read -p "Enter serial port (e.g., /dev/ttyUSB0): " serial_port
    
    if [ -z "$serial_port" ]; then
        print_warning "No port specified, using default: /dev/ttyUSB0"
        serial_port="/dev/ttyUSB0"
    fi
    
    MESHTASTIC_TYPE="serial"
    MESHTASTIC_PORT="$serial_port"
    MESHTASTIC_BAUD="921600"
    
    print_success "Serial configuration saved"
}

# Configure TCP connection
configure_tcp() {
    read -p "Enter Meshtastic device IP address [localhost]: " tcp_host
    tcp_host=${tcp_host:-localhost}
    
    read -p "Enter TCP port [4403]: " tcp_port
    tcp_port=${tcp_port:-4403}
    
    MESHTASTIC_TYPE="tcp"
    MESHTASTIC_HOST="$tcp_host"
    MESHTASTIC_PORT="$tcp_port"
    
    print_success "TCP configuration saved"
}

# Select plugins to enable
select_plugins() {
    print_header "Plugin Selection"
    
    echo "ZephyrGate uses plugins to provide different features."
    echo "Select which plugins you want to enable:"
    echo ""
    
    # Core plugins with descriptions
    declare -A plugins
    plugins["bot_service"]="Interactive bot with commands, games, and auto-response"
    plugins["emergency_service"]="Emergency SOS handling and incident management"
    plugins["bbs_service"]="Bulletin board system with mail and channels"
    plugins["weather_service"]="Weather conditions, forecasts, and alerts"
    plugins["email_service"]="Email gateway for sending/receiving via mesh"
    plugins["asset_service"]="Asset tracking with location monitoring"
    plugins["web_service"]="Web-based administration interface"
    
    # Default selections (recommended for most users)
    declare -A selected
    selected["bot_service"]=1
    selected["emergency_service"]=1
    selected["web_service"]=1
    
    # Display plugins
    local i=1
    declare -A plugin_order
    for plugin in "${!plugins[@]}"; do
        plugin_order[$i]=$plugin
        i=$((i+1))
    done
    
    # Sort and display
    for i in $(seq 1 ${#plugins[@]}); do
        plugin="${plugin_order[$i]}"
        desc="${plugins[$plugin]}"
        if [ "${selected[$plugin]}" = "1" ]; then
            echo "  [$i] [X] $plugin"
        else
            echo "  [$i] [ ] $plugin"
        fi
        echo "      $desc"
        echo ""
    done
    
    echo "Recommended plugins are pre-selected (marked with X)"
    echo ""
    read -p "Use recommended plugins? (Y/n) " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Nn]$ ]]; then
        print_info "Using recommended plugins"
    else
        # Custom selection
        echo ""
        echo "Enter plugin numbers to toggle (space-separated), or 'done' when finished:"
        while true; do
            read -p "> " input
            
            if [ "$input" = "done" ]; then
                break
            fi
            
            for num in $input; do
                if [ "$num" -ge 1 ] && [ "$num" -le ${#plugins[@]} ]; then
                    plugin="${plugin_order[$num]}"
                    if [ "${selected[$plugin]}" = "1" ]; then
                        selected[$plugin]=0
                        echo "  Disabled: $plugin"
                    else
                        selected[$plugin]=1
                        echo "  Enabled: $plugin"
                    fi
                fi
            done
        done
    fi
    
    # Build enabled plugins list
    ENABLED_PLUGINS=""
    for plugin in "${!selected[@]}"; do
        if [ "${selected[$plugin]}" = "1" ]; then
            if [ -z "$ENABLED_PLUGINS" ]; then
                ENABLED_PLUGINS="$plugin"
            else
                ENABLED_PLUGINS="$ENABLED_PLUGINS,$plugin"
            fi
        fi
    done
    
    echo ""
    print_success "Plugin selection complete"
    print_info "Enabled plugins: ${ENABLED_PLUGINS//,/, }"
}

# Create configuration file
create_config() {
    print_header "Creating Configuration"
    
    # Create config directory if it doesn't exist
    mkdir -p config
    mkdir -p data
    mkdir -p logs
    
    # Create config.yaml from template
    if [ -f "config/config.yaml" ]; then
        print_warning "config/config.yaml already exists"
        read -p "Overwrite it? (y/n) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Keeping existing configuration"
            return
        fi
    fi
    
    print_info "Creating config.yaml..."
    
    # Convert comma-separated plugins to YAML list
    PLUGIN_LIST=""
    IFS=',' read -ra PLUGINS <<< "$ENABLED_PLUGINS"
    for plugin in "${PLUGINS[@]}"; do
        PLUGIN_LIST="${PLUGIN_LIST}    - \"${plugin}\"\n"
    done
    
    # Create config file
    cat > config/config.yaml << EOF
# ZephyrGate Configuration
# Generated by installer on $(date)

app:
  name: "ZephyrGate"
  debug: false
  log_level: "INFO"

# Meshtastic interface configuration
meshtastic:
  interfaces:
    - id: "primary"
      type: "${MESHTASTIC_TYPE:-serial}"
EOF

    if [ "$MESHTASTIC_TYPE" = "serial" ]; then
        cat >> config/config.yaml << EOF
      port: "${MESHTASTIC_PORT:-/dev/ttyUSB0}"
      baud_rate: ${MESHTASTIC_BAUD:-921600}
EOF
    elif [ "$MESHTASTIC_TYPE" = "tcp" ]; then
        cat >> config/config.yaml << EOF
      host: "${MESHTASTIC_HOST:-localhost}"
      tcp_port: ${MESHTASTIC_PORT:-4403}
EOF
    fi

    cat >> config/config.yaml << EOF
  
  retry_interval: 30
  max_messages_per_minute: 20

# Database configuration
database:
  path: "data/zephyrgate.db"
  backup_interval: 86400

# Logging
logging:
  level: "INFO"
  console: true
  file: "logs/zephyrgate.log"
  max_file_size: 10485760
  backup_count: 5

# Plugin system
plugins:
  paths:
    - "plugins"
  
  auto_discover: true
  auto_load: true
  
  enabled_plugins:
$(echo -e "$PLUGIN_LIST")
  
  disabled_plugins: []
  
  health_check_interval: 60
  failure_threshold: 3

# Web interface (if web_service plugin is enabled)
web:
  host: "0.0.0.0"
  port: 8080
  auth:
    enabled: true
    default_username: "admin"
    default_password: "admin"

# Security
security:
  require_node_auth: false
  rate_limiting:
    enabled: true
    max_requests_per_minute: 60
EOF
    
    print_success "Configuration file created: config/config.yaml"
    print_warning "Default web admin credentials: admin/admin (change after first login!)"
}

# Create systemd service
create_service() {
    print_header "System Service Setup"
    
    echo "Would you like to install ZephyrGate as a system service?"
    echo "This will make ZephyrGate start automatically on boot."
    echo ""
    read -p "Install as system service? (y/n) " -n 1 -r
    echo
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Skipping service installation"
        return
    fi
    
    local service_file="/etc/systemd/system/zephyrgate.service"
    local install_dir=$(pwd)
    local user=$(whoami)
    
    print_info "Creating systemd service..."
    
    sudo tee "$service_file" > /dev/null << EOF
[Unit]
Description=ZephyrGate Meshtastic Gateway
After=network.target

[Service]
Type=simple
User=$user
WorkingDirectory=$install_dir
ExecStart=$install_dir/.venv/bin/python $install_dir/src/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    
    print_success "Service file created"
    
    print_info "Enabling service..."
    sudo systemctl daemon-reload
    sudo systemctl enable zephyrgate.service
    
    print_success "Service enabled"
    print_info "Service will start automatically on boot"
    print_info "Control with: sudo systemctl [start|stop|restart|status] zephyrgate"
}

# Display completion message
show_completion() {
    print_header "Installation Complete!"
    
    echo -e "${GREEN}ZephyrGate has been successfully installed!${NC}"
    echo ""
    echo "Next steps:"
    echo ""
    echo "  1. Review configuration:"
    echo "     nano config/config.yaml"
    echo ""
    echo "  2. Start ZephyrGate:"
    echo "     ./start.sh"
    echo ""
    echo "  3. Access web interface (if enabled):"
    echo "     http://localhost:8080"
    echo "     Username: admin"
    echo "     Password: admin"
    echo ""
    echo "  4. View logs:"
    echo "     tail -f logs/zephyrgate.log"
    echo ""
    echo "Documentation:"
    echo "  - Installation Guide: docs/INSTALLATION.md"
    echo "  - User Manual: docs/USER_MANUAL.md"
    echo "  - Admin Guide: docs/ADMIN_GUIDE.md"
    echo ""
    print_success "Happy meshing!"
}

# Main installation flow
main() {
    clear
    print_header "ZephyrGate Installation"
    
    echo "Welcome to the ZephyrGate installer!"
    echo "This script will guide you through the installation process."
    echo ""
    
    check_root
    detect_os
    check_requirements
    setup_venv
    configure_meshtastic
    select_plugins
    create_config
    create_service
    show_completion
}

# Run main installation
main
