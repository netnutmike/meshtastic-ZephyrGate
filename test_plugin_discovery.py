#!/usr/bin/env python3
"""
Quick test to verify plugin discovery works for all service plugins
"""

import sys
import asyncio
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from core.plugin_manager import PluginManager
from core.config import ConfigurationManager


async def test_discovery():
    """Test plugin discovery"""
    print("Testing plugin discovery...")
    
    # Load configuration
    config = ConfigurationManager()
    config.load_config()
    
    # Create plugin manager
    pm = PluginManager(config)
    
    # Discover plugins
    plugins = await pm.discover_plugins()
    
    print(f"\n✅ Discovered {len(plugins)} plugins:")
    for plugin_name in sorted(plugins):
        print(f"  - {plugin_name}")
    
    # Check for expected service plugins
    expected_plugins = [
        'bot_service',
        'emergency_service',
        'bbs_service',
        'weather_service',
        'email_service',
        'asset_service',
        'web_service',
        'ping_responder'
    ]
    
    print("\n📋 Checking for expected service plugins:")
    for plugin_name in expected_plugins:
        if plugin_name in plugins:
            print(f"  ✅ {plugin_name}")
        else:
            print(f"  ❌ {plugin_name} - NOT FOUND")
    
    # Get plugin info
    print("\n📄 Plugin manifests:")
    for plugin_name in sorted(plugins):
        try:
            manifest = pm.get_plugin_manifest(plugin_name)
            if manifest:
                print(f"  {plugin_name}: v{manifest.version} - {manifest.description}")
        except Exception as e:
            print(f"  {plugin_name}: Error loading manifest - {e}")
    
    print("\n✅ Plugin discovery test complete!")


if __name__ == "__main__":
    asyncio.run(test_discovery())
