"""
JS8Call Integration Service for ZephyrGate

Provides JS8Call TCP API integration for the BBS system, including:
- TCP connection to JS8Call application
- Message processing and group filtering
- Urgent message notification to mesh network
- Message storage in BBS system
"""

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Callable
from dataclasses import dataclass

from services.bbs.models import JS8CallMessage, JS8CallPriority
from services.bbs.database import get_bbs_database


@dataclass
class JS8CallConfig:
    """JS8Call integration configuration"""
    enabled: bool = False
    host: str = "localhost"
    port: int = 2442
    monitored_groups: List[str] = None
    urgent_keywords: List[str] = None
    emergency_keywords: List[str] = None
    auto_forward_urgent: bool = True
    auto_forward_emergency: bool = True
    reconnect_interval: int = 30
    message_timeout: int = 300
    
    def __post_init__(self):
        if self.monitored_groups is None:
            self.monitored_groups = ["@ALLCALL", "@CQ"]
        if self.urgent_keywords is None:
            self.urgent_keywords = ["urgent", "priority", "important"]
        if self.emergency_keywords is None:
            self.emergency_keywords = ["emergency", "mayday", "sos", "help"]


class JS8CallClient:
    """JS8Call TCP API client"""
    
    def __init__(self, config: JS8CallConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self.running = False
        self.message_handlers: List[Callable] = []
        self.reconnect_task: Optional[asyncio.Task] = None
        
    async def connect(self) -> bool:
        """Connect to JS8Call TCP API"""
        try:
            self.logger.info(f"Connecting to JS8Call at {self.config.host}:{self.config.port}")
            
            self.reader, self.writer = await asyncio.open_connection(
                self.config.host, self.config.port
            )
            
            self.connected = True
            self.logger.info("Connected to JS8Call TCP API")
            
            # Send initial configuration
            await self._send_command({
                "type": "RIG.GET_FREQ"
            })
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to JS8Call: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from JS8Call"""
        self.running = False
        self.connected = False
        
        if self.reconnect_task:
            self.reconnect_task.cancel()
            self.reconnect_task = None
        
        if self.writer:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except Exception as e:
                self.logger.error(f"Error closing JS8Call connection: {e}")
            finally:
                self.writer = None
                self.reader = None
        
        self.logger.info("Disconnected from JS8Call")
    
    async def _send_command(self, command: Dict[str, Any]):
        """Send command to JS8Call"""
        if not self.connected or not self.writer:
            return
        
        try:
            message = json.dumps(command) + '\n'
            self.writer.write(message.encode())
            await self.writer.drain()
            
        except Exception as e:
            self.logger.error(f"Failed to send JS8Call command: {e}")
            self.connected = False
    
    async def _read_messages(self):
        """Read messages from JS8Call"""
        if not self.reader:
            return
        
        try:
            while self.running and self.connected:
                line = await self.reader.readline()
                if not line:
                    self.logger.warning("JS8Call connection closed")
                    self.connected = False
                    break
                
                try:
                    message = json.loads(line.decode().strip())
                    await self._handle_js8call_message(message)
                    
                except json.JSONDecodeError as e:
                    self.logger.error(f"Invalid JSON from JS8Call: {e}")
                except Exception as e:
                    self.logger.error(f"Error processing JS8Call message: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error reading from JS8Call: {e}")
            self.connected = False
    
    async def _handle_js8call_message(self, message: Dict[str, Any]):
        """Handle incoming JS8Call message"""
        try:
            msg_type = message.get("type", "")
            
            if msg_type == "RX.DIRECTED":
                await self._process_directed_message(message)
            elif msg_type == "RX.ACTIVITY":
                await self._process_activity_message(message)
            elif msg_type == "RIG.FREQ":
                self._process_frequency_update(message)
            
        except Exception as e:
            self.logger.error(f"Error handling JS8Call message: {e}")
    
    async def _process_directed_message(self, message: Dict[str, Any]):
        """Process directed JS8Call message"""
        try:
            params = message.get("params", {})
            callsign = params.get("FROM", "")
            to_group = params.get("TO", "")
            text = params.get("TEXT", "")
            frequency = params.get("FREQ", "")
            
            # Check if this is a monitored group
            if not self._is_monitored_group(to_group):
                return
            
            # Determine message priority
            priority = self._determine_priority(text)
            
            # Create JS8Call message object
            js8_message = JS8CallMessage(
                callsign=callsign,
                group=to_group,
                message=text,
                frequency=str(frequency),
                priority=priority,
                timestamp=datetime.utcnow()
            )
            
            # Notify handlers
            for handler in self.message_handlers:
                try:
                    await handler(js8_message)
                except Exception as e:
                    self.logger.error(f"Error in JS8Call message handler: {e}")
            
            self.logger.info(f"JS8Call directed message: {callsign} -> {to_group}: {text}")
            
        except Exception as e:
            self.logger.error(f"Error processing JS8Call directed message: {e}")
    
    async def _process_activity_message(self, message: Dict[str, Any]):
        """Process JS8Call activity message"""
        try:
            params = message.get("params", {})
            callsign = params.get("FROM", "")
            text = params.get("TEXT", "")
            frequency = params.get("FREQ", "")
            
            # Only process if it contains monitored keywords or groups
            if not self._contains_monitored_content(text):
                return
            
            # Determine message priority
            priority = self._determine_priority(text)
            
            # Create JS8Call message object
            js8_message = JS8CallMessage(
                callsign=callsign,
                group="ACTIVITY",
                message=text,
                frequency=str(frequency),
                priority=priority,
                timestamp=datetime.utcnow()
            )
            
            # Notify handlers
            for handler in self.message_handlers:
                try:
                    await handler(js8_message)
                except Exception as e:
                    self.logger.error(f"Error in JS8Call message handler: {e}")
            
            self.logger.info(f"JS8Call activity: {callsign}: {text}")
            
        except Exception as e:
            self.logger.error(f"Error processing JS8Call activity message: {e}")
    
    def _process_frequency_update(self, message: Dict[str, Any]):
        """Process frequency update from JS8Call"""
        try:
            params = message.get("params", {})
            frequency = params.get("FREQ", 0)
            self.logger.debug(f"JS8Call frequency: {frequency} Hz")
            
        except Exception as e:
            self.logger.error(f"Error processing frequency update: {e}")
    
    def _is_monitored_group(self, group: str) -> bool:
        """Check if group is being monitored"""
        if not group:
            return False
        
        group_upper = group.upper()
        for monitored in self.config.monitored_groups:
            if monitored.upper() == group_upper:
                return True
        
        return False
    
    def _contains_monitored_content(self, text: str) -> bool:
        """Check if text contains monitored keywords or groups"""
        if not text:
            return False
        
        text_lower = text.lower()
        
        # Check for monitored groups mentioned in text
        for group in self.config.monitored_groups:
            if group.lower() in text_lower:
                return True
        
        # Check for urgent/emergency keywords
        for keyword in self.config.urgent_keywords + self.config.emergency_keywords:
            if keyword.lower() in text_lower:
                return True
        
        return False
    
    def _determine_priority(self, text: str) -> JS8CallPriority:
        """Determine message priority based on content"""
        if not text:
            return JS8CallPriority.NORMAL
        
        text_lower = text.lower()
        
        # Check for emergency keywords
        for keyword in self.config.emergency_keywords:
            if keyword.lower() in text_lower:
                return JS8CallPriority.EMERGENCY
        
        # Check for urgent keywords
        for keyword in self.config.urgent_keywords:
            if keyword.lower() in text_lower:
                return JS8CallPriority.URGENT
        
        return JS8CallPriority.NORMAL
    
    def add_message_handler(self, handler: Callable):
        """Add message handler"""
        self.message_handlers.append(handler)
    
    def remove_message_handler(self, handler: Callable):
        """Remove message handler"""
        if handler in self.message_handlers:
            self.message_handlers.remove(handler)
    
    async def start(self):
        """Start JS8Call client"""
        self.running = True
        
        while self.running:
            try:
                if not self.connected:
                    if await self.connect():
                        # Start reading messages
                        await self._read_messages()
                    else:
                        # Wait before retry
                        await asyncio.sleep(self.config.reconnect_interval)
                else:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                self.logger.error(f"Error in JS8Call client: {e}")
                self.connected = False
                await asyncio.sleep(self.config.reconnect_interval)
    
    async def stop(self):
        """Stop JS8Call client"""
        self.running = False
        await self.disconnect()


class JS8CallService:
    """JS8Call integration service for BBS"""
    
    def __init__(self, config: JS8CallConfig, mesh_callback: Optional[Callable] = None):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.client: Optional[JS8CallClient] = None
        self.db = get_bbs_database()
        self.mesh_callback = mesh_callback  # Callback to send messages to mesh
        self.running = False
        self.client_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start JS8Call service"""
        if not self.config.enabled:
            self.logger.info("JS8Call integration disabled")
            return
        
        self.logger.info("Starting JS8Call integration service")
        
        try:
            self.client = JS8CallClient(self.config)
            self.client.add_message_handler(self._handle_js8call_message)
            
            self.running = True
            self.client_task = asyncio.create_task(self.client.start())
            
            self.logger.info("JS8Call service started")
            
        except Exception as e:
            self.logger.error(f"Failed to start JS8Call service: {e}")
            await self.stop()
    
    async def stop(self):
        """Stop JS8Call service"""
        self.logger.info("Stopping JS8Call service")
        self.running = False
        
        if self.client_task:
            self.client_task.cancel()
            try:
                await self.client_task
            except asyncio.CancelledError:
                pass
            self.client_task = None
        
        if self.client:
            await self.client.stop()
            self.client = None
        
        self.logger.info("JS8Call service stopped")
    
    async def _handle_js8call_message(self, js8_message: JS8CallMessage):
        """Handle JS8Call message"""
        try:
            # Store message in BBS database
            stored_message = self.db.store_js8call_message(
                js8_message.callsign,
                js8_message.group,
                js8_message.message,
                js8_message.frequency,
                js8_message.priority.value
            )
            
            if stored_message:
                self.logger.info(f"Stored JS8Call message from {js8_message.callsign}")
                
                # Check if message should be forwarded to mesh
                if self._should_forward_to_mesh(js8_message):
                    await self._forward_to_mesh(js8_message)
            
        except Exception as e:
            self.logger.error(f"Error handling JS8Call message: {e}")
    
    def _should_forward_to_mesh(self, js8_message: JS8CallMessage) -> bool:
        """Determine if message should be forwarded to mesh network"""
        if js8_message.is_emergency() and self.config.auto_forward_emergency:
            return True
        
        if js8_message.is_urgent() and self.config.auto_forward_urgent:
            return True
        
        return False
    
    async def _forward_to_mesh(self, js8_message: JS8CallMessage):
        """Forward JS8Call message to mesh network"""
        try:
            if not self.mesh_callback:
                self.logger.warning("No mesh callback configured for JS8Call forwarding")
                return
            
            # Generate mesh message
            mesh_message = js8_message.generate_mesh_message()
            
            # Send to mesh via callback
            await self.mesh_callback(mesh_message, "js8call_bridge")
            
            # Mark as forwarded in database
            if js8_message.id:
                self.db.mark_js8call_message_forwarded(js8_message.id)
            
            # Mark as forwarded in object
            js8_message.forwarded_to_mesh = True
            
            self.logger.info(f"Forwarded JS8Call message to mesh: {js8_message.callsign}")
            
        except Exception as e:
            self.logger.error(f"Error forwarding JS8Call message to mesh: {e}")
    
    def get_recent_messages(self, limit: int = 50) -> List[JS8CallMessage]:
        """Get recent JS8Call messages"""
        return self.db.get_recent_js8call_messages(limit)
    
    def get_messages_by_group(self, group: str, limit: int = 50) -> List[JS8CallMessage]:
        """Get JS8Call messages for a specific group"""
        return self.db.get_js8call_messages_by_group(group, limit)
    
    def get_urgent_messages(self, limit: int = 20) -> List[JS8CallMessage]:
        """Get urgent and emergency JS8Call messages"""
        return self.db.get_urgent_js8call_messages(limit)
    
    def search_messages(self, search_term: str, callsign_filter: Optional[str] = None) -> List[JS8CallMessage]:
        """Search JS8Call messages"""
        return self.db.search_js8call_messages(search_term, callsign_filter)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get JS8Call integration statistics"""
        stats = {
            "enabled": self.config.enabled,
            "connected": self.client.connected if self.client else False,
            "monitored_groups": len(self.config.monitored_groups),
            "urgent_keywords": len(self.config.urgent_keywords),
            "emergency_keywords": len(self.config.emergency_keywords)
        }
        
        # Add database statistics
        db_stats = self.db.get_js8call_statistics()
        stats.update(db_stats)
        
        return stats
    
    def is_connected(self) -> bool:
        """Check if JS8Call client is connected"""
        return self.client.connected if self.client else False
    
    def get_monitored_groups(self) -> List[str]:
        """Get list of monitored groups"""
        return self.config.monitored_groups.copy()
    
    def add_monitored_group(self, group: str):
        """Add group to monitoring list"""
        if group not in self.config.monitored_groups:
            self.config.monitored_groups.append(group)
            self.logger.info(f"Added JS8Call monitored group: {group}")
    
    def remove_monitored_group(self, group: str):
        """Remove group from monitoring list"""
        if group in self.config.monitored_groups:
            self.config.monitored_groups.remove(group)
            self.logger.info(f"Removed JS8Call monitored group: {group}")
    
    def set_mesh_callback(self, callback: Callable):
        """Set callback for forwarding messages to mesh"""
        self.mesh_callback = callback