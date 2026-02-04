"""
BBS Channel Directory Service for ZephyrGate

Handles channel directory operations including adding, listing, searching,
and managing channel information.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from services.bbs.models import BBSChannel, ChannelType, validate_channel_name, validate_frequency
from services.bbs.database import get_bbs_database


class ChannelService:
    """Service for managing channel directory operations"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.bbs_db = get_bbs_database()
    
    def add_channel(self, name: str, frequency: str, description: str,
                   channel_type: str = "other", location: str = "",
                   coverage_area: str = "", tone: str = "", offset: str = "",
                   added_by: str = "") -> Tuple[bool, str]:
        """
        Add a new channel to the directory
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Validate input
            if not validate_channel_name(name):
                return False, "Invalid channel name. Must be 1-50 characters."
            
            if frequency and not validate_frequency(frequency):
                return False, "Invalid frequency format. Use format like '146.520' or '146.520MHz'."
            
            if not description.strip():
                return False, "Description cannot be empty."
            
            if len(description) > 500:
                return False, "Description too long. Maximum 500 characters."
            
            # Parse channel type
            try:
                ch_type = ChannelType(channel_type.lower())
            except ValueError:
                ch_type = ChannelType.OTHER
            
            # Check for duplicate names
            existing_channels = self.bbs_db.get_all_channels()
            for existing in existing_channels:
                if existing.name.lower() == name.strip().lower():
                    return False, f"Channel '{name}' already exists in the directory."
            
            # Add channel
            channel = self.bbs_db.add_channel(
                name=name.strip(),
                frequency=frequency.strip(),
                description=description.strip(),
                channel_type=channel_type.lower(),
                location=location.strip(),
                coverage_area=coverage_area.strip(),
                tone=tone.strip(),
                offset=offset.strip(),
                added_by=added_by
            )
            
            if channel:
                self.logger.info(f"Channel {channel.id} '{name}' added by {added_by}")
                return True, f"Channel '{name}' added to directory successfully."
            else:
                return False, "Failed to add channel. Please try again."
                
        except Exception as e:
            self.logger.error(f"Error adding channel: {e}")
            return False, "An error occurred while adding the channel."
    
    def get_channel(self, channel_id: int) -> Tuple[bool, str]:
        """
        Get detailed information about a specific channel
        
        Returns:
            Tuple of (success: bool, formatted_channel: str)
        """
        try:
            channel = self.bbs_db.get_channel(channel_id)
            
            if not channel:
                return False, f"Channel #{channel_id} not found."
            
            # Format channel for display
            formatted = self._format_channel_display(channel)
            
            return True, formatted
            
        except Exception as e:
            self.logger.error(f"Error getting channel {channel_id}: {e}")
            return False, "An error occurred while retrieving the channel."
    
    def list_channels(self, active_only: bool = True, limit: int = 50, 
                     offset: int = 0) -> Tuple[bool, str]:
        """
        List channels in the directory
        
        Returns:
            Tuple of (success: bool, formatted_list: str)
        """
        try:
            channels = self.bbs_db.get_all_channels(active_only)
            
            if not channels:
                return True, "No channels found in directory."
            
            # Apply limit and offset
            total_count = len(channels)
            channels = channels[offset:offset + limit]
            
            # Format channel list
            formatted = self._format_channel_list(channels, total_count, offset, limit)
            
            return True, formatted
            
        except Exception as e:
            self.logger.error(f"Error listing channels: {e}")
            return False, "An error occurred while retrieving channels."
    
    def search_channels(self, search_term: str) -> Tuple[bool, str]:
        """
        Search channels by name, frequency, description, or location
        
        Returns:
            Tuple of (success: bool, formatted_results: str)
        """
        try:
            if not search_term.strip():
                return False, "Search term cannot be empty."
            
            results = self.bbs_db.search_channels(search_term.strip())
            
            if not results:
                return True, f"No channels found matching '{search_term}'."
            
            # Format search results
            formatted = self._format_search_results(results, search_term)
            
            return True, formatted
            
        except Exception as e:
            self.logger.error(f"Error searching channels: {e}")
            return False, "An error occurred while searching channels."
    
    def update_channel(self, channel_id: int, user_id: str, **updates) -> Tuple[bool, str]:
        """
        Update channel information
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Check if channel exists
            channel = self.bbs_db.get_channel(channel_id)
            
            if not channel:
                return False, f"Channel #{channel_id} not found."
            
            # Check permissions (only original submitter or admin can update)
            if channel.added_by != user_id:
                # TODO: Check if user is admin
                return False, "You can only update channels you added."
            
            # Validate updates
            valid_fields = {
                'name', 'frequency', 'description', 'channel_type',
                'location', 'coverage_area', 'tone', 'offset'
            }
            
            filtered_updates = {}
            for field, value in updates.items():
                if field in valid_fields and value is not None:
                    if field == 'name' and not validate_channel_name(str(value)):
                        return False, "Invalid channel name."
                    if field == 'frequency' and value and not validate_frequency(str(value)):
                        return False, "Invalid frequency format."
                    if field == 'description' and len(str(value)) > 500:
                        return False, "Description too long. Maximum 500 characters."
                    
                    filtered_updates[field] = str(value).strip()
            
            if not filtered_updates:
                return False, "No valid updates provided."
            
            # Update channel
            success = self.bbs_db.update_channel(channel_id, **filtered_updates)
            
            if success:
                self.logger.info(f"Channel {channel_id} updated by {user_id}")
                return True, f"Channel #{channel_id} updated successfully."
            else:
                return False, f"Failed to update channel #{channel_id}."
                
        except Exception as e:
            self.logger.error(f"Error updating channel {channel_id}: {e}")
            return False, "An error occurred while updating the channel."
    
    def delete_channel(self, channel_id: int, user_id: str) -> Tuple[bool, str]:
        """
        Delete (deactivate) a channel
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # Check if channel exists
            channel = self.bbs_db.get_channel(channel_id)
            
            if not channel:
                return False, f"Channel #{channel_id} not found."
            
            # Check permissions (only original submitter or admin can delete)
            if channel.added_by != user_id:
                # TODO: Check if user is admin
                return False, "You can only delete channels you added."
            
            # Delete (deactivate) channel
            success = self.bbs_db.delete_channel(channel_id, user_id)
            
            if success:
                self.logger.info(f"Channel {channel_id} deleted by {user_id}")
                return True, f"Channel #{channel_id} removed from directory."
            else:
                return False, f"Failed to delete channel #{channel_id}."
                
        except Exception as e:
            self.logger.error(f"Error deleting channel {channel_id}: {e}")
            return False, "An error occurred while deleting the channel."
    
    def verify_channel(self, channel_id: int, user_id: str) -> Tuple[bool, str]:
        """
        Mark a channel as verified (admin only)
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            # TODO: Check if user is admin
            # For now, allow any user to verify
            
            success = self.bbs_db.update_channel(channel_id, verified=True)
            
            if success:
                self.logger.info(f"Channel {channel_id} verified by {user_id}")
                return True, f"Channel #{channel_id} marked as verified."
            else:
                return False, f"Failed to verify channel #{channel_id}."
                
        except Exception as e:
            self.logger.error(f"Error verifying channel {channel_id}: {e}")
            return False, "An error occurred while verifying the channel."
    
    def get_channels_by_type(self, channel_type: str) -> Tuple[bool, str]:
        """
        Get channels filtered by type
        
        Returns:
            Tuple of (success: bool, formatted_list: str)
        """
        try:
            # Parse channel type
            try:
                ch_type = ChannelType(channel_type.lower())
            except ValueError:
                return False, f"Invalid channel type '{channel_type}'. Valid types: {', '.join([t.value for t in ChannelType])}"
            
            # Get all channels and filter by type
            all_channels = self.bbs_db.get_all_channels()
            filtered_channels = [ch for ch in all_channels if ch.channel_type == ch_type]
            
            if not filtered_channels:
                return True, f"No {channel_type} channels found."
            
            # Format results
            formatted = self._format_channel_list_by_type(filtered_channels, channel_type)
            
            return True, formatted
            
        except Exception as e:
            self.logger.error(f"Error getting channels by type {channel_type}: {e}")
            return False, "An error occurred while retrieving channels."
    
    def get_channels_by_location(self, location: str) -> Tuple[bool, str]:
        """
        Get channels filtered by location
        
        Returns:
            Tuple of (success: bool, formatted_list: str)
        """
        try:
            if not location.strip():
                return False, "Location cannot be empty."
            
            # Get all channels and filter by location
            all_channels = self.bbs_db.get_all_channels()
            location_lower = location.strip().lower()
            
            filtered_channels = [
                ch for ch in all_channels 
                if location_lower in ch.location.lower() or location_lower in ch.coverage_area.lower()
            ]
            
            if not filtered_channels:
                return True, f"No channels found for location '{location}'."
            
            # Format results
            formatted = self._format_channel_list_by_location(filtered_channels, location)
            
            return True, formatted
            
        except Exception as e:
            self.logger.error(f"Error getting channels by location {location}: {e}")
            return False, "An error occurred while retrieving channels."
    
    def get_channel_stats(self) -> Dict[str, Any]:
        """
        Get channel directory statistics
        
        Returns:
            Dictionary with channel statistics
        """
        try:
            stats = {}
            
            # Get all channels
            all_channels = self.bbs_db.get_all_channels(active_only=False)
            stats['total_channels'] = len(all_channels)
            
            # Count active channels
            active_channels = [ch for ch in all_channels if ch.active]
            stats['active_channels'] = len(active_channels)
            stats['inactive_channels'] = stats['total_channels'] - stats['active_channels']
            
            # Count verified channels
            verified_channels = [ch for ch in active_channels if ch.verified]
            stats['verified_channels'] = len(verified_channels)
            
            # Count by type
            type_counts = {}
            for channel in active_channels:
                ch_type = channel.channel_type.value
                type_counts[ch_type] = type_counts.get(ch_type, 0) + 1
            stats['channels_by_type'] = type_counts
            
            # Count unique contributors
            contributors = set(ch.added_by for ch in all_channels if ch.added_by)
            stats['unique_contributors'] = len(contributors)
            
            if all_channels:
                # Date range
                dates = [ch.added_at for ch in all_channels]
                stats['oldest_channel'] = min(dates)
                stats['newest_channel'] = max(dates)
                
                # Most active contributor
                contributor_counts = {}
                for channel in all_channels:
                    if channel.added_by:
                        contributor_counts[channel.added_by] = contributor_counts.get(channel.added_by, 0) + 1
                
                if contributor_counts:
                    most_active = max(contributor_counts.items(), key=lambda x: x[1])
                    stats['most_active_contributor'] = {
                        'user_id': most_active[0],
                        'channel_count': most_active[1]
                    }
                else:
                    stats['most_active_contributor'] = None
            else:
                stats['oldest_channel'] = None
                stats['newest_channel'] = None
                stats['most_active_contributor'] = None
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error getting channel stats: {e}")
            return {}
    
    def _format_channel_display(self, channel: BBSChannel) -> str:
        """Format channel for detailed display"""
        lines = []
        lines.append("=" * 60)
        lines.append(f"Channel #{channel.id}")
        lines.append("=" * 60)
        lines.append(f"Name: {channel.name}")
        lines.append(f"Type: {channel.channel_type.value.title()}")
        
        if channel.frequency:
            lines.append(f"Frequency: {channel.frequency}")
        
        if channel.tone:
            lines.append(f"Tone: {channel.tone}")
        
        if channel.offset:
            lines.append(f"Offset: {channel.offset}")
        
        if channel.location:
            lines.append(f"Location: {channel.location}")
        
        if channel.coverage_area:
            lines.append(f"Coverage: {channel.coverage_area}")
        
        lines.append(f"Description: {channel.description}")
        lines.append(f"Added by: {channel.added_by}")
        lines.append(f"Added: {channel.added_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append(f"Verified: {'Yes' if channel.verified else 'No'}")
        lines.append(f"Status: {'Active' if channel.active else 'Inactive'}")
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def _format_channel_list(self, channels: List[BBSChannel], total_count: int,
                           offset: int, limit: int) -> str:
        """Format channel list for display"""
        lines = []
        lines.append("Channel Directory:")
        lines.append("=" * 80)
        lines.append(f"{'ID':<4} | {'Name':<20} | {'Type':<10} | {'Frequency':<12} | {'Location':<15}")
        lines.append("-" * 80)
        
        for channel in channels:
            # Truncate long fields
            name = channel.name[:19] + "…" if len(channel.name) > 20 else channel.name
            ch_type = channel.channel_type.value[:9] + "…" if len(channel.channel_type.value) > 10 else channel.channel_type.value
            frequency = channel.frequency[:11] + "…" if len(channel.frequency) > 12 else channel.frequency
            location = channel.location[:14] + "…" if len(channel.location) > 15 else channel.location
            
            # Add verification indicator
            name_display = f"{name}{'✓' if channel.verified else ''}"
            
            lines.append(f"{channel.id:<4} | {name_display:<20} | {ch_type:<10} | {frequency:<12} | {location:<15}")
        
        lines.append("-" * 80)
        
        # Show pagination info
        if total_count > len(channels):
            start = offset + 1
            end = min(offset + limit, total_count)
            lines.append(f"Showing {start}-{end} of {total_count} channels")
        else:
            lines.append(f"Total: {len(channels)} channels")
        
        lines.append("")
        lines.append("Use 'info <ID>' to view detailed channel information")
        lines.append("✓ = Verified channel")
        
        return "\n".join(lines)
    
    def _format_search_results(self, results: List[BBSChannel], search_term: str) -> str:
        """Format search results for display"""
        lines = []
        lines.append(f"Channel search results for '{search_term}':")
        lines.append("=" * 75)
        lines.append(f"{'ID':<4} | {'Name':<18} | {'Type':<10} | {'Frequency':<12} | {'Location':<12}")
        lines.append("-" * 75)
        
        for channel in results[:20]:  # Limit to 20 results
            # Truncate long fields
            name = channel.name[:17] + "…" if len(channel.name) > 18 else channel.name
            ch_type = channel.channel_type.value[:9] + "…" if len(channel.channel_type.value) > 10 else channel.channel_type.value
            frequency = channel.frequency[:11] + "…" if len(channel.frequency) > 12 else channel.frequency
            location = channel.location[:11] + "…" if len(channel.location) > 12 else channel.location
            
            # Add verification indicator
            name_display = f"{name}{'✓' if channel.verified else ''}"
            
            lines.append(f"{channel.id:<4} | {name_display:<18} | {ch_type:<10} | {frequency:<12} | {location:<12}")
        
        if len(results) > 20:
            lines.append(f"... and {len(results) - 20} more results")
        
        lines.append("-" * 75)
        lines.append(f"Found: {len(results)} channels")
        lines.append("")
        lines.append("Use 'info <ID>' to view detailed channel information")
        
        return "\n".join(lines)
    
    def _format_channel_list_by_type(self, channels: List[BBSChannel], channel_type: str) -> str:
        """Format channel list filtered by type"""
        lines = []
        lines.append(f"{channel_type.title()} Channels:")
        lines.append("=" * 70)
        lines.append(f"{'ID':<4} | {'Name':<25} | {'Frequency':<12} | {'Location':<20}")
        lines.append("-" * 70)
        
        for channel in channels:
            # Truncate long fields
            name = channel.name[:24] + "…" if len(channel.name) > 25 else channel.name
            frequency = channel.frequency[:11] + "…" if len(channel.frequency) > 12 else channel.frequency
            location = channel.location[:19] + "…" if len(channel.location) > 20 else channel.location
            
            # Add verification indicator
            name_display = f"{name}{'✓' if channel.verified else ''}"
            
            lines.append(f"{channel.id:<4} | {name_display:<25} | {frequency:<12} | {location:<20}")
        
        lines.append("-" * 70)
        lines.append(f"Total: {len(channels)} {channel_type} channels")
        
        return "\n".join(lines)
    
    def _format_channel_list_by_location(self, channels: List[BBSChannel], location: str) -> str:
        """Format channel list filtered by location"""
        lines = []
        lines.append(f"Channels in '{location}':")
        lines.append("=" * 70)
        lines.append(f"{'ID':<4} | {'Name':<25} | {'Type':<10} | {'Frequency':<12}")
        lines.append("-" * 70)
        
        for channel in channels:
            # Truncate long fields
            name = channel.name[:24] + "…" if len(channel.name) > 25 else channel.name
            ch_type = channel.channel_type.value[:9] + "…" if len(channel.channel_type.value) > 10 else channel.channel_type.value
            frequency = channel.frequency[:11] + "…" if len(channel.frequency) > 12 else channel.frequency
            
            # Add verification indicator
            name_display = f"{name}{'✓' if channel.verified else ''}"
            
            lines.append(f"{channel.id:<4} | {name_display:<25} | {ch_type:<10} | {frequency:<12}")
        
        lines.append("-" * 70)
        lines.append(f"Total: {len(channels)} channels")
        
        return "\n".join(lines)


# Global channel service instance
channel_service: Optional[ChannelService] = None


def get_channel_service() -> ChannelService:
    """Get the global channel service instance"""
    global channel_service
    if channel_service is None:
        channel_service = ChannelService()
    return channel_service