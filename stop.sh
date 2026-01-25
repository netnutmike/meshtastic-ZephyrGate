#!/bin/bash
#
# ZephyrGate Stop Script
# Simple script to stop ZephyrGate gracefully
#

# Colors
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${YELLOW}Stopping ZephyrGate...${NC}"

# Find ZephyrGate process
PID=$(pgrep -f "python.*src/main.py")

if [ -z "$PID" ]; then
    echo -e "${RED}ZephyrGate is not running${NC}"
    exit 0
fi

# Send SIGTERM for graceful shutdown
echo "Sending shutdown signal to process $PID..."
kill -TERM $PID

# Wait for process to stop (max 30 seconds)
for i in {1..30}; do
    if ! ps -p $PID > /dev/null 2>&1; then
        echo -e "${GREEN}ZephyrGate stopped successfully${NC}"
        exit 0
    fi
    sleep 1
done

# Force kill if still running
echo -e "${YELLOW}Process did not stop gracefully, forcing shutdown...${NC}"
kill -KILL $PID

echo -e "${GREEN}ZephyrGate stopped${NC}"
