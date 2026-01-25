"""
Data Logger Plugin - Example of plugin storage usage

This plugin demonstrates:
- Storing and retrieving data using the plugin storage interface
- Data persistence across plugin restarts
- TTL (Time To Live) for cached data
- Data querying and reporting
- Storage best practices

The plugin logs various types of data and provides commands to query
and analyze the stored information.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from src.core.enhanced_plugin import EnhancedPlugin


class DataLoggerPlugin(EnhancedPlugin):
    """
    Data logger plugin that demonstrates storage capabilities.
    
    Features:
    - Log messages and events
    - Store statistics and metrics
    - Query historical data
    - Data retention policies
    - Export functionality
    """
    
    async def initialize(self) -> bool:
        """Initialize the plugin"""
        self.logger.info("Initializing Data Logger Plugin")
        
        # Register commands
        self.register_command(
            "log",
            self.handle_log_command,
            "Log a message or event",
            priority=100
        )
        
        self.register_command(
            "logquery",
            self.handle_query_command,
            "Query logged data",
            priority=100
        )
        
        self.register_command(
            "logstats",
            self.handle_stats_command,
            "Show logging statistics",
            priority=100
        )
        
        self.register_command(
            "logexport",
            self.handle_export_command,
            "Export logged data",
            priority=100
        )
        
        self.register_command(
            "logclear",
            self.handle_clear_command,
            "Clear logged data",
            priority=100
        )
        
        # Register message handler to log all messages
        if self.get_config("auto_log_messages", True):
            self.register_message_handler(self.log_message_handler, priority=200)
        
        # Register scheduled task for periodic statistics
        self.register_scheduled_task(
            "stats_update",
            300,  # 5 minutes
            self.update_statistics_task
        )
        
        # Initialize storage
        await self._initialize_storage()
        
        return True
    
    async def _initialize_storage(self):
        """Initialize storage with default values"""
        # Initialize counters if they don't exist
        if await self.retrieve_data("total_logs") is None:
            await self.store_data("total_logs", 0)
        
        if await self.retrieve_data("total_messages") is None:
            await self.store_data("total_messages", 0)
        
        # Store initialization timestamp
        init_time = await self.retrieve_data("initialized_at")
        if not init_time:
            await self.store_data("initialized_at", datetime.utcnow().isoformat())
            self.logger.info("Storage initialized")
    
    async def handle_log_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle the 'log' command to manually log data.
        
        Usage: log <type> <message>
        Types: info, warning, error, event
        """
        if len(args) < 2:
            return "Usage: log <type> <message>\nTypes: info, warning, error, event"
        
        log_type = args[0].lower()
        message = " ".join(args[1:])
        
        if log_type not in ['info', 'warning', 'error', 'event']:
            return "Invalid type. Use: info, warning, error, or event"
        
        try:
            # Create log entry
            log_entry = {
                'type': log_type,
                'message': message,
                'timestamp': datetime.utcnow().isoformat(),
                'user': context.get('sender_id', 'unknown'),
                'channel': context.get('channel', 'unknown')
            }
            
            # Store the log entry
            await self._store_log_entry(log_entry)
            
            # Update counters
            await self._increment_counter("total_logs")
            await self._increment_counter(f"logs_{log_type}")
            
            return f"Logged {log_type}: {message}"
            
        except Exception as e:
            self.logger.error(f"Error logging data: {e}")
            return f"Error: {str(e)}"
    
    async def handle_query_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle the 'logquery' command to query logged data.
        
        Usage: logquery [type] [limit]
        """
        log_type = args[0] if args else None
        limit = int(args[1]) if len(args) > 1 else 10
        
        try:
            # Get log entries
            entries = await self._get_log_entries(log_type, limit)
            
            if not entries:
                type_str = f" of type '{log_type}'" if log_type else ""
                return f"No log entries found{type_str}"
            
            # Format response
            response = [f"Log Entries (showing {len(entries)}):"]
            response.append("=" * 50)
            
            for entry in entries:
                timestamp = entry['timestamp'][:19]  # Trim microseconds
                response.append(f"[{timestamp}] {entry['type'].upper()}")
                response.append(f"  User: {entry['user']}")
                response.append(f"  Message: {entry['message']}")
                response.append("")
            
            return "\n".join(response)
            
        except Exception as e:
            self.logger.error(f"Error querying logs: {e}")
            return f"Error: {str(e)}"
    
    async def handle_stats_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle the 'logstats' command to show statistics.
        
        Usage: logstats
        """
        try:
            # Get statistics
            total_logs = await self.retrieve_data("total_logs", 0)
            total_messages = await self.retrieve_data("total_messages", 0)
            
            logs_info = await self.retrieve_data("logs_info", 0)
            logs_warning = await self.retrieve_data("logs_warning", 0)
            logs_error = await self.retrieve_data("logs_error", 0)
            logs_event = await self.retrieve_data("logs_event", 0)
            
            init_time = await self.retrieve_data("initialized_at", "unknown")
            last_log = await self.retrieve_data("last_log_time", "never")
            
            # Calculate uptime
            if init_time != "unknown":
                init_dt = datetime.fromisoformat(init_time)
                uptime = datetime.utcnow() - init_dt
                uptime_str = str(uptime).split('.')[0]  # Remove microseconds
            else:
                uptime_str = "unknown"
            
            # Format response
            response = [
                "Data Logger Statistics:",
                "=" * 50,
                f"Total Logs: {total_logs}",
                f"Total Messages Logged: {total_messages}",
                "",
                "Logs by Type:",
                f"  Info: {logs_info}",
                f"  Warning: {logs_warning}",
                f"  Error: {logs_error}",
                f"  Event: {logs_event}",
                "",
                f"Initialized: {init_time}",
                f"Uptime: {uptime_str}",
                f"Last Log: {last_log}",
            ]
            
            return "\n".join(response)
            
        except Exception as e:
            self.logger.error(f"Error getting statistics: {e}")
            return f"Error: {str(e)}"
    
    async def handle_export_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle the 'logexport' command to export data.
        
        Usage: logexport [type] [limit]
        """
        log_type = args[0] if args else None
        limit = int(args[1]) if len(args) > 1 else 100
        
        try:
            # Get log entries
            entries = await self._get_log_entries(log_type, limit)
            
            if not entries:
                return "No log entries to export"
            
            # Create export data
            export_data = {
                'exported_at': datetime.utcnow().isoformat(),
                'entry_count': len(entries),
                'filter_type': log_type,
                'entries': entries
            }
            
            # Store export
            export_key = f"export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            await self.store_data(export_key, export_data, ttl=86400)  # 24 hours
            
            return f"Exported {len(entries)} entries to {export_key}\n(Available for 24 hours)"
            
        except Exception as e:
            self.logger.error(f"Error exporting data: {e}")
            return f"Error: {str(e)}"
    
    async def handle_clear_command(self, args: List[str], context: Dict[str, Any]) -> str:
        """
        Handle the 'logclear' command to clear logged data.
        
        Usage: logclear [type|all]
        """
        if not args:
            return "Usage: logclear <type|all>\nTypes: info, warning, error, event, all"
        
        clear_type = args[0].lower()
        
        try:
            if clear_type == "all":
                # Clear all logs
                await self._clear_all_logs()
                return "All logs cleared"
            elif clear_type in ['info', 'warning', 'error', 'event']:
                # Clear specific type
                await self._clear_logs_by_type(clear_type)
                return f"Cleared all {clear_type} logs"
            else:
                return "Invalid type. Use: info, warning, error, event, or all"
                
        except Exception as e:
            self.logger.error(f"Error clearing logs: {e}")
            return f"Error: {str(e)}"
    
    async def log_message_handler(self, message, context: Dict[str, Any]) -> Optional[str]:
        """
        Message handler to automatically log all messages.
        
        Returns None to allow other handlers to process the message.
        """
        try:
            # Create log entry for the message
            log_entry = {
                'type': 'message',
                'message': message.content[:100],  # Truncate long messages
                'timestamp': datetime.utcnow().isoformat(),
                'user': message.sender_id,
                'channel': context.get('channel', 'unknown')
            }
            
            # Store the log entry
            await self._store_log_entry(log_entry)
            
            # Update message counter
            await self._increment_counter("total_messages")
            
        except Exception as e:
            self.logger.error(f"Error in message handler: {e}")
        
        # Return None to allow other handlers to process
        return None
    
    async def update_statistics_task(self):
        """
        Scheduled task to update statistics.
        
        Runs every 5 minutes to update aggregate statistics.
        """
        self.logger.info("Updating statistics")
        
        try:
            # Calculate statistics
            total_logs = await self.retrieve_data("total_logs", 0)
            
            # Store statistics snapshot
            stats_snapshot = {
                'timestamp': datetime.utcnow().isoformat(),
                'total_logs': total_logs,
                'total_messages': await self.retrieve_data("total_messages", 0)
            }
            
            # Store snapshot with TTL (keep for 7 days)
            snapshot_key = f"stats_snapshot_{datetime.utcnow().strftime('%Y%m%d_%H%M')}"
            await self.store_data(snapshot_key, stats_snapshot, ttl=604800)
            
            self.logger.info(f"Statistics updated: {total_logs} total logs")
            
        except Exception as e:
            self.logger.error(f"Error updating statistics: {e}")
    
    async def _store_log_entry(self, entry: Dict[str, Any]):
        """Store a log entry"""
        # Get current log list
        log_list = await self.retrieve_data("log_entries", [])
        
        # Add new entry
        log_list.append(entry)
        
        # Keep only recent entries (configurable limit)
        max_entries = self.get_config("max_stored_entries", 1000)
        if len(log_list) > max_entries:
            log_list = log_list[-max_entries:]
        
        # Store updated list
        await self.store_data("log_entries", log_list)
        
        # Update last log time
        await self.store_data("last_log_time", entry['timestamp'])
    
    async def _get_log_entries(self, log_type: Optional[str] = None, 
                               limit: int = 10) -> List[Dict[str, Any]]:
        """Get log entries, optionally filtered by type"""
        log_list = await self.retrieve_data("log_entries", [])
        
        # Filter by type if specified
        if log_type:
            log_list = [e for e in log_list if e['type'] == log_type]
        
        # Return most recent entries
        return log_list[-limit:]
    
    async def _increment_counter(self, counter_name: str):
        """Increment a counter"""
        current = await self.retrieve_data(counter_name, 0)
        await self.store_data(counter_name, current + 1)
    
    async def _clear_all_logs(self):
        """Clear all logged data"""
        await self.store_data("log_entries", [])
        await self.store_data("total_logs", 0)
        await self.store_data("total_messages", 0)
        await self.store_data("logs_info", 0)
        await self.store_data("logs_warning", 0)
        await self.store_data("logs_error", 0)
        await self.store_data("logs_event", 0)
    
    async def _clear_logs_by_type(self, log_type: str):
        """Clear logs of a specific type"""
        log_list = await self.retrieve_data("log_entries", [])
        
        # Filter out entries of the specified type
        filtered_list = [e for e in log_list if e['type'] != log_type]
        
        # Calculate how many were removed
        removed_count = len(log_list) - len(filtered_list)
        
        # Store filtered list
        await self.store_data("log_entries", filtered_list)
        
        # Update counters
        await self.store_data(f"logs_{log_type}", 0)
        
        total_logs = await self.retrieve_data("total_logs", 0)
        await self.store_data("total_logs", total_logs - removed_count)


# Example configuration for this plugin (in config.yaml):
"""
plugins:
  data_logger:
    enabled: true
    auto_log_messages: true
    max_stored_entries: 1000
"""
