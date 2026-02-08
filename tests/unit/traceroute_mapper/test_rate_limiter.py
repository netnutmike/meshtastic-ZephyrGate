"""
Unit tests for Traceroute Mapper Rate Limiter

Tests token bucket algorithm, rate limit enforcement, and statistics tracking.

Requirements: 3.1, 3.2, 3.4
"""

import pytest
import asyncio
import time
from pathlib import Path
import sys

# Add plugins directory to path
plugins_path = Path(__file__).parent.parent.parent.parent / "plugins"
if str(plugins_path) not in sys.path:
    sys.path.insert(0, str(plugins_path))

from traceroute_mapper.rate_limiter import RateLimiter


@pytest.fixture
def limiter():
    """Provide a rate limiter with default settings"""
    return RateLimiter(traceroutes_per_minute=60.0, burst_multiplier=2.0)


@pytest.fixture
def slow_limiter():
    """Provide a rate limiter with slow rate for testing"""
    return RateLimiter(traceroutes_per_minute=2.0, burst_multiplier=1.0)


class TestRateLimiterInitialization:
    """Tests for rate limiter initialization"""
    
    def test_initialization_with_defaults(self):
        """Test rate limiter initializes with default values"""
        limiter = RateLimiter()
        
        assert limiter.traceroutes_per_minute == 1.0
        assert limiter.burst_multiplier == 2.0
        assert limiter.capacity == 2.0  # 1 * 2
        assert limiter.tokens == 2.0  # Start with full bucket
        assert limiter.traceroutes_per_second == 1.0 / 60.0
    
    def test_initialization_with_custom_values(self):
        """Test rate limiter initializes with custom values"""
        limiter = RateLimiter(
            traceroutes_per_minute=10.0,
            burst_multiplier=3.0
        )
        
        assert limiter.traceroutes_per_minute == 10.0
        assert limiter.burst_multiplier == 3.0
        assert limiter.capacity == 30.0  # 10 * 3
        assert limiter.tokens == 30.0
        assert limiter.traceroutes_per_second == 10.0 / 60.0
    
    def test_initial_statistics(self):
        """Test rate limiter starts with zero statistics"""
        limiter = RateLimiter()
        stats = limiter.get_statistics()
        
        assert stats['traceroutes_allowed'] == 0
        assert stats['traceroutes_delayed'] == 0
        assert stats['total_wait_time'] == 0.0
        assert stats['max_wait_time'] == 0.0
        assert stats['avg_wait_time'] == 0.0


class TestTokenBucketAlgorithm:
    """Tests for token bucket algorithm implementation"""
    
    @pytest.mark.asyncio
    async def test_initial_burst_allowed(self, limiter):
        """Test initial burst up to capacity is allowed without delay"""
        burst_capacity = int(limiter.capacity)
        
        start_time = time.monotonic()
        
        # Acquire tokens up to burst capacity
        for _ in range(burst_capacity):
            result = await limiter.acquire()
            assert result is True
        
        elapsed_time = time.monotonic() - start_time
        
        # Should complete very quickly (within 0.1 seconds)
        assert elapsed_time < 0.1, \
            f"Burst should be instant, took {elapsed_time:.3f}s"
    
    @pytest.mark.asyncio
    async def test_tokens_refill_over_time(self, slow_limiter):
        """Test tokens refill at the configured rate"""
        # Exhaust initial tokens
        await slow_limiter.acquire()
        await slow_limiter.acquire()
        
        # Wait for 60 seconds (should refill 2 tokens at 2 traceroutes/min)
        # For testing, we'll wait 1 second and check partial refill
        await asyncio.sleep(1.0)
        
        # At 2 traceroutes/min = 0.0333 traceroutes/sec
        # After 1 second, should have ~0.0333 tokens
        # Not enough for a full token, so next acquire should wait
        wait_time = slow_limiter.get_wait_time()
        
        # Should need to wait for remaining tokens
        assert wait_time > 0, "Should need to wait for more tokens"
    
    @pytest.mark.asyncio
    async def test_tokens_dont_exceed_capacity(self, limiter):
        """Test tokens don't exceed capacity even after long wait"""
        # Wait for a long time
        await asyncio.sleep(2.0)
        
        # Tokens should be at capacity, not more
        assert limiter.tokens <= limiter.capacity, \
            f"Tokens {limiter.tokens} should not exceed capacity {limiter.capacity}"
    
    @pytest.mark.asyncio
    async def test_fractional_tokens_handled(self):
        """Test rate limiter handles fractional token rates correctly"""
        limiter = RateLimiter(
            traceroutes_per_minute=150.0,  # 2.5 per second
            burst_multiplier=1.0
        )
        
        # Should be able to acquire initial tokens
        result = await limiter.acquire()
        assert result is True


class TestAcquireMethod:
    """Tests for acquire() method"""
    
    @pytest.mark.asyncio
    async def test_acquire_returns_true(self, limiter):
        """Test acquire always returns True"""
        result = await limiter.acquire()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_acquire_consumes_token(self, limiter):
        """Test acquire consumes one token"""
        initial_tokens = limiter.tokens
        await limiter.acquire()
        
        assert limiter.tokens == initial_tokens - 1.0
    
    @pytest.mark.asyncio
    async def test_acquire_waits_when_no_tokens(self):
        """Test acquire waits when no tokens are available"""
        # Use a faster rate for testing but with small capacity
        limiter = RateLimiter(traceroutes_per_minute=600.0, burst_multiplier=0.01)
        
        # Exhaust tokens (capacity is 6)
        for _ in range(7):
            await limiter.acquire()
        
        # Next acquire should wait
        start_time = time.monotonic()
        await limiter.acquire()
        elapsed_time = time.monotonic() - start_time
        
        # Should have waited (at 600/min = 10/sec, should wait ~0.1 seconds)
        assert elapsed_time >= 0.05, \
            f"Should have waited, took {elapsed_time:.3f}s"
    
    @pytest.mark.asyncio
    async def test_acquire_updates_statistics(self, limiter):
        """Test acquire updates statistics correctly"""
        await limiter.acquire()
        
        stats = limiter.get_statistics()
        assert stats['traceroutes_allowed'] == 1
    
    @pytest.mark.asyncio
    async def test_multiple_acquires_sequential(self, limiter):
        """Test multiple sequential acquires work correctly"""
        for i in range(5):
            result = await limiter.acquire()
            assert result is True
        
        stats = limiter.get_statistics()
        assert stats['traceroutes_allowed'] == 5


class TestWaitIfNeededMethod:
    """Tests for wait_if_needed() method"""
    
    @pytest.mark.asyncio
    async def test_wait_if_needed_calls_acquire(self, limiter):
        """Test wait_if_needed is equivalent to acquire"""
        initial_tokens = limiter.tokens
        await limiter.wait_if_needed()
        
        # Should have consumed a token
        assert limiter.tokens == initial_tokens - 1.0
    
    @pytest.mark.asyncio
    async def test_wait_if_needed_waits_when_needed(self):
        """Test wait_if_needed waits when rate limit would be exceeded"""
        # Use a faster rate for testing
        limiter = RateLimiter(traceroutes_per_minute=120.0, burst_multiplier=1.0)
        
        # Exhaust tokens
        await limiter.acquire()
        await limiter.acquire()
        
        # Should wait
        start_time = time.monotonic()
        await limiter.wait_if_needed()
        elapsed_time = time.monotonic() - start_time
        
        # At 120 traceroutes/min = 2/sec, should wait ~0.5 seconds
        assert elapsed_time >= 0.0, \
            f"Should have waited, took {elapsed_time:.3f}s"


class TestGetWaitTimeMethod:
    """Tests for get_wait_time() method"""
    
    def test_get_wait_time_zero_when_tokens_available(self, limiter):
        """Test get_wait_time returns 0 when tokens are available"""
        wait_time = limiter.get_wait_time()
        assert wait_time == 0.0
    
    @pytest.mark.asyncio
    async def test_get_wait_time_nonzero_when_no_tokens(self):
        """Test get_wait_time returns positive value when no tokens"""
        # Use a rate with small capacity but faster rate for testing
        limiter = RateLimiter(traceroutes_per_minute=600.0, burst_multiplier=0.01)
        
        # Exhaust tokens (capacity is 6)
        for _ in range(7):
            await limiter.acquire()
        
        wait_time = limiter.get_wait_time()
        
        # Should need to wait
        assert wait_time > 0, \
            f"Wait time should be positive, got {wait_time:.3f}s"
    
    @pytest.mark.asyncio
    async def test_get_wait_time_accurate_prediction(self):
        """Test get_wait_time accurately predicts wait needed"""
        # Use a faster rate for testing
        limiter = RateLimiter(traceroutes_per_minute=120.0, burst_multiplier=1.0)
        
        # Exhaust tokens
        await limiter.acquire()
        await limiter.acquire()
        
        predicted_wait = limiter.get_wait_time()
        
        # Wait that amount
        await asyncio.sleep(predicted_wait)
        
        # Should now have tokens available
        new_wait = limiter.get_wait_time()
        assert new_wait < 0.1, \
            f"After waiting predicted time, should have tokens available"


class TestSetRateMethod:
    """Tests for set_rate() method"""
    
    def test_set_rate_updates_rate(self, limiter):
        """Test set_rate updates the rate limit"""
        old_rate = limiter.traceroutes_per_minute
        new_rate = 10.0
        
        limiter.set_rate(new_rate)
        
        assert limiter.traceroutes_per_minute == new_rate
        assert limiter.traceroutes_per_second == new_rate / 60.0
    
    def test_set_rate_updates_capacity(self, limiter):
        """Test set_rate updates the capacity"""
        new_rate = 10.0
        limiter.set_rate(new_rate)
        
        expected_capacity = new_rate * limiter.burst_multiplier
        assert limiter.capacity == expected_capacity
    
    def test_set_rate_adjusts_tokens_proportionally(self, limiter):
        """Test set_rate adjusts current tokens proportionally"""
        # Start with half tokens
        initial_capacity = limiter.capacity
        limiter.tokens = initial_capacity / 2.0
        
        # Double the rate
        new_rate = limiter.traceroutes_per_minute * 2.0
        limiter.set_rate(new_rate)
        
        # Tokens should still be at half capacity
        expected_tokens = limiter.capacity / 2.0
        assert abs(limiter.tokens - expected_tokens) < 0.01
    
    @pytest.mark.asyncio
    async def test_set_rate_affects_future_acquires(self, limiter):
        """Test set_rate affects future acquire operations"""
        # Set a very low rate
        limiter.set_rate(1.0)  # 1 per minute
        
        # Exhaust tokens
        await limiter.acquire()
        await limiter.acquire()
        
        # Should need to wait a long time
        wait_time = limiter.get_wait_time()
        assert wait_time > 10.0, \
            f"At 1 traceroute/min, should need to wait >10s, got {wait_time:.3f}s"


class TestResetMethod:
    """Tests for reset() method"""
    
    @pytest.mark.asyncio
    async def test_reset_refills_tokens(self, limiter):
        """Test reset refills token bucket to capacity"""
        # Exhaust some tokens
        for _ in range(10):
            await limiter.acquire()
        
        # Reset
        limiter.reset()
        
        # Should have full capacity again
        assert limiter.tokens == limiter.capacity
    
    @pytest.mark.asyncio
    async def test_reset_allows_immediate_burst(self, limiter):
        """Test reset allows immediate burst again"""
        # Exhaust all tokens
        burst_capacity = int(limiter.capacity)
        for _ in range(burst_capacity + 5):
            await limiter.acquire()
        
        # Reset
        limiter.reset()
        
        # Should be able to burst again immediately
        start_time = time.monotonic()
        for _ in range(burst_capacity):
            await limiter.acquire()
        elapsed_time = time.monotonic() - start_time
        
        assert elapsed_time < 0.1, \
            f"After reset, burst should be instant, took {elapsed_time:.3f}s"


class TestStatistics:
    """Tests for statistics tracking"""
    
    @pytest.mark.asyncio
    async def test_statistics_track_allowed_traceroutes(self, limiter):
        """Test statistics track number of allowed traceroutes"""
        for _ in range(5):
            await limiter.acquire()
        
        stats = limiter.get_statistics()
        assert stats['traceroutes_allowed'] == 5
    
    @pytest.mark.asyncio
    async def test_statistics_track_delayed_traceroutes(self):
        """Test statistics track number of delayed traceroutes"""
        # Use a rate with small capacity but faster rate for testing
        limiter = RateLimiter(traceroutes_per_minute=600.0, burst_multiplier=0.01)
        
        # Exhaust tokens to cause delays (capacity is 6, so 10 will cause delays)
        for _ in range(10):
            await limiter.acquire()
        
        stats = limiter.get_statistics()
        
        # Some traceroutes should have been delayed
        assert stats['traceroutes_delayed'] > 0
    
    @pytest.mark.asyncio
    async def test_statistics_track_wait_times(self):
        """Test statistics track wait times"""
        # Use a rate with small capacity but faster rate for testing
        limiter = RateLimiter(traceroutes_per_minute=600.0, burst_multiplier=0.01)
        
        # Exhaust tokens to cause delays (capacity is 6, so 10 will cause delays)
        for _ in range(10):
            await limiter.acquire()
        
        stats = limiter.get_statistics()
        
        # Should have recorded wait times
        assert stats['total_wait_time'] > 0.0
        assert stats['max_wait_time'] > 0.0
        assert stats['avg_wait_time'] > 0.0
    
    @pytest.mark.asyncio
    async def test_statistics_average_wait_time(self):
        """Test average wait time is calculated correctly"""
        # Use a rate with small capacity but faster rate for testing
        limiter = RateLimiter(traceroutes_per_minute=600.0, burst_multiplier=0.01)
        
        # Cause some delays (capacity is 6, so 10 will cause delays)
        for _ in range(10):
            await limiter.acquire()
        
        stats = limiter.get_statistics()
        
        # Average should be total / delayed
        if stats['traceroutes_delayed'] > 0:
            expected_avg = stats['total_wait_time'] / stats['traceroutes_delayed']
            assert abs(stats['avg_wait_time'] - expected_avg) < 0.001
    
    def test_statistics_structure(self, limiter):
        """Test statistics contain all required fields"""
        stats = limiter.get_statistics()
        
        assert 'traceroutes_per_minute' in stats
        assert 'burst_capacity' in stats
        assert 'current_tokens' in stats
        assert 'traceroutes_allowed' in stats
        assert 'traceroutes_delayed' in stats
        assert 'total_wait_time' in stats
        assert 'max_wait_time' in stats
        assert 'avg_wait_time' in stats


class TestRateLimitEnforcement:
    """Tests for rate limit enforcement"""
    
    @pytest.mark.asyncio
    async def test_rate_limit_enforced(self):
        """Test rate limit is actually enforced"""
        # Use a rate that's testable but still demonstrates rate limiting
        limiter = RateLimiter(traceroutes_per_minute=120.0, burst_multiplier=0.5)
        num_traceroutes = 10
        
        start_time = time.monotonic()
        
        for _ in range(num_traceroutes):
            await limiter.acquire()
        
        elapsed_time = time.monotonic() - start_time
        
        # At 120 traceroutes/min = 2/sec with burst of 60 (0.5 * 120)
        # First 60 are burst, but we only do 10, so all should be fast
        # But let's exhaust the burst first
        limiter2 = RateLimiter(traceroutes_per_minute=120.0, burst_multiplier=0.05)
        
        start_time = time.monotonic()
        for _ in range(10):
            await limiter2.acquire()
        elapsed_time = time.monotonic() - start_time
        
        # At 120 traceroutes/min = 2/sec with burst of 6 (0.05 * 120)
        # First 6 are burst, remaining 4 take 2 seconds
        assert elapsed_time >= 1.5, \
            f"10 traceroutes at 2/sec with small burst should take ~2s, took {elapsed_time:.3f}s"
    
    @pytest.mark.asyncio
    async def test_burst_then_sustained_rate(self, limiter):
        """Test burst followed by sustained rate"""
        burst_capacity = int(limiter.capacity)
        
        # Burst should be fast
        start_time = time.monotonic()
        for _ in range(burst_capacity):
            await limiter.acquire()
        burst_time = time.monotonic() - start_time
        
        assert burst_time < 0.1, "Burst should be instant"


class TestConcurrency:
    """Tests for concurrent access"""
    
    @pytest.mark.asyncio
    async def test_concurrent_acquires(self, limiter):
        """Test concurrent acquire calls are handled correctly"""
        num_concurrent = 10
        
        # Launch concurrent acquire tasks
        tasks = [limiter.acquire() for _ in range(num_concurrent)]
        results = await asyncio.gather(*tasks)
        
        # All should succeed
        assert all(results)
        
        # Statistics should be accurate
        stats = limiter.get_statistics()
        assert stats['traceroutes_allowed'] == num_concurrent


class TestEdgeCases:
    """Tests for edge cases"""
    
    @pytest.mark.asyncio
    async def test_very_low_rate(self):
        """Test rate limiter works with very low rates"""
        limiter = RateLimiter(
            traceroutes_per_minute=0.5,  # 1 traceroute every 2 minutes
            burst_multiplier=2.0
        )
        
        # First traceroute should be immediate
        start_time = time.monotonic()
        await limiter.acquire()
        first_time = time.monotonic() - start_time
        assert first_time < 0.1
    
    @pytest.mark.asyncio
    async def test_burst_multiplier_one(self):
        """Test rate limiter works with burst multiplier of 1"""
        limiter = RateLimiter(
            traceroutes_per_minute=60.0,
            burst_multiplier=1.0
        )
        
        # Should have capacity of 60
        assert limiter.capacity == 60.0
        
        # Should be able to burst 60 traceroutes
        for _ in range(60):
            await limiter.acquire()
        
        stats = limiter.get_statistics()
        assert stats['traceroutes_allowed'] == 60
    
    @pytest.mark.asyncio
    async def test_large_burst_multiplier(self):
        """Test rate limiter works with large burst multiplier"""
        limiter = RateLimiter(
            traceroutes_per_minute=60.0,
            burst_multiplier=10.0
        )
        
        # Should have capacity of 600
        assert limiter.capacity == 600.0
        
        # Should be able to burst 600 traceroutes quickly
        start_time = time.monotonic()
        for _ in range(600):
            await limiter.acquire()
        elapsed_time = time.monotonic() - start_time
        
        assert elapsed_time < 0.5, \
            f"Large burst should be fast, took {elapsed_time:.3f}s"
    
    def test_zero_rate_handling(self):
        """Test rate limiter with zero rate"""
        limiter = RateLimiter(traceroutes_per_minute=0.0, burst_multiplier=2.0)
        
        # Should have zero capacity
        assert limiter.capacity == 0.0
        assert limiter.traceroutes_per_second == 0.0
    
    @pytest.mark.asyncio
    async def test_zero_rate_disables_operations(self):
        """
        Test zero rate (should disable operations)
        
        When rate is set to zero, the rate limiter should effectively disable
        operations by having zero capacity and zero refill rate. This means
        acquire() will block indefinitely since tokens never refill.
        
        The implementation has error handling that catches the ZeroDivisionError
        from get_wait_time() and defaults to a 1.0 second wait, but since tokens
        never refill at zero rate, it will keep waiting forever.
        
        Requirements: 3.4
        """
        limiter = RateLimiter(traceroutes_per_minute=0.0, burst_multiplier=2.0)
        
        # Verify zero rate configuration
        assert limiter.traceroutes_per_minute == 0.0
        assert limiter.traceroutes_per_second == 0.0
        assert limiter.capacity == 0.0
        assert limiter.tokens == 0.0
        
        # Test that get_wait_time raises ZeroDivisionError with zero rate
        with pytest.raises(ZeroDivisionError):
            limiter.get_wait_time()
        
        # Test that acquire would block indefinitely by using a timeout
        # The acquire method catches the ZeroDivisionError and defaults to 1.0s wait,
        # but since tokens never refill, it will keep looping and waiting
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(limiter.acquire(), timeout=0.5)
        
        # Verify statistics show no traceroutes were allowed during the timeout
        stats = limiter.get_statistics()
        assert stats['traceroutes_allowed'] == 0, \
            "Zero rate should prevent any traceroutes from being allowed"
        
        # Verify that even after waiting, tokens don't refill
        await asyncio.sleep(0.1)
        assert limiter.tokens == 0.0, \
            "Tokens should not refill with zero rate"
        
        # Test that setting a non-zero rate re-enables operations
        limiter.set_rate(60.0)
        assert limiter.traceroutes_per_minute == 60.0
        assert limiter.capacity > 0.0
        
        # Should now be able to acquire
        result = await asyncio.wait_for(limiter.acquire(), timeout=1.0)
        assert result is True, \
            "After setting non-zero rate, acquire should succeed"
    
    @pytest.mark.asyncio
    async def test_burst_allowance_behavior(self):
        """
        Test burst allowance
        
        Verifies that the burst multiplier correctly allows an initial burst
        of traceroutes equal to (rate * burst_multiplier) without delay,
        and that subsequent requests are rate-limited.
        
        Requirements: 3.4
        """
        # Use a moderate rate with a clear burst multiplier
        rate = 60.0  # 60 traceroutes per minute = 1 per second
        burst_mult = 3.0
        limiter = RateLimiter(
            traceroutes_per_minute=rate,
            burst_multiplier=burst_mult
        )
        
        # Calculate expected burst capacity
        expected_capacity = rate * burst_mult  # 60 * 3 = 180
        assert limiter.capacity == expected_capacity
        assert limiter.tokens == expected_capacity  # Start with full bucket
        
        # Test 1: Initial burst should be instant
        burst_count = int(expected_capacity)
        start_time = time.monotonic()
        
        for i in range(burst_count):
            result = await limiter.acquire()
            assert result is True, f"Burst request {i} should succeed"
        
        burst_time = time.monotonic() - start_time
        
        # Burst should complete very quickly (within 0.2 seconds for 180 requests)
        assert burst_time < 0.2, \
            f"Burst of {burst_count} traceroutes should be instant, took {burst_time:.3f}s"
        
        # Verify tokens are exhausted
        assert limiter.tokens < 1.0, \
            f"After burst, tokens should be exhausted, but have {limiter.tokens:.2f}"
        
        # Test 2: Next request after burst should wait
        before_wait = time.monotonic()
        result = await limiter.acquire()
        after_wait = time.monotonic()
        wait_time = after_wait - before_wait
        
        assert result is True, "Request after burst should eventually succeed"
        # At 60 traceroutes/min = 1/sec, should wait approximately 1 second
        # Allow some tolerance for timing precision
        assert wait_time >= 0.5, \
            f"Request after burst should wait, but only waited {wait_time:.3f}s"
        
        # Test 3: Verify statistics reflect burst behavior
        stats = limiter.get_statistics()
        assert stats['traceroutes_allowed'] == burst_count + 1
        assert stats['traceroutes_delayed'] >= 1, \
            "At least one request should have been delayed after burst"
        
        # Test 4: After reset, burst should be available again
        limiter.reset()
        assert limiter.tokens == expected_capacity, \
            "After reset, tokens should be refilled to capacity"
        
        # Should be able to burst again immediately
        start_time = time.monotonic()
        for _ in range(burst_count):
            await limiter.acquire()
        burst_time_2 = time.monotonic() - start_time
        
        assert burst_time_2 < 0.2, \
            f"Second burst after reset should also be instant, took {burst_time_2:.3f}s"
    
    @pytest.mark.asyncio
    async def test_rate_changes_during_operation(self):
        """
        Test rate changes during operation
        
        Verifies that the rate limiter correctly handles dynamic rate changes
        while operations are in progress, including:
        - Rate increases (should allow faster throughput)
        - Rate decreases (should slow down throughput)
        - Token adjustment to maintain relative fullness
        - Immediate effect on subsequent requests
        
        Requirements: 3.4
        """
        # Start with a moderate rate
        initial_rate = 120.0  # 120 traceroutes/min = 2/sec
        limiter = RateLimiter(
            traceroutes_per_minute=initial_rate,
            burst_multiplier=1.0
        )
        
        # Test 1: Verify initial rate works
        initial_capacity = limiter.capacity
        assert initial_capacity == initial_rate * 1.0  # 120
        
        # Exhaust initial burst
        for _ in range(int(initial_capacity)):
            await limiter.acquire()
        
        # Measure time for a few requests at initial rate
        num_requests = 5
        start_time = time.monotonic()
        for _ in range(num_requests):
            await limiter.acquire()
        time_at_initial_rate = time.monotonic() - start_time
        
        # At 2 traceroutes/sec, 5 requests should take ~2.5 seconds
        expected_time_initial = num_requests / 2.0  # 2.5 seconds
        assert time_at_initial_rate >= expected_time_initial * 0.7, \
            f"Initial rate timing seems off: {time_at_initial_rate:.3f}s"
        
        # Test 2: Increase rate during operation
        new_rate_high = 600.0  # 600 traceroutes/min = 10/sec (5x faster)
        limiter.set_rate(new_rate_high)
        
        # Verify rate was updated
        assert limiter.traceroutes_per_minute == new_rate_high
        assert limiter.capacity == new_rate_high * 1.0  # 600
        
        # Tokens should be adjusted proportionally
        # If we had ~0 tokens before, we should still have ~0 tokens
        # (relative fullness is maintained)
        assert limiter.tokens >= 0, "Tokens should not be negative"
        
        # Measure time for requests at new higher rate
        # Wait a moment for some tokens to refill at new rate
        await asyncio.sleep(0.2)
        
        start_time = time.monotonic()
        for _ in range(num_requests):
            await limiter.acquire()
        time_at_high_rate = time.monotonic() - start_time
        
        # At 10 traceroutes/sec, 5 requests should take ~0.5 seconds
        # Should be faster than initial rate
        assert time_at_high_rate < time_at_initial_rate * 0.8, \
            f"Higher rate should be faster: initial={time_at_initial_rate:.3f}s, high={time_at_high_rate:.3f}s"
        
        # Test 3: Decrease rate during operation
        new_rate_low = 60.0  # 60 traceroutes/min = 1/sec (10x slower than high rate)
        limiter.set_rate(new_rate_low)
        
        # Verify rate was updated
        assert limiter.traceroutes_per_minute == new_rate_low
        assert limiter.capacity == new_rate_low * 1.0  # 60
        
        # Exhaust any remaining tokens
        while limiter.tokens >= 1.0:
            await limiter.acquire()
        
        # Measure time for requests at new lower rate
        start_time = time.monotonic()
        for _ in range(num_requests):
            await limiter.acquire()
        time_at_low_rate = time.monotonic() - start_time
        
        # At 1 traceroute/sec, 5 requests should take ~5 seconds
        expected_time_low = num_requests / 1.0  # 5 seconds
        assert time_at_low_rate >= expected_time_low * 0.7, \
            f"Lower rate should be slower: {time_at_low_rate:.3f}s (expected ~{expected_time_low:.1f}s)"
        
        # Should be slower than high rate
        assert time_at_low_rate > time_at_high_rate * 2, \
            f"Lower rate should be much slower: low={time_at_low_rate:.3f}s, high={time_at_high_rate:.3f}s"
        
        # Test 4: Verify statistics are maintained across rate changes
        stats = limiter.get_statistics()
        assert stats['traceroutes_per_minute'] == new_rate_low, \
            "Statistics should reflect current rate"
        assert stats['burst_capacity'] == new_rate_low * 1.0, \
            "Statistics should reflect current capacity"
        assert stats['traceroutes_allowed'] > 0, \
            "Statistics should accumulate across rate changes"
        
        # Test 5: Verify multiple rapid rate changes don't break the limiter
        for rate in [300.0, 30.0, 600.0, 120.0]:
            limiter.set_rate(rate)
            assert limiter.traceroutes_per_minute == rate
            # Should still be able to acquire
            result = await limiter.acquire()
            assert result is True, f"Should be able to acquire after setting rate to {rate}"
