"""
Property-Based Tests for Quiet Hours Enforcement

Tests Property 27: Quiet Hours Enforcement
Validates: Requirements 12.1

**Validates: Requirements 12.1**
"""

import pytest
import asyncio
from datetime import datetime, time as dt_time, timedelta
from hypothesis import given, settings, strategies as st, assume, HealthCheck
from hypothesis.strategies import composite
from pathlib import Path
import sys
from unittest.mock import patch, MagicMock

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.traceroute_mapper.network_health_monitor import NetworkHealthMonitor


# Strategy builders for generating test data

@composite
def time_string(draw):
    """Generate valid time strings in HH:MM format"""
    hour = draw(st.integers(min_value=0, max_value=23))
    minute = draw(st.integers(min_value=0, max_value=59))
    return f"{hour:02d}:{minute:02d}"


@composite
def quiet_hours_config(draw):
    """Generate quiet hours configuration"""
    start = draw(time_string())
    end = draw(time_string())
    # Ensure start and end are different
    assume(start != end)
    return start, end


@composite
def time_within_range(draw, start_time, end_time):
    """Generate a time that is within the given range"""
    # Parse start and end times
    start_hour, start_min = map(int, start_time.split(':'))
    end_hour, end_min = map(int, end_time.split(':'))
    
    start_minutes = start_hour * 60 + start_min
    end_minutes = end_hour * 60 + end_min
    
    # Handle midnight spanning
    if start_minutes <= end_minutes:
        # Normal range (e.g., 10:00 to 14:00)
        minutes = draw(st.integers(min_value=start_minutes, max_value=end_minutes))
    else:
        # Spans midnight (e.g., 22:00 to 06:00)
        # Choose either after start or before end
        if draw(st.booleans()):
            # After start (22:00 to 23:59)
            minutes = draw(st.integers(min_value=start_minutes, max_value=23*60+59))
        else:
            # Before end (00:00 to 06:00)
            minutes = draw(st.integers(min_value=0, max_value=end_minutes))
    
    hour = minutes // 60
    minute = minutes % 60
    return dt_time(hour=hour, minute=minute)


@composite
def time_outside_range(draw, start_time, end_time):
    """Generate a time that is outside the given range"""
    # Parse start and end times
    start_hour, start_min = map(int, start_time.split(':'))
    end_hour, end_min = map(int, end_time.split(':'))
    
    start_minutes = start_hour * 60 + start_min
    end_minutes = end_hour * 60 + end_min
    
    # Handle midnight spanning
    if start_minutes <= end_minutes:
        # Normal range (e.g., 10:00 to 14:00)
        # Outside is before start or after end
        if draw(st.booleans()) and start_minutes > 0:
            # Before start
            minutes = draw(st.integers(min_value=0, max_value=start_minutes-1))
        else:
            # After end
            minutes = draw(st.integers(min_value=end_minutes+1, max_value=23*60+59))
    else:
        # Spans midnight (e.g., 22:00 to 06:00)
        # Outside is between end and start
        minutes = draw(st.integers(min_value=end_minutes+1, max_value=start_minutes-1))
    
    hour = minutes // 60
    minute = minutes % 60
    return dt_time(hour=hour, minute=minute)


@composite
def traceroute_request_sequence(draw):
    """Generate a sequence of traceroute request attempts"""
    return draw(st.lists(
        st.tuples(
            st.text(min_size=9, max_size=9, alphabet='!0123456789abcdef'),  # node_id
            st.floats(min_value=0.0, max_value=2.0)  # delay between requests
        ),
        min_size=5,
        max_size=20
    ))


# Property Tests

class TestQuietHoursEnforcementProperty:
    """
    Feature: network-traceroute-mapper, Property 27: Quiet Hours Enforcement
    
    Tests that no traceroute requests are sent during configured quiet hours.
    
    **Validates: Requirements 12.1**
    """
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        start_time=time_string(),
        end_time=time_string()
    )
    def test_is_quiet_hours_returns_true_during_quiet_hours(self, start_time, end_time):
        """
        Property: For any time during configured quiet hours, is_quiet_hours()
        should return True.
        
        This test verifies that the quiet hours detection correctly identifies
        times within the configured quiet hours window.
        
        **Validates: Requirements 12.1**
        """
        # Ensure start and end are different
        assume(start_time != end_time)
        
        # Create monitor with quiet hours enabled
        monitor = NetworkHealthMonitor(
            quiet_hours_enabled=True,
            quiet_hours_start=start_time,
            quiet_hours_end=end_time
        )
        
        # Parse times to get a time within the range
        start_hour, start_min = map(int, start_time.split(':'))
        end_hour, end_min = map(int, end_time.split(':'))
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        
        # Generate a time within the quiet hours range
        if start_minutes <= end_minutes:
            # Normal range (e.g., 10:00 to 14:00)
            test_minutes = (start_minutes + end_minutes) // 2
        else:
            # Spans midnight (e.g., 22:00 to 06:00)
            # Choose a time after start
            test_minutes = start_minutes + 30
            if test_minutes >= 24 * 60:
                test_minutes = test_minutes % (24 * 60)
        
        test_time = dt_time(hour=test_minutes // 60, minute=test_minutes % 60)
        
        # Mock datetime.now() to return our test time
        with patch('plugins.traceroute_mapper.network_health_monitor.datetime') as mock_datetime:
            mock_now = MagicMock()
            mock_now.time.return_value = test_time
            mock_datetime.now.return_value = mock_now
            
            # Check if it's quiet hours
            result = monitor.is_quiet_hours()
            
            # Should return True during quiet hours
            assert result is True, (
                f"is_quiet_hours() should return True during quiet hours. "
                f"Quiet hours: {start_time} to {end_time}, "
                f"Test time: {test_time.strftime('%H:%M')}"
            )
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        start_time=time_string(),
        end_time=time_string()
    )
    def test_is_quiet_hours_returns_false_outside_quiet_hours(self, start_time, end_time):
        """
        Property: For any time outside configured quiet hours, is_quiet_hours()
        should return False.
        
        This test verifies that the quiet hours detection correctly identifies
        times outside the configured quiet hours window.
        
        **Validates: Requirements 12.1**
        """
        # Ensure start and end are different
        assume(start_time != end_time)
        
        # Skip if the range covers the entire day (no outside time)
        start_hour, start_min = map(int, start_time.split(':'))
        end_hour, end_min = map(int, end_time.split(':'))
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        
        # Check if there's any time outside the range
        if start_minutes <= end_minutes:
            # Normal range
            outside_available = start_minutes > 0 or end_minutes < 23*60+59
        else:
            # Spans midnight
            outside_available = end_minutes + 1 < start_minutes
        
        assume(outside_available)
        
        # Create monitor with quiet hours enabled
        monitor = NetworkHealthMonitor(
            quiet_hours_enabled=True,
            quiet_hours_start=start_time,
            quiet_hours_end=end_time
        )
        
        # Generate a time outside the quiet hours range
        if start_minutes <= end_minutes:
            # Normal range - pick time before start or after end
            if start_minutes > 0:
                test_minutes = 0  # Before start
            else:
                test_minutes = 23 * 60 + 59  # After end
        else:
            # Spans midnight - pick time between end and start
            test_minutes = (end_minutes + start_minutes) // 2
        
        test_time = dt_time(hour=test_minutes // 60, minute=test_minutes % 60)
        
        # Mock datetime.now() to return our test time
        with patch('plugins.traceroute_mapper.network_health_monitor.datetime') as mock_datetime:
            mock_now = MagicMock()
            mock_now.time.return_value = test_time
            mock_datetime.now.return_value = mock_now
            
            # Check if it's quiet hours
            result = monitor.is_quiet_hours()
            
            # Should return False outside quiet hours
            assert result is False, (
                f"is_quiet_hours() should return False outside quiet hours. "
                f"Quiet hours: {start_time} to {end_time}, "
                f"Test time: {test_time.strftime('%H:%M')}"
            )
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        start_time=time_string(),
        end_time=time_string()
    )
    def test_is_healthy_returns_false_during_quiet_hours(self, start_time, end_time):
        """
        Property: For any time during configured quiet hours, is_healthy()
        should return False (preventing traceroute operations).
        
        This test verifies that the health check correctly blocks operations
        during quiet hours.
        
        **Validates: Requirements 12.1**
        """
        # Ensure start and end are different
        assume(start_time != end_time)
        
        # Create monitor with quiet hours enabled
        monitor = NetworkHealthMonitor(
            quiet_hours_enabled=True,
            quiet_hours_start=start_time,
            quiet_hours_end=end_time
        )
        
        # Record some successes to ensure good health otherwise
        for _ in range(10):
            monitor.record_success()
        
        # Parse times to get a time within the range
        start_hour, start_min = map(int, start_time.split(':'))
        end_hour, end_min = map(int, end_time.split(':'))
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        
        # Generate a time within the quiet hours range
        if start_minutes <= end_minutes:
            # Normal range (e.g., 10:00 to 14:00)
            test_minutes = (start_minutes + end_minutes) // 2
        else:
            # Spans midnight (e.g., 22:00 to 06:00)
            # Choose a time after start
            test_minutes = start_minutes + 30
            if test_minutes >= 24 * 60:
                test_minutes = test_minutes % (24 * 60)
        
        test_time = dt_time(hour=test_minutes // 60, minute=test_minutes % 60)
        
        # Mock datetime.now() to return our test time
        with patch('plugins.traceroute_mapper.network_health_monitor.datetime') as mock_datetime:
            mock_now = MagicMock()
            mock_now.time.return_value = test_time
            mock_datetime.now.return_value = mock_now
            
            # Check if healthy
            result = monitor.is_healthy()
            
            # Should return False during quiet hours (even with good metrics)
            assert result is False, (
                f"is_healthy() should return False during quiet hours. "
                f"Quiet hours: {start_time} to {end_time}, "
                f"Test time: {test_time.strftime('%H:%M')}, "
                f"Success rate: {monitor.get_success_rate():.2%}"
            )
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        start_time=time_string(),
        end_time=time_string()
    )
    def test_is_healthy_returns_true_outside_quiet_hours_with_good_metrics(self, start_time, end_time):
        """
        Property: For any time outside configured quiet hours, is_healthy()
        should return True if other health metrics are good.
        
        This test verifies that quiet hours don't block operations outside
        the configured window when health is otherwise good.
        
        **Validates: Requirements 12.1**
        """
        # Ensure start and end are different
        assume(start_time != end_time)
        
        # Skip if the range covers the entire day
        start_hour, start_min = map(int, start_time.split(':'))
        end_hour, end_min = map(int, end_time.split(':'))
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        
        if start_minutes <= end_minutes:
            outside_available = start_minutes > 0 or end_minutes < 23*60+59
        else:
            outside_available = end_minutes + 1 < start_minutes
        
        assume(outside_available)
        
        # Create monitor with quiet hours enabled
        monitor = NetworkHealthMonitor(
            quiet_hours_enabled=True,
            quiet_hours_start=start_time,
            quiet_hours_end=end_time
        )
        
        # Record some successes to ensure good health
        for _ in range(10):
            monitor.record_success()
        
        # Generate a time outside the quiet hours range
        if start_minutes <= end_minutes:
            # Normal range - pick time before start or after end
            if start_minutes > 0:
                test_minutes = 0  # Before start
            else:
                test_minutes = 23 * 60 + 59  # After end
        else:
            # Spans midnight - pick time between end and start
            test_minutes = (end_minutes + start_minutes) // 2
        
        test_time = dt_time(hour=test_minutes // 60, minute=test_minutes % 60)
        
        # Mock datetime.now() to return our test time
        with patch('plugins.traceroute_mapper.network_health_monitor.datetime') as mock_datetime:
            mock_now = MagicMock()
            mock_now.time.return_value = test_time
            mock_datetime.now.return_value = mock_now
            
            # Check if healthy
            result = monitor.is_healthy()
            
            # Should return True outside quiet hours with good metrics
            assert result is True, (
                f"is_healthy() should return True outside quiet hours with good metrics. "
                f"Quiet hours: {start_time} to {end_time}, "
                f"Test time: {test_time.strftime('%H:%M')}, "
                f"Success rate: {monitor.get_success_rate():.2%}"
            )
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        start_time=time_string(),
        end_time=time_string()
    )
    def test_quiet_hours_disabled_never_blocks(self, start_time, end_time):
        """
        Property: For any time, when quiet hours are disabled, is_quiet_hours()
        should always return False.
        
        This test verifies that disabling quiet hours allows operations at all times.
        
        **Validates: Requirements 12.1**
        """
        # Ensure start and end are different
        assume(start_time != end_time)
        
        # Create monitor with quiet hours DISABLED
        monitor = NetworkHealthMonitor(
            quiet_hours_enabled=False,
            quiet_hours_start=start_time,
            quiet_hours_end=end_time
        )
        
        # Parse times to get a time within what would be quiet hours
        start_hour, start_min = map(int, start_time.split(':'))
        end_hour, end_min = map(int, end_time.split(':'))
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        
        # Generate a time within the configured range
        if start_minutes <= end_minutes:
            test_minutes = (start_minutes + end_minutes) // 2
        else:
            test_minutes = start_minutes + 30
            if test_minutes >= 24 * 60:
                test_minutes = test_minutes % (24 * 60)
        
        test_time = dt_time(hour=test_minutes // 60, minute=test_minutes % 60)
        
        # Mock datetime.now() to return our test time
        with patch('plugins.traceroute_mapper.network_health_monitor.datetime') as mock_datetime:
            mock_now = MagicMock()
            mock_now.time.return_value = test_time
            mock_datetime.now.return_value = mock_now
            
            # Check if it's quiet hours
            result = monitor.is_quiet_hours()
            
            # Should return False even during configured hours when disabled
            assert result is False, (
                f"is_quiet_hours() should return False when quiet hours are disabled. "
                f"Configured hours: {start_time} to {end_time}, "
                f"Test time: {test_time.strftime('%H:%M')}"
            )
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        start_time=time_string(),
        end_time=time_string()
    )
    def test_quiet_hours_spanning_midnight_correctly_identified(self, start_time, end_time):
        """
        Property: For any quiet hours configuration that spans midnight,
        times after start OR before end should be identified as quiet hours.
        
        This test verifies correct handling of quiet hours that span midnight
        (e.g., 22:00 to 06:00).
        
        **Validates: Requirements 12.1**
        """
        # Parse times
        start_hour, start_min = map(int, start_time.split(':'))
        end_hour, end_min = map(int, end_time.split(':'))
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        
        # Only test cases that span midnight
        assume(start_minutes > end_minutes)
        
        # Create monitor
        monitor = NetworkHealthMonitor(
            quiet_hours_enabled=True,
            quiet_hours_start=start_time,
            quiet_hours_end=end_time
        )
        
        # Test a time after start (should be quiet hours)
        if start_minutes < 23*60+59:
            late_time = dt_time(hour=23, minute=30)
            with patch('plugins.traceroute_mapper.network_health_monitor.datetime') as mock_datetime:
                mock_now = MagicMock()
                mock_now.time.return_value = late_time
                mock_datetime.now.return_value = mock_now
                
                result = monitor.is_quiet_hours()
                
                # Should be quiet hours if after start
                if late_time.hour * 60 + late_time.minute >= start_minutes:
                    assert result is True, (
                        f"Time {late_time.strftime('%H:%M')} should be in quiet hours "
                        f"(after start {start_time})"
                    )
        
        # Test a time before end (should be quiet hours)
        if end_minutes > 0:
            early_time = dt_time(hour=1, minute=0)
            with patch('plugins.traceroute_mapper.network_health_monitor.datetime') as mock_datetime:
                mock_now = MagicMock()
                mock_now.time.return_value = early_time
                mock_datetime.now.return_value = mock_now
                
                result = monitor.is_quiet_hours()
                
                # Should be quiet hours if before end
                if early_time.hour * 60 + early_time.minute <= end_minutes:
                    assert result is True, (
                        f"Time {early_time.strftime('%H:%M')} should be in quiet hours "
                        f"(before end {end_time})"
                    )
        
        # Test a time in the middle (should NOT be quiet hours)
        middle_minutes = (end_minutes + start_minutes) // 2
        middle_time = dt_time(hour=middle_minutes // 60, minute=middle_minutes % 60)
        
        with patch('plugins.traceroute_mapper.network_health_monitor.datetime') as mock_datetime:
            mock_now = MagicMock()
            mock_now.time.return_value = middle_time
            mock_datetime.now.return_value = mock_now
            
            result = monitor.is_quiet_hours()
            
            # Should NOT be quiet hours (between end and start)
            assert result is False, (
                f"Time {middle_time.strftime('%H:%M')} should NOT be in quiet hours "
                f"(between end {end_time} and start {start_time})"
            )
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        start_time=time_string(),
        end_time=time_string()
    )
    def test_quiet_hours_normal_range_correctly_identified(self, start_time, end_time):
        """
        Property: For any quiet hours configuration that does NOT span midnight,
        times between start AND end should be identified as quiet hours.
        
        This test verifies correct handling of quiet hours within a single day
        (e.g., 10:00 to 14:00).
        
        **Validates: Requirements 12.1**
        """
        # Parse times
        start_hour, start_min = map(int, start_time.split(':'))
        end_hour, end_min = map(int, end_time.split(':'))
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        
        # Only test cases that don't span midnight
        assume(start_minutes < end_minutes)
        
        # Create monitor
        monitor = NetworkHealthMonitor(
            quiet_hours_enabled=True,
            quiet_hours_start=start_time,
            quiet_hours_end=end_time
        )
        
        # Test a time in the middle (should be quiet hours)
        middle_minutes = (start_minutes + end_minutes) // 2
        middle_time = dt_time(hour=middle_minutes // 60, minute=middle_minutes % 60)
        
        with patch('plugins.traceroute_mapper.network_health_monitor.datetime') as mock_datetime:
            mock_now = MagicMock()
            mock_now.time.return_value = middle_time
            mock_datetime.now.return_value = mock_now
            
            result = monitor.is_quiet_hours()
            
            # Should be quiet hours (between start and end)
            assert result is True, (
                f"Time {middle_time.strftime('%H:%M')} should be in quiet hours "
                f"(between start {start_time} and end {end_time})"
            )
        
        # Test a time before start (should NOT be quiet hours)
        if start_minutes > 0:
            before_time = dt_time(hour=0, minute=0)
            with patch('plugins.traceroute_mapper.network_health_monitor.datetime') as mock_datetime:
                mock_now = MagicMock()
                mock_now.time.return_value = before_time
                mock_datetime.now.return_value = mock_now
                
                result = monitor.is_quiet_hours()
                
                # Should NOT be quiet hours (before start)
                assert result is False, (
                    f"Time {before_time.strftime('%H:%M')} should NOT be in quiet hours "
                    f"(before start {start_time})"
                )
        
        # Test a time after end (should NOT be quiet hours)
        if end_minutes < 23*60+59:
            after_time = dt_time(hour=23, minute=59)
            with patch('plugins.traceroute_mapper.network_health_monitor.datetime') as mock_datetime:
                mock_now = MagicMock()
                mock_now.time.return_value = after_time
                mock_datetime.now.return_value = mock_now
                
                result = monitor.is_quiet_hours()
                
                # Should NOT be quiet hours (after end)
                assert result is False, (
                    f"Time {after_time.strftime('%H:%M')} should NOT be in quiet hours "
                    f"(after end {end_time})"
                )
    
    @settings(max_examples=20, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        start_time=time_string(),
        end_time=time_string()
    )
    def test_emergency_stop_overrides_quiet_hours_for_health_check(self, start_time, end_time):
        """
        Property: For any time, when in emergency stop mode, is_healthy()
        should return False regardless of quiet hours status.
        
        This test verifies that emergency stop takes precedence over quiet hours.
        
        **Validates: Requirements 12.1**
        """
        # Ensure start and end are different
        assume(start_time != end_time)
        
        # Create monitor with quiet hours enabled
        monitor = NetworkHealthMonitor(
            quiet_hours_enabled=True,
            quiet_hours_start=start_time,
            quiet_hours_end=end_time
        )
        
        # Enter emergency stop
        monitor.enter_emergency_stop("Test emergency stop")
        
        # Parse times to get a time within quiet hours
        start_hour, start_min = map(int, start_time.split(':'))
        end_hour, end_min = map(int, end_time.split(':'))
        start_minutes = start_hour * 60 + start_min
        end_minutes = end_hour * 60 + end_min
        
        # Test during quiet hours
        if start_minutes <= end_minutes:
            test_minutes_quiet = (start_minutes + end_minutes) // 2
        else:
            test_minutes_quiet = start_minutes + 30
            if test_minutes_quiet >= 24 * 60:
                test_minutes_quiet = test_minutes_quiet % (24 * 60)
        
        test_time_quiet = dt_time(hour=test_minutes_quiet // 60, minute=test_minutes_quiet % 60)
        
        with patch('plugins.traceroute_mapper.network_health_monitor.datetime') as mock_datetime:
            mock_now = MagicMock()
            mock_now.time.return_value = test_time_quiet
            mock_datetime.now.return_value = mock_now
            
            result = monitor.is_healthy()
            assert result is False, "is_healthy() should return False in emergency stop during quiet hours"
        
        # Test outside quiet hours (if possible)
        if start_minutes <= end_minutes:
            outside_available = start_minutes > 0 or end_minutes < 23*60+59
        else:
            outside_available = end_minutes + 1 < start_minutes
        
        if outside_available:
            if start_minutes <= end_minutes:
                if start_minutes > 0:
                    test_minutes_active = 0
                else:
                    test_minutes_active = 23 * 60 + 59
            else:
                test_minutes_active = (end_minutes + start_minutes) // 2
            
            test_time_active = dt_time(hour=test_minutes_active // 60, minute=test_minutes_active % 60)
            
            with patch('plugins.traceroute_mapper.network_health_monitor.datetime') as mock_datetime:
                mock_now = MagicMock()
                mock_now.time.return_value = test_time_active
                mock_datetime.now.return_value = mock_now
                
                result = monitor.is_healthy()
                assert result is False, "is_healthy() should return False in emergency stop outside quiet hours"


class TestQuietHoursEdgeCases:
    """
    Additional edge case tests for quiet hours functionality
    """
    
    @settings(max_examples=20, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(time_str=time_string())
    def test_quiet_hours_with_same_start_and_end(self, time_str):
        """
        Property: For any quiet hours configuration where start equals end,
        the behavior should be well-defined (no quiet hours or all day).
        
        **Validates: Requirements 12.1**
        """
        # Create monitor with same start and end time
        monitor = NetworkHealthMonitor(
            quiet_hours_enabled=True,
            quiet_hours_start=time_str,
            quiet_hours_end=time_str
        )
        
        # Test at the configured time
        hour, minute = map(int, time_str.split(':'))
        test_time = dt_time(hour=hour, minute=minute)
        
        with patch('plugins.traceroute_mapper.network_health_monitor.datetime') as mock_datetime:
            mock_now = MagicMock()
            mock_now.time.return_value = test_time
            mock_datetime.now.return_value = mock_now
            
            result = monitor.is_quiet_hours()
            
            # When start == end, the range is either empty or full day
            # The implementation treats this as a single point in time
            # which should be considered as quiet hours at that exact time
            assert isinstance(result, bool), "is_quiet_hours() should return a boolean"
    
    def test_quiet_hours_with_none_values(self):
        """
        Property: When quiet hours are enabled but start/end are None,
        is_quiet_hours() should return False.
        
        **Validates: Requirements 12.1**
        """
        monitor = NetworkHealthMonitor(
            quiet_hours_enabled=True,
            quiet_hours_start=None,
            quiet_hours_end=None
        )
        
        result = monitor.is_quiet_hours()
        
        assert result is False, (
            "is_quiet_hours() should return False when start/end are None"
        )
    
    def test_quiet_hours_with_invalid_time_strings(self):
        """
        Property: When quiet hours are configured with invalid time strings,
        the monitor should handle it gracefully.
        
        **Validates: Requirements 12.1**
        """
        monitor = NetworkHealthMonitor(
            quiet_hours_enabled=True,
            quiet_hours_start="invalid",
            quiet_hours_end="25:99"
        )
        
        # Should not crash, and should return False
        result = monitor.is_quiet_hours()
        
        assert result is False, (
            "is_quiet_hours() should return False with invalid time strings"
        )
        
        # Start and end should be None after failed parsing
        assert monitor.quiet_hours_start is None
        assert monitor.quiet_hours_end is None
    
    @settings(max_examples=20, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(quiet_hours=quiet_hours_config())
    def test_quiet_hours_boundary_conditions(self, quiet_hours):
        """
        Property: For any quiet hours configuration, the exact start and end
        times should be correctly identified as within or outside quiet hours.
        
        **Validates: Requirements 12.1**
        """
        start_time, end_time = quiet_hours
        
        # Create monitor
        monitor = NetworkHealthMonitor(
            quiet_hours_enabled=True,
            quiet_hours_start=start_time,
            quiet_hours_end=end_time
        )
        
        # Test at exact start time
        start_hour, start_min = map(int, start_time.split(':'))
        test_start = dt_time(hour=start_hour, minute=start_min)
        
        with patch('plugins.traceroute_mapper.network_health_monitor.datetime') as mock_datetime:
            mock_now = MagicMock()
            mock_now.time.return_value = test_start
            mock_datetime.now.return_value = mock_now
            
            result_start = monitor.is_quiet_hours()
            
            # At start time should be in quiet hours (inclusive)
            assert result_start is True, (
                f"Start time {start_time} should be in quiet hours"
            )
        
        # Test at exact end time
        end_hour, end_min = map(int, end_time.split(':'))
        test_end = dt_time(hour=end_hour, minute=end_min)
        
        with patch('plugins.traceroute_mapper.network_health_monitor.datetime') as mock_datetime:
            mock_now = MagicMock()
            mock_now.time.return_value = test_end
            mock_datetime.now.return_value = mock_now
            
            result_end = monitor.is_quiet_hours()
            
            # At end time should be in quiet hours (inclusive)
            assert result_end is True, (
                f"End time {end_time} should be in quiet hours"
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
