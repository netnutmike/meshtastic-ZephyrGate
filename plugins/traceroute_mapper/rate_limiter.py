"""
Rate limiter for Traceroute Mapper

Implements token bucket algorithm for rate limiting traceroute requests.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any


class RateLimiter:
    """
    Token bucket rate limiter for traceroute requests.
    
    Features:
    - Token bucket algorithm for smooth rate limiting
    - Configurable rate limit (traceroutes per minute)
    - Burst support with configurable multiplier
    - Wait/acquire methods for rate limit enforcement
    - Dynamic rate adjustment
    - Statistics tracking
    
    Requirements: 3.1, 3.2, 3.4
    """

    def __init__(
        self,
        traceroutes_per_minute: float = 1.0,
        burst_multiplier: float = 2.0,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize rate limiter.
        
        Args:
            traceroutes_per_minute: Maximum traceroutes allowed per minute
            burst_multiplier: Multiplier for burst capacity (capacity = rate * multiplier)
            logger: Logger instance for rate limiter operations
        """
        self.traceroutes_per_minute = traceroutes_per_minute
        self.burst_multiplier = burst_multiplier
        self.logger = logger or logging.getLogger(__name__)
        
        # Convert to traceroutes per second for token bucket
        self.traceroutes_per_second = traceroutes_per_minute / 60.0
        
        # Token bucket parameters
        self.capacity = traceroutes_per_minute * burst_multiplier
        self.tokens = self.capacity  # Start with full bucket
        self.last_refill_time = time.monotonic()
        
        # Statistics
        self._stats = {
            'traceroutes_allowed': 0,
            'traceroutes_delayed': 0,
            'total_wait_time': 0.0,
            'max_wait_time': 0.0,
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """
        Acquire a token to send a traceroute.
        
        This method will wait if necessary until a token is available.
        
        Handles errors gracefully:
        - Time calculation errors
        - Lock acquisition errors
        - Sleep interruption
        
        Returns:
            True when a token is acquired (always returns True)
            
        Requirements: 3.1, 3.2
        """
        try:
            async with self._lock:
                # Refill tokens based on time elapsed
                try:
                    self._refill_tokens()
                except Exception as e:
                    self.logger.error(f"Error refilling tokens: {e}", exc_info=True)
                    # Continue anyway - better to allow the traceroute than block forever
                
                # If we have tokens, consume one and return immediately
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    self._stats['traceroutes_allowed'] += 1
                    return True
                
                # Calculate wait time needed
                try:
                    wait_time = self.get_wait_time()
                except Exception as e:
                    self.logger.error(f"Error calculating wait time: {e}", exc_info=True)
                    # Default to a small wait time
                    wait_time = 1.0
                
                if wait_time > 0:
                    self._stats['traceroutes_delayed'] += 1
                    self._stats['total_wait_time'] += wait_time
                    self._stats['max_wait_time'] = max(
                        self._stats['max_wait_time'],
                        wait_time
                    )
                    
                    # Log rate limit event with details
                    self.logger.debug(
                        f"Rate limit reached - "
                        f"wait_time={wait_time:.3f}s, "
                        f"current_tokens={self.tokens:.2f}, "
                        f"capacity={self.capacity:.2f}, "
                        f"rate={self.traceroutes_per_minute} traceroutes/min, "
                        f"traceroutes_delayed={self._stats['traceroutes_delayed']}"
                    )
                    
                    # Log warning if wait time is significant
                    if wait_time > 60.0:
                        self.logger.warning(
                            f"Significant rate limit delay - "
                            f"wait_time={wait_time:.3f}s, "
                            f"consider increasing traceroutes_per_minute"
                        )
                    
                    # Wait inside the lock to serialize access
                    try:
                        await asyncio.sleep(wait_time)
                    except asyncio.CancelledError:
                        # If cancelled, still consume a token to maintain consistency
                        self.logger.debug("Rate limiter wait cancelled")
                        raise
                    
                    # Refill tokens after waiting
                    try:
                        self._refill_tokens()
                    except Exception as e:
                        self.logger.error(f"Error refilling tokens after wait: {e}", exc_info=True)
                
                # Consume token
                self.tokens -= 1.0
                self._stats['traceroutes_allowed'] += 1
                return True
                
        except asyncio.CancelledError:
            # Re-raise cancellation
            raise
        except Exception as e:
            # Catch-all for unexpected errors
            self.logger.error(f"Unexpected error in rate limiter acquire: {e}", exc_info=True)
            # Allow the traceroute through rather than blocking forever
            self._stats['traceroutes_allowed'] += 1
            return True

    async def wait_if_needed(self) -> None:
        """
        Wait if rate limit would be exceeded.
        
        This is a convenience method that calls acquire() and discards the result.
        
        Requirements: 3.2
        """
        await self.acquire()

    def get_wait_time(self) -> float:
        """
        Get the time to wait before next traceroute can be sent.
        
        Returns:
            Wait time in seconds (0 if no wait needed)
            
        Requirements: 3.2
        """
        # Refill tokens first
        self._refill_tokens()
        
        # If we have tokens, no wait needed
        if self.tokens >= 1.0:
            return 0.0
        
        # Calculate how many tokens we need
        tokens_needed = 1.0 - self.tokens
        
        # Calculate time to generate those tokens
        wait_time = tokens_needed / self.traceroutes_per_second
        
        return wait_time

    def set_rate(self, traceroutes_per_minute: float) -> None:
        """
        Set a new rate limit dynamically.
        
        This allows the rate to be adjusted at runtime, for example in response
        to network congestion or health monitoring.
        
        Args:
            traceroutes_per_minute: New rate limit in traceroutes per minute
            
        Requirements: 3.4
        """
        old_rate = self.traceroutes_per_minute
        self.traceroutes_per_minute = traceroutes_per_minute
        self.traceroutes_per_second = traceroutes_per_minute / 60.0
        
        # Update capacity based on new rate
        old_capacity = self.capacity
        self.capacity = traceroutes_per_minute * self.burst_multiplier
        
        # Adjust current tokens proportionally to maintain relative fullness
        if old_capacity > 0:
            fullness_ratio = self.tokens / old_capacity
            self.tokens = self.capacity * fullness_ratio
        else:
            self.tokens = self.capacity
        
        # Log rate change
        self.logger.info(
            f"Rate limit changed - "
            f"old_rate={old_rate:.2f} traceroutes/min, "
            f"new_rate={traceroutes_per_minute:.2f} traceroutes/min, "
            f"old_capacity={old_capacity:.2f}, "
            f"new_capacity={self.capacity:.2f}, "
            f"tokens={self.tokens:.2f}"
        )

    def reset(self) -> None:
        """
        Reset the rate limiter to initial state.
        
        This refills the token bucket to capacity and resets the refill time.
        """
        old_tokens = self.tokens
        self.tokens = self.capacity
        self.last_refill_time = time.monotonic()
        
        # Log rate limiter reset
        self.logger.info(
            f"Rate limiter reset - "
            f"old_tokens={old_tokens:.2f}, "
            f"new_tokens={self.tokens:.2f}, "
            f"capacity={self.capacity:.2f}, "
            f"rate={self.traceroutes_per_minute} traceroutes/min"
        )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get rate limiter statistics.
        
        Returns:
            Dictionary containing rate limiter statistics including:
            - traceroutes_per_minute: Current rate limit
            - burst_capacity: Maximum burst capacity
            - current_tokens: Available tokens
            - traceroutes_allowed: Total traceroutes allowed
            - traceroutes_delayed: Total traceroutes delayed
            - total_wait_time: Total time spent waiting
            - max_wait_time: Maximum wait time for a single traceroute
            - avg_wait_time: Average wait time per delayed traceroute
        """
        avg_wait_time = 0.0
        if self._stats['traceroutes_delayed'] > 0:
            avg_wait_time = (
                self._stats['total_wait_time'] / self._stats['traceroutes_delayed']
            )
        
        return {
            'traceroutes_per_minute': self.traceroutes_per_minute,
            'burst_capacity': self.capacity,
            'current_tokens': self.tokens,
            'traceroutes_allowed': self._stats['traceroutes_allowed'],
            'traceroutes_delayed': self._stats['traceroutes_delayed'],
            'total_wait_time': self._stats['total_wait_time'],
            'max_wait_time': self._stats['max_wait_time'],
            'avg_wait_time': avg_wait_time,
        }

    def _refill_tokens(self) -> None:
        """
        Refill tokens based on time elapsed since last refill.
        
        This implements the token bucket algorithm's refill mechanism.
        
        Handles errors gracefully:
        - Time calculation errors
        - Arithmetic errors
        
        Requirements: 3.1
        """
        try:
            now = time.monotonic()
            time_elapsed = now - self.last_refill_time
            
            # Sanity check - if time went backwards or is negative, reset
            if time_elapsed < 0:
                self.logger.warning(f"Negative time elapsed ({time_elapsed}s), resetting refill time")
                self.last_refill_time = now
                return
            
            # Calculate tokens to add based on time elapsed
            tokens_to_add = time_elapsed * self.traceroutes_per_second
            
            # Add tokens, but don't exceed capacity
            self.tokens = min(self.capacity, self.tokens + tokens_to_add)
            
            # Update last refill time
            self.last_refill_time = now
            
        except Exception as e:
            # Catch-all for unexpected errors
            self.logger.error(f"Error refilling tokens: {e}", exc_info=True)
            # Reset to a safe state
            try:
                self.last_refill_time = time.monotonic()
            except Exception:
                pass
