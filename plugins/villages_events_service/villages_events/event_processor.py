"""Event processor module for extracting and processing event data."""

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


import logging
from typing import List, Tuple, Dict, Any, Optional

from .config import Config
from .exceptions import ProcessingError


logger = logging.getLogger(__name__)


class EventProcessor:
    """Processes event data and applies venue abbreviations."""

    def __init__(self, venue_mappings: Dict[str, str], output_fields: Optional[List[str]] = None):
        """
        Initialize with venue abbreviation mappings and output fields.

        Args:
            venue_mappings: Dictionary mapping keywords to abbreviations
            output_fields: List of field paths to extract (e.g., ["title", "location.title", "start.date"])
                          Defaults to DEFAULT_OUTPUT_FIELDS for backward compatibility
        """
        self.venue_mappings = venue_mappings
        self.output_fields = output_fields if output_fields is not None else Config.DEFAULT_OUTPUT_FIELDS

    def abbreviate_venue(self, venue: str) -> str:
        """
        Abbreviates venue name based on keyword matching.

        Args:
            venue: Full venue name

        Returns:
            Abbreviated venue name or original if no match
        """
        if not venue:
            return venue

        # Check if venue contains any keyword from mappings
        for keyword, abbreviation in self.venue_mappings.items():
            if keyword in venue:
                return abbreviation

        # Return original venue if no match found
        return venue

    def extract_field(self, event: Dict[str, Any], field_path: str) -> Any:
        """
        Extracts a field value from an event using dot notation.

        Args:
            event: Event dictionary from API response
            field_path: Dot-separated path to field (e.g., "location.title", "start.date")

        Returns:
            Field value or empty string if not found
        """
        # Split the field path by dots to handle nested fields
        parts = field_path.split('.')
        current = event

        # Navigate through nested dictionaries
        for part in parts:
            if not isinstance(current, dict):
                return ""
            
            if part not in current:
                return ""
            
            current = current[part]

        # Return the value, or empty string if None
        return current if current is not None else ""

    def process_events(self, api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extracts and processes events from API response.

        Args:
            api_response: Parsed JSON response from API

        Returns:
            List of dictionaries with extracted fields

        Raises:
            ProcessingError: If events array is missing from response
        """
        # Extract events array from response
        if "events" not in api_response:
            raise ProcessingError("Missing 'events' key in API response")

        events = api_response["events"]
        if not isinstance(events, list):
            raise ProcessingError("'events' field is not a list")

        processed_events = []

        for idx, event in enumerate(events):
            try:
                # Extract all specified fields for this event
                event_data = {}
                
                for field_path in self.output_fields:
                    # Extract the field value using dot notation
                    value = self.extract_field(event, field_path)
                    
                    # Apply venue abbreviation only to "location.title" field
                    if field_path == "location.title" and value:
                        value = self.abbreviate_venue(value)
                    
                    # Store the extracted value
                    event_data[field_path] = value

                # Add to processed events list
                processed_events.append(event_data)

            except Exception as e:
                logger.warning(f"Error processing event at index {idx}: {e}, skipping")
                continue

        return processed_events
