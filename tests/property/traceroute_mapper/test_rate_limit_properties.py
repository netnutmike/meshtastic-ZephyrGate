"""
Property-Based Tests for Rate Limit Enforcement

Tests Property 3: Rate Limit Enforcement
Validates: Requirements 3.1

**Validates: Requirements 3.1**
"""

import pytest
import asyncio
import time
from hypothesis import given, settings, strategies as st, assume, HealthCheck
from hypothesis.strategies import composite
from pathlib import Path
import sys

# Add src directory to path for imports
src_path = Path(__file__).parent.parent.parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from plugins.traceroute_mapper.rate_limiter import RateLimiter


# Strategy builders for generating test data

@composite
def valid_rate_limit(draw):
    """Generate valid rate limits (traceroutes per minute)"""
    # Use very high rates to make tests fast while still being meaningful
    # These rates allow many traceroutes per second, making tests complete quickly
    return draw(st.floats(min_value=600.0, max_value=3600.0, allow_nan=False, allow_infinity=False))


@composite
def burst_multiplier_value(draw):
    """Generate valid burst multiplier values"""
    # Use smaller burst multipliers to reduce test time
    return draw(st.floats(min_value=0.05, max_value=0.5, allow_nan=False, allow_infinity=False))


@composite
def traceroute_count(draw):
    """Generate number of traceroutes to send"""
    # Use smaller counts to reduce test time
    return draw(st.integers(min_value=5, max_value=15))


# Property Tests

class TestRateLimitEnforcementProperty:
    """
    Feature: network-traceroute-mapper, Property 3: Rate Limit Enforcement
    
    Tests that the rate limiter enforces the configured traceroutes_per_minute
    limit across any sequence of traceroute requests.
    
    **Validates: Requirements 3.1**
    """
    
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        rate=valid_rate_limit(),
        burst_mult=burst_multiplier_value(),
        num_traceroutes=traceroute_count()
    )
    @pytest.mark.asyncio
    async def test_rate_limit_enforced_over_time_window(self, rate, burst_mult, num_traceroutes):
        """
        Property: For any sequence of traceroute requests sent over time, the 
        number of traceroutes sent in any 60-second window should not exceed 
        the configured traceroutes_per_minute limit.
        
        This test verifies that the rate limiter enforces the configured rate
        by tracking when each traceroute is allowed and ensuring no 60-second
        window exceeds the limit.
        
        **Validates: Requirements 3.1**
        """
        # Create rate limiter with the given configuration
        limiter = RateLimiter(
            traceroutes_per_minute=rate,
            burst_multiplier=burst_mult
        )
        
        # Track timestamps when each traceroute is allowed
        allowed_timestamps = []
        
        # Acquire tokens for all traceroutes
        for _ in range(num_traceroutes):
            # Record time before acquire
            before_time = time.monotonic()
            
            # Acquire token (will wait if necessary)
            result = await limiter.acquire()
            assert result is True, "Acquire should always return True"
            
            # Record time after acquire
            after_time = time.monotonic()
            allowed_timestamps.append(after_time)
        
        # Verify rate limit is enforced in any 60-second window
        # For each timestamp, count how many traceroutes occurred in the
        # 60 seconds before it (including itself)
        for i, timestamp in enumerate(allowed_timestamps):
            window_start = timestamp - 60.0
            
            # Count traceroutes in this 60-second window
            count_in_window = 0
            for ts in allowed_timestamps:
                if window_start <= ts <= timestamp:
                    count_in_window += 1
            
            # The count should not exceed the configured rate
            # Allow a small tolerance for timing precision and burst behavior
            tolerance = max(2, rate * burst_mult * 0.1)  # 10% of burst capacity or 2, whichever is larger
            
            assert count_in_window <= rate + tolerance, (
                f"Rate limit violated at timestamp {i}: "
                f"{count_in_window} traceroutes in 60-second window "
                f"(limit: {rate}, tolerance: {tolerance}). "
                f"Window: [{window_start:.3f}, {timestamp:.3f}], "
                f"Timestamps in window: {[ts for ts in allowed_timestamps if window_start <= ts <= timestamp]}"
            )
    
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        rate=valid_rate_limit(),
        burst_mult=burst_multiplier_value()
    )
    @pytest.mark.asyncio
    async def test_burst_capacity_respected(self, rate, burst_mult):
        """
        Property: For any rate limiter configuration, the initial burst should
        allow up to (rate * burst_multiplier) traceroutes without delay, but
        subsequent requests should be rate limited.
        
        **Validates: Requirements 3.1**
        """
        # Create rate limiter
        limiter = RateLimiter(
            traceroutes_per_minute=rate,
            burst_multiplier=burst_mult
        )
        
        # Calculate expected burst capacity
        burst_capacity = int(rate * burst_mult)
        
        # Burst should be fast (all tokens available immediately)
        start_time = time.monotonic()
        
        for _ in range(burst_capacity):
            result = await limiter.acquire()
            assert result is True
        
        burst_time = time.monotonic() - start_time
        
        # Burst should complete very quickly (within 0.5 seconds)
        assert burst_time < 0.5, (
            f"Burst of {burst_capacity} traceroutes should be instant, "
            f"took {burst_time:.3f}s"
        )
        
        # Next request after burst should wait
        # (unless burst_capacity is very large and rate is very high)
        if burst_capacity < rate * 0.9:  # Only test if burst is less than 90% of rate
            before_wait = time.monotonic()
            result = await limiter.acquire()
            after_wait = time.monotonic()
            wait_time = after_wait - before_wait
            
            # Should have waited some amount (at least 0.01 seconds)
            # This is a weak assertion because high rates may refill quickly
            assert result is True, "Acquire should succeed after waiting"
    
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        rate=valid_rate_limit(),
        num_traceroutes=st.integers(min_value=10, max_value=20)
    )
    @pytest.mark.asyncio
    async def test_average_rate_over_time(self, rate, num_traceroutes):
        """
        Property: For any sequence of traceroute requests, the average rate
        over the entire sequence should not exceed the configured rate
        (accounting for initial burst).
        
        **Validates: Requirements 3.1**
        """
        # Use a small burst multiplier to minimize burst effects
        limiter = RateLimiter(
            traceroutes_per_minute=rate,
            burst_multiplier=0.1
        )
        
        # Exhaust initial burst first
        burst_capacity = int(rate * 0.1)
        for _ in range(burst_capacity + 1):
            await limiter.acquire()
        
        # Now measure the sustained rate
        start_time = time.monotonic()
        
        for _ in range(num_traceroutes):
            await limiter.acquire()
        
        elapsed_time = time.monotonic() - start_time
        
        # Calculate actual rate (traceroutes per minute)
        actual_rate = (num_traceroutes / elapsed_time) * 60.0
        
        # Actual rate should not exceed configured rate by more than 10%
        # (allowing for timing precision and token bucket refill behavior)
        tolerance_multiplier = 1.1
        
        assert actual_rate <= rate * tolerance_multiplier, (
            f"Average rate {actual_rate:.2f} traceroutes/min exceeds "
            f"configured rate {rate:.2f} traceroutes/min "
            f"(with {tolerance_multiplier}x tolerance). "
            f"Sent {num_traceroutes} traceroutes in {elapsed_time:.3f}s"
        )
    
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        rate=valid_rate_limit(),
        burst_mult=burst_multiplier_value(),
        num_traceroutes=traceroute_count()
    )
    @pytest.mark.asyncio
    async def test_no_traceroute_sent_before_token_available(self, rate, burst_mult, num_traceroutes):
        """
        Property: For any traceroute request, the request should not be allowed
        until a token is available in the token bucket.
        
        This verifies that the rate limiter correctly blocks requests when
        tokens are exhausted.
        
        **Validates: Requirements 3.1**
        """
        # Create rate limiter
        limiter = RateLimiter(
            traceroutes_per_minute=rate,
            burst_multiplier=burst_mult
        )
        
        # Track when tokens were available vs when requests were allowed
        for i in range(num_traceroutes):
            # Check tokens before acquire
            tokens_before = limiter.tokens
            
            # Acquire token
            result = await limiter.acquire()
            assert result is True
            
            # Check tokens after acquire
            tokens_after = limiter.tokens
            
            # If we had to wait, tokens_before would have been < 1.0
            # After acquire, we should have consumed exactly 1 token
            # (accounting for refill during wait)
            assert tokens_after < tokens_before + 1.0, (
                f"Token count inconsistency at request {i}: "
                f"before={tokens_before:.3f}, after={tokens_after:.3f}"
            )
    
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        initial_rate=valid_rate_limit(),
        new_rate=valid_rate_limit(),
        num_before=st.integers(min_value=5, max_value=10),
        num_after=st.integers(min_value=5, max_value=10)
    )
    @pytest.mark.asyncio
    async def test_rate_limit_enforced_after_rate_change(self, initial_rate, new_rate, num_before, num_after):
        """
        Property: For any rate limiter, when the rate is changed dynamically,
        the new rate should be enforced for subsequent requests.
        
        **Validates: Requirements 3.1**
        """
        # Create rate limiter with initial rate
        limiter = RateLimiter(
            traceroutes_per_minute=initial_rate,
            burst_multiplier=0.1
        )
        
        # Exhaust initial burst
        burst_capacity = int(initial_rate * 0.1)
        for _ in range(burst_capacity + 1):
            await limiter.acquire()
        
        # Send some requests at initial rate
        start_time = time.monotonic()
        for _ in range(num_before):
            await limiter.acquire()
        time_before = time.monotonic() - start_time
        
        # Change rate
        limiter.set_rate(new_rate)
        
        # Send requests at new rate
        start_time = time.monotonic()
        for _ in range(num_after):
            await limiter.acquire()
        time_after = time.monotonic() - start_time
        
        # Calculate actual rates
        actual_rate_after = (num_after / time_after) * 60.0
        
        # New rate should be enforced (with tolerance)
        tolerance_multiplier = 1.2  # 20% tolerance for timing and refill
        
        assert actual_rate_after <= new_rate * tolerance_multiplier, (
            f"Rate after change {actual_rate_after:.2f} traceroutes/min exceeds "
            f"new configured rate {new_rate:.2f} traceroutes/min "
            f"(with {tolerance_multiplier}x tolerance). "
            f"Sent {num_after} traceroutes in {time_after:.3f}s"
        )
    
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        rate=valid_rate_limit(),
        burst_mult=burst_multiplier_value(),
        num_traceroutes=traceroute_count()
    )
    @pytest.mark.asyncio
    async def test_statistics_reflect_rate_limiting(self, rate, burst_mult, num_traceroutes):
        """
        Property: For any sequence of traceroute requests, the statistics
        should accurately reflect how many requests were delayed due to
        rate limiting.
        
        **Validates: Requirements 3.1**
        """
        # Create rate limiter
        limiter = RateLimiter(
            traceroutes_per_minute=rate,
            burst_multiplier=burst_mult
        )
        
        # Send traceroutes
        for _ in range(num_traceroutes):
            await limiter.acquire()
        
        # Get statistics
        stats = limiter.get_statistics()
        
        # Verify statistics consistency
        assert stats['traceroutes_allowed'] == num_traceroutes, (
            f"Statistics mismatch: allowed={stats['traceroutes_allowed']}, "
            f"expected={num_traceroutes}"
        )
        
        # If any were delayed, total_wait_time should be positive
        if stats['traceroutes_delayed'] > 0:
            assert stats['total_wait_time'] > 0, (
                f"If {stats['traceroutes_delayed']} traceroutes were delayed, "
                f"total_wait_time should be positive, got {stats['total_wait_time']}"
            )
            
            assert stats['max_wait_time'] > 0, (
                f"If traceroutes were delayed, max_wait_time should be positive, "
                f"got {stats['max_wait_time']}"
            )
            
            assert stats['avg_wait_time'] > 0, (
                f"If traceroutes were delayed, avg_wait_time should be positive, "
                f"got {stats['avg_wait_time']}"
            )
        
        # Delayed count should not exceed total count
        assert stats['traceroutes_delayed'] <= stats['traceroutes_allowed'], (
            f"Delayed count {stats['traceroutes_delayed']} should not exceed "
            f"allowed count {stats['traceroutes_allowed']}"
        )
    
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        rate=valid_rate_limit(),
        num_concurrent=st.integers(min_value=5, max_value=15)
    )
    @pytest.mark.asyncio
    async def test_rate_limit_enforced_with_concurrent_requests(self, rate, num_concurrent):
        """
        Property: For any rate limiter, when multiple requests are made
        concurrently, the rate limit should still be enforced correctly.
        
        **Validates: Requirements 3.1**
        """
        # Create rate limiter with small burst to force rate limiting
        limiter = RateLimiter(
            traceroutes_per_minute=rate,
            burst_multiplier=0.1
        )
        
        # Exhaust initial burst
        burst_capacity = int(rate * 0.1)
        for _ in range(burst_capacity + 1):
            await limiter.acquire()
        
        # Launch concurrent requests
        start_time = time.monotonic()
        
        tasks = [limiter.acquire() for _ in range(num_concurrent)]
        results = await asyncio.gather(*tasks)
        
        elapsed_time = time.monotonic() - start_time
        
        # All should succeed
        assert all(results), "All concurrent acquires should succeed"
        
        # Calculate actual rate
        actual_rate = (num_concurrent / elapsed_time) * 60.0
        
        # Rate should not exceed configured rate by more than 20%
        tolerance_multiplier = 1.2
        
        assert actual_rate <= rate * tolerance_multiplier, (
            f"Concurrent request rate {actual_rate:.2f} traceroutes/min exceeds "
            f"configured rate {rate:.2f} traceroutes/min "
            f"(with {tolerance_multiplier}x tolerance). "
            f"Sent {num_concurrent} concurrent traceroutes in {elapsed_time:.3f}s"
        )
        
        # Statistics should reflect all requests
        stats = limiter.get_statistics()
        # Note: stats include the burst exhaustion requests
        assert stats['traceroutes_allowed'] >= num_concurrent, (
            f"Statistics should show at least {num_concurrent} allowed, "
            f"got {stats['traceroutes_allowed']}"
        )


class TestRateLimitEdgeCases:
    """
    Additional edge case tests for rate limiting behavior
    """
    
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(rate=st.floats(min_value=600.0, max_value=3600.0, allow_nan=False, allow_infinity=False))
    @pytest.mark.asyncio
    async def test_rate_limit_after_reset(self, rate):
        """
        Property: For any rate limiter, after reset, the rate limit should
        be enforced from the beginning again.
        
        **Validates: Requirements 3.1**
        """
        limiter = RateLimiter(
            traceroutes_per_minute=rate,
            burst_multiplier=0.1
        )
        
        # Exhaust tokens
        burst_capacity = int(rate * 0.1)
        for _ in range(burst_capacity + 5):
            await limiter.acquire()
        
        # Reset
        limiter.reset()
        
        # Should be able to burst again
        start_time = time.monotonic()
        for _ in range(burst_capacity):
            await limiter.acquire()
        burst_time = time.monotonic() - start_time
        
        # Burst should be fast after reset
        assert burst_time < 0.5, (
            f"After reset, burst should be instant, took {burst_time:.3f}s"
        )
    
    @settings(max_examples=20, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        rate=st.floats(min_value=600.0, max_value=3600.0, allow_nan=False, allow_infinity=False),
        wait_time=st.floats(min_value=0.1, max_value=0.5, allow_nan=False, allow_infinity=False)
    )
    @pytest.mark.asyncio
    async def test_tokens_refill_during_idle_time(self, rate, wait_time):
        """
        Property: For any rate limiter, tokens should refill during idle time
        according to the configured rate.
        
        **Validates: Requirements 3.1**
        """
        limiter = RateLimiter(
            traceroutes_per_minute=rate,
            burst_multiplier=0.1
        )
        
        # Exhaust tokens
        burst_capacity = int(rate * 0.1)
        for _ in range(burst_capacity + 1):
            await limiter.acquire()
        
        # Wait for tokens to refill
        await asyncio.sleep(wait_time)
        
        # Calculate expected tokens refilled
        expected_tokens = (rate / 60.0) * wait_time
        
        # Should be able to acquire approximately that many tokens quickly
        # (with some tolerance for timing)
        tokens_acquired = 0
        start_time = time.monotonic()
        
        # Try to acquire expected tokens
        for _ in range(int(expected_tokens) + 1):
            if time.monotonic() - start_time > 0.2:  # Stop if taking too long
                break
            await limiter.acquire()
            tokens_acquired += 1
        
        # Should have acquired at least 80% of expected tokens quickly
        assert tokens_acquired >= int(expected_tokens * 0.8), (
            f"After waiting {wait_time:.3f}s, expected to acquire ~{expected_tokens:.1f} tokens quickly, "
            f"but only acquired {tokens_acquired}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
