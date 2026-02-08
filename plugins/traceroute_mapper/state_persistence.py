"""
State Persistence Module for Traceroute Mapper

Handles saving and loading node state to/from disk using JSON serialization.

Responsibilities:
- Persist node state to JSON file
- Load node state at startup
- Handle file corruption gracefully
- Periodic auto-save
- Store traceroute history

Validates: Requirements 13.1, 13.2, 13.3, 13.5
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from plugins.traceroute_mapper.node_state_tracker import NodeState


logger = logging.getLogger(__name__)


class StatePersistence:
    """
    Handles state persistence for the Traceroute Mapper.
    
    Saves and loads node states to/from JSON files with error handling
    for missing files and corrupted data.
    """
    
    def __init__(self, state_file_path: str, history_per_node: int = 10):
        """
        Initialize state persistence.
        
        Args:
            state_file_path: Path to the state file
            history_per_node: Maximum number of traceroute history entries per node
        """
        self.state_file_path = Path(state_file_path)
        self.history_per_node = history_per_node
        self.logger = logger
        
        # Ensure parent directory exists
        self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def save_state(self, node_states: Dict[str, NodeState]) -> bool:
        """
        Save node states to JSON file.
        
        Args:
            node_states: Dictionary mapping node_id to NodeState
            
        Returns:
            True if save was successful, False otherwise
            
        Validates: Requirements 13.1, 13.3
        """
        try:
            # Convert NodeState objects to dictionaries
            nodes_dict = {}
            for node_id, node_state in node_states.items():
                node_dict = asdict(node_state)
                
                # Convert datetime objects to ISO format strings
                if node_dict.get('last_seen'):
                    node_dict['last_seen'] = node_dict['last_seen'].isoformat()
                if node_dict.get('last_traced'):
                    node_dict['last_traced'] = node_dict['last_traced'].isoformat()
                if node_dict.get('next_recheck'):
                    node_dict['next_recheck'] = node_dict['next_recheck'].isoformat()
                
                nodes_dict[node_id] = node_dict
            
            # Create state structure with version and timestamp
            state_data = {
                'version': '1.0',
                'last_saved': datetime.now().isoformat(),
                'nodes': nodes_dict
            }
            
            # Write to temporary file first, then rename (atomic operation)
            temp_file = self.state_file_path.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(state_data, f, indent=2)
            
            # Rename temp file to actual file (atomic on most systems)
            temp_file.replace(self.state_file_path)
            
            self.logger.debug(
                f"Saved state for {len(node_states)} nodes to {self.state_file_path}"
            )
            return True
            
        except OSError as e:
            self.logger.error(
                f"File I/O error saving state to {self.state_file_path}: {e}"
            )
            return False
        except Exception as e:
            self.logger.error(
                f"Unexpected error saving state: {e}",
                exc_info=True
            )
            return False
    
    async def load_state(self) -> Dict[str, NodeState]:
        """
        Load node states from JSON file.
        
        Returns:
            Dictionary mapping node_id to NodeState, or empty dict if file
            doesn't exist or is corrupted
            
        Validates: Requirements 13.2, 13.5
        """
        # Handle missing file gracefully
        if not self.state_file_path.exists():
            self.logger.info(
                f"State file {self.state_file_path} does not exist, starting with empty state"
            )
            return {}
        
        try:
            # Read state file
            with open(self.state_file_path, 'r') as f:
                state_data = json.load(f)
            
            # Validate version
            version = state_data.get('version', '1.0')
            if version != '1.0':
                self.logger.warning(
                    f"State file version {version} does not match expected version 1.0"
                )
            
            # Parse nodes
            nodes_dict = state_data.get('nodes', {})
            node_states = {}
            
            for node_id, node_dict in nodes_dict.items():
                try:
                    # Convert ISO format strings back to datetime objects
                    if node_dict.get('last_seen'):
                        node_dict['last_seen'] = datetime.fromisoformat(node_dict['last_seen'])
                    if node_dict.get('last_traced'):
                        node_dict['last_traced'] = datetime.fromisoformat(node_dict['last_traced'])
                    if node_dict.get('next_recheck'):
                        node_dict['next_recheck'] = datetime.fromisoformat(node_dict['next_recheck'])
                    
                    # Create NodeState object
                    node_state = NodeState(**node_dict)
                    node_states[node_id] = node_state
                    
                except (ValueError, TypeError) as e:
                    self.logger.warning(
                        f"Error parsing node {node_id} from state file: {e}"
                    )
                    continue
            
            self.logger.info(
                f"Loaded state for {len(node_states)} nodes from {self.state_file_path}"
            )
            return node_states
            
        except json.JSONDecodeError as e:
            # Handle corrupted JSON file
            self.logger.error(
                f"Corrupted state file {self.state_file_path}: {e}"
            )
            
            # Backup corrupted file
            backup_path = self.state_file_path.with_suffix(
                f'.corrupted.{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            )
            try:
                shutil.copy(self.state_file_path, backup_path)
                self.logger.info(f"Backed up corrupted state to {backup_path}")
            except Exception as backup_error:
                self.logger.error(f"Failed to backup corrupted state: {backup_error}")
            
            return {}
            
        except OSError as e:
            # Handle file I/O errors
            self.logger.error(
                f"File I/O error loading state from {self.state_file_path}: {e}"
            )
            return {}
            
        except Exception as e:
            # Handle unexpected errors
            self.logger.error(
                f"Unexpected error loading state: {e}",
                exc_info=True
            )
            return {}
    
    async def save_traceroute_history(
        self,
        node_id: str,
        result: Dict[str, Any]
    ) -> bool:
        """
        Save a traceroute result to the history for a specific node.
        
        Args:
            node_id: The node ID
            result: Traceroute result dictionary with keys:
                - timestamp: datetime
                - success: bool
                - hop_count: int
                - route: List[str]
                - snr_values: List[float]
                - rssi_values: List[float]
                - duration_ms: float
                - error_message: Optional[str]
                
        Returns:
            True if save was successful, False otherwise
            
        Validates: Requirements 13.4
        """
        try:
            # Load existing history
            history = await self._load_history()
            
            # Get or create history list for this node
            if node_id not in history:
                history[node_id] = []
            
            # Convert datetime to ISO format
            result_copy = result.copy()
            if result_copy.get('timestamp'):
                result_copy['timestamp'] = result_copy['timestamp'].isoformat()
            
            # Add new result to history
            history[node_id].append(result_copy)
            
            # Enforce history limit (keep most recent entries)
            if len(history[node_id]) > self.history_per_node:
                history[node_id] = history[node_id][-self.history_per_node:]
            
            # Save updated history
            return await self._save_history(history)
            
        except Exception as e:
            self.logger.error(
                f"Error saving traceroute history for node {node_id}: {e}",
                exc_info=True
            )
            return False
    
    async def get_traceroute_history(
        self,
        node_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get traceroute history for a specific node.
        
        Args:
            node_id: The node ID
            limit: Maximum number of entries to return (most recent first)
            
        Returns:
            List of traceroute result dictionaries, or empty list if none found
        """
        try:
            history = await self._load_history()
            node_history = history.get(node_id, [])
            
            # Convert ISO format strings back to datetime objects
            for result in node_history:
                if result.get('timestamp'):
                    result['timestamp'] = datetime.fromisoformat(result['timestamp'])
            
            # Apply limit if specified
            if limit is not None and limit > 0:
                node_history = node_history[-limit:]
            
            return node_history
            
        except Exception as e:
            self.logger.error(
                f"Error loading traceroute history for node {node_id}: {e}",
                exc_info=True
            )
            return []
    
    async def _load_history(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load traceroute history from state file.
        
        Returns:
            Dictionary mapping node_id to list of traceroute results
        """
        if not self.state_file_path.exists():
            return {}
        
        try:
            with open(self.state_file_path, 'r') as f:
                state_data = json.load(f)
            
            return state_data.get('traceroute_history', {})
            
        except (json.JSONDecodeError, OSError) as e:
            self.logger.error(f"Error loading history: {e}")
            return {}
    
    async def _save_history(self, history: Dict[str, List[Dict[str, Any]]]) -> bool:
        """
        Save traceroute history to state file.
        
        Args:
            history: Dictionary mapping node_id to list of traceroute results
            
        Returns:
            True if save was successful, False otherwise
        """
        try:
            # Load existing state data or create new
            if self.state_file_path.exists():
                with open(self.state_file_path, 'r') as f:
                    state_data = json.load(f)
            else:
                state_data = {
                    'version': '1.0',
                    'last_saved': datetime.now().isoformat(),
                    'nodes': {}
                }
            
            # Update history section
            state_data['traceroute_history'] = history
            state_data['last_saved'] = datetime.now().isoformat()
            
            # Write to temporary file first, then rename
            temp_file = self.state_file_path.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(state_data, f, indent=2)
            
            temp_file.replace(self.state_file_path)
            
            return True
            
        except (json.JSONDecodeError, OSError) as e:
            self.logger.error(f"Error saving history: {e}")
            return False
