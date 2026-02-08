"""
Network Health Monitor for Traceroute Mapper

Monitors network health and adjusts traceroute behavior accordingly.
Tracks success/failure rates, implements quiet hours, detects congestion,
and triggers emergency stop when needed.

Requirements: 12.1, 12.2, 12.3, 12.4, 12.5
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time, timedelta
from typing import Optional, List
from collections import deque


@dataclass
class NetworkHealthMetrics:
    """Network health metrics"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    timeout_count: int = 0
    success_rate: float = 0.0
    avg_response_time: float = 0.0
    is_congested: bool = False
    is_emergency_stop: bool = False


class NetworkHealthMonitor:
    """
    Monitor network health and protect network from excessive traceroute traffic.
    
    Responsibilities:
    - Track success/failure rates
    - Detect network congestion
    - Implement quiet hours
    - Trigger emergency stop when needed
    - Dynamically adjust rate limits
    """
    
    def __init__(
        self,
        success_rate_threshold: float = 0.5,
        failure_threshold: float = 0.2,
        consecutive_failures_threshold: int = 10,
        auto_recovery_minutes: int = 30,
        quiet_hours_enabled: bool = False,
        quiet_hours_start: Optional[str] = None,
        quiet_hours_end: Optional[str] = None,
        congestion_enabled: bool = True,
        throttle_multiplier: float = 0.5,
        window_size: int = 20
    ):
        """
        Initialize network health monitor.
        
        Args:
            success_rate_threshold: Threshold for congestion detection (default: 0.5)
            failure_threshold: Threshold for emergency stop (default: 0.2)
            consecutive_failures_threshold: Number of consecutive failures to trigger emergency stop (default: 10)
            auto_recovery_minutes: Minutes to wait before auto-recovery (default: 30)
            quiet_hours_enabled: Whether quiet hours are enabled (default: False)
            quiet_hours_start: Start time for quiet hours (HH:MM format)
            quiet_hours_end: End time for quiet hours (HH:MM format)
            congestion_enabled: Whether congestion detection is enabled (default: True)
            throttle_multiplier: Rate reduction multiplier when congested (default: 0.5)
            window_size: Number of recent requests to track for metrics (default: 20)
        """
        self.logger = logging.getLogger(__name__)
        
        # Configuration
        self.success_rate_threshold = success_rate_threshold
        self.failure_threshold = failure_threshold
        self.consecutive_failures_threshold = consecutive_failures_threshold
        self.auto_recovery_minutes = auto_recovery_minutes
        self.quiet_hours_enabled = quiet_hours_enabled
        self.congestion_enabled = congestion_enabled
        self.throttle_multiplier = throttle_multiplier
        self.window_size = window_size
        
        # Parse quiet hours
        self.quiet_hours_start = self._parse_time(quiet_hours_start) if quiet_hours_start else None
        self.quiet_hours_end = self._parse_time(quiet_hours_end) if quiet_hours_end else None
        
        # Metrics tracking
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.timeout_count = 0
        self.consecutive_failures = 0
        
        # Recent results for windowed metrics (True = success, False = failure)
        self.recent_results: deque = deque(maxlen=window_size)
        
        # Response time tracking
        self.response_times: List[float] = []
        self.max_response_times = 100  # Keep last 100 response times
        
        # Emergency stop state
        self.is_emergency_stop = False
        self.emergency_stop_time: Optional[datetime] = None
        self.emergency_stop_reason: Optional[str] = None
        
        # Congestion state
        self.is_congested = False
        
        self.logger.info(
            f"NetworkHealthMonitor initialized: "
            f"success_threshold={success_rate_threshold:.2%}, "
            f"failure_threshold={failure_threshold:.2%}, "
            f"consecutive_failures={consecutive_failures_threshold}, "
            f"quiet_hours={'enabled' if quiet_hours_enabled else 'disabled'}"
        )
    
    def _parse_time(self, time_str: str) -> Optional[dt_time]:
        """
        Parse time string in HH:MM format.
        
        Args:
            time_str: Time string in HH:MM format
            
        Returns:
            datetime.time object or None if parsing fails
        """
        try:
            hour, minute = map(int, time_str.split(':'))
            return dt_time(hour=hour, minute=minute)
        except (ValueError, AttributeError) as e:
            self.logger.error(f"Failed to parse time '{time_str}': {e}")
            return None
    
    def record_success(self, response_time: Optional[float] = None) -> None:
        """
        Record a successful traceroute.
        
        Args:
            response_time: Response time in seconds (optional)
        """
        self.total_requests += 1
        self.successful_requests += 1
        self.consecutive_failures = 0  # Reset consecutive failures
        self.recent_results.append(True)
        
        # Track response time
        if response_time is not None:
            self.response_times.append(response_time)
            if len(self.response_times) > self.max_response_times:
                self.response_times.pop(0)
        
        # Update congestion state
        self._update_congestion_state()
        
        # Check for auto-recovery from emergency stop
        if self.is_emergency_stop:
            self._check_auto_recovery()
        
        self.logger.debug(
            f"Recorded success: total={self.total_requests}, "
            f"success_rate={self.get_success_rate():.2%}, "
            f"consecutive_failures={self.consecutive_failures}"
        )
    
    def record_failure(self, is_timeout: bool = False) -> None:
        """
        Record a failed traceroute.
        
        Args:
            is_timeout: Whether the failure was due to timeout
        """
        self.total_requests += 1
        self.failed_requests += 1
        self.consecutive_failures += 1
        self.recent_results.append(False)
        
        if is_timeout:
            self.timeout_count += 1
        
        # Update congestion state
        self._update_congestion_state()
        
        # Check for emergency stop trigger
        self._check_emergency_stop()
        
        self.logger.debug(
            f"Recorded failure: total={self.total_requests}, "
            f"success_rate={self.get_success_rate():.2%}, "
            f"consecutive_failures={self.consecutive_failures}"
        )
    
    def get_success_rate(self) -> float:
        """
        Get overall success rate.
        
        Returns:
            Success rate as a float between 0.0 and 1.0
        """
        if self.total_requests == 0:
            return 1.0  # No failures yet, assume healthy
        return self.successful_requests / self.total_requests
    
    def get_recent_success_rate(self) -> float:
        """
        Get success rate for recent requests (within window).
        
        Returns:
            Recent success rate as a float between 0.0 and 1.0
        """
        if len(self.recent_results) == 0:
            return 1.0  # No data yet, assume healthy
        
        successes = sum(1 for result in self.recent_results if result)
        return successes / len(self.recent_results)
    
    def get_avg_response_time(self) -> float:
        """
        Get average response time.
        
        Returns:
            Average response time in seconds
        """
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)
    
    def is_healthy(self) -> bool:
        """
        Check if network is healthy enough for traceroutes.
        
        Returns:
            True if healthy, False otherwise
        """
        # Emergency stop overrides everything
        if self.is_emergency_stop:
            return False
        
        # Check quiet hours
        if self.is_quiet_hours():
            return False
        
        # Check success rate
        success_rate = self.get_success_rate()
        if success_rate < self.failure_threshold:
            return False
        
        return True
    
    def is_quiet_hours(self) -> bool:
        """
        Check if current time is within quiet hours.
        
        Returns:
            True if in quiet hours, False otherwise
        """
        if not self.quiet_hours_enabled:
            return False
        
        if self.quiet_hours_start is None or self.quiet_hours_end is None:
            return False
        
        now = datetime.now().time()
        
        # Handle quiet hours that span midnight
        if self.quiet_hours_start <= self.quiet_hours_end:
            # Normal case: start < end (e.g., 22:00 to 23:00)
            return self.quiet_hours_start <= now <= self.quiet_hours_end
        else:
            # Spans midnight: start > end (e.g., 22:00 to 06:00)
            return now >= self.quiet_hours_start or now <= self.quiet_hours_end
    
    def should_throttle(self) -> bool:
        """
        Check if traceroute rate should be throttled due to congestion.
        
        Returns:
            True if should throttle, False otherwise
        """
        return self.is_congested
    
    def get_recommended_rate(self, base_rate: float) -> float:
        """
        Get recommended traceroute rate based on network health.
        
        Args:
            base_rate: Base traceroute rate (traceroutes per minute)
            
        Returns:
            Recommended rate (traceroutes per minute)
        """
        if self.is_emergency_stop:
            return 0.0
        
        if self.is_congested:
            return base_rate * self.throttle_multiplier
        
        return base_rate
    
    def _update_congestion_state(self) -> None:
        """Update congestion detection state based on recent metrics."""
        if not self.congestion_enabled:
            self.is_congested = False
            return
        
        # Check recent success rate
        recent_success_rate = self.get_recent_success_rate()
        
        # Detect congestion
        was_congested = self.is_congested
        self.is_congested = recent_success_rate < self.success_rate_threshold
        
        # Log state changes
        if self.is_congested and not was_congested:
            self.logger.warning(
                f"Network congestion detected: recent_success_rate={recent_success_rate:.2%} "
                f"< threshold={self.success_rate_threshold:.2%}"
            )
        elif not self.is_congested and was_congested:
            self.logger.info(
                f"Network congestion cleared: recent_success_rate={recent_success_rate:.2%}"
            )
    
    def _check_emergency_stop(self) -> None:
        """Check if emergency stop should be triggered."""
        # Already in emergency stop
        if self.is_emergency_stop:
            return
        
        # Check consecutive failures
        if self.consecutive_failures >= self.consecutive_failures_threshold:
            self.enter_emergency_stop(
                f"Consecutive failures threshold exceeded: {self.consecutive_failures}"
            )
            return
        
        # Check overall success rate
        success_rate = self.get_success_rate()
        if self.total_requests >= 20 and success_rate < self.failure_threshold:
            self.enter_emergency_stop(
                f"Success rate below threshold: {success_rate:.2%} < {self.failure_threshold:.2%}"
            )
            return
    
    def _check_auto_recovery(self) -> None:
        """Check if conditions are met for auto-recovery from emergency stop."""
        if not self.is_emergency_stop:
            return
        
        # Check if enough time has passed
        if self.emergency_stop_time is None:
            return
        
        time_since_stop = datetime.now() - self.emergency_stop_time
        if time_since_stop < timedelta(minutes=self.auto_recovery_minutes):
            return
        
        # Check if success rate has improved
        recent_success_rate = self.get_recent_success_rate()
        
        # Require success rate to be above failure threshold * 1.5 for recovery
        recovery_threshold = self.failure_threshold * 1.5
        
        if recent_success_rate > recovery_threshold:
            self.logger.info(
                f"Auto-recovery conditions met: recent_success_rate={recent_success_rate:.2%} "
                f"> recovery_threshold={recovery_threshold:.2%}, "
                f"time_since_stop={time_since_stop.total_seconds():.0f}s"
            )
            self.exit_emergency_stop()
    
    def enter_emergency_stop(self, reason: str) -> None:
        """
        Enter emergency stop mode.
        
        Args:
            reason: Reason for emergency stop
        """
        if self.is_emergency_stop:
            return
        
        self.is_emergency_stop = True
        self.emergency_stop_time = datetime.now()
        self.emergency_stop_reason = reason
        
        self.logger.error(
            f"EMERGENCY STOP TRIGGERED: {reason}. "
            f"All traceroute operations paused. "
            f"Auto-recovery in {self.auto_recovery_minutes} minutes if conditions improve."
        )
    
    def exit_emergency_stop(self) -> None:
        """Exit emergency stop mode."""
        if not self.is_emergency_stop:
            return
        
        self.is_emergency_stop = False
        self.emergency_stop_time = None
        self.emergency_stop_reason = None
        
        self.logger.info("Emergency stop cleared. Resuming normal operations.")
    
    def get_metrics(self) -> NetworkHealthMetrics:
        """
        Get current network health metrics.
        
        Returns:
            NetworkHealthMetrics object
        """
        return NetworkHealthMetrics(
            total_requests=self.total_requests,
            successful_requests=self.successful_requests,
            failed_requests=self.failed_requests,
            timeout_count=self.timeout_count,
            success_rate=self.get_success_rate(),
            avg_response_time=self.get_avg_response_time(),
            is_congested=self.is_congested,
            is_emergency_stop=self.is_emergency_stop
        )
    
    def get_status(self) -> dict:
        """
        Get detailed status information.
        
        Returns:
            Dictionary with status information
        """
        metrics = self.get_metrics()
        
        return {
            'healthy': self.is_healthy(),
            'is_emergency_stop': self.is_emergency_stop,
            'emergency_stop_reason': self.emergency_stop_reason,
            'emergency_stop_time': self.emergency_stop_time.isoformat() if self.emergency_stop_time else None,
            'is_congested': self.is_congested,
            'is_quiet_hours': self.is_quiet_hours(),
            'total_requests': metrics.total_requests,
            'successful_requests': metrics.successful_requests,
            'failed_requests': metrics.failed_requests,
            'timeout_count': metrics.timeout_count,
            'success_rate': metrics.success_rate,
            'recent_success_rate': self.get_recent_success_rate(),
            'consecutive_failures': self.consecutive_failures,
            'avg_response_time': metrics.avg_response_time,
            'quiet_hours_enabled': self.quiet_hours_enabled,
            'quiet_hours_start': self.quiet_hours_start.strftime('%H:%M') if self.quiet_hours_start else None,
            'quiet_hours_end': self.quiet_hours_end.strftime('%H:%M') if self.quiet_hours_end else None,
            'congestion_enabled': self.congestion_enabled,
            'success_rate_threshold': self.success_rate_threshold,
            'failure_threshold': self.failure_threshold,
            'consecutive_failures_threshold': self.consecutive_failures_threshold
        }
    
    def reset(self) -> None:
        """Reset all metrics and state."""
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
        self.timeout_count = 0
        self.consecutive_failures = 0
        self.recent_results.clear()
        self.response_times.clear()
        self.is_emergency_stop = False
        self.emergency_stop_time = None
        self.emergency_stop_reason = None
        self.is_congested = False
        
        self.logger.info("NetworkHealthMonitor reset")
