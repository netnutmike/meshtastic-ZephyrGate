"""
Asset Tracking Service

Provides check-in/check-out functionality, asset tracking, and accountability
reporting for ZephyrGate mesh network operations.
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from ...core.database import get_database, DatabaseError
from ...core.plugin_interfaces import BaseMessageHandler
from .models import (
    CheckInRecord, AssetInfo, AssetStatus, CheckInAction,
    ChecklistSummary, CheckInStats
)


class AssetTrackingService(BaseMessageHandler):
    """
    Asset tracking service for check-in/check-out operations and accountability reporting
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(priority=50)  # Initialize base class
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.db = get_database()
        self.running = False
        
        # Configuration options
        self.auto_checkout_hours = config.get('auto_checkout_hours', 24)
        self.cleanup_days = config.get('cleanup_days', 30)
        self.enable_auto_checkout = config.get('enable_auto_checkout', False)
        
        self.logger.info("Asset Tracking Service initialized")
    
    async def start(self) -> None:
        """Start the asset tracking service"""
        self.running = True
        self.logger.info("Asset Tracking Service started")
        
        # Start background cleanup task if enabled
        if self.enable_auto_checkout:
            asyncio.create_task(self._cleanup_task())
    
    async def stop(self) -> None:
        """Stop the asset tracking service"""
        self.running = False
        self.logger.info("Asset Tracking Service stopped")
    
    async def handle_message(self, message: str, sender_id: str, **kwargs) -> Optional[str]:
        """
        Handle incoming messages for asset tracking commands
        
        Args:
            message: The message content
            sender_id: ID of the message sender
            **kwargs: Additional message context
            
        Returns:
            Response message if command was handled, None otherwise
        """
        message = message.strip().lower()
        
        # Check-in command
        if message.startswith('checkin'):
            return await self._handle_checkin(message, sender_id)
        
        # Check-out command
        elif message.startswith('checkout'):
            return await self._handle_checkout(message, sender_id)
        
        # Checklist view command
        elif message == 'checklist':
            return await self._handle_checklist_view(sender_id)
        
        # Asset status query
        elif message.startswith('status'):
            return await self._handle_status_query(message, sender_id)
        
        # Bulk operations (admin only)
        elif message.startswith('bulk'):
            return await self._handle_bulk_operations(message, sender_id)
        
        return None
    
    def can_handle(self, message) -> bool:
        """Check if this service can handle the message"""
        if hasattr(message, 'content'):
            content = message.content.strip().lower()
            return any(content.startswith(cmd) for cmd in ['checkin', 'checkout', 'checklist', 'status', 'bulk'])
        return False
    
    async def _handle_checkin(self, message: str, sender_id: str) -> str:
        """Handle check-in command"""
        try:
            # Parse notes from command (checkin optional notes)
            parts = message.split(' ', 1)
            notes = parts[1] if len(parts) > 1 else None
            
            # Create check-in record
            record = CheckInRecord(
                node_id=sender_id,
                action=CheckInAction.CHECKIN,
                notes=notes,
                timestamp=datetime.utcnow()
            )
            
            # Store in database
            record_id = await self._store_checkin_record(record)
            
            # Get user info for response
            user = self.db.get_user(sender_id)
            user_name = user.get('short_name', sender_id) if user else sender_id
            
            response = f"✅ {user_name} checked in"
            if notes:
                response += f" - {notes}"
            
            # Get current checklist count
            summary = await self.get_checklist_summary()
            response += f"\n📋 Total checked in: {summary.checked_in_users}"
            
            self.logger.info(f"User {sender_id} checked in with notes: {notes}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error handling check-in for {sender_id}: {e}")
            return "❌ Error processing check-in. Please try again."
    
    async def _handle_checkout(self, message: str, sender_id: str) -> str:
        """Handle check-out command"""
        try:
            # Parse notes from command (checkout optional notes)
            parts = message.split(' ', 1)
            notes = parts[1] if len(parts) > 1 else None
            
            # Create check-out record
            record = CheckInRecord(
                node_id=sender_id,
                action=CheckInAction.CHECKOUT,
                notes=notes,
                timestamp=datetime.utcnow()
            )
            
            # Store in database
            record_id = await self._store_checkin_record(record)
            
            # Get user info for response
            user = self.db.get_user(sender_id)
            user_name = user.get('short_name', sender_id) if user else sender_id
            
            response = f"✅ {user_name} checked out"
            if notes:
                response += f" - {notes}"
            
            # Get current checklist count
            summary = await self.get_checklist_summary()
            response += f"\n📋 Total checked in: {summary.checked_in_users}"
            
            self.logger.info(f"User {sender_id} checked out with notes: {notes}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error handling check-out for {sender_id}: {e}")
            return "❌ Error processing check-out. Please try again."
    
    async def _handle_checklist_view(self, sender_id: str) -> str:
        """Handle checklist view command"""
        try:
            summary = await self.get_checklist_summary()
            
            response = f"📋 **CHECKLIST STATUS**\n"
            response += f"Total Users: {summary.total_users}\n"
            response += f"✅ Checked In: {summary.checked_in_users}\n"
            response += f"❌ Checked Out: {summary.checked_out_users}\n"
            response += f"❓ Unknown: {summary.unknown_status_users}\n\n"
            
            # Show checked-in users
            checked_in = [asset for asset in summary.assets if asset.status == AssetStatus.CHECKED_IN]
            if checked_in:
                response += "**CHECKED IN:**\n"
                for asset in checked_in[:10]:  # Limit to 10 for message size
                    time_str = asset.last_checkin.strftime("%H:%M") if asset.last_checkin else "?"
                    response += f"• {asset.short_name} ({time_str})"
                    if asset.current_notes:
                        response += f" - {asset.current_notes[:30]}..."
                    response += "\n"
                
                if len(checked_in) > 10:
                    response += f"... and {len(checked_in) - 10} more\n"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error generating checklist for {sender_id}: {e}")
            return "❌ Error retrieving checklist. Please try again."
    
    async def _handle_status_query(self, message: str, sender_id: str) -> str:
        """Handle status query command"""
        try:
            parts = message.split(' ', 1)
            if len(parts) < 2:
                # Show own status
                target_id = sender_id
            else:
                # Show status for specified user (by name or ID)
                target_name = parts[1].strip()
                target_id = await self._find_user_by_name(target_name)
                if not target_id:
                    return f"❌ User '{target_name}' not found."
            
            asset_info = await self.get_asset_status(target_id)
            if not asset_info:
                return "❌ No status information available."
            
            response = f"📊 **STATUS: {asset_info.short_name}**\n"
            response += f"Status: {asset_info.status.value.replace('_', ' ').title()}\n"
            
            if asset_info.last_checkin:
                response += f"Last Check-in: {asset_info.last_checkin.strftime('%m/%d %H:%M')}\n"
            if asset_info.last_checkout:
                response += f"Last Check-out: {asset_info.last_checkout.strftime('%m/%d %H:%M')}\n"
            if asset_info.current_notes:
                response += f"Notes: {asset_info.current_notes}\n"
            
            response += f"Total Check-ins: {asset_info.checkin_count}"
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error handling status query for {sender_id}: {e}")
            return "❌ Error retrieving status. Please try again."
    
    async def _handle_bulk_operations(self, message: str, sender_id: str) -> str:
        """Handle bulk operations (admin only)"""
        try:
            # Check if user has admin permissions
            user = self.db.get_user(sender_id)
            if not user or not user.get('permissions', {}).get('admin', False):
                return "❌ Admin permissions required for bulk operations."
            
            parts = message.split(' ', 2)
            if len(parts) < 2:
                return "❌ Usage: bulk <operation> [notes]\nOperations: checkout_all, checkin_all, clear_all"
            
            operation = parts[1].lower()
            notes = parts[2] if len(parts) > 2 else f"Bulk {operation} by admin"
            
            if operation == 'checkout_all':
                count = await self._bulk_checkout_all(notes)
                return f"✅ Bulk check-out completed for {count} users."
            
            elif operation == 'checkin_all':
                count = await self._bulk_checkin_all(notes)
                return f"✅ Bulk check-in completed for {count} users."
            
            elif operation == 'clear_all':
                count = await self._clear_all_checkins()
                return f"✅ Cleared all check-in records ({count} records removed)."
            
            else:
                return "❌ Unknown operation. Use: checkout_all, checkin_all, or clear_all"
                
        except Exception as e:
            self.logger.error(f"Error handling bulk operation for {sender_id}: {e}")
            return "❌ Error processing bulk operation. Please try again."
    
    async def _store_checkin_record(self, record: CheckInRecord) -> int:
        """Store check-in record in database"""
        query = """
            INSERT INTO checklist (node_id, action, notes, timestamp)
            VALUES (?, ?, ?, ?)
        """
        
        with self.db.transaction() as conn:
            cursor = conn.execute(
                query,
                (record.node_id, record.action.value, record.notes, record.timestamp.isoformat())
            )
            return cursor.lastrowid
    
    async def get_checklist_summary(self) -> ChecklistSummary:
        """Get current checklist summary"""
        try:
            # Get all users
            users = self.db.execute_query("SELECT node_id, short_name, long_name FROM users")
            
            assets = []
            checked_in_count = 0
            checked_out_count = 0
            unknown_count = 0
            
            for user in users:
                asset_info = await self.get_asset_status(user['node_id'])
                if asset_info:
                    assets.append(asset_info)
                    
                    if asset_info.status == AssetStatus.CHECKED_IN:
                        checked_in_count += 1
                    elif asset_info.status == AssetStatus.CHECKED_OUT:
                        checked_out_count += 1
                    else:
                        unknown_count += 1
            
            return ChecklistSummary(
                total_users=len(users),
                checked_in_users=checked_in_count,
                checked_out_users=checked_out_count,
                unknown_status_users=unknown_count,
                assets=assets
            )
            
        except Exception as e:
            self.logger.error(f"Error generating checklist summary: {e}")
            return ChecklistSummary()
    
    async def get_asset_status(self, node_id: str) -> Optional[AssetInfo]:
        """Get status information for a specific asset"""
        try:
            # Get user info
            user = self.db.get_user(node_id)
            if not user:
                return None
            
            # Get latest check-in/out records
            query = """
                SELECT action, notes, timestamp
                FROM checklist
                WHERE node_id = ?
                ORDER BY timestamp DESC
                LIMIT 10
            """
            
            records = self.db.execute_query(query, (node_id,))
            
            if not records:
                return AssetInfo(
                    node_id=node_id,
                    short_name=user.get('short_name', node_id),
                    long_name=user.get('long_name'),
                    status=AssetStatus.UNKNOWN
                )
            
            # Determine current status from most recent record
            latest_record = records[0]
            status = AssetStatus.CHECKED_IN if latest_record['action'] == 'checkin' else AssetStatus.CHECKED_OUT
            
            # Find last check-in and check-out times
            last_checkin = None
            last_checkout = None
            current_notes = None
            
            for record in records:
                if record['action'] == 'checkin' and not last_checkin:
                    last_checkin = datetime.fromisoformat(record['timestamp'])
                    if status == AssetStatus.CHECKED_IN:
                        current_notes = record['notes']
                
                elif record['action'] == 'checkout' and not last_checkout:
                    last_checkout = datetime.fromisoformat(record['timestamp'])
                    if status == AssetStatus.CHECKED_OUT:
                        current_notes = record['notes']
            
            # Count total check-ins
            checkin_count = len([r for r in records if r['action'] == 'checkin'])
            
            return AssetInfo(
                node_id=node_id,
                short_name=user.get('short_name', node_id),
                long_name=user.get('long_name'),
                status=status,
                last_checkin=last_checkin,
                last_checkout=last_checkout,
                current_notes=current_notes,
                checkin_count=checkin_count
            )
            
        except Exception as e:
            self.logger.error(f"Error getting asset status for {node_id}: {e}")
            return None
    
    async def get_checkin_stats(self, days: int = 7) -> CheckInStats:
        """Get check-in statistics for the specified number of days"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Get all records within the time period
            query = """
                SELECT node_id, action, notes, timestamp
                FROM checklist
                WHERE timestamp >= ?
                ORDER BY timestamp DESC
            """
            
            records = self.db.execute_query(query, (cutoff_date.isoformat(),))
            
            total_checkins = 0
            total_checkouts = 0
            user_activity = {}
            recent_activity = []
            
            for record in records:
                if record['action'] == 'checkin':
                    total_checkins += 1
                else:
                    total_checkouts += 1
                
                # Track user activity
                node_id = record['node_id']
                user_activity[node_id] = user_activity.get(node_id, 0) + 1
                
                # Add to recent activity (limit to 20)
                if len(recent_activity) < 20:
                    recent_activity.append(CheckInRecord.from_dict(dict(record)))
            
            # Find most active user
            most_active_user = None
            most_active_count = 0
            if user_activity:
                most_active_user = max(user_activity, key=user_activity.get)
                most_active_count = user_activity[most_active_user]
            
            return CheckInStats(
                total_checkins=total_checkins,
                total_checkouts=total_checkouts,
                unique_users=len(user_activity),
                most_active_user=most_active_user,
                most_active_count=most_active_count,
                recent_activity=recent_activity
            )
            
        except Exception as e:
            self.logger.error(f"Error generating check-in stats: {e}")
            return CheckInStats()
    
    async def _find_user_by_name(self, name: str) -> Optional[str]:
        """Find user node ID by short name or long name"""
        query = """
            SELECT node_id FROM users
            WHERE LOWER(short_name) = LOWER(?) OR LOWER(long_name) = LOWER(?)
            LIMIT 1
        """
        
        results = self.db.execute_query(query, (name, name))
        return results[0]['node_id'] if results else None
    
    async def _bulk_checkout_all(self, notes: str) -> int:
        """Bulk check-out all users"""
        # Get all users who are currently checked in
        summary = await self.get_checklist_summary()
        checked_in_users = [asset.node_id for asset in summary.assets if asset.status == AssetStatus.CHECKED_IN]
        
        count = 0
        for node_id in checked_in_users:
            record = CheckInRecord(
                node_id=node_id,
                action=CheckInAction.CHECKOUT,
                notes=notes,
                timestamp=datetime.utcnow()
            )
            await self._store_checkin_record(record)
            count += 1
        
        return count
    
    async def _bulk_checkin_all(self, notes: str) -> int:
        """Bulk check-in all users"""
        # Get all users
        users = self.db.execute_query("SELECT node_id FROM users")
        
        count = 0
        for user in users:
            record = CheckInRecord(
                node_id=user['node_id'],
                action=CheckInAction.CHECKIN,
                notes=notes,
                timestamp=datetime.utcnow()
            )
            await self._store_checkin_record(record)
            count += 1
        
        return count
    
    async def _clear_all_checkins(self) -> int:
        """Clear all check-in records"""
        return self.db.execute_update("DELETE FROM checklist")
    
    async def _cleanup_task(self):
        """Background task for automatic cleanup"""
        while self.running:
            try:
                # Auto check-out users who have been checked in too long
                if self.auto_checkout_hours > 0:
                    cutoff_time = datetime.utcnow() - timedelta(hours=self.auto_checkout_hours)
                    
                    # Find users who checked in before cutoff and haven't checked out since
                    query = """
                        SELECT DISTINCT c1.node_id
                        FROM checklist c1
                        WHERE c1.action = 'checkin'
                        AND c1.timestamp < ?
                        AND NOT EXISTS (
                            SELECT 1 FROM checklist c2
                            WHERE c2.node_id = c1.node_id
                            AND c2.action = 'checkout'
                            AND c2.timestamp > c1.timestamp
                        )
                    """
                    
                    users_to_checkout = self.db.execute_query(query, (cutoff_time.isoformat(),))
                    
                    for user in users_to_checkout:
                        record = CheckInRecord(
                            node_id=user['node_id'],
                            action=CheckInAction.CHECKOUT,
                            notes=f"Auto check-out after {self.auto_checkout_hours} hours",
                            timestamp=datetime.utcnow()
                        )
                        await self._store_checkin_record(record)
                        self.logger.info(f"Auto checked out user {user['node_id']} after {self.auto_checkout_hours} hours")
                
                # Clean up old records
                if self.cleanup_days > 0:
                    cutoff_date = datetime.utcnow() - timedelta(days=self.cleanup_days)
                    deleted = self.db.execute_update(
                        "DELETE FROM checklist WHERE timestamp < ?",
                        (cutoff_date.isoformat(),)
                    )
                    if deleted > 0:
                        self.logger.info(f"Cleaned up {deleted} old check-in records")
                
                # Sleep for 1 hour before next cleanup
                await asyncio.sleep(3600)
                
            except Exception as e:
                self.logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(3600)  # Wait an hour before retrying
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get service health status"""
        try:
            # Test database connectivity
            self.db.execute_query("SELECT COUNT(*) FROM checklist LIMIT 1")
            
            return {
                'status': 'healthy',
                'service': 'asset_tracking',
                'running': self.running,
                'auto_checkout_enabled': self.enable_auto_checkout,
                'auto_checkout_hours': self.auto_checkout_hours,
                'cleanup_days': self.cleanup_days
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'service': 'asset_tracking',
                'error': str(e),
                'running': self.running
            }