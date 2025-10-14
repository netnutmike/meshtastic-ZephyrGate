"""
Unit tests for Asset Tracking Models

Tests data models and serialization for asset tracking.
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any

from src.services.asset.models import (
    CheckInRecord, AssetInfo, AssetStatus, CheckInAction,
    ChecklistSummary, CheckInStats
)


class TestAssetModels:
    """Test cases for asset tracking models"""
    
    def test_checkin_action_enum(self):
        """Test CheckInAction enum"""
        assert CheckInAction.CHECKIN.value == "checkin"
        assert CheckInAction.CHECKOUT.value == "checkout"
    
    def test_asset_status_enum(self):
        """Test AssetStatus enum"""
        assert AssetStatus.CHECKED_IN.value == "checked_in"
        assert AssetStatus.CHECKED_OUT.value == "checked_out"
        assert AssetStatus.UNKNOWN.value == "unknown"
    
    def test_checkin_record_creation(self):
        """Test CheckInRecord creation and serialization"""
        now = datetime.now(timezone.utc)
        
        record = CheckInRecord(
            id=1,
            node_id="!12345678",
            action=CheckInAction.CHECKIN,
            notes="Ready for duty",
            timestamp=now
        )
        
        assert record.id == 1
        assert record.node_id == "!12345678"
        assert record.action == CheckInAction.CHECKIN
        assert record.notes == "Ready for duty"
        assert record.timestamp == now
    
    def test_checkin_record_to_dict(self):
        """Test CheckInRecord serialization to dictionary"""
        now = datetime.now(timezone.utc)
        
        record = CheckInRecord(
            id=1,
            node_id="!12345678",
            action=CheckInAction.CHECKIN,
            notes="Test notes",
            timestamp=now
        )
        
        data = record.to_dict()
        
        assert data['id'] == 1
        assert data['node_id'] == "!12345678"
        assert data['action'] == "checkin"
        assert data['notes'] == "Test notes"
        assert data['timestamp'] == now.isoformat()
    
    def test_checkin_record_from_dict(self):
        """Test CheckInRecord deserialization from dictionary"""
        now = datetime.now(timezone.utc)
        
        data = {
            'id': 1,
            'node_id': "!12345678",
            'action': "checkin",
            'notes': "Test notes",
            'timestamp': now.isoformat()
        }
        
        record = CheckInRecord.from_dict(data)
        
        assert record.id == 1
        assert record.node_id == "!12345678"
        assert record.action == CheckInAction.CHECKIN
        assert record.notes == "Test notes"
        assert record.timestamp == now
    
    def test_asset_info_creation(self):
        """Test AssetInfo creation"""
        now = datetime.now(timezone.utc)
        
        asset = AssetInfo(
            node_id="!12345678",
            short_name="TestUser",
            long_name="Test User",
            status=AssetStatus.CHECKED_IN,
            last_checkin=now,
            current_notes="Ready",
            checkin_count=5
        )
        
        assert asset.node_id == "!12345678"
        assert asset.short_name == "TestUser"
        assert asset.long_name == "Test User"
        assert asset.status == AssetStatus.CHECKED_IN
        assert asset.last_checkin == now
        assert asset.current_notes == "Ready"
        assert asset.checkin_count == 5
    
    def test_asset_info_to_dict(self):
        """Test AssetInfo serialization"""
        now = datetime.now(timezone.utc)
        
        asset = AssetInfo(
            node_id="!12345678",
            short_name="TestUser",
            status=AssetStatus.CHECKED_IN,
            last_checkin=now,
            checkin_count=3
        )
        
        data = asset.to_dict()
        
        assert data['node_id'] == "!12345678"
        assert data['short_name'] == "TestUser"
        assert data['status'] == "checked_in"
        assert data['last_checkin'] == now.isoformat()
        assert data['checkin_count'] == 3
    
    def test_checklist_summary_creation(self):
        """Test ChecklistSummary creation"""
        asset1 = AssetInfo(
            node_id="!user1",
            short_name="User1",
            status=AssetStatus.CHECKED_IN
        )
        
        asset2 = AssetInfo(
            node_id="!user2",
            short_name="User2",
            status=AssetStatus.CHECKED_OUT
        )
        
        summary = ChecklistSummary(
            total_users=2,
            checked_in_users=1,
            checked_out_users=1,
            unknown_status_users=0,
            assets=[asset1, asset2]
        )
        
        assert summary.total_users == 2
        assert summary.checked_in_users == 1
        assert summary.checked_out_users == 1
        assert summary.unknown_status_users == 0
        assert len(summary.assets) == 2
    
    def test_checklist_summary_to_dict(self):
        """Test ChecklistSummary serialization"""
        asset = AssetInfo(
            node_id="!user1",
            short_name="User1",
            status=AssetStatus.CHECKED_IN
        )
        
        summary = ChecklistSummary(
            total_users=1,
            checked_in_users=1,
            checked_out_users=0,
            unknown_status_users=0,
            assets=[asset]
        )
        
        data = summary.to_dict()
        
        assert data['total_users'] == 1
        assert data['checked_in_users'] == 1
        assert data['checked_out_users'] == 0
        assert data['unknown_status_users'] == 0
        assert len(data['assets']) == 1
        assert data['assets'][0]['node_id'] == "!user1"
    
    def test_checkin_stats_creation(self):
        """Test CheckInStats creation"""
        now = datetime.now(timezone.utc)
        
        record1 = CheckInRecord(
            node_id="!user1",
            action=CheckInAction.CHECKIN,
            timestamp=now
        )
        
        record2 = CheckInRecord(
            node_id="!user1",
            action=CheckInAction.CHECKOUT,
            timestamp=now - timedelta(hours=1)
        )
        
        stats = CheckInStats(
            total_checkins=1,
            total_checkouts=1,
            unique_users=1,
            most_active_user="!user1",
            most_active_count=2,
            recent_activity=[record1, record2]
        )
        
        assert stats.total_checkins == 1
        assert stats.total_checkouts == 1
        assert stats.unique_users == 1
        assert stats.most_active_user == "!user1"
        assert stats.most_active_count == 2
        assert len(stats.recent_activity) == 2
    
    def test_checkin_stats_to_dict(self):
        """Test CheckInStats serialization"""
        record = CheckInRecord(
            node_id="!user1",
            action=CheckInAction.CHECKIN,
            timestamp=datetime.now(timezone.utc)
        )
        
        stats = CheckInStats(
            total_checkins=5,
            total_checkouts=3,
            unique_users=2,
            most_active_user="!user1",
            most_active_count=8,
            recent_activity=[record]
        )
        
        data = stats.to_dict()
        
        assert data['total_checkins'] == 5
        assert data['total_checkouts'] == 3
        assert data['unique_users'] == 2
        assert data['most_active_user'] == "!user1"
        assert data['most_active_count'] == 8
        assert len(data['recent_activity']) == 1
        assert data['recent_activity'][0]['node_id'] == "!user1"
    
    def test_default_values(self):
        """Test model default values"""
        # Test CheckInRecord defaults
        record = CheckInRecord(node_id="!test")
        assert record.id is None
        assert record.action == CheckInAction.CHECKIN
        assert record.notes is None
        assert isinstance(record.timestamp, datetime)
        
        # Test AssetInfo defaults
        asset = AssetInfo(node_id="!test", short_name="Test")
        assert asset.long_name is None
        assert asset.status == AssetStatus.UNKNOWN
        assert asset.last_checkin is None
        assert asset.last_checkout is None
        assert asset.current_notes is None
        assert asset.checkin_count == 0
        
        # Test ChecklistSummary defaults
        summary = ChecklistSummary()
        assert summary.total_users == 0
        assert summary.checked_in_users == 0
        assert summary.checked_out_users == 0
        assert summary.unknown_status_users == 0
        assert len(summary.assets) == 0
        
        # Test CheckInStats defaults
        stats = CheckInStats()
        assert stats.total_checkins == 0
        assert stats.total_checkouts == 0
        assert stats.unique_users == 0
        assert stats.most_active_user is None
        assert stats.most_active_count == 0
        assert len(stats.recent_activity) == 0


if __name__ == '__main__':
    pytest.main([__file__])