#!/bin/bash
#
# ZephyrGate Start Script
# Simple script to start ZephyrGate with virtual environment
#

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}Starting ZephyrGate...${NC}"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo -e "${RED}Error: Virtual environment not found${NC}"
    echo "Please run ./install.sh first"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Check if config exists
if [ ! -f "config/config.yaml" ]; then
    echo -e "${RED}Error: Configuration file not found${NC}"
    echo "Please run ./install.sh first"
    exit 1
fi

# Start ZephyrGate
echo -e "${GREEN}ZephyrGate is starting...${NC}"
echo "Press Ctrl+C to stop"
echo ""

python src/main.py
