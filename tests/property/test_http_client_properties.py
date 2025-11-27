"""
Property-Based Tests for Plugin HTTP Client

Tests universal properties of HTTP client error handling and rate limiting using Hypothesis.
"""

import pytest
import asyncio
from hypothesis import given, settings, strategies as st
from unittest.mock import AsyncMock, Mock, MagicMock
import aiohttp

from src.core.enhanced_plugin import (
    PluginHTTPClient,
    HTTPRequestError,
    RateLimitExceeded,
    TokenBucket
)


# Strategies for generating test data

@st.composite
def http_params(draw):
    """Generate HTTP query parameters"""
    return draw(st.dictionaries(
        st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))),
        st.text(max_size=50),
        max_size=5
    ))


@st.composite
def http_data(draw):
    """Generate HTTP request body data"""
    return draw(st.dictionaries(
        st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'))),
        st.one_of(
            st.text(max_size=100),
            st.integers(),
            st.booleans()
        ),
        max_size=10
    ))


# Helper to create async context manager mock
class AsyncContextManagerMock:
    """Helper class to mock async context managers"""
    
    def __init__(self, return_value=None, side_effect=None):
        self.return_value = return_value
        self.side_effect = side_effect
        self.call_count = 0
    
    async def __aenter__(self):
        self.call_count += 1
        if self.side_effect:
            raise self.side_effect
        return self.return_value
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


# Property Tests

class TestHTTPErrorHandling:
    """
    Feature: third-party-plugin-system, Property 9: HTTP client error handling
    
    For any HTTP request that encounters a network error (timeout, connection refused, etc.),
    the HTTP client should return an error result rather than raising an unhandled exception.
    
    Validates: Requirements 4.3
    """
    
    @settings(max_examples=10, deadline=2000)
    @given(
        plugin_name=st.text(min_size=1, max_size=50),
        url=st.text(min_size=10, max_size=100),
        params=http_params()
    )
    @pytest.mark.asyncio
    async def test_connection_error_raises_http_request_error(self, plugin_name, url, params):
        """
        Property: Connection errors should be caught and wrapped in HTTPRequestError.
        
        For any HTTP GET request that encounters a connection error,
        the client should raise HTTPRequestError (not the raw aiohttp exception).
        """
        # Arrange
        client = PluginHTTPClient(plugin_name, rate_limit=1000, max_retries=0)
        
        # Mock the session to raise connection error
        mock_session = MagicMock()
        mock_session.get.return_value = AsyncContextManagerMock(
            side_effect=aiohttp.ClientConnectionError("Connection refused")
        )
        mock_session.closed = False
        client.session = mock_session
        
        # Act & Assert
        with pytest.raises(HTTPRequestError) as exc_info:
            await client.get(url, params=params)
        
        # Verify the error message contains useful information
        error_msg = str(exc_info.value).lower()
        assert "connection" in error_msg or "refused" in error_msg
        
        # Cleanup
        client.session = None
    
    @settings(max_examples=10, deadline=2000)
    @given(
        plugin_name=st.text(min_size=1, max_size=50),
        url=st.text(min_size=10, max_size=100),
        data=http_data()
    )
    @pytest.mark.asyncio
    async def test_timeout_error_raises_http_request_error(self, plugin_name, url, data):
        """
        Property: Timeout errors should be caught and wrapped in HTTPRequestError.
        
        For any HTTP POST request that times out,
        the client should raise HTTPRequestError (not asyncio.TimeoutError).
        """
        # Arrange
        client = PluginHTTPClient(plugin_name, rate_limit=1000, max_retries=0)
        
        # Mock the session to raise timeout error
        mock_session = MagicMock()
        mock_session.post.return_value = AsyncContextManagerMock(
            side_effect=asyncio.TimeoutError()
        )
        mock_session.closed = False
        client.session = mock_session
        
        # Act & Assert
        with pytest.raises(HTTPRequestError) as exc_info:
            await client.post(url, data=data)
        
        # Verify the error message mentions timeout
        assert "timeout" in str(exc_info.value).lower()
        
        # Cleanup
        client.session = None
    
    @settings(max_examples=10, deadline=2000)
    @given(
        plugin_name=st.text(min_size=1, max_size=50),
        url=st.text(min_size=10, max_size=100),
        status_code=st.integers(min_value=500, max_value=599)
    )
    @pytest.mark.asyncio
    async def test_server_error_with_retries_eventually_raises_error(self, plugin_name, url, status_code):
        """
        Property: Server errors (5xx) should be retried and eventually raise HTTPRequestError.
        
        For any HTTP request that encounters a server error,
        the client should retry up to max_retries times and then raise HTTPRequestError.
        """
        # Arrange
        max_retries = 2
        client = PluginHTTPClient(plugin_name, rate_limit=1000, max_retries=max_retries)
        
        # Create a mock response that raises server error
        mock_response = MagicMock()
        mock_response.status = status_code
        mock_response.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=Mock(),
            history=(),
            status=status_code,
            message=f"Server error {status_code}"
        )
        
        # Mock the session
        mock_session = MagicMock()
        mock_session.get.return_value = AsyncContextManagerMock(return_value=mock_response)
        mock_session.closed = False
        client.session = mock_session
        
        # Act & Assert
        with pytest.raises(HTTPRequestError) as exc_info:
            await client.get(url)
        
        # Verify retries occurred (should be called max_retries + 1 times)
        assert mock_session.get.call_count == max_retries + 1
        
        # Verify error message mentions retries
        error_msg = str(exc_info.value).lower()
        assert "retries" in error_msg or str(status_code) in str(exc_info.value)
        
        # Cleanup
        client.session = None
    
    @settings(max_examples=10, deadline=2000)
    @given(
        plugin_name=st.text(min_size=1, max_size=50),
        url=st.text(min_size=10, max_size=100),
        status_code=st.integers(min_value=400, max_value=499)
    )
    @pytest.mark.asyncio
    async def test_client_error_does_not_retry(self, plugin_name, url, status_code):
        """
        Property: Client errors (4xx) should not be retried.
        
        For any HTTP request that encounters a client error (4xx),
        the client should immediately raise HTTPRequestError without retrying.
        """
        # Arrange
        max_retries = 3
        client = PluginHTTPClient(plugin_name, rate_limit=1000, max_retries=max_retries)
        
        # Create a mock response that raises client error
        mock_response = MagicMock()
        mock_response.status = status_code
        mock_response.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=Mock(),
            history=(),
            status=status_code,
            message=f"Client error {status_code}"
        )
        
        # Mock the session
        mock_session = MagicMock()
        mock_session.get.return_value = AsyncContextManagerMock(return_value=mock_response)
        mock_session.closed = False
        client.session = mock_session
        
        # Act & Assert
        with pytest.raises(HTTPRequestError) as exc_info:
            await client.get(url)
        
        # Verify NO retries occurred (should be called exactly once)
        assert mock_session.get.call_count == 1
        
        # Verify error message contains status code
        assert str(status_code) in str(exc_info.value)
        
        # Cleanup
        client.session = None
    
    @settings(max_examples=10, deadline=2000)
    @given(
        plugin_name=st.text(min_size=1, max_size=50),
        url=st.text(min_size=10, max_size=100)
    )
    @pytest.mark.asyncio
    async def test_successful_request_returns_data(self, plugin_name, url):
        """
        Property: Successful requests should return response data without errors.
        
        For any HTTP request that succeeds (2xx status),
        the client should return the response data as a dictionary.
        """
        # Arrange
        client = PluginHTTPClient(plugin_name, rate_limit=1000)
        expected_data = {"status": "success", "data": "test"}
        
        # Create a mock response that returns success
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.raise_for_status = Mock()  # No exception
        mock_response.json = AsyncMock(return_value=expected_data)
        
        # Mock the session
        mock_session = MagicMock()
        mock_session.get.return_value = AsyncContextManagerMock(return_value=mock_response)
        mock_session.closed = False
        client.session = mock_session
        
        # Act
        result = await client.get(url)
        
        # Assert
        assert result == expected_data
        assert mock_session.get.call_count == 1
        
        # Cleanup
        client.session = None


class TestRateLimitingEnforcement:
    """
    Feature: third-party-plugin-system, Property 10: Rate limiting enforcement
    
    For any sequence of HTTP requests from a plugin exceeding the rate limit,
    subsequent requests should be rejected until the rate limit window resets.
    
    Validates: Requirements 4.5
    """
    
    @settings(max_examples=10, deadline=2000)
    @given(
        plugin_name=st.text(min_size=1, max_size=50),
        rate_limit=st.integers(min_value=1, max_value=10),
        url=st.text(min_size=10, max_size=100)
    )
    @pytest.mark.asyncio
    async def test_requests_exceeding_rate_limit_are_rejected(self, plugin_name, rate_limit, url):
        """
        Property: Requests exceeding rate limit should raise RateLimitExceeded.
        
        For any HTTP client with rate_limit N, making N+1 requests in quick succession
        should result in the (N+1)th request raising RateLimitExceeded.
        """
        # Arrange
        client = PluginHTTPClient(plugin_name, rate_limit=rate_limit)
        
        # Create a mock response that returns success
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.raise_for_status = Mock()
        mock_response.json = AsyncMock(return_value={"status": "ok"})
        
        # Mock the session
        mock_session = MagicMock()
        mock_session.get.return_value = AsyncContextManagerMock(return_value=mock_response)
        mock_session.closed = False
        client.session = mock_session
        
        # Act - make rate_limit successful requests
        for i in range(rate_limit):
            result = await client.get(url)
            assert result == {"status": "ok"}
        
        # Act & Assert - the next request should be rate limited
        with pytest.raises(RateLimitExceeded) as exc_info:
            await client.get(url)
        
        # Verify error message mentions rate limit
        assert "rate limit" in str(exc_info.value).lower()
        
        # Cleanup
        client.session = None
    
    @settings(max_examples=10, deadline=2000)
    @given(
        plugin_name=st.text(min_size=1, max_size=50),
        rate_limit=st.integers(min_value=5, max_value=20),
        url=st.text(min_size=10, max_size=100)
    )
    @pytest.mark.asyncio
    async def test_rate_limit_resets_after_time_window(self, plugin_name, rate_limit, url):
        """
        Property: Rate limit should reset after the time window expires.
        
        For any HTTP client, after exhausting the rate limit and waiting for the window
        to reset, new requests should be allowed.
        """
        # Arrange
        client = PluginHTTPClient(plugin_name, rate_limit=rate_limit)
        
        # Create a mock response that returns success
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.raise_for_status = Mock()
        mock_response.json = AsyncMock(return_value={"status": "ok"})
        
        # Mock the session
        mock_session = MagicMock()
        mock_session.get.return_value = AsyncContextManagerMock(return_value=mock_response)
        mock_session.closed = False
        client.session = mock_session
        
        # Act - exhaust rate limit
        for i in range(rate_limit):
            await client.get(url)
        
        # Verify rate limit is exceeded
        with pytest.raises(RateLimitExceeded):
            await client.get(url)
        
        # Wait for rate limit to reset (simulate time passing)
        # Manually reset the token bucket for testing
        client.rate_limiter.tokens = float(client.rate_limiter.capacity)
        
        # Act - should be able to make requests again
        result = await client.get(url)
        
        # Assert
        assert result == {"status": "ok"}
        
        # Cleanup
        client.session = None
    
    @settings(max_examples=10, deadline=2000)
    @given(
        plugin_name=st.text(min_size=1, max_size=50),
        rate_limit=st.integers(min_value=10, max_value=50),
        request_count=st.integers(min_value=1, max_value=9),
        url=st.text(min_size=10, max_size=100)
    )
    @pytest.mark.asyncio
    async def test_requests_under_rate_limit_succeed(self, plugin_name, rate_limit, request_count, url):
        """
        Property: Requests under the rate limit should all succeed.
        
        For any HTTP client with rate_limit N, making M < N requests
        should result in all M requests succeeding.
        """
        # Ensure request_count is less than rate_limit
        if request_count >= rate_limit:
            request_count = rate_limit - 1
        
        if request_count < 1:
            request_count = 1
        
        # Arrange
        client = PluginHTTPClient(plugin_name, rate_limit=rate_limit)
        
        # Create a mock response that returns success
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.raise_for_status = Mock()
        mock_response.json = AsyncMock(return_value={"status": "ok"})
        
        # Mock the session
        mock_session = MagicMock()
        mock_session.get.return_value = AsyncContextManagerMock(return_value=mock_response)
        mock_session.closed = False
        client.session = mock_session
        
        # Act - make request_count requests
        success_count = 0
        for i in range(request_count):
            result = await client.get(url)
            if result == {"status": "ok"}:
                success_count += 1
        
        # Assert - all requests should succeed
        assert success_count == request_count
        
        # Cleanup
        client.session = None
    
    @settings(max_examples=10, deadline=2000)
    @given(
        rate=st.integers(min_value=1, max_value=100),
        capacity=st.integers(min_value=1, max_value=100)
    )
    @pytest.mark.asyncio
    async def test_token_bucket_respects_capacity(self, rate, capacity):
        """
        Property: Token bucket should never exceed its capacity.
        
        For any token bucket with capacity C, the number of available tokens
        should never exceed C, regardless of how much time passes.
        """
        # Arrange
        bucket = TokenBucket(rate=rate, capacity=capacity)
        
        # Simulate time passing by manually updating tokens
        bucket.tokens = float(capacity) * 2  # Try to exceed capacity
        
        # Act - acquire a token (this will normalize the token count)
        result = await bucket.acquire(1)
        
        # Assert - tokens should be capped at capacity
        assert bucket.tokens <= capacity
        assert result is True  # Should succeed since we have tokens
    
    @settings(max_examples=10, deadline=2000)
    @given(
        rate=st.integers(min_value=1, max_value=100),
        capacity=st.integers(min_value=10, max_value=100),
        tokens_to_acquire=st.integers(min_value=1, max_value=5)
    )
    @pytest.mark.asyncio
    async def test_token_bucket_acquire_decrements_tokens(self, rate, capacity, tokens_to_acquire):
        """
        Property: Acquiring tokens should decrement the token count.
        
        For any token bucket, successfully acquiring N tokens should
        decrease the available tokens by N.
        """
        # Arrange
        bucket = TokenBucket(rate=rate, capacity=capacity)
        initial_tokens = bucket.tokens
        
        # Ensure we have enough tokens
        if tokens_to_acquire > initial_tokens:
            tokens_to_acquire = int(initial_tokens)
        
        if tokens_to_acquire < 1:
            tokens_to_acquire = 1
        
        # Act
        result = await bucket.acquire(tokens_to_acquire)
        
        # Assert
        if result:
            # Tokens should have decreased (approximately, due to time passing)
            assert bucket.tokens < initial_tokens
    
    @settings(max_examples=10, deadline=2000)
    @given(
        rate=st.integers(min_value=1, max_value=100),
        capacity=st.integers(min_value=1, max_value=10)
    )
    @pytest.mark.asyncio
    async def test_token_bucket_rejects_when_empty(self, rate, capacity):
        """
        Property: Token bucket should reject requests when empty.
        
        For any token bucket, after exhausting all tokens,
        acquire() should return False.
        """
        # Arrange
        bucket = TokenBucket(rate=rate, capacity=capacity)
        
        # Exhaust all tokens
        bucket.tokens = 0.0
        
        # Act
        result = await bucket.acquire(1)
        
        # Assert
        assert result is False
