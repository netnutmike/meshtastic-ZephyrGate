"""
Property-Based Tests for Traceroute Retry Logic

Tests Property 24: Retry Attempts Limit
Tests Property 25: Exponential Backoff Calculation
Tests Property 26: Timeout Enforcement

Validates: Requirements 11.1, 11.3, 11.4

**Validates: Requirements 11.1, 11.3, 11.4**
"""

import pytest
import asyncio
from hypothesis import given, settings, strategies as st, assume
from hypothesis.strategies import composite
from pathlib import Path
import sys
from datetime import datetime, timedelta

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.traceroute_mapper.traceroute_manager import TracerouteManager, PendingTraceroute


# Strategy builders for generating test data

@composite
def valid_max_retries(draw):
    """Generate valid max_retries values"""
    return draw(st.integers(min_value=0, max_value=10))


@composite
def valid_retry_count(draw):
    """Generate valid retry count values"""
    return draw(st.integers(min_value=0, max_value=10))


@composite
def valid_backoff_multiplier(draw):
    """Generate valid backoff multiplier values"""
    return draw(st.floats(min_value=1.0, max_value=5.0, allow_nan=False, allow_infinity=False))


@composite
def valid_timeout_seconds(draw):
    """Generate valid timeout values in seconds"""
    return draw(st.integers(min_value=10, max_value=300))


@composite
def valid_initial_delay(draw):
    """Generate valid initial delay values"""
    return draw(st.floats(min_value=1.0, max_value=30.0, allow_nan=False, allow_infinity=False))


# Property Tests

class TestRetryAttemptsLimitProperty:
    """
    Feature: network-traceroute-mapper, Property 24: Retry Attempts Limit
    
    Tests that for any failed traceroute, the system retries up to max_retries
    times before giving up.
    
    **Validates: Requirements 11.1**
    """
    
    @settings(max_examples=10, deadline=5000)
    @given(
        max_retries=valid_max_retries(),
        node_id=st.text(min_size=9, max_size=9, alphabet='0123456789abcdef').map(lambda x: f"!{x}")
    )
    @pytest.mark.asyncio
    async def test_retry_limit_enforced(self, max_retries, node_id):
        """
        Property: For any failed traceroute, the system should retry up to
        max_retries times and then give up.
        
        **Validates: Requirements 11.1**
        """
        # Create manager with specific max_retries
        manager = TracerouteManager(
            max_hops=7,
            timeout_seconds=60,
            max_retries=max_retries
        )
        
        # Send a traceroute request
        request_id = await manager.send_traceroute(node_id)
        
        # Get the pending traceroute
        pending = manager._pending_traceroutes.get(request_id)
        assert pending is not None, "Pending traceroute should exist"
        assert pending.max_retries == max_retries, (
            f"max_retries should be {max_retries}, got {pending.max_retries}"
        )
        
        # Simulate failures and retries
        retry_count = 0
        while retry_count < max_retries:
            # Schedule retry
            result = await manager.schedule_retry(pending)
            assert result is True, f"Retry {retry_count + 1} should succeed"
            retry_count += 1
            assert pending.retry_count == retry_count, (
                f"retry_count should be {retry_count}, got {pending.retry_count}"
            )
        
        # Next retry should fail (exceeded max_retries)
        result = await manager.schedule_retry(pending)
        assert result is False, "Retry should fail after max_retries exceeded"
        assert pending.retry_count == max_retries, (
            f"retry_count should be {max_retries}, got {pending.retry_count}"
        )
    
    @settings(max_examples=10, deadline=5000)
    @given(
        max_retries=valid_max_retries(),
        node_id=st.text(min_size=8, max_size=8, alphabet='0123456789abcdef').map(lambda x: f"!{x}")
    )
    @pytest.mark.asyncio
    async def test_retry_count_increments_correctly(self, max_retries, node_id):
        """
        Property: For any sequence of retry attempts, the retry_count should
        increment by 1 for each retry.
        
        **Validates: Requirements 11.1**
        """
        # Create manager
        manager = TracerouteManager(
            max_hops=7,
            timeout_seconds=60,
            max_retries=max_retries
        )
        
        # Send a traceroute request
        request_id = await manager.send_traceroute(node_id)
        pending = manager._pending_traceroutes.get(request_id)
        
        # Initial retry_count should be 0
        assert pending.retry_count == 0, "Initial retry_count should be 0"
        
        # Schedule retries and verify count increments
        for expected_count in range(1, max_retries + 1):
            result = await manager.schedule_retry(pending)
            if result:
                assert pending.retry_count == expected_count, (
                    f"After retry {expected_count}, retry_count should be {expected_count}, "
                    f"got {pending.retry_count}"
                )
    
    @settings(max_examples=10, deadline=5000)
    @given(
        max_retries=st.integers(min_value=1, max_value=5),
        node_id=st.text(min_size=8, max_size=8, alphabet='0123456789abcdef').map(lambda x: f"!{x}")
    )
    @pytest.mark.asyncio
    async def test_statistics_track_retries(self, max_retries, node_id):
        """
        Property: For any sequence of retry attempts, the retries statistic
        should accurately reflect the number of retries scheduled.
        
        **Validates: Requirements 11.1**
        """
        # Create manager
        manager = TracerouteManager(
            max_hops=7,
            timeout_seconds=60,
            max_retries=max_retries
        )
        
        # Get initial statistics
        initial_stats = manager.get_statistics()
        initial_retries = initial_stats['retries']
        
        # Send a traceroute request
        request_id = await manager.send_traceroute(node_id)
        pending = manager._pending_traceroutes.get(request_id)
        
        # Schedule all retries
        successful_retries = 0
        for _ in range(max_retries):
            result = await manager.schedule_retry(pending)
            if result:
                successful_retries += 1
        
        # Get updated statistics
        updated_stats = manager.get_statistics()
        
        # Verify statistics were updated correctly
        assert updated_stats['retries'] == initial_retries + successful_retries, (
            f"retries statistic should be {initial_retries + successful_retries}, "
            f"got {updated_stats['retries']}"
        )


class TestExponentialBackoffCalculationProperty:
    """
    Feature: network-traceroute-mapper, Property 25: Exponential Backoff Calculation
    
    Tests that for any retry attempt N, the backoff delay is calculated as
    initial_delay * (backoff_multiplier ^ (N-1)), capped at max_delay.
    
    **Validates: Requirements 11.3**
    """
    
    @settings(max_examples=10, deadline=5000)
    @given(
        retry_count=valid_retry_count(),
        backoff_multiplier=valid_backoff_multiplier(),
        initial_delay=valid_initial_delay()
    )
    def test_exponential_backoff_formula(self, retry_count, backoff_multiplier, initial_delay):
        """
        Property: For any retry attempt N, the backoff delay should be
        initial_delay * (backoff_multiplier ^ N).
        
        **Validates: Requirements 11.3**
        """
        # Create manager with specific backoff multiplier
        manager = TracerouteManager(
            max_hops=7,
            timeout_seconds=60,
            max_retries=10,
            retry_backoff_multiplier=backoff_multiplier
        )
        
        # Calculate delay
        delay = manager.calculate_retry_delay(retry_count, initial_delay=initial_delay)
        
        # Calculate expected delay
        expected_delay = initial_delay * (backoff_multiplier ** retry_count)
        
        # Verify delay matches expected (within small tolerance for floating point)
        assert abs(delay - expected_delay) < 0.01 or delay == 300.0, (
            f"For retry_count={retry_count}, expected delay={expected_delay:.2f}s, "
            f"got {delay:.2f}s (multiplier={backoff_multiplier}, initial={initial_delay})"
        )
    
    @settings(max_examples=10, deadline=5000)
    @given(
        retry_count=valid_retry_count(),
        backoff_multiplier=valid_backoff_multiplier(),
        initial_delay=valid_initial_delay(),
        max_delay=st.floats(min_value=10.0, max_value=500.0, allow_nan=False, allow_infinity=False)
    )
    def test_backoff_capped_at_max_delay(self, retry_count, backoff_multiplier, initial_delay, max_delay):
        """
        Property: For any retry attempt, the backoff delay should never exceed
        the configured max_delay.
        
        **Validates: Requirements 11.3**
        """
        # Create manager
        manager = TracerouteManager(
            max_hops=7,
            timeout_seconds=60,
            max_retries=10,
            retry_backoff_multiplier=backoff_multiplier
        )
        
        # Calculate delay
        delay = manager.calculate_retry_delay(retry_count, initial_delay=initial_delay, max_delay=max_delay)
        
        # Verify delay does not exceed max_delay
        assert delay <= max_delay, (
            f"Delay {delay:.2f}s should not exceed max_delay {max_delay:.2f}s "
            f"(retry_count={retry_count}, multiplier={backoff_multiplier}, initial={initial_delay})"
        )
    
    @settings(max_examples=10, deadline=5000)
    @given(
        backoff_multiplier=valid_backoff_multiplier(),
        initial_delay=valid_initial_delay()
    )
    def test_backoff_increases_with_retry_count(self, backoff_multiplier, initial_delay):
        """
        Property: For any backoff multiplier > 1, the delay should increase
        with each retry attempt.
        
        **Validates: Requirements 11.3**
        """
        # Skip if multiplier is exactly 1 (no increase)
        assume(backoff_multiplier > 1.0)
        
        # Create manager
        manager = TracerouteManager(
            max_hops=7,
            timeout_seconds=60,
            max_retries=10,
            retry_backoff_multiplier=backoff_multiplier
        )
        
        # Calculate delays for increasing retry counts
        delays = []
        for retry_count in range(5):
            delay = manager.calculate_retry_delay(retry_count, initial_delay=initial_delay, max_delay=1000.0)
            delays.append(delay)
        
        # Verify delays are non-decreasing
        for i in range(len(delays) - 1):
            assert delays[i] <= delays[i + 1], (
                f"Delay should increase with retry count: "
                f"delay[{i}]={delays[i]:.2f}s, delay[{i+1}]={delays[i+1]:.2f}s"
            )
    
    @settings(max_examples=10, deadline=5000)
    @given(
        node_id=st.text(min_size=8, max_size=8, alphabet='0123456789abcdef').map(lambda x: f"!{x}"),
        backoff_multiplier=valid_backoff_multiplier()
    )
    @pytest.mark.asyncio
    async def test_schedule_retry_applies_backoff_delay(self, node_id, backoff_multiplier):
        """
        Property: For any retry scheduled, the sent_at time should be set to
        current_time + backoff_delay.
        
        **Validates: Requirements 11.3**
        """
        # Create manager
        manager = TracerouteManager(
            max_hops=7,
            timeout_seconds=60,
            max_retries=5,
            retry_backoff_multiplier=backoff_multiplier
        )
        
        # Send a traceroute request
        request_id = await manager.send_traceroute(node_id)
        pending = manager._pending_traceroutes.get(request_id)
        
        # Record time before scheduling retry
        before_time = datetime.utcnow()
        
        # Schedule retry
        result = await manager.schedule_retry(pending)
        assert result is True, "Retry should be scheduled successfully"
        
        # Calculate expected delay
        expected_delay = manager.calculate_retry_delay(0)  # First retry
        
        # Verify sent_at is in the future by approximately the backoff delay
        time_diff = (pending.sent_at - before_time).total_seconds()
        
        # Allow some tolerance for execution time
        assert time_diff >= expected_delay * 0.9, (
            f"sent_at should be delayed by ~{expected_delay:.2f}s, "
            f"got {time_diff:.2f}s"
        )
        assert time_diff <= expected_delay * 1.1 + 1.0, (
            f"sent_at should be delayed by ~{expected_delay:.2f}s, "
            f"got {time_diff:.2f}s"
        )


class TestTimeoutEnforcementProperty:
    """
    Feature: network-traceroute-mapper, Property 26: Timeout Enforcement
    
    Tests that for any traceroute request sent, if no response is received
    within timeout_seconds, the request is marked as failed.
    
    **Validates: Requirements 11.4**
    """
    
    @settings(max_examples=10, deadline=5000)
    @given(
        timeout_seconds=valid_timeout_seconds(),
        node_id=st.text(min_size=8, max_size=8, alphabet='0123456789abcdef').map(lambda x: f"!{x}")
    )
    @pytest.mark.asyncio
    async def test_timeout_set_correctly(self, timeout_seconds, node_id):
        """
        Property: For any traceroute request, the timeout_at timestamp should
        be set to sent_at + timeout_seconds.
        
        **Validates: Requirements 11.4**
        """
        # Create manager with specific timeout
        manager = TracerouteManager(
            max_hops=7,
            timeout_seconds=timeout_seconds,
            max_retries=3
        )
        
        # Send a traceroute request
        request_id = await manager.send_traceroute(node_id)
        
        # Get the pending traceroute
        pending = manager._pending_traceroutes.get(request_id)
        assert pending is not None, "Pending traceroute should exist"
        
        # Calculate expected timeout
        expected_timeout = pending.sent_at + timedelta(seconds=timeout_seconds)
        
        # Verify timeout_at is set correctly (within 1 second tolerance)
        time_diff = abs((pending.timeout_at - expected_timeout).total_seconds())
        assert time_diff < 1.0, (
            f"timeout_at should be sent_at + {timeout_seconds}s, "
            f"difference is {time_diff:.2f}s"
        )
    
    @settings(max_examples=10, deadline=5000)
    @given(
        timeout_seconds=st.integers(min_value=1, max_value=10),
        node_id=st.text(min_size=8, max_size=8, alphabet='0123456789abcdef').map(lambda x: f"!{x}")
    )
    @pytest.mark.asyncio
    async def test_timeout_detection(self, timeout_seconds, node_id):
        """
        Property: For any traceroute request that times out, check_timeouts()
        should detect it and remove it from pending requests.
        
        **Validates: Requirements 11.4**
        """
        # Create manager with short timeout
        manager = TracerouteManager(
            max_hops=7,
            timeout_seconds=timeout_seconds,
            max_retries=3
        )
        
        # Send a traceroute request
        request_id = await manager.send_traceroute(node_id)
        
        # Verify it's pending
        assert manager.is_pending(request_id), "Request should be pending"
        
        # Manually set timeout to past
        pending = manager._pending_traceroutes[request_id]
        pending.timeout_at = datetime.utcnow() - timedelta(seconds=1)
        
        # Check for timeouts
        timed_out = manager.check_timeouts()
        
        # Verify request was detected as timed out
        assert len(timed_out) == 1, "Should detect 1 timed out request"
        assert timed_out[0].request_id == request_id, (
            f"Timed out request should be {request_id}"
        )
        
        # Verify request was removed from pending
        assert not manager.is_pending(request_id), (
            "Request should not be pending after timeout"
        )
    
    @settings(max_examples=10, deadline=5000)
    @given(
        timeout_seconds=st.integers(min_value=1, max_value=10),
        num_requests=st.integers(min_value=1, max_value=10)
    )
    @pytest.mark.asyncio
    async def test_timeout_statistics_updated(self, timeout_seconds, num_requests):
        """
        Property: For any timed out traceroute requests, the timeouts statistic
        should be incremented correctly.
        
        **Validates: Requirements 11.4**
        """
        # Create manager
        manager = TracerouteManager(
            max_hops=7,
            timeout_seconds=timeout_seconds,
            max_retries=3
        )
        
        # Get initial statistics
        initial_stats = manager.get_statistics()
        initial_timeouts = initial_stats['timeouts']
        
        # Send multiple traceroute requests
        request_ids = []
        for i in range(num_requests):
            request_id = await manager.send_traceroute(f"!{i:08x}")
            request_ids.append(request_id)
        
        # Set all to timeout
        for request_id in request_ids:
            pending = manager._pending_traceroutes[request_id]
            pending.timeout_at = datetime.utcnow() - timedelta(seconds=1)
        
        # Check for timeouts
        timed_out = manager.check_timeouts()
        
        # Verify statistics were updated
        updated_stats = manager.get_statistics()
        assert updated_stats['timeouts'] == initial_timeouts + num_requests, (
            f"timeouts statistic should be {initial_timeouts + num_requests}, "
            f"got {updated_stats['timeouts']}"
        )
    
    @settings(max_examples=10, deadline=5000)
    @given(
        timeout_seconds=valid_timeout_seconds(),
        node_id=st.text(min_size=8, max_size=8, alphabet='0123456789abcdef').map(lambda x: f"!{x}")
    )
    @pytest.mark.asyncio
    async def test_timeout_updated_on_retry(self, timeout_seconds, node_id):
        """
        Property: For any retry scheduled, the timeout_at should be updated
        to the new sent_at + timeout_seconds.
        
        **Validates: Requirements 11.4**
        """
        # Create manager
        manager = TracerouteManager(
            max_hops=7,
            timeout_seconds=timeout_seconds,
            max_retries=5
        )
        
        # Send a traceroute request
        request_id = await manager.send_traceroute(node_id)
        pending = manager._pending_traceroutes.get(request_id)
        
        # Record original timeout
        original_timeout = pending.timeout_at
        
        # Schedule retry
        result = await manager.schedule_retry(pending)
        assert result is True, "Retry should be scheduled"
        
        # Verify timeout was updated
        assert pending.timeout_at != original_timeout, (
            "timeout_at should be updated on retry"
        )
        
        # Verify new timeout is sent_at + timeout_seconds
        expected_timeout = pending.sent_at + timedelta(seconds=timeout_seconds)
        time_diff = abs((pending.timeout_at - expected_timeout).total_seconds())
        assert time_diff < 1.0, (
            f"New timeout_at should be sent_at + {timeout_seconds}s, "
            f"difference is {time_diff:.2f}s"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
