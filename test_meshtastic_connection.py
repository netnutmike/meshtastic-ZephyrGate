#!/usr/bin/env python3
"""
Simple test script to verify Meshtastic device connection
"""

import meshtastic.serial_interface
import time

print("Attempting to connect to Meshtastic device...")
print("Device: /dev/cu.usbmodem9070698283041")

try:
    # Try to connect
    interface = meshtastic.serial_interface.SerialInterface(
        devPath="/dev/cu.usbmodem9070698283041"
    )
    
    print("Connection initiated...")
    
    # Wait for connection
    time.sleep(5)
    
    if interface.myInfo:
        print(f"✓ Connected successfully!")
        print(f"Node ID: {interface.myInfo.my_node_num}")
        print(f"Device: {interface.myInfo}")
    else:
        print("✗ Connection failed - no device info received")
    
    # Close connection
    interface.close()
    print("Connection closed")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
