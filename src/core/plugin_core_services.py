"""
Core Service Access Interfaces for Plugins

Provides controlled access to core ZephyrGate services with permission enforcement.
"""

import logging
from typing import Any, Dict, List, Optional, Set
from datetime import datetime
from enum import Enum

from ..models.message import Message, MessageType
from .plugin_interfaces import PluginMessage, PluginMessageType, PluginResponse


class Permission(Enum):
    """Permissions that plugins can request"""
    SEND_MESSAGES = "send_messages"
    DATABASE_ACCESS = "database_access"
    HTTP_REQUESTS = "http_requests"
    SCHEDULE_TASKS = "schedule_tasks"
    SYSTEM_STATE_READ = "system_state_read"
    INTER_PLUGIN_MESSAGING = "inter_plugin_messaging"
    CORE_SERVICE_ACCESS = "core_service_access"


class PermissionDeniedError(Exception):
    """Exception raised when a plugin attempts an action without permission"""
    pass


class PermissionManager:
    """Manages plugin permissions"""
    
    def __init__(self):
        self.plugin_permissions: Dict[str, Set[Permission]] = {}
        self.logger = logging.getLogger(__name__)
    
    def grant_permissions(self, plugin_name: str, permissions: List[str]):
        """
        Grant permissions to a plugin.
        
        Args:
            plugin_name: Name of the plugin
            permissions: List of permission strings
        """
        if plugin_name not in self.plugin_permissions:
            self.plugin_permissions[plugin_name] = set()
        
        for perm_str in permissions:
            try:
                perm = Permission(perm_str)
                self.plugin_permissions[plugin_name].add(perm)
                self.logger.debug(f"Granted {perm_str} to {plugin_name}")
            except ValueError:
                self.logger.warning(f"Unknown permission: {perm_str}")
    
    def revoke_permission(self, plugin_name: str, permission: Permission):
        """
        Revoke a permission from a plugin.
        
        Args:
            plugin_name: Name of the plugin
            permission: Permission to revoke
        """
        if plugin_name in self.plugin_permissions:
            self.plugin_permissions[plugin_name].discard(permission)
            self.logger.debug(f"Revoked {permission.value} from {plugin_name}")
    
    def has_permission(self, plugin_name: str, permission: Permission) -> bool:
        """
        Check if a plugin has a specific permission.
        
        Args:
            plugin_name: Name of the plugin
            permission: Permission to check
            
        Returns:
            True if plugin has the permission
        """
        return permission in self.plugin_permissions.get(plugin_name, set())
    
    def check_permission(self, plugin_name: str, permission: Permission):
        """
        Check permission and raise exception if not granted.
        
        Args:
            plugin_name: Name of the plugin
            permission: Permission to check
            
        Raises:
            PermissionDeniedError: If plugin doesn't have the permission
        """
        if not self.has_permission(plugin_name, permission):
            raise PermissionDeniedError(
                f"Plugin '{plugin_name}' does not have permission: {permission.value}"
            )
    
    def get_plugin_permissions(self, plugin_name: str) -> Set[Permission]:
        """
        Get all permissions for a plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Set of permissions
        """
        return self.plugin_permissions.get(plugin_name, set()).copy()
    
    def clear_plugin_permissions(self, plugin_name: str):
        """
        Clear all permissions for a plugin.
        
        Args:
            plugin_name: Name of the plugin
        """
        if plugin_name in self.plugin_permissions:
            del self.plugin_permissions[plugin_name]
            self.logger.debug(f"Cleared all permissions for {plugin_name}")


class SystemStateQuery:
    """Read-only interface for querying system state"""
    
    def __init__(self, plugin_manager, permission_manager: PermissionManager):
        self.plugin_manager = plugin_manager
        self.permission_manager = permission_manager
        self.logger = logging.getLogger(__name__)
    
    def get_node_info(self, plugin_name: str, node_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get information about a mesh node.
        
        Args:
            plugin_name: Name of the requesting plugin
            node_id: Node ID (None for local node)
            
        Returns:
            Node information dictionary or None if not found
            
        Raises:
            PermissionDeniedError: If plugin doesn't have permission
        """
        self.permission_manager.check_permission(plugin_name, Permission.SYSTEM_STATE_READ)
        
        # Get node info from plugin manager or mesh interface
        # This is a placeholder - actual implementation would query the mesh interface
        return {
            'node_id': node_id or 'local',
            'status': 'online',
            'last_seen': datetime.utcnow().isoformat()
        }
    
    def get_network_status(self, plugin_name: str) -> Dict[str, Any]:
        """
        Get current network status.
        
        Args:
            plugin_name: Name of the requesting plugin
            
        Returns:
            Network status dictionary
            
        Raises:
            PermissionDeniedError: If plugin doesn't have permission
        """
        self.permission_manager.check_permission(plugin_name, Permission.SYSTEM_STATE_READ)
        
        return {
            'connected': True,
            'node_count': 0,
            'channel': 0,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def get_plugin_list(self, plugin_name: str) -> List[str]:
        """
        Get list of running plugins.
        
        Args:
            plugin_name: Name of the requesting plugin
            
        Returns:
            List of plugin names
            
        Raises:
            PermissionDeniedError: If plugin doesn't have permission
        """
        self.permission_manager.check_permission(plugin_name, Permission.SYSTEM_STATE_READ)
        
        if hasattr(self.plugin_manager, 'get_running_plugins'):
            return self.plugin_manager.get_running_plugins()
        return []
    
    def get_plugin_status(self, plugin_name: str, target_plugin: str) -> Optional[Dict[str, Any]]:
        """
        Get status of another plugin.
        
        Args:
            plugin_name: Name of the requesting plugin
            target_plugin: Name of the plugin to query
            
        Returns:
            Plugin status dictionary or None if not found
            
        Raises:
            PermissionDeniedError: If plugin doesn't have permission
        """
        self.permission_manager.check_permission(plugin_name, Permission.SYSTEM_STATE_READ)
        
        if hasattr(self.plugin_manager, 'get_plugin_status'):
            return self.plugin_manager.get_plugin_status(target_plugin)
        return None


class MessageRoutingService:
    """Service for routing messages to the mesh network with permission enforcement"""
    
    def __init__(self, message_router, permission_manager: PermissionManager):
        self.message_router = message_router
        self.permission_manager = permission_manager
        self.logger = logging.getLogger(__name__)
    
    async def send_mesh_message(self, plugin_name: str, content: str,
                                destination: Optional[str] = None,
                                channel: Optional[int] = None) -> bool:
        """
        Send a message to the mesh network.
        
        Args:
            plugin_name: Name of the plugin sending the message
            content: Message content
            destination: Destination node ID (None for broadcast)
            channel: Channel number (None for default)
            
        Returns:
            True if message was queued successfully
            
        Raises:
            PermissionDeniedError: If plugin doesn't have permission
        """
        self.permission_manager.check_permission(plugin_name, Permission.SEND_MESSAGES)
        
        try:
            message = Message(
                id=f"{plugin_name}_{datetime.utcnow().timestamp()}",
                message_type=MessageType.TEXT,
                content=content,
                sender_id=plugin_name,
                recipient_id=destination,
                channel=channel or 0,
                timestamp=datetime.utcnow()
            )
            
            # Queue message through message router
            if hasattr(self.message_router, 'queue_outgoing_message'):
                await self.message_router.queue_outgoing_message(message)
                self.logger.info(f"Plugin {plugin_name} sent message to mesh")
                return True
            elif hasattr(self.message_router, 'send_message'):
                return await self.message_router.send_message(message)
            
            self.logger.warning("Message router doesn't support message sending")
            return False
            
        except Exception as e:
            self.logger.error(f"Failed to send mesh message from {plugin_name}: {e}")
            return False


class InterPluginMessaging:
    """Service for inter-plugin communication with permission enforcement"""
    
    def __init__(self, plugin_manager, permission_manager: PermissionManager):
        self.plugin_manager = plugin_manager
        self.permission_manager = permission_manager
        self.logger = logging.getLogger(__name__)
        self.message_handlers: Dict[str, List] = {}
    
    async def send_to_plugin(self, source_plugin: str, target_plugin: str,
                            message_type: str, data: Any) -> Optional[PluginResponse]:
        """
        Send a message to another plugin.
        
        Args:
            source_plugin: Name of the sending plugin
            target_plugin: Name of the target plugin
            message_type: Type of message
            data: Message data
            
        Returns:
            Response from target plugin or None
            
        Raises:
            PermissionDeniedError: If plugin doesn't have permission
        """
        self.permission_manager.check_permission(source_plugin, Permission.INTER_PLUGIN_MESSAGING)
        
        message = PluginMessage(
            type=PluginMessageType.DIRECT_MESSAGE,
            source_plugin=source_plugin,
            target_plugin=target_plugin,
            data=data,
            metadata={'message_type': message_type}
        )
        
        # Deliver message to target plugin
        if target_plugin in self.message_handlers:
            for handler in self.message_handlers[target_plugin]:
                try:
                    result = await handler(message)
                    if result is not None:
                        return PluginResponse(
                            request_id=message.id,
                            success=True,
                            data=result
                        )
                except Exception as e:
                    self.logger.error(f"Error delivering message to {target_plugin}: {e}")
                    return PluginResponse(
                        request_id=message.id,
                        success=False,
                        error=str(e)
                    )
        
        self.logger.warning(f"No handlers registered for plugin {target_plugin}")
        return None
    
    async def broadcast_to_plugins(self, source_plugin: str, message_type: str,
                                   data: Any) -> List[PluginResponse]:
        """
        Broadcast a message to all plugins.
        
        Args:
            source_plugin: Name of the sending plugin
            message_type: Type of message
            data: Message data
            
        Returns:
            List of responses from plugins
            
        Raises:
            PermissionDeniedError: If plugin doesn't have permission
        """
        self.permission_manager.check_permission(source_plugin, Permission.INTER_PLUGIN_MESSAGING)
        
        message = PluginMessage(
            type=PluginMessageType.BROADCAST,
            source_plugin=source_plugin,
            data=data,
            metadata={'message_type': message_type}
        )
        
        responses = []
        for target_plugin, handlers in self.message_handlers.items():
            if target_plugin == source_plugin:
                continue  # Don't send to self
            
            for handler in handlers:
                try:
                    result = await handler(message)
                    if result is not None:
                        responses.append(PluginResponse(
                            request_id=message.id,
                            success=True,
                            data=result,
                            metadata={'target_plugin': target_plugin}
                        ))
                except Exception as e:
                    self.logger.error(f"Error broadcasting to {target_plugin}: {e}")
                    responses.append(PluginResponse(
                        request_id=message.id,
                        success=False,
                        error=str(e),
                        metadata={'target_plugin': target_plugin}
                    ))
        
        return responses
    
    def register_message_handler(self, plugin_name: str, handler):
        """
        Register a message handler for a plugin.
        
        Args:
            plugin_name: Name of the plugin
            handler: Async function that handles PluginMessage
        """
        if plugin_name not in self.message_handlers:
            self.message_handlers[plugin_name] = []
        self.message_handlers[plugin_name].append(handler)
        self.logger.debug(f"Registered message handler for {plugin_name}")
    
    def unregister_message_handler(self, plugin_name: str, handler):
        """
        Unregister a message handler for a plugin.
        
        Args:
            plugin_name: Name of the plugin
            handler: Handler to remove
        """
        if plugin_name in self.message_handlers:
            try:
                self.message_handlers[plugin_name].remove(handler)
                self.logger.debug(f"Unregistered message handler for {plugin_name}")
            except ValueError:
                pass


class CoreServiceAccess:
    """
    Main interface for plugin access to core services.
    
    Provides controlled access to:
    - Message routing to mesh network
    - System state queries
    - Inter-plugin messaging
    
    All access is controlled by the permission system.
    """
    
    def __init__(self, plugin_manager, message_router):
        self.plugin_manager = plugin_manager
        self.message_router = message_router
        self.permission_manager = PermissionManager()
        
        # Initialize service interfaces
        self.system_state = SystemStateQuery(plugin_manager, self.permission_manager)
        self.message_routing = MessageRoutingService(message_router, self.permission_manager)
        self.inter_plugin = InterPluginMessaging(plugin_manager, self.permission_manager)
        
        self.logger = logging.getLogger(__name__)
    
    def initialize_plugin_permissions(self, plugin_name: str, permissions: List[str]):
        """
        Initialize permissions for a plugin from its manifest.
        
        Args:
            plugin_name: Name of the plugin
            permissions: List of permission strings from manifest
        """
        self.permission_manager.grant_permissions(plugin_name, permissions)
        self.logger.info(f"Initialized permissions for {plugin_name}: {permissions}")
    
    def cleanup_plugin(self, plugin_name: str):
        """
        Clean up plugin resources when plugin is stopped.
        
        Args:
            plugin_name: Name of the plugin
        """
        self.permission_manager.clear_plugin_permissions(plugin_name)
        # Clear any message handlers
        if plugin_name in self.inter_plugin.message_handlers:
            del self.inter_plugin.message_handlers[plugin_name]
        self.logger.info(f"Cleaned up core service access for {plugin_name}")


__all__ = [
    'Permission',
    'PermissionDeniedError',
    'PermissionManager',
    'SystemStateQuery',
    'MessageRoutingService',
    'InterPluginMessaging',
    'CoreServiceAccess',
]
