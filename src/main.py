"""
ZephyrGate Main Application Entry Point

This is the main entry point for the ZephyrGate unified Meshtastic gateway application.
It initializes all core systems and starts the application.
"""

import asyncio
import signal
import sys
from pathlib import Path

# Add src to Python path
sys.path.insert(0, str(Path(__file__).parent))

from core.config import ConfigurationManager
from core.logging import initialize_logging, get_logger
from core.database import initialize_database


class ZephyrGateApplication:
    """Main ZephyrGate application class"""
    
    def __init__(self):
        self.config_manager = None
        self.db_manager = None
        self.logger = None
        self.running = False
        self.shutdown_event = asyncio.Event()
    
    async def initialize(self):
        """Initialize all application components"""
        print("Initializing ZephyrGate...")
        
        # Initialize configuration
        self.config_manager = ConfigurationManager()
        self.config_manager.load_config()
        
        # Initialize logging
        initialize_logging(self.config_manager.config)
        self.logger = get_logger('main')
        
        self.logger.info("ZephyrGate starting up...")
        self.logger.info(f"Version: {self.config_manager.get('app.version', 'unknown')}")
        self.logger.info(f"Debug mode: {self.config_manager.get('app.debug', False)}")
        
        # Initialize database
        db_path = self.config_manager.get('database.path', 'data/zephyrgate.db')
        max_connections = self.config_manager.get('database.max_connections', 10)
        self.db_manager = initialize_database(db_path, max_connections)
        
        self.logger.info("Core systems initialized successfully")
    
    async def start(self):
        """Start the application"""
        await self.initialize()
        
        self.running = True
        self.logger.info("ZephyrGate is now running")
        
        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
        
        try:
            # Main application loop
            await self._main_loop()
        except Exception as e:
            self.logger.error(f"Application error: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()
    
    async def _main_loop(self):
        """Main application event loop"""
        self.logger.info("Entering main application loop")
        
        # Wait for shutdown signal
        await self.shutdown_event.wait()
        
        self.logger.info("Shutdown signal received")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}")
        self.shutdown_event.set()
    
    async def shutdown(self):
        """Shutdown the application gracefully"""
        if not self.running:
            return
        
        self.logger.info("Shutting down ZephyrGate...")
        self.running = False
        
        # Close database connections
        if self.db_manager:
            self.db_manager.close()
        
        self.logger.info("ZephyrGate shutdown complete")


async def main():
    """Main entry point"""
    app = ZephyrGateApplication()
    
    try:
        await app.start()
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Application failed to start: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the application
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nApplication interrupted")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)