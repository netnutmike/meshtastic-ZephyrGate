"""
Rate limiter for MQTT Gateway

Implements token bucket algorithm for rate limiting MQTT message publishing.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any


class RateLimiter:
    """
    Token bucket rate limiter for MQTT message publishing.
    
    Features:
    - Token bucket algorithm for smooth rate limiting
    - Configurable rate limit (messages per second)
    - Burst support with configurable multiplier
    - Wait/acquire methods for rate limit enforcement
    - Statistics tracking
    """

    def __init__(
        self,
        max_messages_per_second: float = 10.0,
        burst_multiplier: float = 2.0,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize rate limiter.
        
        Args:
            max_messages_per_second: Maximum messages allowed per second
            burst_multiplier: Multiplier for burst capacity (capacity = rate * multiplier)
            logger: Logger instance for rate limiter operations
        """
        self.max_messages_per_second = max_messages_per_second
        self.burst_multiplier = burst_multiplier
        self.logger = logger or logging.getLogger(__name__)
        
        # Token bucket parameters
        self.capacity = max_messages_per_second * burst_multiplier
        self.tokens = self.capacity  # Start with full bucket
        self.last_refill_time = time.monotonic()
        
        # Statistics
        self._stats = {
            'messages_allowed': 0,
            'messages_delayed': 0,
            'total_wait_time': 0.0,
            'max_wait_time': 0.0,
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """
        Acquire a token to send a message.
        
        This method will wait if necessary until a token is available.
        
        Handles errors gracefully:
        - Time calculation errors
        - Lock acquisition errors
        - Sleep interruption
        
        Returns:
            True when a token is acquired (always returns True)
            
        Requirements: 7.1, 8.4
        """
        try:
            async with self._lock:
                # Refill tokens based on time elapsed
                try:
                    self._refill_tokens()
                except Exception as e:
                    self.logger.error(f"Error refilling tokens: {e}", exc_info=True)
                    # Continue anyway - better to allow the message than block forever
                
                # If we have tokens, consume one and return immediately
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    self._stats['messages_allowed'] += 1
                    return True
                
                # Calculate wait time needed
                try:
                    wait_time = self.get_wait_time()
                except Exception as e:
                    self.logger.error(f"Error calculating wait time: {e}", exc_info=True)
                    # Default to a small wait time
                    wait_time = 0.1
                
                if wait_time > 0:
                    self._stats['messages_delayed'] += 1
                    self._stats['total_wait_time'] += wait_time
                    self._stats['max_wait_time'] = max(
                        self._stats['max_wait_time'],
                        wait_time
                    )
                    
                    # Log rate limit event with details (Requirement 11.5)
                    self.logger.debug(
                        f"Rate limit reached - "
                        f"wait_time={wait_time:.3f}s, "
                        f"current_tokens={self.tokens:.2f}, "
                        f"capacity={self.capacity:.2f}, "
                        f"rate={self.max_messages_per_second} msg/s, "
                        f"messages_delayed={self._stats['messages_delayed']}"
                    )
                    
                    # Log warning if wait time is significant
                    if wait_time > 1.0:
                        self.logger.warning(
                            f"Significant rate limit delay - "
                            f"wait_time={wait_time:.3f}s, "
                            f"consider increasing max_messages_per_second"
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
                self._stats['messages_allowed'] += 1
                return True
                
        except asyncio.CancelledError:
            # Re-raise cancellation
            raise
        except Exception as e:
            # Catch-all for unexpected errors
            self.logger.error(f"Unexpected error in rate limiter acquire: {e}", exc_info=True)
            # Allow the message through rather than blocking forever
            self._stats['messages_allowed'] += 1
            return True

    async def wait_if_needed(self) -> None:
        """
        Wait if rate limit would be exceeded.
        
        This is a convenience method that calls acquire() and discards the result.
        """
        await self.acquire()

    def get_wait_time(self) -> float:
        """
        Get the time to wait before next message can be sent.
        
        Returns:
            Wait time in seconds (0 if no wait needed)
        """
        # Refill tokens first
        self._refill_tokens()
        
        # If we have tokens, no wait needed
        if self.tokens >= 1.0:
            return 0.0
        
        # Calculate how many tokens we need
        tokens_needed = 1.0 - self.tokens
        
        # Calculate time to generate those tokens
        wait_time = tokens_needed / self.max_messages_per_second
        
        return wait_time

    def reset(self) -> None:
        """
        Reset the rate limiter to initial state.
        
        This refills the token bucket to capacity and resets the refill time.
        """
        old_tokens = self.tokens
        self.tokens = self.capacity
        self.last_refill_time = time.monotonic()
        
        # Log rate limiter reset (Requirement 11.5)
        self.logger.info(
            f"Rate limiter reset - "
            f"old_tokens={old_tokens:.2f}, "
            f"new_tokens={self.tokens:.2f}, "
            f"capacity={self.capacity:.2f}, "
            f"rate={self.max_messages_per_second} msg/s"
        )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get rate limiter statistics.
        
        Returns:
            Dictionary containing rate limiter statistics
        """
        avg_wait_time = 0.0
        if self._stats['messages_delayed'] > 0:
            avg_wait_time = (
                self._stats['total_wait_time'] / self._stats['messages_delayed']
            )
        
        return {
            'max_messages_per_second': self.max_messages_per_second,
            'burst_capacity': self.capacity,
            'current_tokens': self.tokens,
            'messages_allowed': self._stats['messages_allowed'],
            'messages_delayed': self._stats['messages_delayed'],
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
        
        Requirements: 7.1, 8.4
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
            tokens_to_add = time_elapsed * self.max_messages_per_second
            
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
