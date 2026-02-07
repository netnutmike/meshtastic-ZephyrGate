"""
Property-based tests for MQTT Gateway Rate Limiter

Tests universal properties of rate limiting, token bucket algorithm,
and message throughput enforcement.

Properties tested:
- Property 12: Rate Limit Enforcement (Requirements 7.1)

Author: ZephyrGate Team
Version: 1.0.0
License: GPL-3.0
"""

import pytest
import asyncio
import time
from hypothesis import given, strategies as st, assume, settings
from pathlib import Path
import sys

# Add plugins directory to path
plugins_path = Path(__file__).parent.parent.parent.parent / "plugins"
if str(plugins_path) not in sys.path:
    sys.path.insert(0, str(plugins_path))

from mqtt_gateway.rate_limiter import RateLimiter


# ============================================================================
# Hypothesis Strategies for Generating Test Data
# ============================================================================

@st.composite
def rate_limit_config_strategy(draw):
    """Generate valid rate limiter configurations"""
    return {
        'max_messages_per_second': draw(st.floats(min_value=1.0, max_value=100.0)),
        'burst_multiplier': draw(st.floats(min_value=1.0, max_value=5.0))
    }


# ============================================================================
# Property 12: Rate Limit Enforcement
# ============================================================================

class TestRateLimitEnforcementProperty:
    """
    **Validates: Requirements 7.1**
    
    For any sequence of message publish attempts, the number of messages
    published in any 1-second window should not exceed the configured
    max_messages_per_second limit.
    """
    
    @pytest.mark.asyncio
    @given(
        rate_limit=st.floats(min_value=10.0, max_value=50.0),
        num_messages=st.integers(min_value=20, max_value=60)
    )
    @settings(max_examples=10, deadline=None)
    async def test_rate_limit_not_exceeded(self, rate_limit, num_messages):
        """
        Property: Rate limit is never exceeded
        
        When acquiring tokens at maximum speed, the actual rate should
        not exceed the configured max_messages_per_second.
        """
        assume(num_messages > rate_limit)  # Ensure we test rate limiting
        
        limiter = RateLimiter(
            max_messages_per_second=rate_limit,
            burst_multiplier=1.0  # No burst for strict testing
        )
        
        start_time = time.monotonic()
        
        # Acquire tokens as fast as possible
        for _ in range(num_messages):
            await limiter.acquire()
        
        end_time = time.monotonic()
        elapsed_time = end_time - start_time
        
        # Calculate actual rate
        actual_rate = num_messages / elapsed_time
        
        # Allow 10% tolerance for timing variations
        tolerance = rate_limit * 0.1
        
        assert actual_rate <= rate_limit + tolerance, \
            f"Actual rate {actual_rate:.2f} exceeds limit {rate_limit:.2f} (tolerance: {tolerance:.2f})"
    
    @pytest.mark.asyncio
    @given(
        rate_limit=st.floats(min_value=10.0, max_value=50.0),
        burst_multiplier=st.floats(min_value=1.5, max_value=3.0)
    )
    @settings(max_examples=15, deadline=None)
    async def test_burst_capacity_respected(self, rate_limit, burst_multiplier):
        """
        Property: Burst capacity allows initial burst
        
        The rate limiter should allow an initial burst up to the burst
        capacity without delay.
        """
        limiter = RateLimiter(
            max_messages_per_second=rate_limit,
            burst_multiplier=burst_multiplier
        )
        
        burst_capacity = int(rate_limit * burst_multiplier)
        
        start_time = time.monotonic()
        
        # Acquire tokens up to burst capacity
        for _ in range(burst_capacity):
            await limiter.acquire()
        
        end_time = time.monotonic()
        elapsed_time = end_time - start_time
        
        # Burst should complete very quickly (within 0.1 seconds)
        assert elapsed_time < 0.1, \
            f"Burst of {burst_capacity} messages took {elapsed_time:.3f}s, should be nearly instant"
    
    @pytest.mark.asyncio
    @given(
        rate_limit=st.floats(min_value=20.0, max_value=50.0)
    )
    @settings(max_examples=10, deadline=None)
    async def test_sustained_rate_matches_limit(self, rate_limit):
        """
        Property: Sustained rate matches configured limit
        
        After the initial burst, the sustained rate should match the
        configured max_messages_per_second.
        """
        limiter = RateLimiter(
            max_messages_per_second=rate_limit,
            burst_multiplier=1.0
        )
        
        # Exhaust initial tokens
        await limiter.acquire()
        
        # Now measure sustained rate
        num_messages = int(rate_limit * 2)  # 2 seconds worth
        start_time = time.monotonic()
        
        for _ in range(num_messages):
            await limiter.acquire()
        
        end_time = time.monotonic()
        elapsed_time = end_time - start_time
        
        actual_rate = num_messages / elapsed_time
        
        # Allow 15% tolerance for sustained rate
        tolerance = rate_limit * 0.15
        
        assert abs(actual_rate - rate_limit) <= tolerance, \
            f"Sustained rate {actual_rate:.2f} differs from limit {rate_limit:.2f} by more than {tolerance:.2f}"
    
    @pytest.mark.asyncio
    @given(
        rate_limit=st.floats(min_value=20.0, max_value=50.0),
        num_messages=st.integers(min_value=10, max_value=20)
    )
    @settings(max_examples=10, deadline=None)
    async def test_wait_time_calculation_accurate(self, rate_limit, num_messages):
        """
        Property: Wait time calculation is accurate
        
        The get_wait_time() method should accurately predict the time
        needed before the next message can be sent.
        """
        limiter = RateLimiter(
            max_messages_per_second=rate_limit,
            burst_multiplier=1.0
        )
        
        # Exhaust tokens
        for _ in range(int(rate_limit) + 1):
            await limiter.acquire()
        
        # Get predicted wait time
        predicted_wait = limiter.get_wait_time()
        
        # Wait that amount
        await asyncio.sleep(predicted_wait)
        
        # Should be able to acquire immediately now
        start_time = time.monotonic()
        await limiter.acquire()
        end_time = time.monotonic()
        
        actual_wait = end_time - start_time
        
        # Should complete very quickly (within 0.05 seconds)
        assert actual_wait < 0.05, \
            f"After waiting predicted time {predicted_wait:.3f}s, " \
            f"acquire still took {actual_wait:.3f}s"
    
    @pytest.mark.asyncio
    @given(
        rate_limit=st.floats(min_value=10.0, max_value=50.0)
    )
    @settings(max_examples=15, deadline=None)
    async def test_reset_refills_tokens(self, rate_limit):
        """
        Property: Reset refills token bucket to capacity
        
        After reset, the rate limiter should allow immediate burst
        up to capacity.
        """
        limiter = RateLimiter(
            max_messages_per_second=rate_limit,
            burst_multiplier=2.0
        )
        
        # Exhaust all tokens
        burst_capacity = int(rate_limit * 2.0)
        for _ in range(burst_capacity + 5):
            await limiter.acquire()
        
        # Reset the limiter
        limiter.reset()
        
        # Should be able to burst again immediately
        start_time = time.monotonic()
        for _ in range(burst_capacity):
            await limiter.acquire()
        end_time = time.monotonic()
        
        elapsed_time = end_time - start_time
        
        # Burst should complete very quickly
        assert elapsed_time < 0.1, \
            f"After reset, burst took {elapsed_time:.3f}s, should be nearly instant"
    
    @pytest.mark.asyncio
    @given(
        rate_limit=st.floats(min_value=20.0, max_value=50.0),
        num_acquires=st.integers(min_value=10, max_value=30)
    )
    @settings(max_examples=10, deadline=None)
    async def test_statistics_accuracy(self, rate_limit, num_acquires):
        """
        Property: Statistics accurately track operations
        
        The statistics should accurately reflect the number of messages
        allowed and delayed.
        """
        limiter = RateLimiter(
            max_messages_per_second=rate_limit,
            burst_multiplier=1.5
        )
        
        # Acquire tokens
        for _ in range(num_acquires):
            await limiter.acquire()
        
        stats = limiter.get_statistics()
        
        # Total messages allowed should equal number of acquires
        assert stats['messages_allowed'] == num_acquires, \
            f"Expected {num_acquires} messages allowed, got {stats['messages_allowed']}"
        
        # If we exceeded burst capacity, some should be delayed
        burst_capacity = int(rate_limit * 1.5)
        if num_acquires > burst_capacity:
            assert stats['messages_delayed'] > 0, \
                f"Expected some messages delayed when exceeding burst capacity"
    
    @pytest.mark.asyncio
    @given(
        rate_limit=st.floats(min_value=20.0, max_value=50.0)
    )
    @settings(max_examples=10, deadline=None)
    async def test_concurrent_acquires(self, rate_limit):
        """
        Property: Concurrent acquires are handled correctly
        
        Multiple concurrent acquire calls should be serialized and
        rate limited correctly.
        """
        limiter = RateLimiter(
            max_messages_per_second=rate_limit,
            burst_multiplier=1.0
        )
        
        num_concurrent = int(rate_limit * 2)
        
        start_time = time.monotonic()
        
        # Launch concurrent acquire tasks
        tasks = [limiter.acquire() for _ in range(num_concurrent)]
        await asyncio.gather(*tasks)
        
        end_time = time.monotonic()
        elapsed_time = end_time - start_time
        
        # Calculate actual rate
        actual_rate = num_concurrent / elapsed_time
        
        # Allow 15% tolerance
        tolerance = rate_limit * 0.15
        
        assert actual_rate <= rate_limit + tolerance, \
            f"Concurrent acquires resulted in rate {actual_rate:.2f} " \
            f"exceeding limit {rate_limit:.2f}"
    
    @pytest.mark.asyncio
    @given(
        rate_limit=st.floats(min_value=10.0, max_value=50.0),
        pause_duration=st.floats(min_value=0.1, max_value=0.5)
    )
    @settings(max_examples=10, deadline=None)
    async def test_token_refill_over_time(self, rate_limit, pause_duration):
        """
        Property: Tokens refill over time
        
        After waiting, tokens should refill according to the rate limit,
        allowing more messages without delay.
        """
        limiter = RateLimiter(
            max_messages_per_second=rate_limit,
            burst_multiplier=1.0
        )
        
        # Exhaust tokens
        await limiter.acquire()
        
        # Wait for tokens to refill
        await asyncio.sleep(pause_duration)
        
        # Calculate expected tokens refilled
        expected_tokens = pause_duration * rate_limit
        
        # Should be able to acquire that many tokens quickly
        num_to_acquire = int(expected_tokens)
        if num_to_acquire > 0:
            start_time = time.monotonic()
            for _ in range(num_to_acquire):
                await limiter.acquire()
            end_time = time.monotonic()
            
            elapsed_time = end_time - start_time
            
            # Should complete relatively quickly (within 0.2 seconds)
            assert elapsed_time < 0.2, \
                f"After waiting {pause_duration:.3f}s, acquiring {num_to_acquire} " \
                f"tokens took {elapsed_time:.3f}s, should be quick"


# ============================================================================
# Edge Cases and Integration Tests
# ============================================================================

class TestRateLimiterPropertyEdgeCases:
    """Test edge cases for rate limiter"""
    
    @pytest.mark.asyncio
    async def test_very_low_rate_limit(self):
        """
        Edge case: Very low rate limit (< 1 msg/sec)
        
        The rate limiter should work correctly even with very low rates.
        """
        limiter = RateLimiter(
            max_messages_per_second=0.5,  # 1 message every 2 seconds
            burst_multiplier=1.0
        )
        
        # First message should be immediate
        start_time = time.monotonic()
        await limiter.acquire()
        first_elapsed = time.monotonic() - start_time
        assert first_elapsed < 0.1, "First acquire should be immediate"
        
        # Second message should take ~2 seconds
        start_time = time.monotonic()
        await limiter.acquire()
        second_elapsed = time.monotonic() - start_time
        
        # Should be close to 2 seconds (allow 20% tolerance)
        assert 1.6 <= second_elapsed <= 2.4, \
            f"Second acquire should take ~2s, took {second_elapsed:.3f}s"
    
    @pytest.mark.asyncio
    async def test_very_high_rate_limit(self):
        """
        Edge case: Very high rate limit (> 100 msg/sec)
        
        The rate limiter should work correctly even with very high rates.
        """
        limiter = RateLimiter(
            max_messages_per_second=200.0,
            burst_multiplier=2.0
        )
        
        # Should be able to burst many messages quickly
        num_messages = 400  # 2 seconds worth at 200/sec
        
        start_time = time.monotonic()
        for _ in range(num_messages):
            await limiter.acquire()
        end_time = time.monotonic()
        
        elapsed_time = end_time - start_time
        actual_rate = num_messages / elapsed_time
        
        # Should be close to 200 msg/sec (allow 20% tolerance)
        assert 160 <= actual_rate <= 240, \
            f"Rate should be ~200 msg/sec, got {actual_rate:.2f}"
    
    @pytest.mark.asyncio
    async def test_zero_wait_time_when_tokens_available(self):
        """
        Edge case: Wait time should be zero when tokens are available
        
        get_wait_time() should return 0 when tokens are available.
        """
        limiter = RateLimiter(
            max_messages_per_second=10.0,
            burst_multiplier=2.0
        )
        
        # Initially should have tokens
        wait_time = limiter.get_wait_time()
        assert wait_time == 0.0, \
            f"Wait time should be 0 initially, got {wait_time}"
        
        # After acquiring some (but not all) tokens
        for _ in range(5):
            await limiter.acquire()
        
        wait_time = limiter.get_wait_time()
        assert wait_time == 0.0, \
            f"Wait time should be 0 when tokens remain, got {wait_time}"
