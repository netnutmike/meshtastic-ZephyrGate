"""Session manager module for Villages Event Scraper.

This module handles HTTP session management and cookie handling
for API requests to The Villages.
"""

"""
Copyright (C) 2025

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""


import requests
from typing import Optional

from .exceptions import SessionError
from .config import Config


class SessionManager:
    """Manages HTTP session and cookies for API requests."""
    
    def __init__(self):
        """Initialize session with requests.Session()."""
        self._session: Optional[requests.Session] = requests.Session()
        self._session.headers.update({
            'User-Agent': Config.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
    
    def establish_session(self, calendar_url: str, timeout: int = Config.DEFAULT_TIMEOUT) -> None:
        """Visit calendar page to establish session and capture cookies.
        
        Args:
            calendar_url: URL to the calendar page
            timeout: Request timeout in seconds
            
        Raises:
            SessionError: If session establishment fails
        """
        if self._session is None:
            raise SessionError("Session has been closed")
        
        try:
            # Visit the calendar page to establish session and capture cookies
            response = self._session.get(calendar_url, timeout=timeout)
            response.raise_for_status()
            
            # Update headers with Origin and Referer for subsequent API requests
            self._session.headers.update({
                'Origin': 'https://www.thevillages.com',
                'Referer': calendar_url,
            })
            
        except requests.exceptions.Timeout as e:
            raise SessionError(f"Timeout while establishing session: {e}")
        except requests.exceptions.RequestException as e:
            raise SessionError(f"Failed to establish session: {e}")
    
    def get_session(self) -> requests.Session:
        """Returns the active session object.
        
        Returns:
            Active requests.Session instance
            
        Raises:
            SessionError: If session has been closed
        """
        if self._session is None:
            raise SessionError("Session has been closed")
        return self._session
    
    def close(self) -> None:
        """Closes the session and cleans up resources."""
        if self._session is not None:
            self._session.close()
            self._session = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup."""
        self.close()
        return False
