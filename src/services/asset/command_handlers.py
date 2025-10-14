"""
Asset Management Command Handlers

Provides command handlers for check-in/check-out operations, checklist management,
and asset status reporting.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple

from ...core.database import get_database
from .asset_tracking_service import AssetTrackingService
from .models import AssetStatus, CheckInAction


class AssetCommandHandler:
    """
    Command handler for asset management operations
    """
    
    def __init__(self, asset_service: AssetTrackingService):
        self.asset_service = asset_service
        self.logger = logging.getLogger(__name__)
        self.db = get_database()
        
        # Command mappings
        self.commands = {
            'checkin': self.handle_checkin,
            'checkout': self.handle_checkout,
            'checklist': self.handle_checklist,
            'status': self.handle_status,
            'mystatus': self.handle_my_status,
            'assetstats': self.handle_asset_stats,
            'bulkops': self.handle_bulk_operations,
            'clearlist': self.handle_clear_list
        }
    
    async def handle_command(self, command: str, args: List[str], sender_id: str, 
                           is_admin: bool = False) -> Tuple[bool, str]:
        """
        Handle asset management commands
        
        Args:
            command: The command name
            args: Command arguments
            sender_id: ID of the command sender
            is_admin: Whether sender has admin privileges
            
        Returns:
            Tuple of (success, response_message)
        """
        try:
            handler = self.commands.get(command.lower())
            if not handler:
                return False, f"❌ Unknown asset command: {command}"
            
            return await handler(args, sender_id, is_admin)
            
        except Exception as e:
            self.logger.error(f"Error handling asset command {command}: {e}")
            return False, "❌ Error processing command. Please try again."
    
    async def handle_checkin(self, args: List[str], sender_id: str, is_admin: bool) -> Tuple[bool, str]:
        """Handle check-in command"""
        try:
            # Parse optional notes
            notes = ' '.join(args) if args else None
            
            # Use the asset service to handle check-in
            response = await self.asset_service._handle_checkin(f"checkin {notes}" if notes else "checkin", sender_id)
            return True, response
            
        except Exception as e:
            self.logger.error(f"Error in checkin command: {e}")
            return False, "❌ Error processing check-in. Please try again."
    
    async def handle_checkout(self, args: List[str], sender_id: str, is_admin: bool) -> Tuple[bool, str]:
        """Handle check-out command"""
        try:
            # Parse optional notes
            notes = ' '.join(args) if args else None
            
            # Use the asset service to handle check-out
            response = await self.asset_service._handle_checkout(f"checkout {notes}" if notes else "checkout", sender_id)
            return True, response
            
        except Exception as e:
            self.logger.error(f"Error in checkout command: {e}")
            return False, "❌ Error processing check-out. Please try again."
    
    async def handle_checklist(self, args: List[str], sender_id: str, is_admin: bool) -> Tuple[bool, str]:
        """Handle checklist view command"""
        try:
            # Check for optional filters
            filter_type = args[0].lower() if args else None
            
            if filter_type == 'in':
                # Show only checked-in users
                return await self._show_filtered_checklist(sender_id, AssetStatus.CHECKED_IN)
            elif filter_type == 'out':
                # Show only checked-out users
                return await self._show_filtered_checklist(sender_id, AssetStatus.CHECKED_OUT)
            elif filter_type == 'all':
                # Show all users with status
                return await self._show_detailed_checklist(sender_id)
            else:
                # Default checklist view
                response = await self.asset_service._handle_checklist_view(sender_id)
                return True, response
                
        except Exception as e:
            self.logger.error(f"Error in checklist command: {e}")
            return False, "❌ Error retrieving checklist. Please try again."
    
    async def handle_status(self, args: List[str], sender_id: str, is_admin: bool) -> Tuple[bool, str]:
        """Handle status query command"""
        try:
            if args:
                # Status for specific user
                target_name = ' '.join(args)
                response = await self.asset_service._handle_status_query(f"status {target_name}", sender_id)
            else:
                # Own status
                response = await self.asset_service._handle_status_query("status", sender_id)
            
            return True, response
            
        except Exception as e:
            self.logger.error(f"Error in status command: {e}")
            return False, "❌ Error retrieving status. Please try again."
    
    async def handle_my_status(self, args: List[str], sender_id: str, is_admin: bool) -> Tuple[bool, str]:
        """Handle personal status query"""
        try:
            asset_info = await self.asset_service.get_asset_status(sender_id)
            if not asset_info:
                return False, "❌ No status information available."
            
            response = f"📊 **YOUR STATUS**\n"
            response += f"Status: {asset_info.status.value.replace('_', ' ').title()}\n"
            
            if asset_info.last_checkin:
                response += f"Last Check-in: {asset_info.last_checkin.strftime('%m/%d %H:%M')}\n"
            if asset_info.last_checkout:
                response += f"Last Check-out: {asset_info.last_checkout.strftime('%m/%d %H:%M')}\n"
            if asset_info.current_notes:
                response += f"Notes: {asset_info.current_notes}\n"
            
            response += f"Total Check-ins: {asset_info.checkin_count}"
            
            return True, response
            
        except Exception as e:
            self.logger.error(f"Error in mystatus command: {e}")
            return False, "❌ Error retrieving your status. Please try again."
    
    async def handle_asset_stats(self, args: List[str], sender_id: str, is_admin: bool) -> Tuple[bool, str]:
        """Handle asset statistics command"""
        try:
            # Parse optional days parameter
            days = 7  # Default to 7 days
            if args and args[0].isdigit():
                days = min(int(args[0]), 30)  # Max 30 days
            
            stats = await self.asset_service.get_checkin_stats(days)
            
            response = f"📊 **ASSET STATISTICS** (Last {days} days)\n"
            response += f"Total Check-ins: {stats.total_checkins}\n"
            response += f"Total Check-outs: {stats.total_checkouts}\n"
            response += f"Active Users: {stats.unique_users}\n"
            
            if stats.most_active_user:
                user = self.db.get_user(stats.most_active_user)
                user_name = user.get('short_name', stats.most_active_user) if user else stats.most_active_user
                response += f"Most Active: {user_name} ({stats.most_active_count} actions)\n"
            
            # Show recent activity
            if stats.recent_activity:
                response += f"\n**RECENT ACTIVITY:**\n"
                for record in stats.recent_activity[:5]:  # Show last 5
                    user = self.db.get_user(record.node_id)
                    user_name = user.get('short_name', record.node_id) if user else record.node_id
                    action_icon = "✅" if record.action == CheckInAction.CHECKIN else "❌"
                    time_str = record.timestamp.strftime("%m/%d %H:%M")
                    response += f"{action_icon} {user_name} - {time_str}\n"
            
            return True, response
            
        except Exception as e:
            self.logger.error(f"Error in assetstats command: {e}")
            return False, "❌ Error retrieving statistics. Please try again."
    
    async def handle_bulk_operations(self, args: List[str], sender_id: str, is_admin: bool) -> Tuple[bool, str]:
        """Handle bulk operations (admin only)"""
        if not is_admin:
            return False, "❌ Admin permissions required for bulk operations."
        
        try:
            if not args:
                return False, "❌ Usage: bulkops <operation> [notes]\nOperations: checkin_all, checkout_all, clear_all"
            
            operation = args[0].lower()
            notes = ' '.join(args[1:]) if len(args) > 1 else f"Bulk {operation} by admin"
            
            response = await self.asset_service._handle_bulk_operations(f"bulk {operation} {notes}", sender_id)
            return True, response
            
        except Exception as e:
            self.logger.error(f"Error in bulk operations: {e}")
            return False, "❌ Error processing bulk operation. Please try again."
    
    async def handle_clear_list(self, args: List[str], sender_id: str, is_admin: bool) -> Tuple[bool, str]:
        """Handle clear checklist command (admin only)"""
        if not is_admin:
            return False, "❌ Admin permissions required to clear checklist."
        
        try:
            # Confirm operation
            if not args or args[0].lower() != 'confirm':
                return True, "⚠️ This will clear ALL check-in records. Use 'clearlist confirm' to proceed."
            
            count = await self.asset_service._clear_all_checkins()
            return True, f"✅ Cleared all check-in records ({count} records removed)."
            
        except Exception as e:
            self.logger.error(f"Error clearing checklist: {e}")
            return False, "❌ Error clearing checklist. Please try again."
    
    async def _show_filtered_checklist(self, sender_id: str, status_filter: AssetStatus) -> Tuple[bool, str]:
        """Show checklist filtered by status"""
        try:
            summary = await self.asset_service.get_checklist_summary()
            
            filtered_assets = [asset for asset in summary.assets if asset.status == status_filter]
            
            status_name = status_filter.value.replace('_', ' ').title()
            response = f"📋 **{status_name.upper()} USERS** ({len(filtered_assets)})\n"
            
            if not filtered_assets:
                response += f"No users currently {status_name.lower()}."
                return True, response
            
            for asset in filtered_assets[:15]:  # Limit to 15 for message size
                if status_filter == AssetStatus.CHECKED_IN:
                    time_str = asset.last_checkin.strftime("%H:%M") if asset.last_checkin else "?"
                else:
                    time_str = asset.last_checkout.strftime("%H:%M") if asset.last_checkout else "?"
                
                response += f"• {asset.short_name} ({time_str})"
                if asset.current_notes:
                    response += f" - {asset.current_notes[:25]}..."
                response += "\n"
            
            if len(filtered_assets) > 15:
                response += f"... and {len(filtered_assets) - 15} more"
            
            return True, response
            
        except Exception as e:
            self.logger.error(f"Error showing filtered checklist: {e}")
            return False, "❌ Error retrieving filtered checklist."
    
    async def _show_detailed_checklist(self, sender_id: str) -> Tuple[bool, str]:
        """Show detailed checklist with all users and their status"""
        try:
            summary = await self.asset_service.get_checklist_summary()
            
            response = f"📋 **DETAILED CHECKLIST**\n"
            response += f"Total: {summary.total_users} | "
            response += f"✅ In: {summary.checked_in_users} | "
            response += f"❌ Out: {summary.checked_out_users} | "
            response += f"❓ Unknown: {summary.unknown_status_users}\n\n"
            
            # Group by status
            status_groups = {
                AssetStatus.CHECKED_IN: [],
                AssetStatus.CHECKED_OUT: [],
                AssetStatus.UNKNOWN: []
            }
            
            for asset in summary.assets:
                status_groups[asset.status].append(asset)
            
            # Show each group
            for status, assets in status_groups.items():
                if not assets:
                    continue
                
                status_icon = {"checked_in": "✅", "checked_out": "❌", "unknown": "❓"}[status.value]
                status_name = status.value.replace('_', ' ').title()
                
                response += f"**{status_icon} {status_name} ({len(assets)}):**\n"
                
                for asset in assets[:8]:  # Limit per group
                    if status == AssetStatus.CHECKED_IN and asset.last_checkin:
                        time_str = asset.last_checkin.strftime("%H:%M")
                    elif status == AssetStatus.CHECKED_OUT and asset.last_checkout:
                        time_str = asset.last_checkout.strftime("%H:%M")
                    else:
                        time_str = "?"
                    
                    response += f"  • {asset.short_name} ({time_str})\n"
                
                if len(assets) > 8:
                    response += f"  ... and {len(assets) - 8} more\n"
                response += "\n"
            
            return True, response
            
        except Exception as e:
            self.logger.error(f"Error showing detailed checklist: {e}")
            return False, "❌ Error retrieving detailed checklist."
    
    def get_command_help(self, command: str) -> str:
        """Get help text for asset commands"""
        help_text = {
            'checkin': "📝 **CHECKIN** - Check in to the system\nUsage: checkin [notes]\nExample: checkin Ready for duty",
            'checkout': "📝 **CHECKOUT** - Check out from the system\nUsage: checkout [notes]\nExample: checkout Going off duty",
            'checklist': "📋 **CHECKLIST** - View current checklist\nUsage: checklist [filter]\nFilters: in, out, all\nExample: checklist in",
            'status': "📊 **STATUS** - View asset status\nUsage: status [username]\nExample: status or status John",
            'mystatus': "📊 **MYSTATUS** - View your own status\nUsage: mystatus",
            'assetstats': "📈 **ASSETSTATS** - View asset statistics\nUsage: assetstats [days]\nExample: assetstats 7",
            'bulkops': "⚙️ **BULKOPS** - Bulk operations (admin)\nUsage: bulkops <operation> [notes]\nOperations: checkin_all, checkout_all, clear_all",
            'clearlist': "🗑️ **CLEARLIST** - Clear all records (admin)\nUsage: clearlist confirm"
        }
        
        return help_text.get(command.lower(), f"No help available for command: {command}")
    
    def get_available_commands(self, is_admin: bool = False) -> List[str]:
        """Get list of available commands"""
        basic_commands = ['checkin', 'checkout', 'checklist', 'status', 'mystatus', 'assetstats']
        
        if is_admin:
            basic_commands.extend(['bulkops', 'clearlist'])
        
        return basic_commands