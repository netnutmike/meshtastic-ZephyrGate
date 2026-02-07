"""
Unit tests for MQTT Gateway Rate Limiter

Tests token bucket algorithm, rate limit enforcement, and statistics tracking.

Requirements: 7.1
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

from mqtt_gateway.rate_limiter import RateLimiter


@pytest.fixture
def limiter():
    """Provide a rate limiter with default settings"""
    return RateLimiter(max_messages_per_second=10.0, burst_multiplier=2.0)


@pytest.fixture
def slow_limiter():
    """Provide a rate limiter with slow rate for testing"""
    return RateLimiter(max_messages_per_second=2.0, burst_multiplier=1.0)


class TestRateLimiterInitialization:
    """Tests for rate limiter initialization"""
    
    def test_initialization_with_defaults(self):
        """Test rate limiter initializes with default values"""
        limiter = RateLimiter()
        
        assert limiter.max_messages_per_second == 10.0
        assert limiter.burst_multiplier == 2.0
        assert limiter.capacity == 20.0  # 10 * 2
        assert limiter.tokens == 20.0  # Start with full bucket
    
    def test_initialization_with_custom_values(self):
        """Test rate limiter initializes with custom values"""
        limiter = RateLimiter(
            max_messages_per_second=5.0,
            burst_multiplier=3.0
        )
        
        assert limiter.max_messages_per_second == 5.0
        assert limiter.burst_multiplier == 3.0
        assert limiter.capacity == 15.0  # 5 * 3
        assert limiter.tokens == 15.0
    
    def test_initial_statistics(self):
        """Test rate limiter starts with zero statistics"""
        limiter = RateLimiter()
        stats = limiter.get_statistics()
        
        assert stats['messages_allowed'] == 0
        assert stats['messages_delayed'] == 0
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
        # Exhaust initial token
        await slow_limiter.acquire()
        
        # Wait for 1 second (should refill 2 tokens at 2 msg/sec)
        await asyncio.sleep(1.0)
        
        # Should be able to acquire 2 tokens quickly
        start_time = time.monotonic()
        await slow_limiter.acquire()
        await slow_limiter.acquire()
        elapsed_time = time.monotonic() - start_time
        
        # Should complete quickly since tokens were refilled
        assert elapsed_time < 0.1, \
            f"Refilled tokens should be available immediately, took {elapsed_time:.3f}s"
    
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
            max_messages_per_second=2.5,  # Fractional rate
            burst_multiplier=1.0
        )
        
        # Should be able to acquire initial token
        result = await limiter.acquire()
        assert result is True
        
        # Wait for 0.4 seconds (should refill 1 token at 2.5/sec)
        await asyncio.sleep(0.4)
        
        # Should be able to acquire another token quickly
        start_time = time.monotonic()
        await limiter.acquire()
        elapsed_time = time.monotonic() - start_time
        
        assert elapsed_time < 0.1, \
            f"Should have refilled token, took {elapsed_time:.3f}s"


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
    async def test_acquire_waits_when_no_tokens(self, slow_limiter):
        """Test acquire waits when no tokens are available"""
        # Exhaust tokens
        await slow_limiter.acquire()
        await slow_limiter.acquire()
        
        # Next acquire should wait
        start_time = time.monotonic()
        await slow_limiter.acquire()
        elapsed_time = time.monotonic() - start_time
        
        # Should have waited approximately 0.5 seconds (1/2 msg/sec)
        assert elapsed_time >= 0.4, \
            f"Should have waited ~0.5s, only waited {elapsed_time:.3f}s"
    
    @pytest.mark.asyncio
    async def test_acquire_updates_statistics(self, limiter):
        """Test acquire updates statistics correctly"""
        await limiter.acquire()
        
        stats = limiter.get_statistics()
        assert stats['messages_allowed'] == 1
    
    @pytest.mark.asyncio
    async def test_multiple_acquires_sequential(self, limiter):
        """Test multiple sequential acquires work correctly"""
        for i in range(5):
            result = await limiter.acquire()
            assert result is True
        
        stats = limiter.get_statistics()
        assert stats['messages_allowed'] == 5


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
    async def test_wait_if_needed_waits_when_needed(self, slow_limiter):
        """Test wait_if_needed waits when rate limit would be exceeded"""
        # Exhaust tokens
        await slow_limiter.acquire()
        await slow_limiter.acquire()
        
        # Should wait
        start_time = time.monotonic()
        await slow_limiter.wait_if_needed()
        elapsed_time = time.monotonic() - start_time
        
        assert elapsed_time >= 0.4, \
            f"Should have waited, only took {elapsed_time:.3f}s"


class TestGetWaitTimeMethod:
    """Tests for get_wait_time() method"""
    
    def test_get_wait_time_zero_when_tokens_available(self, limiter):
        """Test get_wait_time returns 0 when tokens are available"""
        wait_time = limiter.get_wait_time()
        assert wait_time == 0.0
    
    @pytest.mark.asyncio
    async def test_get_wait_time_nonzero_when_no_tokens(self, slow_limiter):
        """Test get_wait_time returns positive value when no tokens"""
        # Exhaust tokens
        await slow_limiter.acquire()
        await slow_limiter.acquire()
        
        wait_time = slow_limiter.get_wait_time()
        
        # Should need to wait approximately 0.5 seconds
        assert wait_time > 0.4, \
            f"Wait time should be ~0.5s, got {wait_time:.3f}s"
    
    @pytest.mark.asyncio
    async def test_get_wait_time_accurate_prediction(self, slow_limiter):
        """Test get_wait_time accurately predicts wait needed"""
        # Exhaust tokens
        await slow_limiter.acquire()
        await slow_limiter.acquire()
        
        predicted_wait = slow_limiter.get_wait_time()
        
        # Wait that amount
        await asyncio.sleep(predicted_wait)
        
        # Should now have tokens available
        new_wait = slow_limiter.get_wait_time()
        assert new_wait < 0.1, \
            f"After waiting predicted time, should have tokens available"


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
    async def test_statistics_track_allowed_messages(self, limiter):
        """Test statistics track number of allowed messages"""
        for _ in range(5):
            await limiter.acquire()
        
        stats = limiter.get_statistics()
        assert stats['messages_allowed'] == 5
    
    @pytest.mark.asyncio
    async def test_statistics_track_delayed_messages(self, slow_limiter):
        """Test statistics track number of delayed messages"""
        # Exhaust tokens to cause delays
        for _ in range(5):
            await slow_limiter.acquire()
        
        stats = slow_limiter.get_statistics()
        
        # Some messages should have been delayed
        assert stats['messages_delayed'] > 0
    
    @pytest.mark.asyncio
    async def test_statistics_track_wait_times(self, slow_limiter):
        """Test statistics track wait times"""
        # Exhaust tokens to cause delays
        for _ in range(5):
            await slow_limiter.acquire()
        
        stats = slow_limiter.get_statistics()
        
        # Should have recorded wait times
        assert stats['total_wait_time'] > 0.0
        assert stats['max_wait_time'] > 0.0
        assert stats['avg_wait_time'] > 0.0
    
    @pytest.mark.asyncio
    async def test_statistics_average_wait_time(self, slow_limiter):
        """Test average wait time is calculated correctly"""
        # Cause some delays
        for _ in range(5):
            await slow_limiter.acquire()
        
        stats = slow_limiter.get_statistics()
        
        # Average should be total / delayed
        if stats['messages_delayed'] > 0:
            expected_avg = stats['total_wait_time'] / stats['messages_delayed']
            assert abs(stats['avg_wait_time'] - expected_avg) < 0.001
    
    def test_statistics_structure(self, limiter):
        """Test statistics contain all required fields"""
        stats = limiter.get_statistics()
        
        assert 'max_messages_per_second' in stats
        assert 'burst_capacity' in stats
        assert 'current_tokens' in stats
        assert 'messages_allowed' in stats
        assert 'messages_delayed' in stats
        assert 'total_wait_time' in stats
        assert 'max_wait_time' in stats
        assert 'avg_wait_time' in stats


class TestRateLimitEnforcement:
    """Tests for rate limit enforcement"""
    
    @pytest.mark.asyncio
    async def test_rate_limit_enforced(self, slow_limiter):
        """Test rate limit is actually enforced"""
        num_messages = 10
        
        start_time = time.monotonic()
        
        for _ in range(num_messages):
            await slow_limiter.acquire()
        
        elapsed_time = time.monotonic() - start_time
        
        # At 2 msg/sec, 10 messages should take at least 4 seconds
        # (first 2 are burst, remaining 8 take 4 seconds)
        assert elapsed_time >= 3.5, \
            f"10 messages at 2/sec should take ~4s, took {elapsed_time:.3f}s"
    
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
        
        # Sustained rate should match limit
        sustained_count = 20
        start_time = time.monotonic()
        for _ in range(sustained_count):
            await limiter.acquire()
        sustained_time = time.monotonic() - start_time
        
        # At 10 msg/sec, 20 messages should take ~2 seconds
        assert sustained_time >= 1.8, \
            f"20 messages at 10/sec should take ~2s, took {sustained_time:.3f}s"


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
        assert stats['messages_allowed'] == num_concurrent
    
    @pytest.mark.asyncio
    async def test_concurrent_acquires_rate_limited(self, slow_limiter):
        """Test concurrent acquires are still rate limited"""
        num_concurrent = 10
        
        start_time = time.monotonic()
        
        # Launch concurrent acquire tasks
        tasks = [slow_limiter.acquire() for _ in range(num_concurrent)]
        await asyncio.gather(*tasks)
        
        elapsed_time = time.monotonic() - start_time
        
        # Should still take time due to rate limiting
        # At 2 msg/sec, 10 messages should take at least 4 seconds
        assert elapsed_time >= 3.5, \
            f"Concurrent acquires should still be rate limited, took {elapsed_time:.3f}s"


class TestEdgeCases:
    """Tests for edge cases"""
    
    @pytest.mark.asyncio
    async def test_very_low_rate(self):
        """Test rate limiter works with very low rates"""
        limiter = RateLimiter(
            max_messages_per_second=0.5,  # 1 message every 2 seconds
            burst_multiplier=2.0  # Need burst > 1 to have at least 1 token initially
        )
        
        # First message should be immediate (we have 1.0 token from 0.5 * 2.0)
        start_time = time.monotonic()
        await limiter.acquire()
        first_time = time.monotonic() - start_time
        assert first_time < 0.1
        
        # Second message should take ~2 seconds (need to wait for 1 token at 0.5/sec)
        start_time = time.monotonic()
        await limiter.acquire()
        second_time = time.monotonic() - start_time
        assert second_time >= 1.8
    
    @pytest.mark.asyncio
    async def test_burst_multiplier_one(self):
        """Test rate limiter works with burst multiplier of 1"""
        limiter = RateLimiter(
            max_messages_per_second=10.0,
            burst_multiplier=1.0
        )
        
        # Should have capacity of 10
        assert limiter.capacity == 10.0
        
        # Should be able to burst 10 messages
        for _ in range(10):
            await limiter.acquire()
        
        stats = limiter.get_statistics()
        assert stats['messages_allowed'] == 10
    
    @pytest.mark.asyncio
    async def test_large_burst_multiplier(self):
        """Test rate limiter works with large burst multiplier"""
        limiter = RateLimiter(
            max_messages_per_second=10.0,
            burst_multiplier=10.0
        )
        
        # Should have capacity of 100
        assert limiter.capacity == 100.0
        
        # Should be able to burst 100 messages quickly
        start_time = time.monotonic()
        for _ in range(100):
            await limiter.acquire()
        elapsed_time = time.monotonic() - start_time
        
        assert elapsed_time < 0.2, \
            f"Large burst should be fast, took {elapsed_time:.3f}s"
