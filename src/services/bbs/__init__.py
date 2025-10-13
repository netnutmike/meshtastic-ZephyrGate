"""
BBS Service Module for ZephyrGate

Bulletin Board System with mail, bulletins, channel directory, and JS8Call integration.
"""

from .models import (
    BBSBulletin, BBSMail, BBSChannel, JS8CallMessage, BBSSession,
    BBSMessageType, MailStatus, ChannelType, JS8CallPriority,
    generate_unique_id, validate_bulletin_subject, validate_bulletin_content,
    validate_mail_subject, validate_mail_content, validate_channel_name
)

from .database import BBSDatabase, get_bbs_database
from .bulletin_service import BulletinService, get_bulletin_service
from .mail_service import MailService, get_mail_service
from .channel_service import ChannelService, get_channel_service
from .sync_service import BBSSyncService, SyncPeer, SyncMessage, SyncMessageType

__all__ = [
    'BBSBulletin', 'BBSMail', 'BBSChannel', 'JS8CallMessage', 'BBSSession',
    'BBSMessageType', 'MailStatus', 'ChannelType', 'JS8CallPriority',
    'generate_unique_id', 'validate_bulletin_subject', 'validate_bulletin_content',
    'validate_mail_subject', 'validate_mail_content', 'validate_channel_name',
    'BBSDatabase', 'get_bbs_database',
    'BulletinService', 'get_bulletin_service',
    'MailService', 'get_mail_service',
    'ChannelService', 'get_channel_service',
    'BBSSyncService', 'SyncPeer', 'SyncMessage', 'SyncMessageType'
]