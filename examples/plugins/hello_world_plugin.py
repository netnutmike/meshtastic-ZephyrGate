"""
Hello World Plugin - Example of using EnhancedPlugin

This is a minimal example plugin that demonstrates:
- Command registration
- Message handling
- Configuration access
- Mesh messaging
"""

from src.core.enhanced_plugin import EnhancedPlugin
from src.core.plugin_manager import PluginMetadata, PluginPriority


class HelloWorldPlugin(EnhancedPlugin):
    """
    A simple hello world plugin that responds to commands.
    """
    
    async def initialize(self) -> bool:
        """Initialize the plugin"""
        self.logger.info("Initializing Hello World Plugin")
        
        # Register commands
        self.register_command(
            "hello",
            self.handle_hello_command,
            "Say hello to the mesh network",
            priority=100
        )
        
        self.register_command(
            "greet",
            self.handle_greet_command,
            "Greet a specific user",
            priority=100
        )
        
        # Register a message handler (optional)
        self.register_message_handler(self.handle_message, priority=200)
        
        # Register a scheduled task (optional)
        greeting_interval = self.get_config("greeting_interval", 3600)
        self.register_scheduled_task(
            "periodic_greeting",
            greeting_interval,
            self.send_periodic_greeting
        )
        
        return True
    
    async def handle_hello_command(self, args, context):
        """Handle the 'hello' command"""
        sender = context.get('sender_id', 'unknown')
        
        # Get custom greeting from config
        greeting = self.get_config("greeting_message", "Hello")
        
        response = f"{greeting}, {sender}! Welcome to the mesh network."
        
        # Store interaction count
        count = await self.retrieve_data("interaction_count", 0)
        count += 1
        await self.store_data("interaction_count", count)
        
        response += f" (Interaction #{count})"
        
        return response
    
    async def handle_greet_command(self, args, context):
        """Handle the 'greet' command with a specific user"""
        if not args:
            return "Usage: greet <name>"
        
        name = " ".join(args)
        greeting = self.get_config("greeting_message", "Hello")
        
        return f"{greeting}, {name}! Nice to meet you on the mesh."
    
    async def handle_message(self, message, context):
        """Handle incoming messages (optional processing)"""
        # Example: Log all messages containing "hello"
        if "hello" in message.content.lower():
            self.logger.info(f"Detected greeting from {message.sender_id}")
        
        # Return None to allow other handlers to process
        return None
    
    async def send_periodic_greeting(self):
        """Send a periodic greeting to the mesh"""
        enabled = self.get_config("periodic_greeting_enabled", False)
        
        if enabled:
            greeting = self.get_config("greeting_message", "Hello")
            await self.send_message(f"{greeting} from Hello World Plugin!")
            self.logger.info("Sent periodic greeting")
    
    def get_metadata(self) -> PluginMetadata:
        """Get plugin metadata"""
        return PluginMetadata(
            name="hello_world",
            version="1.0.0",
            description="A simple hello world plugin demonstrating EnhancedPlugin features",
            author="ZephyrGate Team",
            priority=PluginPriority.NORMAL,
            enabled=True
        )


# Example configuration for this plugin (in config.yaml):
"""
plugins:
  hello_world:
    enabled: true
    greeting_message: "Greetings"
    greeting_interval: 3600  # 1 hour
    periodic_greeting_enabled: false
"""
