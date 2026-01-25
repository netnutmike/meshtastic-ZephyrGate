"""
BBS Synchronization Service for ZephyrGate

Handles peer BBS node communication, message synchronization with duplicate prevention,
and conflict resolution for synchronized data.
"""

import asyncio
import json
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

from core.interfaces import InterfaceManager
from models.message import Message, MessageType
from .database import get_bbs_database
from .models import BBSBulletin, BBSMail, BBSChannel


class SyncMessageType(Enum):
    """BBS synchronization message types"""
    SYNC_REQUEST = "sync_request"
    SYNC_RESPONSE = "sync_response"
    BULLETIN_SYNC = "bulletin_sync"
    MAIL_SYNC = "mail_sync"
    CHANNEL_SYNC = "channel_sync"
    SYNC_ACK = "sync_ack"
    PEER_DISCOVERY = "peer_discovery"
    PEER_ANNOUNCE = "peer_announce"


class ConflictResolution(Enum):
    """Conflict resolution strategies"""
    TIMESTAMP_WINS = "timestamp_wins"  # Most recent timestamp wins
    SENDER_PRIORITY = "sender_priority"  # Based on sender priority
    MERGE_CONTENT = "merge_content"  # Attempt to merge content
    MANUAL_REVIEW = "manual_review"  # Flag for manual review


@dataclass
class SyncPeer:
    """BBS synchronization peer"""
    node_id: str
    name: str
    last_sync: Optional[datetime] = None
    sync_enabled: bool = True
    priority: int = 1  # Higher number = higher priority
    sync_bulletins: bool = True
    sync_mail: bool = True
    sync_channels: bool = True
    max_sync_age_days: int = 30
    
    def should_sync_with(self, message_age: timedelta) -> bool:
        """Check if message should be synced based on age"""
        return message_age.days <= self.max_sync_age_days


@dataclass
class SyncMessage:
    """BBS synchronization message"""
    message_type: SyncMessageType
    sender_id: str
    recipient_id: Optional[str]
    data: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)
    sync_id: str = field(default_factory=lambda: hashlib.sha256(
        f"{datetime.utcnow().isoformat()}".encode()).hexdigest()[:16])
    
    def to_mesh_message(self) -> str:
        """Convert to mesh message format"""
        return json.dumps({
            'type': 'bbs_sync',
            'sync_type': self.message_type.value,
            'sender': self.sender_id,
            'recipient': self.recipient_id,
            'data': self.data,
            'timestamp': self.timestamp.isoformat(),
            'sync_id': self.sync_id
        })
    
    @classmethod
    def from_mesh_message(cls, message_content: str) -> Optional['SyncMessage']:
        """Create from mesh message"""
        try:
            data = json.loads(message_content)
            if data.get('type') != 'bbs_sync':
                return None
            
            sync_msg = cls(
                message_type=SyncMessageType(data['sync_type']),
                sender_id=data['sender'],
                recipient_id=data.get('recipient'),
                data=data['data'],
                sync_id=data.get('sync_id', '')
            )
            
            # Parse timestamp
            if 'timestamp' in data:
                sync_msg.timestamp = datetime.fromisoformat(data['timestamp'])
            
            return sync_msg
            
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logging.error(f"Failed to parse sync message: {e}")
            return None


class BBSSyncService:
    """BBS synchronization service"""
    
    def __init__(self, interface_manager: InterfaceManager, node_id: str):
        self.logger = logging.getLogger(__name__)
        self.interface_manager = interface_manager
        self.node_id = node_id
        self.db = get_bbs_database()
        
        # Sync configuration
        self.peers: Dict[str, SyncPeer] = {}
        self.sync_enabled = True
        self.sync_interval_minutes = 30
        self.max_sync_batch_size = 10
        self.conflict_resolution = ConflictResolution.TIMESTAMP_WINS
        
        # Sync state tracking
        self.pending_syncs: Dict[str, SyncMessage] = {}
        self.sync_history: List[Tuple[str, datetime, bool]] = []  # peer_id, timestamp, success
        self.last_sync_check = datetime.utcnow()
        
        # Start sync task
        self._sync_task: Optional[asyncio.Task] = None
        
    async def start(self):
        """Start the synchronization service"""
        if self._sync_task is None or self._sync_task.done():
            self._sync_task = asyncio.create_task(self._sync_loop())
            self.logger.info("BBS synchronization service started")
    
    async def stop(self):
        """Stop the synchronization service"""
        if self._sync_task and not self._sync_task.done():
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
            self.logger.info("BBS synchronization service stopped")
    
    def add_peer(self, peer: SyncPeer):
        """Add a synchronization peer"""
        self.peers[peer.node_id] = peer
        self.logger.info(f"Added BBS sync peer: {peer.name} ({peer.node_id})")
    
    def remove_peer(self, node_id: str):
        """Remove a synchronization peer"""
        if node_id in self.peers:
            peer = self.peers.pop(node_id)
            self.logger.info(f"Removed BBS sync peer: {peer.name} ({node_id})")
    
    def get_peer(self, node_id: str) -> Optional[SyncPeer]:
        """Get peer by node ID"""
        return self.peers.get(node_id)
    
    async def handle_message(self, message: Message) -> bool:
        """Handle incoming synchronization message"""
        try:
            sync_msg = SyncMessage.from_mesh_message(message.content)
            if not sync_msg:
                return False
            
            # Check if this is a sync message for us
            if sync_msg.recipient_id and sync_msg.recipient_id != self.node_id:
                return False
            
            self.logger.debug(f"Received sync message: {sync_msg.message_type.value} from {sync_msg.sender_id}")
            
            # Handle different sync message types
            if sync_msg.message_type == SyncMessageType.PEER_DISCOVERY:
                await self._handle_peer_discovery(sync_msg)
            elif sync_msg.message_type == SyncMessageType.PEER_ANNOUNCE:
                await self._handle_peer_announce(sync_msg)
            elif sync_msg.message_type == SyncMessageType.SYNC_REQUEST:
                await self._handle_sync_request(sync_msg)
            elif sync_msg.message_type == SyncMessageType.SYNC_RESPONSE:
                await self._handle_sync_response(sync_msg)
            elif sync_msg.message_type == SyncMessageType.BULLETIN_SYNC:
                await self._handle_bulletin_sync(sync_msg)
            elif sync_msg.message_type == SyncMessageType.MAIL_SYNC:
                await self._handle_mail_sync(sync_msg)
            elif sync_msg.message_type == SyncMessageType.CHANNEL_SYNC:
                await self._handle_channel_sync(sync_msg)
            elif sync_msg.message_type == SyncMessageType.SYNC_ACK:
                await self._handle_sync_ack(sync_msg)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error handling sync message: {e}")
            return False
    
    async def sync_with_peer(self, peer_id: str, force: bool = False) -> bool:
        """Initiate synchronization with a specific peer"""
        peer = self.get_peer(peer_id)
        if not peer or not peer.sync_enabled:
            return False
        
        try:
            # Check if sync is needed
            if not force and peer.last_sync:
                time_since_sync = datetime.utcnow() - peer.last_sync
                if time_since_sync.total_seconds() < (self.sync_interval_minutes * 60):
                    return True  # Too soon to sync again
            
            # Send sync request
            sync_request = SyncMessage(
                message_type=SyncMessageType.SYNC_REQUEST,
                sender_id=self.node_id,
                recipient_id=peer_id,
                data={
                    'last_sync': peer.last_sync.isoformat() if peer.last_sync else None,
                    'sync_bulletins': peer.sync_bulletins,
                    'sync_mail': peer.sync_mail,
                    'sync_channels': peer.sync_channels,
                    'max_age_days': peer.max_sync_age_days
                }
            )
            
            await self._send_sync_message(sync_request)
            self.pending_syncs[sync_request.sync_id] = sync_request
            
            self.logger.info(f"Initiated sync with peer {peer.name} ({peer_id})")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to sync with peer {peer_id}: {e}")
            return False
    
    async def sync_all_peers(self, force: bool = False) -> int:
        """Sync with all configured peers"""
        success_count = 0
        
        for peer_id, peer in self.peers.items():
            if await self.sync_with_peer(peer_id, force):
                success_count += 1
                # Add small delay between syncs to avoid overwhelming the network
                await asyncio.sleep(1)
        
        return success_count
    
    async def announce_to_network(self):
        """Announce this BBS node to the network"""
        try:
            announce_msg = SyncMessage(
                message_type=SyncMessageType.PEER_ANNOUNCE,
                sender_id=self.node_id,
                recipient_id=None,  # Broadcast
                data={
                    'name': f"BBS-{self.node_id[-4:]}",
                    'capabilities': {
                        'bulletins': True,
                        'mail': True,
                        'channels': True
                    },
                    'version': '1.0'
                }
            )
            
            await self._send_sync_message(announce_msg)
            self.logger.info("Announced BBS node to network")
            
        except Exception as e:
            self.logger.error(f"Failed to announce to network: {e}")
    
    async def discover_peers(self):
        """Discover other BBS nodes on the network"""
        try:
            discovery_msg = SyncMessage(
                message_type=SyncMessageType.PEER_DISCOVERY,
                sender_id=self.node_id,
                recipient_id=None,  # Broadcast
                data={
                    'requesting_node': self.node_id,
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            
            await self._send_sync_message(discovery_msg)
            self.logger.info("Sent peer discovery request")
            
        except Exception as e:
            self.logger.error(f"Failed to discover peers: {e}")
    
    # Private methods
    
    async def _sync_loop(self):
        """Main synchronization loop"""
        while True:
            try:
                # Check if it's time for periodic sync
                now = datetime.utcnow()
                time_since_check = now - self.last_sync_check
                
                if time_since_check.total_seconds() >= (self.sync_interval_minutes * 60):
                    await self.sync_all_peers()
                    self.last_sync_check = now
                
                # Clean up old pending syncs
                await self._cleanup_pending_syncs()
                
                # Sleep for a minute before next check
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in sync loop: {e}")
                await asyncio.sleep(60)
    
    async def _send_sync_message(self, sync_msg: SyncMessage):
        """Send synchronization message"""
        message = Message(
            sender_id=self.node_id,
            recipient_id=sync_msg.recipient_id,
            content=sync_msg.to_mesh_message(),
            message_type=MessageType.TEXT,
            channel=0  # Use primary channel for sync
        )
        
        await self.interface_manager.send_message(message)
    
    async def _handle_peer_discovery(self, sync_msg: SyncMessage):
        """Handle peer discovery request"""
        if sync_msg.sender_id == self.node_id:
            return  # Ignore our own discovery messages
        
        # Respond with our announcement
        response = SyncMessage(
            message_type=SyncMessageType.PEER_ANNOUNCE,
            sender_id=self.node_id,
            recipient_id=sync_msg.sender_id,
            data={
                'name': f"BBS-{self.node_id[-4:]}",
                'capabilities': {
                    'bulletins': True,
                    'mail': True,
                    'channels': True
                },
                'version': '1.0'
            }
        )
        
        await self._send_sync_message(response)
    
    async def _handle_peer_announce(self, sync_msg: SyncMessage):
        """Handle peer announcement"""
        if sync_msg.sender_id == self.node_id:
            return  # Ignore our own announcements
        
        # Check if we already know this peer
        if sync_msg.sender_id not in self.peers:
            # Auto-add discovered peer with default settings
            peer = SyncPeer(
                node_id=sync_msg.sender_id,
                name=sync_msg.data.get('name', f"BBS-{sync_msg.sender_id[-4:]}"),
                sync_enabled=True,
                priority=1
            )
            self.add_peer(peer)
            
            self.logger.info(f"Auto-discovered BBS peer: {peer.name} ({peer.node_id})")
    
    async def _handle_sync_request(self, sync_msg: SyncMessage):
        """Handle synchronization request from peer"""
        peer = self.get_peer(sync_msg.sender_id)
        if not peer or not peer.sync_enabled:
            return
        
        try:
            # Parse request data
            last_sync_str = sync_msg.data.get('last_sync')
            last_sync = datetime.fromisoformat(last_sync_str) if last_sync_str else None
            sync_bulletins = sync_msg.data.get('sync_bulletins', True)
            sync_mail = sync_msg.data.get('sync_mail', True)
            sync_channels = sync_msg.data.get('sync_channels', True)
            max_age_days = sync_msg.data.get('max_age_days', 30)
            
            # Collect data to sync
            sync_data = {}
            
            if sync_bulletins:
                bulletins = await self._get_bulletins_for_sync(last_sync, max_age_days)
                sync_data['bulletins'] = [b.to_dict() for b in bulletins]
            
            if sync_mail:
                mail = await self._get_mail_for_sync(last_sync, max_age_days)
                sync_data['mail'] = [m.to_dict() for m in mail]
            
            if sync_channels:
                channels = await self._get_channels_for_sync(last_sync, max_age_days)
                sync_data['channels'] = [c.to_dict() for c in channels]
            
            # Send response
            response = SyncMessage(
                message_type=SyncMessageType.SYNC_RESPONSE,
                sender_id=self.node_id,
                recipient_id=sync_msg.sender_id,
                data=sync_data
            )
            
            await self._send_sync_message(response)
            self.logger.debug(f"Sent sync response to {peer.name}")
            
        except Exception as e:
            self.logger.error(f"Error handling sync request from {sync_msg.sender_id}: {e}")
    
    async def _handle_sync_response(self, sync_msg: SyncMessage):
        """Handle synchronization response from peer"""
        peer = self.get_peer(sync_msg.sender_id)
        if not peer:
            return
        
        try:
            # Process received data
            sync_data = sync_msg.data
            conflicts = []
            
            # Process bulletins
            if 'bulletins' in sync_data:
                bulletin_conflicts = await self._sync_bulletins(sync_data['bulletins'], peer)
                conflicts.extend(bulletin_conflicts)
            
            # Process mail
            if 'mail' in sync_data:
                mail_conflicts = await self._sync_mail(sync_data['mail'], peer)
                conflicts.extend(mail_conflicts)
            
            # Process channels
            if 'channels' in sync_data:
                channel_conflicts = await self._sync_channels(sync_data['channels'], peer)
                conflicts.extend(channel_conflicts)
            
            # Update peer sync timestamp
            peer.last_sync = datetime.utcnow()
            
            # Log sync completion
            self.sync_history.append((peer.node_id, peer.last_sync, len(conflicts) == 0))
            
            if conflicts:
                self.logger.warning(f"Sync with {peer.name} completed with {len(conflicts)} conflicts")
            else:
                self.logger.info(f"Sync with {peer.name} completed successfully")
            
            # Send acknowledgment
            ack = SyncMessage(
                message_type=SyncMessageType.SYNC_ACK,
                sender_id=self.node_id,
                recipient_id=sync_msg.sender_id,
                data={
                    'success': len(conflicts) == 0,
                    'conflicts': len(conflicts),
                    'timestamp': datetime.utcnow().isoformat()
                }
            )
            
            await self._send_sync_message(ack)
            
        except Exception as e:
            self.logger.error(f"Error handling sync response from {sync_msg.sender_id}: {e}")
    
    async def _handle_bulletin_sync(self, sync_msg: SyncMessage):
        """Handle individual bulletin sync message"""
        # This would be used for real-time sync of individual bulletins
        pass
    
    async def _handle_mail_sync(self, sync_msg: SyncMessage):
        """Handle individual mail sync message"""
        # This would be used for real-time sync of individual mail
        pass
    
    async def _handle_channel_sync(self, sync_msg: SyncMessage):
        """Handle individual channel sync message"""
        # This would be used for real-time sync of individual channels
        pass
    
    async def _handle_sync_ack(self, sync_msg: SyncMessage):
        """Handle sync acknowledgment"""
        # Remove from pending syncs
        for sync_id, pending_msg in list(self.pending_syncs.items()):
            if pending_msg.recipient_id == sync_msg.sender_id:
                del self.pending_syncs[sync_id]
                break
        
        success = sync_msg.data.get('success', False)
        conflicts = sync_msg.data.get('conflicts', 0)
        
        if success:
            self.logger.debug(f"Sync acknowledged by {sync_msg.sender_id}")
        else:
            self.logger.warning(f"Sync with {sync_msg.sender_id} had {conflicts} conflicts")
    
    async def _get_bulletins_for_sync(self, since: Optional[datetime], max_age_days: int) -> List[BBSBulletin]:
        """Get bulletins that need to be synced"""
        try:
            # Get recent bulletins
            cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)
            
            if since and since > cutoff_date:
                # Get bulletins since last sync
                bulletins = self.db.get_all_bulletins(limit=1000)
                return [b for b in bulletins if b.timestamp > since]
            else:
                # Get all recent bulletins
                bulletins = self.db.get_all_bulletins(limit=1000)
                return [b for b in bulletins if b.timestamp > cutoff_date]
                
        except Exception as e:
            self.logger.error(f"Error getting bulletins for sync: {e}")
            return []
    
    async def _get_mail_for_sync(self, since: Optional[datetime], max_age_days: int) -> List[BBSMail]:
        """Get mail that needs to be synced"""
        try:
            # For now, we don't sync private mail between nodes
            # This could be extended to sync mail for users who exist on multiple nodes
            return []
            
        except Exception as e:
            self.logger.error(f"Error getting mail for sync: {e}")
            return []
    
    async def _get_channels_for_sync(self, since: Optional[datetime], max_age_days: int) -> List[BBSChannel]:
        """Get channels that need to be synced"""
        try:
            # Get all active channels
            channels = self.db.get_all_channels(active_only=True)
            
            if since:
                # Filter by timestamp
                return [c for c in channels if c.added_at > since]
            else:
                return channels
                
        except Exception as e:
            self.logger.error(f"Error getting channels for sync: {e}")
            return []
    
    async def _sync_bulletins(self, bulletin_data: List[Dict], peer: SyncPeer) -> List[str]:
        """Sync bulletins with conflict detection"""
        conflicts = []
        
        for data in bulletin_data:
            try:
                bulletin = BBSBulletin.from_dict(data)
                
                # Check for existing bulletin with same unique_id
                existing = None
                try:
                    # We'd need to add a method to get bulletin by unique_id
                    # For now, we'll check by content hash
                    existing_bulletins = self.db.search_bulletins(bulletin.subject[:20])
                    for existing_bulletin in existing_bulletins:
                        if existing_bulletin.unique_id == bulletin.unique_id:
                            existing = existing_bulletin
                            break
                except:
                    pass
                
                if existing:
                    # Handle conflict
                    conflict = await self._resolve_bulletin_conflict(existing, bulletin, peer)
                    if conflict:
                        conflicts.append(conflict)
                else:
                    # Create new bulletin
                    self.db.create_bulletin(
                        bulletin.board,
                        bulletin.sender_id,
                        bulletin.sender_name,
                        bulletin.subject,
                        bulletin.content
                    )
                    
            except Exception as e:
                self.logger.error(f"Error syncing bulletin: {e}")
                conflicts.append(f"Failed to sync bulletin: {e}")
        
        return conflicts
    
    async def _sync_mail(self, mail_data: List[Dict], peer: SyncPeer) -> List[str]:
        """Sync mail with conflict detection"""
        # For now, we don't sync private mail between nodes
        # This could be extended for shared mailboxes or system messages
        return []
    
    async def _sync_channels(self, channel_data: List[Dict], peer: SyncPeer) -> List[str]:
        """Sync channels with conflict detection"""
        conflicts = []
        
        for data in channel_data:
            try:
                channel = BBSChannel.from_dict(data)
                
                # Check for existing channel with same name and frequency
                existing_channels = self.db.search_channels(channel.name)
                existing = None
                
                for existing_channel in existing_channels:
                    if (existing_channel.name.lower() == channel.name.lower() and
                        existing_channel.frequency == channel.frequency):
                        existing = existing_channel
                        break
                
                if existing:
                    # Handle conflict
                    conflict = await self._resolve_channel_conflict(existing, channel, peer)
                    if conflict:
                        conflicts.append(conflict)
                else:
                    # Add new channel
                    self.db.add_channel(
                        channel.name,
                        channel.frequency,
                        channel.description,
                        channel.channel_type.value,
                        channel.location,
                        channel.coverage_area,
                        channel.tone,
                        channel.offset,
                        f"sync:{peer.node_id}"
                    )
                    
            except Exception as e:
                self.logger.error(f"Error syncing channel: {e}")
                conflicts.append(f"Failed to sync channel: {e}")
        
        return conflicts
    
    async def _resolve_bulletin_conflict(self, existing: BBSBulletin, incoming: BBSBulletin, peer: SyncPeer) -> Optional[str]:
        """Resolve bulletin conflict"""
        if self.conflict_resolution == ConflictResolution.TIMESTAMP_WINS:
            if incoming.timestamp > existing.timestamp:
                # Update existing bulletin (if possible)
                # For now, we'll just log the conflict
                self.logger.warning(f"Bulletin conflict: incoming is newer but we can't update existing")
                return f"Bulletin conflict: {existing.subject} vs {incoming.subject}"
        
        return None
    
    async def _resolve_channel_conflict(self, existing: BBSChannel, incoming: BBSChannel, peer: SyncPeer) -> Optional[str]:
        """Resolve channel conflict"""
        if self.conflict_resolution == ConflictResolution.TIMESTAMP_WINS:
            if incoming.added_at > existing.added_at:
                # Update existing channel
                self.db.update_channel(
                    existing.id,
                    description=incoming.description,
                    location=incoming.location,
                    coverage_area=incoming.coverage_area,
                    tone=incoming.tone,
                    offset=incoming.offset
                )
                return None
        
        return f"Channel conflict: {existing.name} has conflicting information"
    
    async def _cleanup_pending_syncs(self):
        """Clean up old pending sync requests"""
        cutoff = datetime.utcnow() - timedelta(minutes=10)
        
        for sync_id, sync_msg in list(self.pending_syncs.items()):
            if sync_msg.timestamp < cutoff:
                del self.pending_syncs[sync_id]
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get synchronization status"""
        return {
            'enabled': self.sync_enabled,
            'peers': len(self.peers),
            'pending_syncs': len(self.pending_syncs),
            'last_sync_check': self.last_sync_check.isoformat(),
            'sync_history': [
                {
                    'peer_id': peer_id,
                    'timestamp': timestamp.isoformat(),
                    'success': success
                }
                for peer_id, timestamp, success in self.sync_history[-10:]  # Last 10 syncs
            ]
        }