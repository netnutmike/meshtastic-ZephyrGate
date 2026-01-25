"""
Bot Service Plugin Package

Wraps the interactive bot service as a plugin for the ZephyrGate plugin system.
"""

# CRITICAL: Add src to path BEFORE any imports
import sys
from pathlib import Path
_src_path = Path(__file__).parent.parent.parent / "src"
if str(_src_path) not in sys.path:
    sys.path.insert(0, str(_src_path))

from .plugin import BotServicePlugin

__all__ = ['BotServicePlugin']
