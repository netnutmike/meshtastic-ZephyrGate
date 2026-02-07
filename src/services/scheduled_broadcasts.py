"""
Scheduled Broadcasts Service

Standalone service for sending scheduled broadcasts independent of asset tracking.
Supports cron expressions, intervals, and one-time broadcasts.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from croniter import croniter

from core.config_loader import load_scheduled_broadcasts
from models.message import Message, MessageType


class ScheduledBroadcastsService:
    """Service for managing and executing scheduled broadcasts"""
    
    def __init__(self, config: Dict[str, Any], message_sender=None, plugin_manager=None):
        """
        Initialize the scheduled broadcasts service
        
        Args:
            config: Configuration dictionary
            message_sender: Callable to send messages (async function)
            plugin_manager: Plugin manager instance for calling plugin methods
        """
        self.config = config
        self.message_sender = message_sender
        self.plugin_manager = plugin_manager
        self.logger = logging.getLogger(__name__)
        
        self.broadcasts: List[Dict[str, Any]] = []
        self.running = False
        self.scheduler_task: Optional[asyncio.Task] = None
        
        # Track last execution times
        self.last_execution: Dict[str, datetime] = {}
        
        self.logger.info("Scheduled Broadcasts Service initialized")
    
    async def start(self):
        """Start the scheduled broadcasts service"""
        try:
            # Load broadcasts from configuration
            self.broadcasts = load_scheduled_broadcasts(self.config)
            
            if not self.broadcasts:
                self.logger.info("No scheduled broadcasts configured")
                return
            
            self.logger.info(f"Loaded {len(self.broadcasts)} scheduled broadcast(s)")
            
            self.running = True
            self.scheduler_task = asyncio.create_task(self._scheduler_loop())
            
            self.logger.info("Scheduled Broadcasts Service started")
            
        except Exception as e:
            self.logger.error(f"Failed to start scheduled broadcasts service: {e}", exc_info=True)
    
    async def stop(self):
        """Stop the scheduled broadcasts service"""
        self.running = False
        
        if self.scheduler_task:
            self.scheduler_task.cancel()
            try:
                await self.scheduler_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Scheduled Broadcasts Service stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop that checks for broadcasts to send"""
        while self.running:
            try:
                await self._check_and_send_broadcasts()
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in scheduler loop: {e}", exc_info=True)
                await asyncio.sleep(60)
    
    async def _check_and_send_broadcasts(self):
        """Check all broadcasts and send any that are due"""
        now = datetime.now(timezone.utc)
        
        for broadcast in self.broadcasts:
            if not broadcast.get('enabled', True):
                continue
            
            broadcast_name = broadcast['name']
            schedule_type = broadcast['schedule_type']
            
            try:
                should_send = False
                
                if schedule_type == 'cron':
                    should_send = self._should_send_cron(broadcast, now)
                elif schedule_type == 'interval':
                    should_send = self._should_send_interval(broadcast, now)
                elif schedule_type == 'one_time':
                    should_send = self._should_send_one_time(broadcast, now)
                
                if should_send:
                    await self._send_broadcast(broadcast)
                    self.last_execution[broadcast_name] = now
                    
            except Exception as e:
                self.logger.error(f"Error checking broadcast '{broadcast_name}': {e}", exc_info=True)
    
    def _should_send_cron(self, broadcast: Dict[str, Any], now: datetime) -> bool:
        """Check if a cron-based broadcast should be sent"""
        cron_expression = broadcast.get('cron_expression')
        if not cron_expression:
            return False
        
        broadcast_name = broadcast['name']
        last_exec = self.last_execution.get(broadcast_name)
        
        try:
            # Create croniter instance
            cron = croniter(cron_expression, now)
            
            # Get the previous scheduled time
            prev_time = cron.get_prev(datetime)
            
            # If we've never executed, or the previous scheduled time is after our last execution
            if last_exec is None:
                # Check if prev_time is within the last minute (to avoid sending on startup for past schedules)
                time_diff = (now - prev_time).total_seconds()
                if 0 <= time_diff <= 60:
                    return True
            elif prev_time > last_exec:
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error parsing cron expression '{cron_expression}': {e}")
            return False
    
    def _should_send_interval(self, broadcast: Dict[str, Any], now: datetime) -> bool:
        """Check if an interval-based broadcast should be sent"""
        interval_seconds = broadcast.get('interval_seconds')
        if not interval_seconds:
            return False
        
        broadcast_name = broadcast['name']
        last_exec = self.last_execution.get(broadcast_name)
        
        if last_exec is None:
            # First execution
            return True
        
        # Check if enough time has passed
        elapsed = (now - last_exec).total_seconds()
        if elapsed >= interval_seconds:
            return True
        
        return False
    
    def _should_send_one_time(self, broadcast: Dict[str, Any], now: datetime) -> bool:
        """Check if a one-time broadcast should be sent"""
        scheduled_time_str = broadcast.get('scheduled_time')
        if not scheduled_time_str:
            return False
        
        broadcast_name = broadcast['name']
        
        # Check if already sent
        if broadcast_name in self.last_execution:
            return False
        
        try:
            # Parse scheduled time (ISO format)
            scheduled_time = datetime.fromisoformat(scheduled_time_str.replace('Z', '+00:00'))
            
            # Make sure scheduled_time is timezone-aware
            if scheduled_time.tzinfo is None:
                scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)
            
            # Check if it's time to send (within the last minute)
            time_diff = (now - scheduled_time).total_seconds()
            
            if time_diff < 0:
                # Scheduled time is in the future
                return False
            elif time_diff > 60:
                # Scheduled time was more than 60 seconds ago - missed window
                self.logger.warning(f"One-time broadcast '{broadcast_name}' missed send window. Scheduled: {scheduled_time}, Now: {now}, Diff: {time_diff:.0f}s")
                return False
            else:
                # Within the send window
                return True
            
        except Exception as e:
            self.logger.error(f"Error parsing scheduled time '{scheduled_time_str}': {e}")
            return False
    
    async def _send_broadcast(self, broadcast: Dict[str, Any]):
        """Send a broadcast message"""
        try:
            broadcast_name = broadcast['name']
            
            # Check if this is a message broadcast or plugin call
            if 'message' in broadcast:
                # Simple message broadcast
                message_content = broadcast['message']
                channel = broadcast.get('channel', 0)
                priority = broadcast.get('priority', 'normal')
                hop_limit = broadcast.get('hop_limit', None)  # None = use default (3)
                
                if self.message_sender:
                    await self.message_sender(
                        content=message_content,
                        channel=channel,
                        priority=priority,
                        hop_limit=hop_limit
                    )
                else:
                    self.logger.warning("No message sender configured, cannot send broadcast")
                
            elif 'plugin_name' in broadcast:
                # Plugin method call
                plugin_name = broadcast['plugin_name']
                plugin_method = broadcast['plugin_method']
                plugin_args = broadcast.get('plugin_args', {})
                channel = broadcast.get('channel', 0)
                
                if not self.plugin_manager:
                    self.logger.error("Plugin manager not available, cannot call plugin methods")
                    return
                
                try:
                    # Get the plugin instance
                    plugin_info = self.plugin_manager.get_plugin_info(plugin_name)
                    if not plugin_info or not plugin_info.instance:
                        self.logger.error(f"Plugin '{plugin_name}' not found or not loaded")
                        return
                    
                    plugin_instance = plugin_info.instance
                    
                    # Check if the method exists
                    if not hasattr(plugin_instance, plugin_method):
                        self.logger.error(f"Plugin '{plugin_name}' does not have method '{plugin_method}'")
                        return
                    
                    # Call the plugin method
                    method = getattr(plugin_instance, plugin_method)
                    
                    # Call the method with args
                    if asyncio.iscoroutinefunction(method):
                        result = await method(**plugin_args)
                    else:
                        result = method(**plugin_args)
                    
                    # Convert result to string if needed
                    if isinstance(result, tuple):
                        # Handle (success, message) tuple format
                        success, message_content = result
                        if not success:
                            self.logger.error(f"Plugin method returned error: {message_content}")
                            return
                        result = message_content
                    elif not isinstance(result, str):
                        result = str(result)
                    
                    # Send the result as a broadcast
                    if self.message_sender and result:
                        hop_limit = broadcast.get('hop_limit', None)  # None = use default (3)
                        await self.message_sender(
                            content=result,
                            channel=channel,
                            priority=broadcast.get('priority', 'normal'),
                            hop_limit=hop_limit
                        )
                    
                except Exception as e:
                    self.logger.error(f"Error calling plugin method {plugin_name}.{plugin_method}: {e}", exc_info=True)
                
            elif 'command' in broadcast:
                # Shell command execution
                command = broadcast['command']
                prefix = broadcast.get('prefix', '')
                timeout = broadcast.get('timeout', 10)
                max_output_length = broadcast.get('max_output_length', 200)
                
                # TODO: Implement command execution
                self.logger.warning("Command execution not yet implemented for scheduled broadcasts")
            
            else:
                self.logger.error(f"Broadcast '{broadcast_name}' has no message, plugin, or command configured")
            
        except Exception as e:
            self.logger.error(f"Error sending broadcast '{broadcast['name']}': {e}", exc_info=True)
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status"""
        return {
            'running': self.running,
            'broadcasts_configured': len(self.broadcasts),
            'broadcasts_enabled': len([b for b in self.broadcasts if b.get('enabled', True)]),
            'last_executions': {
                name: time.isoformat() 
                for name, time in self.last_execution.items()
            }
        }
