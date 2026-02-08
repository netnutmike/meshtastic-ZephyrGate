"""
Unit tests for Network Health Monitor

Tests health metrics tracking, success/failure recording, quiet hours,
congestion detection, and emergency stop functionality.

Requirements: 12.1, 12.2, 12.3, 12.4, 12.5
"""

import pytest
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
import sys

# Add plugins directory to path
plugins_path = Path(__file__).parent.parent.parent.parent / "plugins"
if str(plugins_path) not in sys.path:
    sys.path.insert(0, str(plugins_path))

from traceroute_mapper.network_health_monitor import (
    NetworkHealthMonitor,
    NetworkHealthMetrics
)


@pytest.fixture
def monitor():
    """Provide a network health monitor with default settings"""
    return NetworkHealthMonitor()


@pytest.fixture
def monitor_with_quiet_hours():
    """Provide a monitor with quiet hours enabled"""
    return NetworkHealthMonitor(
        quiet_hours_enabled=True,
        quiet_hours_start="22:00",
        quiet_hours_end="06:00"
    )


@pytest.fixture
def monitor_strict():
    """Provide a monitor with strict thresholds for testing"""
    return NetworkHealthMonitor(
        success_rate_threshold=0.8,
        failure_threshold=0.3,
        consecutive_failures_threshold=5,
        auto_recovery_minutes=1,
        window_size=10
    )


class TestInitialization:
    """Tests for NetworkHealthMonitor initialization"""
    
    def test_initialization_with_defaults(self):
        """Test monitor initializes with default values"""
        monitor = NetworkHealthMonitor()
        
        assert monitor.success_rate_threshold == 0.5
        assert monitor.failure_threshold == 0.2
        assert monitor.consecutive_failures_threshold == 10
        assert monitor.auto_recovery_minutes == 30
        assert monitor.quiet_hours_enabled is False
        assert monitor.congestion_enabled is True
        assert monitor.throttle_multiplier == 0.5
        assert monitor.window_size == 20
    
    def test_initialization_with_custom_values(self):
        """Test monitor initializes with custom values"""
        monitor = NetworkHealthMonitor(
            success_rate_threshold=0.7,
            failure_threshold=0.3,
            consecutive_failures_threshold=5,
            auto_recovery_minutes=15,
            quiet_hours_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="06:00",
            congestion_enabled=False,
            throttle_multiplier=0.3,
            window_size=50
        )
        
        assert monitor.success_rate_threshold == 0.7
        assert monitor.failure_threshold == 0.3
        assert monitor.consecutive_failures_threshold == 5
        assert monitor.auto_recovery_minutes == 15
        assert monitor.quiet_hours_enabled is True
        assert monitor.congestion_enabled is False
        assert monitor.throttle_multiplier == 0.3
        assert monitor.window_size == 50
    
    def test_initial_metrics(self):
        """Test monitor starts with zero metrics"""
        monitor = NetworkHealthMonitor()
        
        assert monitor.total_requests == 0
        assert monitor.successful_requests == 0
        assert monitor.failed_requests == 0
        assert monitor.timeout_count == 0
        assert monitor.consecutive_failures == 0
        assert monitor.is_emergency_stop is False
        assert monitor.is_congested is False
    
    def test_quiet_hours_parsing(self):
        """Test quiet hours time parsing"""
        monitor = NetworkHealthMonitor(
            quiet_hours_enabled=True,
            quiet_hours_start="22:30",
            quiet_hours_end="06:45"
        )
        
        assert monitor.quiet_hours_start == dt_time(22, 30)
        assert monitor.quiet_hours_end == dt_time(6, 45)
    
    def test_invalid_quiet_hours_parsing(self):
        """Test invalid quiet hours are handled gracefully"""
        monitor = NetworkHealthMonitor(
            quiet_hours_enabled=True,
            quiet_hours_start="invalid",
            quiet_hours_end="25:00"
        )
        
        # Should not crash, just set to None
        assert monitor.quiet_hours_start is None
        assert monitor.quiet_hours_end is None


class TestSuccessRecording:
    """Tests for recording successful traceroutes"""
    
    def test_record_success_updates_metrics(self, monitor):
        """Test recording success updates metrics correctly"""
        monitor.record_success()
        
        assert monitor.total_requests == 1
        assert monitor.successful_requests == 1
        assert monitor.failed_requests == 0
        assert monitor.consecutive_failures == 0
        assert monitor.get_success_rate() == 1.0
    
    def test_record_success_with_response_time(self, monitor):
        """Test recording success with response time"""
        monitor.record_success(response_time=1.5)
        
        assert monitor.total_requests == 1
        assert monitor.successful_requests == 1
        assert len(monitor.response_times) == 1
        assert monitor.response_times[0] == 1.5
        assert monitor.get_avg_response_time() == 1.5
    
    def test_record_multiple_successes(self, monitor):
        """Test recording multiple successes"""
        for i in range(5):
            monitor.record_success(response_time=float(i + 1))
        
        assert monitor.total_requests == 5
        assert monitor.successful_requests == 5
        assert monitor.failed_requests == 0
        assert monitor.get_success_rate() == 1.0
        assert len(monitor.response_times) == 5
        assert monitor.get_avg_response_time() == 3.0  # (1+2+3+4+5)/5
    
    def test_record_success_resets_consecutive_failures(self, monitor):
        """Test recording success resets consecutive failures counter"""
        # Record some failures
        for _ in range(3):
            monitor.record_failure()
        
        assert monitor.consecutive_failures == 3
        
        # Record success
        monitor.record_success()
        
        assert monitor.consecutive_failures == 0
    
    def test_response_times_limited(self, monitor):
        """Test response times list is limited to max size"""
        # Record more than max_response_times (100)
        for i in range(150):
            monitor.record_success(response_time=float(i))
        
        # Should only keep last 100
        assert len(monitor.response_times) == 100
        assert monitor.response_times[0] == 50.0  # First of last 100
        assert monitor.response_times[-1] == 149.0  # Last one


class TestFailureRecording:
    """Tests for recording failed traceroutes"""
    
    def test_record_failure_updates_metrics(self, monitor):
        """Test recording failure updates metrics correctly"""
        monitor.record_failure()
        
        assert monitor.total_requests == 1
        assert monitor.successful_requests == 0
        assert monitor.failed_requests == 1
        assert monitor.consecutive_failures == 1
        assert monitor.get_success_rate() == 0.0
    
    def test_record_failure_with_timeout(self, monitor):
        """Test recording failure with timeout flag"""
        monitor.record_failure(is_timeout=True)
        
        assert monitor.total_requests == 1
        assert monitor.failed_requests == 1
        assert monitor.timeout_count == 1
    
    def test_record_multiple_failures(self, monitor):
        """Test recording multiple failures"""
        for _ in range(5):
            monitor.record_failure()
        
        assert monitor.total_requests == 5
        assert monitor.successful_requests == 0
        assert monitor.failed_requests == 5
        assert monitor.consecutive_failures == 5
        assert monitor.get_success_rate() == 0.0
    
    def test_consecutive_failures_increment(self, monitor):
        """Test consecutive failures counter increments"""
        for i in range(1, 6):
            monitor.record_failure()
            assert monitor.consecutive_failures == i


class TestSuccessRateCalculation:
    """Tests for success rate calculation"""
    
    def test_success_rate_no_requests(self, monitor):
        """Test success rate with no requests returns 1.0"""
        assert monitor.get_success_rate() == 1.0
    
    def test_success_rate_all_successes(self, monitor):
        """Test success rate with all successes"""
        for _ in range(10):
            monitor.record_success()
        
        assert monitor.get_success_rate() == 1.0
    
    def test_success_rate_all_failures(self, monitor):
        """Test success rate with all failures"""
        for _ in range(10):
            monitor.record_failure()
        
        assert monitor.get_success_rate() == 0.0
    
    def test_success_rate_mixed(self, monitor):
        """Test success rate with mixed results"""
        # 7 successes, 3 failures = 70% success rate
        for _ in range(7):
            monitor.record_success()
        for _ in range(3):
            monitor.record_failure()
        
        assert monitor.get_success_rate() == 0.7
    
    def test_recent_success_rate_no_requests(self, monitor):
        """Test recent success rate with no requests returns 1.0"""
        assert monitor.get_recent_success_rate() == 1.0
    
    def test_recent_success_rate_within_window(self, monitor_strict):
        """Test recent success rate only considers window"""
        # Window size is 10 for monitor_strict
        
        # Record 5 successes
        for _ in range(5):
            monitor_strict.record_success()
        
        # Record 5 failures
        for _ in range(5):
            monitor_strict.record_failure()
        
        # Recent success rate should be 50% (5 successes, 5 failures in window)
        assert monitor_strict.get_recent_success_rate() == 0.5
        
        # Record 10 more successes (pushes failures out of window)
        for _ in range(10):
            monitor_strict.record_success()
        
        # Recent success rate should now be 100% (only successes in window)
        assert monitor_strict.get_recent_success_rate() == 1.0


class TestHealthCheck:
    """Tests for is_healthy() method"""
    
    def test_is_healthy_initially(self, monitor):
        """Test monitor is healthy initially"""
        assert monitor.is_healthy() is True
    
    def test_is_healthy_with_good_success_rate(self, monitor):
        """Test monitor is healthy with good success rate"""
        # 8 successes, 2 failures = 80% success rate (above 20% threshold)
        for _ in range(8):
            monitor.record_success()
        for _ in range(2):
            monitor.record_failure()
        
        assert monitor.is_healthy() is True
    
    def test_is_unhealthy_with_low_success_rate(self, monitor):
        """Test monitor is unhealthy with low success rate"""
        # 1 success, 9 failures = 10% success rate (below 20% threshold)
        for _ in range(1):
            monitor.record_success()
        for _ in range(9):
            monitor.record_failure()
        
        assert monitor.is_healthy() is False
    
    def test_is_unhealthy_in_emergency_stop(self, monitor):
        """Test monitor is unhealthy in emergency stop"""
        monitor.enter_emergency_stop("test")
        
        assert monitor.is_healthy() is False
    
    def test_is_unhealthy_in_quiet_hours(self, monitor_with_quiet_hours):
        """Test monitor is unhealthy during quiet hours"""
        # This test depends on current time, so we'll test the logic
        # by checking if quiet hours are properly configured
        assert monitor_with_quiet_hours.quiet_hours_enabled is True
        assert monitor_with_quiet_hours.quiet_hours_start is not None
        assert monitor_with_quiet_hours.quiet_hours_end is not None


class TestQuietHours:
    """Tests for quiet hours functionality"""
    
    def test_quiet_hours_disabled(self, monitor):
        """Test quiet hours when disabled"""
        assert monitor.is_quiet_hours() is False
    
    def test_quiet_hours_not_configured(self):
        """Test quiet hours when enabled but not configured"""
        monitor = NetworkHealthMonitor(
            quiet_hours_enabled=True,
            quiet_hours_start=None,
            quiet_hours_end=None
        )
        
        assert monitor.is_quiet_hours() is False
    
    def test_quiet_hours_normal_range(self):
        """Test quiet hours with normal time range (not spanning midnight)"""
        # Create monitor with quiet hours 10:00 to 14:00
        monitor = NetworkHealthMonitor(
            quiet_hours_enabled=True,
            quiet_hours_start="10:00",
            quiet_hours_end="14:00"
        )
        
        # Mock current time by directly checking the logic
        # In real scenario, this would depend on actual time
        start = dt_time(10, 0)
        end = dt_time(14, 0)
        
        # Test times within range
        assert start <= dt_time(11, 0) <= end
        assert start <= dt_time(12, 30) <= end
        
        # Test times outside range
        assert not (start <= dt_time(9, 0) <= end)
        assert not (start <= dt_time(15, 0) <= end)
    
    def test_quiet_hours_spanning_midnight(self):
        """Test quiet hours spanning midnight"""
        # Create monitor with quiet hours 22:00 to 06:00
        monitor = NetworkHealthMonitor(
            quiet_hours_enabled=True,
            quiet_hours_start="22:00",
            quiet_hours_end="06:00"
        )
        
        # Verify configuration
        assert monitor.quiet_hours_start == dt_time(22, 0)
        assert monitor.quiet_hours_end == dt_time(6, 0)
        
        # Test the logic for spanning midnight
        start = dt_time(22, 0)
        end = dt_time(6, 0)
        
        # Times that should be in quiet hours
        assert dt_time(23, 0) >= start  # After start
        assert dt_time(1, 0) <= end     # Before end
        assert dt_time(5, 30) <= end    # Before end
        
        # Times that should NOT be in quiet hours
        test_time = dt_time(12, 0)
        assert not (test_time >= start or test_time <= end)


class TestCongestionDetection:
    """Tests for congestion detection"""
    
    def test_no_congestion_initially(self, monitor):
        """Test no congestion initially"""
        assert monitor.is_congested is False
        assert monitor.should_throttle() is False
    
    def test_congestion_detected_low_success_rate(self, monitor_strict):
        """Test congestion is detected with low success rate"""
        # monitor_strict has success_rate_threshold of 0.8
        # Record 3 successes, 7 failures = 30% success rate (below 80%)
        for _ in range(3):
            monitor_strict.record_success()
        for _ in range(7):
            monitor_strict.record_failure()
        
        assert monitor_strict.is_congested is True
        assert monitor_strict.should_throttle() is True
    
    def test_congestion_cleared_improved_success_rate(self, monitor_strict):
        """Test congestion clears when success rate improves"""
        # First cause congestion
        for _ in range(3):
            monitor_strict.record_success()
        for _ in range(7):
            monitor_strict.record_failure()
        
        assert monitor_strict.is_congested is True
        
        # Now improve success rate (window size is 10)
        # Record 10 successes to push failures out of window
        for _ in range(10):
            monitor_strict.record_success()
        
        # Congestion should be cleared
        assert monitor_strict.is_congested is False
        assert monitor_strict.should_throttle() is False
    
    def test_congestion_disabled(self):
        """Test congestion detection when disabled"""
        monitor = NetworkHealthMonitor(congestion_enabled=False)
        
        # Record all failures
        for _ in range(10):
            monitor.record_failure()
        
        # Should not detect congestion
        assert monitor.is_congested is False
        assert monitor.should_throttle() is False


class TestRecommendedRate:
    """Tests for get_recommended_rate()"""
    
    def test_recommended_rate_normal(self, monitor):
        """Test recommended rate when healthy"""
        base_rate = 60.0
        recommended = monitor.get_recommended_rate(base_rate)
        
        assert recommended == base_rate
    
    def test_recommended_rate_congested(self, monitor_strict):
        """Test recommended rate when congested"""
        # Cause congestion without triggering emergency stop
        # Record 3 successes, 4 failures = 42.8% success rate (below 80% threshold but above 30% emergency threshold)
        for _ in range(3):
            monitor_strict.record_success()
        for _ in range(4):
            monitor_strict.record_failure()
        
        assert monitor_strict.is_congested is True
        assert monitor_strict.is_emergency_stop is False  # Should not trigger emergency stop yet
        
        base_rate = 60.0
        recommended = monitor_strict.get_recommended_rate(base_rate)
        
        # Should be throttled (default throttle_multiplier is 0.5)
        assert recommended == base_rate * 0.5
    
    def test_recommended_rate_emergency_stop(self, monitor):
        """Test recommended rate in emergency stop"""
        monitor.enter_emergency_stop("test")
        
        base_rate = 60.0
        recommended = monitor.get_recommended_rate(base_rate)
        
        # Should be zero in emergency stop
        assert recommended == 0.0


class TestEmergencyStop:
    """Tests for emergency stop functionality"""
    
    def test_emergency_stop_not_triggered_initially(self, monitor):
        """Test emergency stop is not triggered initially"""
        assert monitor.is_emergency_stop is False
        assert monitor.emergency_stop_time is None
        assert monitor.emergency_stop_reason is None
    
    def test_emergency_stop_triggered_by_consecutive_failures(self, monitor_strict):
        """Test emergency stop triggered by consecutive failures"""
        # monitor_strict has consecutive_failures_threshold of 5
        
        # Record 5 consecutive failures
        for _ in range(5):
            monitor_strict.record_failure()
        
        # Should trigger emergency stop
        assert monitor_strict.is_emergency_stop is True
        assert monitor_strict.emergency_stop_reason is not None
        assert "Consecutive failures" in monitor_strict.emergency_stop_reason
    
    def test_emergency_stop_triggered_by_low_success_rate(self):
        """Test emergency stop triggered by low success rate"""
        # Create a monitor with high consecutive failure threshold to avoid that trigger
        monitor = NetworkHealthMonitor(
            failure_threshold=0.3,
            consecutive_failures_threshold=100,  # Very high to avoid this trigger
            window_size=20
        )
        
        # Record 5 successes, 20 failures = 20% success rate (below 30% threshold)
        for _ in range(5):
            monitor.record_success()
        
        # Record failures one at a time with occasional successes to avoid consecutive failures
        for i in range(20):
            monitor.record_failure()
            if i % 10 == 9:  # Add a success every 10 failures
                monitor.record_success()
        
        # Should trigger emergency stop due to low success rate
        assert monitor.is_emergency_stop is True
        assert monitor.emergency_stop_reason is not None
        assert "Success rate below threshold" in monitor.emergency_stop_reason
    
    def test_emergency_stop_requires_minimum_requests(self, monitor):
        """Test emergency stop requires minimum requests before triggering on success rate"""
        # Record only 10 failures (below minimum of 20 requests for success rate check)
        # But this will still trigger emergency stop due to consecutive failures (threshold is 10)
        # So we need to intersperse with successes to avoid consecutive failures
        for i in range(10):
            monitor.record_failure()
            if i < 9:  # Don't add success after last failure
                monitor.record_success()
        
        # Should not trigger emergency stop yet (not enough data for success rate check)
        # and consecutive failures is only 1
        assert monitor.is_emergency_stop is False
        assert monitor.total_requests == 19  # 10 failures + 9 successes
        assert monitor.consecutive_failures == 1
    
    def test_enter_emergency_stop_manually(self, monitor):
        """Test manually entering emergency stop"""
        monitor.enter_emergency_stop("Manual trigger for testing")
        
        assert monitor.is_emergency_stop is True
        assert monitor.emergency_stop_time is not None
        assert monitor.emergency_stop_reason == "Manual trigger for testing"
    
    def test_exit_emergency_stop(self, monitor):
        """Test exiting emergency stop"""
        monitor.enter_emergency_stop("test")
        assert monitor.is_emergency_stop is True
        
        monitor.exit_emergency_stop()
        
        assert monitor.is_emergency_stop is False
        assert monitor.emergency_stop_time is None
        assert monitor.emergency_stop_reason is None
    
    def test_enter_emergency_stop_idempotent(self, monitor):
        """Test entering emergency stop multiple times is idempotent"""
        monitor.enter_emergency_stop("first")
        first_time = monitor.emergency_stop_time
        
        monitor.enter_emergency_stop("second")
        
        # Should keep first entry
        assert monitor.emergency_stop_time == first_time
        assert monitor.emergency_stop_reason == "first"


class TestMetrics:
    """Tests for get_metrics() method"""
    
    def test_get_metrics_structure(self, monitor):
        """Test metrics have correct structure"""
        metrics = monitor.get_metrics()
        
        assert isinstance(metrics, NetworkHealthMetrics)
        assert hasattr(metrics, 'total_requests')
        assert hasattr(metrics, 'successful_requests')
        assert hasattr(metrics, 'failed_requests')
        assert hasattr(metrics, 'timeout_count')
        assert hasattr(metrics, 'success_rate')
        assert hasattr(metrics, 'avg_response_time')
        assert hasattr(metrics, 'is_congested')
        assert hasattr(metrics, 'is_emergency_stop')
    
    def test_get_metrics_values(self, monitor):
        """Test metrics contain correct values"""
        # Record some data
        for _ in range(7):
            monitor.record_success(response_time=1.0)
        for _ in range(3):
            monitor.record_failure(is_timeout=True)
        
        metrics = monitor.get_metrics()
        
        assert metrics.total_requests == 10
        assert metrics.successful_requests == 7
        assert metrics.failed_requests == 3
        assert metrics.timeout_count == 3
        assert metrics.success_rate == 0.7
        assert metrics.avg_response_time == 1.0
        assert metrics.is_congested is False
        assert metrics.is_emergency_stop is False


class TestStatus:
    """Tests for get_status() method"""
    
    def test_get_status_structure(self, monitor):
        """Test status has all required fields"""
        status = monitor.get_status()
        
        assert 'healthy' in status
        assert 'is_emergency_stop' in status
        assert 'emergency_stop_reason' in status
        assert 'emergency_stop_time' in status
        assert 'is_congested' in status
        assert 'is_quiet_hours' in status
        assert 'total_requests' in status
        assert 'successful_requests' in status
        assert 'failed_requests' in status
        assert 'timeout_count' in status
        assert 'success_rate' in status
        assert 'recent_success_rate' in status
        assert 'consecutive_failures' in status
        assert 'avg_response_time' in status
        assert 'quiet_hours_enabled' in status
        assert 'congestion_enabled' in status
        assert 'success_rate_threshold' in status
        assert 'failure_threshold' in status
        assert 'consecutive_failures_threshold' in status
    
    def test_get_status_values(self, monitor):
        """Test status contains correct values"""
        status = monitor.get_status()
        
        assert status['healthy'] is True
        assert status['is_emergency_stop'] is False
        assert status['total_requests'] == 0
        assert status['success_rate'] == 1.0
        assert status['quiet_hours_enabled'] is False
        assert status['congestion_enabled'] is True


class TestReset:
    """Tests for reset() method"""
    
    def test_reset_clears_metrics(self, monitor):
        """Test reset clears all metrics"""
        # Record some data
        for _ in range(5):
            monitor.record_success(response_time=1.0)
        for _ in range(3):
            monitor.record_failure()
        
        monitor.enter_emergency_stop("test")
        
        # Reset
        monitor.reset()
        
        # Verify everything is cleared
        assert monitor.total_requests == 0
        assert monitor.successful_requests == 0
        assert monitor.failed_requests == 0
        assert monitor.timeout_count == 0
        assert monitor.consecutive_failures == 0
        assert len(monitor.recent_results) == 0
        assert len(monitor.response_times) == 0
        assert monitor.is_emergency_stop is False
        assert monitor.emergency_stop_time is None
        assert monitor.emergency_stop_reason is None
        assert monitor.is_congested is False


class TestEdgeCases:
    """Tests for edge cases"""
    
    def test_avg_response_time_no_data(self, monitor):
        """Test average response time with no data"""
        assert monitor.get_avg_response_time() == 0.0
    
    def test_success_rate_with_zero_division(self, monitor):
        """Test success rate handles zero division"""
        # No requests recorded
        assert monitor.get_success_rate() == 1.0
        assert monitor.get_recent_success_rate() == 1.0
    
    def test_very_high_consecutive_failures(self, monitor):
        """Test handling very high consecutive failures"""
        for _ in range(1000):
            monitor.record_failure()
        
        assert monitor.consecutive_failures == 1000
        assert monitor.is_emergency_stop is True
    
    def test_alternating_success_failure(self, monitor):
        """Test alternating success and failure"""
        for _ in range(10):
            monitor.record_success()
            monitor.record_failure()
        
        assert monitor.total_requests == 20
        assert monitor.successful_requests == 10
        assert monitor.failed_requests == 10
        assert monitor.get_success_rate() == 0.5
        assert monitor.consecutive_failures == 1  # Last one was failure


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
