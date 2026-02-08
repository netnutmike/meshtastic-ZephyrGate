"""
Property-Based Tests for Network Health Protection

Tests Property 28: Congestion Throttling
Tests Property 29: Emergency Stop Trigger
Tests Property 30: Automatic Recovery

Validates: Requirements 12.2, 12.3, 12.5

**Validates: Requirements 12.2, 12.3, 12.5**
"""

import pytest
from datetime import datetime, timedelta
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
def success_failure_sequence(draw, min_size=10, max_size=50):
    """Generate a sequence of success/failure results"""
    return draw(st.lists(
        st.booleans(),  # True = success, False = failure
        min_size=min_size,
        max_size=max_size
    ))


@composite
def health_monitor_config(draw):
    """Generate valid health monitor configuration"""
    return {
        'success_rate_threshold': draw(st.floats(min_value=0.3, max_value=0.9)),
        'failure_threshold': draw(st.floats(min_value=0.1, max_value=0.4)),
        'consecutive_failures_threshold': draw(st.integers(min_value=3, max_value=20)),
        'throttle_multiplier': draw(st.floats(min_value=0.1, max_value=0.9)),
        'window_size': draw(st.integers(min_value=10, max_value=50))
    }


@composite
def response_time_sequence(draw, min_size=5, max_size=30):
    """Generate a sequence of response times"""
    return draw(st.lists(
        st.floats(min_value=0.1, max_value=10.0),
        min_size=min_size,
        max_size=max_size
    ))


# Property Tests

class TestCongestionThrottlingProperty:
    """
    Feature: network-traceroute-mapper, Property 28: Congestion Throttling
    
    Tests that when network congestion is detected (success_rate < success_rate_threshold),
    the traceroute rate is reduced by the configured throttle_multiplier.
    
    **Validates: Requirements 12.2**
    """
    
    @settings(max_examples=20, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        config=health_monitor_config(),
        results=success_failure_sequence(min_size=20, max_size=50)
    )
    def test_congestion_detected_when_success_rate_below_threshold(self, config, results):
        """
        Property: For any sequence of results where the recent success rate
        falls below success_rate_threshold, congestion should be detected
        and should_throttle() should return True.
        
        **Validates: Requirements 12.2**
        """
        # Create monitor with test configuration
        monitor = NetworkHealthMonitor(
            success_rate_threshold=config['success_rate_threshold'],
            failure_threshold=config['failure_threshold'],
            consecutive_failures_threshold=config['consecutive_failures_threshold'],
            throttle_multiplier=config['throttle_multiplier'],
            window_size=config['window_size'],
            congestion_enabled=True
        )
        
        # Record the results
        for result in results:
            if result:
                monitor.record_success()
            else:
                monitor.record_failure()
        
        # Calculate expected recent success rate
        window_results = results[-config['window_size']:]
        expected_success_rate = sum(1 for r in window_results if r) / len(window_results)
        
        # Check congestion detection
        actual_success_rate = monitor.get_recent_success_rate()
        is_congested = monitor.is_congested
        should_throttle = monitor.should_throttle()
        
        # Verify the success rate calculation
        assert abs(actual_success_rate - expected_success_rate) < 0.01, (
            f"Success rate mismatch: expected {expected_success_rate:.2%}, "
            f"got {actual_success_rate:.2%}"
        )
        
        # Verify congestion detection
        if expected_success_rate < config['success_rate_threshold']:
            assert is_congested is True, (
                f"Congestion should be detected when success rate "
                f"({expected_success_rate:.2%}) < threshold "
                f"({config['success_rate_threshold']:.2%})"
            )
            assert should_throttle is True, (
                f"should_throttle() should return True when congested"
            )
        else:
            assert is_congested is False, (
                f"Congestion should not be detected when success rate "
                f"({expected_success_rate:.2%}) >= threshold "
                f"({config['success_rate_threshold']:.2%})"
            )
            assert should_throttle is False, (
                f"should_throttle() should return False when not congested"
            )
    
    @settings(max_examples=20, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        config=health_monitor_config(),
        base_rate=st.floats(min_value=1.0, max_value=120.0),
        results=success_failure_sequence(min_size=20, max_size=50)
    )
    def test_recommended_rate_reduced_when_congested(self, config, base_rate, results):
        """
        Property: For any base rate and congested state, the recommended rate
        should be base_rate * throttle_multiplier when congested (unless in
        emergency stop, which overrides to 0.0).
        
        **Validates: Requirements 12.2**
        """
        # Create monitor with test configuration
        monitor = NetworkHealthMonitor(
            success_rate_threshold=config['success_rate_threshold'],
            failure_threshold=config['failure_threshold'],
            consecutive_failures_threshold=config['consecutive_failures_threshold'],
            throttle_multiplier=config['throttle_multiplier'],
            window_size=config['window_size'],
            congestion_enabled=True
        )
        
        # Record the results
        for result in results:
            if result:
                monitor.record_success()
            else:
                monitor.record_failure()
        
        # Get recommended rate
        recommended_rate = monitor.get_recommended_rate(base_rate)
        
        # Calculate expected rate
        # Emergency stop overrides everything
        if monitor.is_emergency_stop:
            expected_rate = 0.0
        elif monitor.is_congested:
            expected_rate = base_rate * config['throttle_multiplier']
        else:
            expected_rate = base_rate
        
        # Verify recommended rate
        assert abs(recommended_rate - expected_rate) < 0.01, (
            f"Recommended rate mismatch: expected {expected_rate:.2f}, "
            f"got {recommended_rate:.2f}, "
            f"congested={monitor.is_congested}, "
            f"emergency_stop={monitor.is_emergency_stop}, "
            f"throttle_multiplier={config['throttle_multiplier']}"
        )
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        success_rate_threshold=st.floats(min_value=0.3, max_value=0.9),
        window_size=st.integers(min_value=10, max_value=30)
    )
    def test_congestion_clears_when_success_rate_improves(self, success_rate_threshold, window_size):
        """
        Property: For any monitor in congested state, when the success rate
        improves above the threshold, congestion should clear.
        
        **Validates: Requirements 12.2**
        """
        # Create monitor
        monitor = NetworkHealthMonitor(
            success_rate_threshold=success_rate_threshold,
            window_size=window_size,
            congestion_enabled=True
        )
        
        # Cause congestion by recording mostly failures
        num_failures = int(window_size * 0.8)  # 80% failures
        num_successes = window_size - num_failures
        
        for _ in range(num_successes):
            monitor.record_success()
        for _ in range(num_failures):
            monitor.record_failure()
        
        # Should be congested now
        assert monitor.is_congested is True, "Should be congested after mostly failures"
        
        # Now record enough successes to push failures out of window
        for _ in range(window_size):
            monitor.record_success()
        
        # Congestion should be cleared
        assert monitor.is_congested is False, (
            f"Congestion should clear after success rate improves. "
            f"Recent success rate: {monitor.get_recent_success_rate():.2%}, "
            f"Threshold: {success_rate_threshold:.2%}"
        )
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        results=success_failure_sequence(min_size=20, max_size=50)
    )
    def test_congestion_disabled_never_throttles(self, results):
        """
        Property: For any sequence of results, when congestion detection is
        disabled, should_throttle() should always return False.
        
        **Validates: Requirements 12.2**
        """
        # Create monitor with congestion disabled
        monitor = NetworkHealthMonitor(
            success_rate_threshold=0.5,
            congestion_enabled=False
        )
        
        # Record the results (even if they would cause congestion)
        for result in results:
            if result:
                monitor.record_success()
            else:
                monitor.record_failure()
        
        # Should never throttle when disabled
        assert monitor.is_congested is False, (
            "is_congested should be False when congestion detection is disabled"
        )
        assert monitor.should_throttle() is False, (
            "should_throttle() should return False when congestion detection is disabled"
        )


class TestEmergencyStopTriggerProperty:
    """
    Feature: network-traceroute-mapper, Property 29: Emergency Stop Trigger
    
    Tests that emergency stop is triggered when success rate falls below
    failure_threshold OR consecutive_failures threshold is exceeded.
    
    **Validates: Requirements 12.3**
    """
    
    @settings(max_examples=20, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        consecutive_failures_threshold=st.integers(min_value=3, max_value=20),
        extra_failures=st.integers(min_value=0, max_value=10)
    )
    def test_emergency_stop_triggered_by_consecutive_failures(
        self, consecutive_failures_threshold, extra_failures
    ):
        """
        Property: For any consecutive_failures_threshold, when that many
        consecutive failures occur, emergency stop should be triggered.
        
        **Validates: Requirements 12.3**
        """
        # Create monitor with high failure threshold to avoid that trigger
        monitor = NetworkHealthMonitor(
            failure_threshold=0.01,  # Very low to avoid success rate trigger
            consecutive_failures_threshold=consecutive_failures_threshold,
            window_size=50
        )
        
        # Record consecutive failures up to threshold
        num_failures = consecutive_failures_threshold + extra_failures
        for _ in range(num_failures):
            monitor.record_failure()
        
        # Emergency stop should be triggered
        assert monitor.is_emergency_stop is True, (
            f"Emergency stop should be triggered after "
            f"{num_failures} consecutive failures "
            f"(threshold: {consecutive_failures_threshold})"
        )
        assert monitor.emergency_stop_reason is not None
        assert "Consecutive failures" in monitor.emergency_stop_reason
    
    @settings(max_examples=20, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        failure_threshold=st.floats(min_value=0.1, max_value=0.4),
        window_size=st.integers(min_value=20, max_value=50)
    )
    def test_emergency_stop_triggered_by_low_success_rate(self, failure_threshold, window_size):
        """
        Property: For any failure_threshold, when the overall success rate
        falls below that threshold (with sufficient data), emergency stop
        should be triggered.
        
        **Validates: Requirements 12.3**
        """
        # Create monitor with high consecutive failure threshold to avoid that trigger
        monitor = NetworkHealthMonitor(
            failure_threshold=failure_threshold,
            consecutive_failures_threshold=1000,  # Very high to avoid this trigger
            window_size=window_size
        )
        
        # Calculate number of successes/failures to get below threshold
        # Need at least 20 requests for success rate check
        total_requests = max(25, window_size)
        target_success_rate = failure_threshold * 0.8  # 80% of threshold
        num_successes = int(total_requests * target_success_rate)
        num_failures = total_requests - num_successes
        
        # Record results with occasional successes to avoid consecutive failures
        for i in range(total_requests):
            if i < num_successes:
                monitor.record_success()
            else:
                monitor.record_failure()
                # Add occasional success to break consecutive failures
                if (i - num_successes) % 5 == 4 and i < total_requests - 1:
                    monitor.record_success()
                    num_successes += 1
                    num_failures -= 1
        
        # Check if emergency stop was triggered
        actual_success_rate = monitor.get_success_rate()
        
        if actual_success_rate < failure_threshold and monitor.total_requests >= 20:
            assert monitor.is_emergency_stop is True, (
                f"Emergency stop should be triggered when success rate "
                f"({actual_success_rate:.2%}) < threshold ({failure_threshold:.2%}) "
                f"with {monitor.total_requests} requests"
            )
            assert monitor.emergency_stop_reason is not None
            assert "Success rate below threshold" in monitor.emergency_stop_reason
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        consecutive_failures_threshold=st.integers(min_value=5, max_value=15)
    )
    def test_emergency_stop_not_triggered_below_threshold(self, consecutive_failures_threshold):
        """
        Property: For any consecutive_failures_threshold, when fewer than
        that many consecutive failures occur, emergency stop should NOT
        be triggered (assuming success rate is acceptable).
        
        **Validates: Requirements 12.3**
        """
        # Create monitor
        monitor = NetworkHealthMonitor(
            failure_threshold=0.2,
            consecutive_failures_threshold=consecutive_failures_threshold,
            window_size=50
        )
        
        # Record failures just below threshold, with successes interspersed
        num_failures = consecutive_failures_threshold - 1
        
        # Record some successes first to keep success rate high
        for _ in range(20):
            monitor.record_success()
        
        # Record failures below threshold
        for _ in range(num_failures):
            monitor.record_failure()
        
        # Emergency stop should NOT be triggered
        assert monitor.is_emergency_stop is False, (
            f"Emergency stop should NOT be triggered with "
            f"{num_failures} consecutive failures "
            f"(threshold: {consecutive_failures_threshold})"
        )
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        base_rate=st.floats(min_value=1.0, max_value=120.0)
    )
    def test_emergency_stop_sets_recommended_rate_to_zero(self, base_rate):
        """
        Property: For any base rate, when in emergency stop mode,
        get_recommended_rate() should return 0.0.
        
        **Validates: Requirements 12.3**
        """
        # Create monitor
        monitor = NetworkHealthMonitor(
            consecutive_failures_threshold=5
        )
        
        # Trigger emergency stop
        for _ in range(10):
            monitor.record_failure()
        
        assert monitor.is_emergency_stop is True
        
        # Recommended rate should be zero
        recommended_rate = monitor.get_recommended_rate(base_rate)
        assert recommended_rate == 0.0, (
            f"Recommended rate should be 0.0 in emergency stop, "
            f"got {recommended_rate}"
        )
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        consecutive_failures_threshold=st.integers(min_value=5, max_value=15)
    )
    def test_emergency_stop_makes_monitor_unhealthy(self, consecutive_failures_threshold):
        """
        Property: For any monitor in emergency stop mode, is_healthy()
        should return False.
        
        **Validates: Requirements 12.3**
        """
        # Create monitor
        monitor = NetworkHealthMonitor(
            consecutive_failures_threshold=consecutive_failures_threshold
        )
        
        # Record some successes first (good health)
        for _ in range(20):
            monitor.record_success()
        
        assert monitor.is_healthy() is True, "Should be healthy initially"
        
        # Trigger emergency stop
        for _ in range(consecutive_failures_threshold + 1):
            monitor.record_failure()
        
        assert monitor.is_emergency_stop is True
        
        # Should be unhealthy now
        assert monitor.is_healthy() is False, (
            "is_healthy() should return False in emergency stop mode"
        )


class TestAutomaticRecoveryProperty:
    """
    Feature: network-traceroute-mapper, Property 30: Automatic Recovery
    
    Tests that when in emergency stop state, the system automatically
    resumes normal operations when network conditions improve.
    
    **Validates: Requirements 12.5**
    """
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        failure_threshold=st.floats(min_value=0.1, max_value=0.4),
        window_size=st.integers(min_value=10, max_value=30)
    )
    def test_auto_recovery_when_success_rate_improves(self, failure_threshold, window_size):
        """
        Property: For any monitor in emergency stop, when the recent success
        rate improves above failure_threshold * 1.5 and sufficient time has
        passed, emergency stop should be cleared.
        
        **Validates: Requirements 12.5**
        """
        # Create monitor with short auto-recovery time for testing
        monitor = NetworkHealthMonitor(
            failure_threshold=failure_threshold,
            consecutive_failures_threshold=5,
            auto_recovery_minutes=0,  # Immediate recovery for testing
            window_size=window_size
        )
        
        # Trigger emergency stop with consecutive failures
        for _ in range(10):
            monitor.record_failure()
        
        assert monitor.is_emergency_stop is True, "Should be in emergency stop"
        
        # Record enough successes to improve success rate
        # Need to fill the window with successes
        for _ in range(window_size):
            monitor.record_success()
        
        # Calculate recovery threshold
        recovery_threshold = failure_threshold * 1.5
        recent_success_rate = monitor.get_recent_success_rate()
        
        # Check if auto-recovery should have happened
        if recent_success_rate > recovery_threshold:
            # Auto-recovery should have cleared emergency stop
            assert monitor.is_emergency_stop is False, (
                f"Emergency stop should be cleared when recent success rate "
                f"({recent_success_rate:.2%}) > recovery threshold "
                f"({recovery_threshold:.2%})"
            )
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        failure_threshold=st.floats(min_value=0.2, max_value=0.4),
        window_size=st.integers(min_value=10, max_value=30)
    )
    def test_auto_recovery_requires_sufficient_improvement(self, failure_threshold, window_size):
        """
        Property: For any monitor in emergency stop, auto-recovery should
        NOT occur if success rate is only slightly above failure_threshold.
        It must be above failure_threshold * 1.5.
        
        **Validates: Requirements 12.5**
        """
        # Create monitor with short auto-recovery time
        monitor = NetworkHealthMonitor(
            failure_threshold=failure_threshold,
            consecutive_failures_threshold=5,
            auto_recovery_minutes=0,  # Immediate recovery for testing
            window_size=window_size
        )
        
        # Trigger emergency stop
        for _ in range(10):
            monitor.record_failure()
        
        assert monitor.is_emergency_stop is True
        
        # Improve success rate to just above failure_threshold but below recovery threshold
        # Target: failure_threshold * 1.2 (between threshold and recovery threshold)
        target_success_rate = failure_threshold * 1.2
        recovery_threshold = failure_threshold * 1.5
        
        # Ensure target is between failure and recovery thresholds
        assume(target_success_rate < recovery_threshold)
        
        # Calculate number of successes needed
        num_successes = int(window_size * target_success_rate)
        num_failures = window_size - num_successes
        
        # Record results to achieve target success rate
        for _ in range(num_successes):
            monitor.record_success()
        for _ in range(num_failures):
            monitor.record_failure()
        
        recent_success_rate = monitor.get_recent_success_rate()
        
        # Should still be in emergency stop (not enough improvement)
        if recent_success_rate <= recovery_threshold:
            assert monitor.is_emergency_stop is True, (
                f"Emergency stop should remain when recent success rate "
                f"({recent_success_rate:.2%}) <= recovery threshold "
                f"({recovery_threshold:.2%})"
            )
    
    @settings(max_examples=10, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        auto_recovery_minutes=st.integers(min_value=1, max_value=5)
    )
    def test_auto_recovery_requires_time_to_pass(self, auto_recovery_minutes):
        """
        Property: For any auto_recovery_minutes setting, auto-recovery should
        NOT occur until that much time has passed since emergency stop was
        triggered, even if success rate improves.
        
        **Validates: Requirements 12.5**
        """
        # Create monitor with specified auto-recovery time
        monitor = NetworkHealthMonitor(
            failure_threshold=0.2,
            consecutive_failures_threshold=5,
            auto_recovery_minutes=auto_recovery_minutes,
            window_size=20
        )
        
        # Trigger emergency stop
        for _ in range(10):
            monitor.record_failure()
        
        assert monitor.is_emergency_stop is True
        emergency_stop_time = monitor.emergency_stop_time
        assert emergency_stop_time is not None
        
        # Improve success rate immediately (fill window with successes)
        for _ in range(20):
            monitor.record_success()
        
        # Mock current time to be just before auto-recovery time
        time_before_recovery = emergency_stop_time + timedelta(
            minutes=auto_recovery_minutes - 0.1
        )
        
        with patch('plugins.traceroute_mapper.network_health_monitor.datetime') as mock_datetime:
            mock_datetime.now.return_value = time_before_recovery
            
            # Manually trigger recovery check
            monitor._check_auto_recovery()
            
            # Should still be in emergency stop (not enough time passed)
            assert monitor.is_emergency_stop is True, (
                f"Emergency stop should remain until {auto_recovery_minutes} minutes pass"
            )
        
        # Mock current time to be after auto-recovery time
        time_after_recovery = emergency_stop_time + timedelta(
            minutes=auto_recovery_minutes + 0.1
        )
        
        with patch('plugins.traceroute_mapper.network_health_monitor.datetime') as mock_datetime:
            mock_datetime.now.return_value = time_after_recovery
            
            # Manually trigger recovery check
            monitor._check_auto_recovery()
            
            # Should have recovered now (time passed and success rate good)
            recovery_threshold = monitor.failure_threshold * 1.5
            recent_success_rate = monitor.get_recent_success_rate()
            
            if recent_success_rate > recovery_threshold:
                assert monitor.is_emergency_stop is False, (
                    f"Emergency stop should clear after {auto_recovery_minutes} minutes "
                    f"with good success rate ({recent_success_rate:.2%})"
                )
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        consecutive_failures_threshold=st.integers(min_value=5, max_value=15)
    )
    def test_success_after_emergency_stop_triggers_recovery_check(
        self, consecutive_failures_threshold
    ):
        """
        Property: For any monitor in emergency stop, recording a success
        should trigger an auto-recovery check.
        
        **Validates: Requirements 12.5**
        """
        # Create monitor with immediate auto-recovery
        monitor = NetworkHealthMonitor(
            failure_threshold=0.2,
            consecutive_failures_threshold=consecutive_failures_threshold,
            auto_recovery_minutes=0,
            window_size=20
        )
        
        # Trigger emergency stop
        for _ in range(consecutive_failures_threshold + 1):
            monitor.record_failure()
        
        assert monitor.is_emergency_stop is True
        
        # Record enough successes to improve success rate above recovery threshold
        for _ in range(20):
            monitor.record_success()
        
        # Auto-recovery should have been checked and cleared emergency stop
        recovery_threshold = monitor.failure_threshold * 1.5
        recent_success_rate = monitor.get_recent_success_rate()
        
        if recent_success_rate > recovery_threshold:
            assert monitor.is_emergency_stop is False, (
                f"Emergency stop should be cleared after recording successes "
                f"that improve success rate to {recent_success_rate:.2%}"
            )
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        window_size=st.integers(min_value=10, max_value=30)
    )
    def test_manual_exit_emergency_stop_clears_state(self, window_size):
        """
        Property: For any monitor in emergency stop, manually calling
        exit_emergency_stop() should clear the emergency stop state.
        
        **Validates: Requirements 12.5**
        """
        # Create monitor
        monitor = NetworkHealthMonitor(
            consecutive_failures_threshold=5,
            window_size=window_size
        )
        
        # Trigger emergency stop
        for _ in range(10):
            monitor.record_failure()
        
        assert monitor.is_emergency_stop is True
        assert monitor.emergency_stop_time is not None
        assert monitor.emergency_stop_reason is not None
        
        # Manually exit emergency stop
        monitor.exit_emergency_stop()
        
        # State should be cleared
        assert monitor.is_emergency_stop is False, (
            "is_emergency_stop should be False after exit_emergency_stop()"
        )
        assert monitor.emergency_stop_time is None, (
            "emergency_stop_time should be None after exit_emergency_stop()"
        )
        assert monitor.emergency_stop_reason is None, (
            "emergency_stop_reason should be None after exit_emergency_stop()"
        )


class TestNetworkHealthIntegrationProperties:
    """
    Integration tests for network health properties working together
    """
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        config=health_monitor_config(),
        results=success_failure_sequence(min_size=30, max_size=60)
    )
    def test_congestion_and_emergency_stop_independent(self, config, results):
        """
        Property: Congestion detection and emergency stop should be
        independent - congestion can occur without emergency stop and
        vice versa.
        
        **Validates: Requirements 12.2, 12.3**
        """
        # Create monitor
        monitor = NetworkHealthMonitor(
            success_rate_threshold=config['success_rate_threshold'],
            failure_threshold=config['failure_threshold'],
            consecutive_failures_threshold=config['consecutive_failures_threshold'],
            throttle_multiplier=config['throttle_multiplier'],
            window_size=config['window_size'],
            congestion_enabled=True
        )
        
        # Record results
        for result in results:
            if result:
                monitor.record_success()
            else:
                monitor.record_failure()
        
        # Get states
        is_congested = monitor.is_congested
        is_emergency_stop = monitor.is_emergency_stop
        recent_success_rate = monitor.get_recent_success_rate()
        overall_success_rate = monitor.get_success_rate()
        consecutive_failures = monitor.consecutive_failures
        
        # Verify congestion logic
        if recent_success_rate < config['success_rate_threshold']:
            assert is_congested is True, "Should be congested with low recent success rate"
        else:
            assert is_congested is False, "Should not be congested with good recent success rate"
        
        # Verify emergency stop logic
        if (consecutive_failures >= config['consecutive_failures_threshold'] or
            (monitor.total_requests >= 20 and overall_success_rate < config['failure_threshold'])):
            assert is_emergency_stop is True, "Should be in emergency stop"
        
        # Emergency stop should make monitor unhealthy regardless of congestion
        if is_emergency_stop:
            assert monitor.is_healthy() is False, (
                "Monitor should be unhealthy in emergency stop"
            )
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        success_rate_threshold=st.floats(min_value=0.5, max_value=0.9),
        failure_threshold=st.floats(min_value=0.1, max_value=0.3),
        window_size=st.integers(min_value=15, max_value=30)
    )
    def test_thresholds_properly_ordered(self, success_rate_threshold, failure_threshold, window_size):
        """
        Property: For any configuration, failure_threshold should be lower
        than success_rate_threshold (emergency stop is more severe than
        congestion).
        
        **Validates: Requirements 12.2, 12.3**
        """
        # Ensure proper ordering
        assume(failure_threshold < success_rate_threshold)
        
        # Create monitor
        monitor = NetworkHealthMonitor(
            success_rate_threshold=success_rate_threshold,
            failure_threshold=failure_threshold,
            consecutive_failures_threshold=100,  # High to avoid this trigger
            window_size=window_size,
            congestion_enabled=True
        )
        
        # Create a success rate between the two thresholds
        target_rate = (failure_threshold + success_rate_threshold) / 2
        num_successes = int(window_size * target_rate)
        num_failures = window_size - num_successes
        
        # Record enough requests for emergency stop check (need 20+)
        total_requests = max(25, window_size)
        for i in range(total_requests):
            if i < num_successes:
                monitor.record_success()
            else:
                monitor.record_failure()
        
        actual_rate = monitor.get_success_rate()
        
        # Should be congested (below success_rate_threshold)
        if actual_rate < success_rate_threshold:
            assert monitor.is_congested is True, (
                f"Should be congested when rate ({actual_rate:.2%}) < "
                f"success_rate_threshold ({success_rate_threshold:.2%})"
            )
        
        # Should NOT be in emergency stop (above failure_threshold)
        if actual_rate > failure_threshold:
            assert monitor.is_emergency_stop is False, (
                f"Should NOT be in emergency stop when rate ({actual_rate:.2%}) > "
                f"failure_threshold ({failure_threshold:.2%})"
            )


class TestEdgeCases:
    """Edge case tests for network health properties"""
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        window_size=st.integers(min_value=5, max_value=20)
    )
    def test_all_successes_never_triggers_emergency_stop(self, window_size):
        """
        Property: For any sequence of only successes, emergency stop
        should never be triggered.
        
        **Validates: Requirements 12.3**
        """
        monitor = NetworkHealthMonitor(
            failure_threshold=0.2,
            consecutive_failures_threshold=5,
            window_size=window_size
        )
        
        # Record many successes
        for _ in range(100):
            monitor.record_success()
        
        assert monitor.is_emergency_stop is False, (
            "Emergency stop should never trigger with only successes"
        )
        assert monitor.is_congested is False, (
            "Congestion should never be detected with only successes"
        )
        assert monitor.is_healthy() is True, (
            "Monitor should be healthy with only successes"
        )
    
    @settings(max_examples=10, deadline=5000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        window_size=st.integers(min_value=5, max_value=20)
    )
    def test_all_failures_triggers_both_congestion_and_emergency_stop(self, window_size):
        """
        Property: For any sequence of only failures, both congestion
        and emergency stop should be triggered.
        
        **Validates: Requirements 12.2, 12.3**
        """
        monitor = NetworkHealthMonitor(
            success_rate_threshold=0.5,
            failure_threshold=0.2,
            consecutive_failures_threshold=5,
            window_size=window_size,
            congestion_enabled=True
        )
        
        # Record many failures
        for _ in range(25):  # Need 20+ for emergency stop check
            monitor.record_failure()
        
        assert monitor.is_congested is True, (
            "Congestion should be detected with only failures"
        )
        assert monitor.is_emergency_stop is True, (
            "Emergency stop should be triggered with only failures"
        )
        assert monitor.is_healthy() is False, (
            "Monitor should be unhealthy with only failures"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
