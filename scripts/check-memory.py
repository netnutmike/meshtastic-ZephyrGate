#!/usr/bin/env python3
"""
Memory Usage Checker for ZephyrGate

Provides accurate memory usage information, especially on macOS where
standard tools can be misleading.
"""

import psutil
import sys
from pathlib import Path

def format_bytes(bytes_value):
    """Format bytes to human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} PB"

def get_zephyrgate_process():
    """Find the ZephyrGate main process"""
    for proc in psutil.process_iter(['pid', 'name', 'memory_info', 'cmdline', 'cpu_percent']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if 'main.py' in cmdline and 'zephyrgate' in cmdline.lower():
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return None

def check_memory():
    """Check system and ZephyrGate memory usage"""
    print("=" * 70)
    print("ZephyrGate Memory Usage Report")
    print("=" * 70)
    
    # System memory
    memory = psutil.virtual_memory()
    print("\n📊 System Memory:")
    print(f"  Total:     {format_bytes(memory.total)}")
    print(f"  Available: {format_bytes(memory.available)}")
    print(f"  Used:      {format_bytes(memory.used)}")
    
    # Platform-specific accurate calculation
    if hasattr(memory, 'active') and hasattr(memory, 'wired'):
        # macOS
        truly_used = memory.active + memory.wired
        accurate_percent = (truly_used / memory.total) * 100
        
        print(f"\n  macOS Breakdown:")
        print(f"    Active:   {format_bytes(memory.active)} (in use)")
        print(f"    Wired:    {format_bytes(memory.wired)} (kernel)")
        print(f"    Inactive: {format_bytes(memory.inactive)} (cached)")
        print(f"    Free:     {format_bytes(memory.free)}")
        
        print(f"\n  Standard Percent:  {memory.percent:.1f}% (misleading)")
        print(f"  Accurate Percent:  {accurate_percent:.1f}% ✅")
        
        if accurate_percent > 80:
            status = "🔴 CRITICAL"
        elif accurate_percent > 60:
            status = "⚠️  WARNING"
        else:
            status = "✅ HEALTHY"
        print(f"  Status: {status}")
    else:
        # Linux/Windows
        print(f"\n  Memory Percent: {memory.percent:.1f}%")
        if memory.percent > 90:
            status = "🔴 CRITICAL"
        elif memory.percent > 70:
            status = "⚠️  WARNING"
        else:
            status = "✅ HEALTHY"
        print(f"  Status: {status}")
    
    # Swap memory
    if hasattr(psutil, 'swap_memory'):
        swap = psutil.swap_memory()
        print(f"\n💾 Swap Memory:")
        print(f"  Total: {format_bytes(swap.total)}")
        print(f"  Used:  {format_bytes(swap.used)}")
        print(f"  Free:  {format_bytes(swap.free)}")
        print(f"  Percent: {swap.percent:.1f}%")
        
        if swap.percent > 80:
            status = "🔴 HIGH PRESSURE"
        elif swap.percent > 60:
            status = "⚠️  MODERATE PRESSURE"
        else:
            status = "✅ LOW PRESSURE"
        print(f"  Status: {status}")
    
    # ZephyrGate process
    print(f"\n🚀 ZephyrGate Process:")
    proc = get_zephyrgate_process()
    
    if proc:
        mem_info = proc.memory_info()
        print(f"  PID:  {proc.pid}")
        print(f"  RSS:  {format_bytes(mem_info.rss)} (physical memory)")
        print(f"  VMS:  {format_bytes(mem_info.vms)} (virtual memory)")
        
        # Calculate percentage of total RAM
        rss_percent = (mem_info.rss / memory.total) * 100
        print(f"  % of Total RAM: {rss_percent:.2f}%")
        
        # CPU usage
        try:
            cpu_percent = proc.cpu_percent(interval=1)
            print(f"  CPU: {cpu_percent:.1f}%")
        except:
            pass
        
        if rss_percent > 10:
            status = "⚠️  HIGH"
        elif rss_percent > 5:
            status = "⚠️  MODERATE"
        else:
            status = "✅ NORMAL"
        print(f"  Status: {status}")
    else:
        print("  ❌ Not running")
    
    # Top memory consumers
    print(f"\n🔝 Top 5 Memory Consumers:")
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'memory_info']):
        try:
            if proc.info['memory_info'] is not None:
                mem_info = proc.info['memory_info']
                processes.append((proc.info['name'], proc.info['pid'], mem_info.rss))
        except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
            pass
    
    processes.sort(key=lambda x: x[2], reverse=True)
    for i, (name, pid, rss) in enumerate(processes[:5], 1):
        rss_percent = (rss / memory.total) * 100
        print(f"  {i}. {name[:30]:30} {format_bytes(rss):>12} ({rss_percent:.1f}%)")
    
    print("\n" + "=" * 70)
    
    # Recommendations
    if hasattr(memory, 'active') and hasattr(memory, 'wired'):
        truly_used = memory.active + memory.wired
        accurate_percent = (truly_used / memory.total) * 100
        
        if accurate_percent > 80:
            print("\n⚠️  RECOMMENDATIONS:")
            print("  - Close unused applications")
            print("  - Restart memory-intensive applications")
            print("  - Consider adding more RAM")
    
    if hasattr(psutil, 'swap_memory'):
        swap = psutil.swap_memory()
        if swap.percent > 70:
            print("\n⚠️  HIGH SWAP USAGE DETECTED:")
            print("  - System is under memory pressure")
            print("  - Close unused browser tabs and applications")
            print("  - Restart the system if performance is degraded")

if __name__ == '__main__':
    try:
        check_memory()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
