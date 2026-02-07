"""Custom exception classes for Villages Event Scraper.

This module defines the exception hierarchy for better error handling
throughout the application.
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



class VillagesEventError(Exception):
    """Base exception for Villages Event Scraper."""
    pass


class TokenFetchError(VillagesEventError):
    """Raised when token fetching or extraction fails."""
    pass


class SessionError(VillagesEventError):
    """Raised when session establishment fails."""
    pass


class APIError(VillagesEventError):
    """Raised when API request fails."""
    pass


class ProcessingError(VillagesEventError):
    """Raised when event processing fails."""
    pass
