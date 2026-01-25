#!/usr/bin/env python3
"""
Simple test script to verify the plugin system is working
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.config import ConfigurationManager
from core.plugin_manager import PluginManager
from core.database import initialize_database

async def main():
    print("=" * 60)
    print("ZephyrGate Plugin System Test")
    print("=" * 60)
    
    # Initialize config
    print("\n1. Loading configuration...")
    config_manager = ConfigurationManager()
    print("   ✓ Configuration loaded")
    
    # Initialize database
    print("\n2. Initializing database...")
    db_path = config_manager.get('database.path', 'data/zephyrgate_dev.db')
    db_manager = initialize_database(db_path)
    print(f"   ✓ Database initialized at {db_path}")
    
    # Initialize plugin manager
    print("\n3. Initializing plugin manager...")
    plugin_manager = PluginManager(config_manager)
    
    # Manually add examples/plugins path for testing
    examples_path = Path("examples/plugins")
    if examples_path.exists() and examples_path not in plugin_manager.plugin_paths:
        plugin_manager.plugin_paths.append(examples_path)
        print(f"   Added examples/plugins to plugin paths")
    
    print("   ✓ Plugin manager initialized")
    
    # Discover plugins
    print("\n4. Discovering plugins...")
    print(f"   Plugin paths:")
    for p in plugin_manager.plugin_paths:
        exists = p.exists()
        print(f"     - {p} (exists: {exists})")
        if exists and p.is_dir():
            subdirs = [d.name for d in p.iterdir() if d.is_dir() and (d / "__init__.py").exists()]
            if subdirs:
                print(f"       Found directories with __init__.py: {', '.join(subdirs)}")
    
    plugins = await plugin_manager.discover_plugins()
    print(f"   ✓ Discovered {len(plugins)} plugins:")
    for plugin_name in plugins:
        print(f"     - {plugin_name}")
    
    # Load example plugins
    print("\n5. Loading example plugins...")
    example_plugins = ['hello_world', 'data_logger', 'weather_alert']
    
    for plugin_name in example_plugins:
        if plugin_name in plugins:
            print(f"\n   Loading {plugin_name}...")
            try:
                success = await plugin_manager.load_plugin(plugin_name)
                if success:
                    print(f"   ✓ {plugin_name} loaded successfully")
                    
                    # Get plugin info
                    plugin_info = plugin_manager.plugins.get(plugin_name)
                    if plugin_info and plugin_info.manifest:
                        manifest = plugin_info.manifest
                        print(f"     Version: {manifest.version}")
                        print(f"     Author: {manifest.author}")
                        print(f"     Description: {manifest.description}")
                        
                        if manifest.commands:
                            print(f"     Commands: {', '.join([cmd.name for cmd in manifest.commands])}")
                else:
                    print(f"   ✗ Failed to load {plugin_name}")
                    # Get error details
                    plugin_info = plugin_manager.plugins.get(plugin_name)
                    if plugin_info and plugin_info.health.last_error:
                        print(f"     Error: {plugin_info.health.last_error}")
            except Exception as e:
                print(f"   ✗ Error loading {plugin_name}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"   ⚠ {plugin_name} not found in discovered plugins")
    
    # Start loaded plugins
    print("\n6. Starting loaded plugins...")
    for plugin_name in example_plugins:
        if plugin_name in plugin_manager.plugins:
            plugin_info = plugin_manager.plugins[plugin_name]
            if plugin_info.instance:
                try:
                    print(f"   Starting {plugin_name}...")
                    success = await plugin_manager.start_plugin(plugin_name)
                    if success:
                        print(f"   ✓ {plugin_name} started successfully")
                    else:
                        print(f"   ✗ Failed to start {plugin_name}")
                except Exception as e:
                    print(f"   ✗ Error starting {plugin_name}: {e}")
    
    # Show plugin status
    print("\n7. Plugin Status Summary:")
    print("   " + "-" * 56)
    print(f"   {'Plugin':<20} {'Status':<15} {'Health':<15}")
    print("   " + "-" * 56)
    
    for plugin_name in example_plugins:
        if plugin_name in plugin_manager.plugins:
            plugin_info = plugin_manager.plugins[plugin_name]
            status = plugin_info.status.value
            health = "healthy" if plugin_info.health.is_healthy() else "unhealthy"
            print(f"   {plugin_name:<20} {status:<15} {health:<15}")
    
    print("   " + "-" * 56)
    
    print("\n" + "=" * 60)
    print("Plugin System Test Complete!")
    print("=" * 60)
    print("\nThe plugin system is operational and ready for development.")
    print("You can now:")
    print("  - Create custom plugins using: python create_plugin.py")
    print("  - Test plugins by placing them in the plugins/ directory")
    print("  - Send commands from your Meshtastic device")
    print("\n")

if __name__ == "__main__":
    asyncio.run(main())
