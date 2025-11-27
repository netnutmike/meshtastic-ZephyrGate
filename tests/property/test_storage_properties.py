"""
Property-Based Tests for Plugin Storage System

Tests universal properties of plugin storage isolation using Hypothesis.

Feature: third-party-plugin-system, Property 20: Database isolation
"""

import pytest
import asyncio
import tempfile
from pathlib import Path
from contextlib import contextmanager
from hypothesis import given, settings, strategies as st, HealthCheck
from unittest.mock import Mock

from src.core.enhanced_plugin import PluginStorage
from src.core.plugin_manager import PluginManager
from src.core.database import DatabaseManager, initialize_database


# Strategies for generating test data

@st.composite
def valid_plugin_name(draw):
    """Generate valid plugin names"""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='_-'),
        min_size=1,
        max_size=50
    ).filter(lambda x: x.strip() and not x.startswith('-') and not x.startswith('_')))


@st.composite
def valid_storage_key(draw):
    """Generate valid storage keys"""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='_-:.'),
        min_size=1,
        max_size=100
    ).filter(lambda x: x.strip()))


@st.composite
def json_serializable_value(draw):
    """Generate JSON-serializable values"""
    return draw(st.one_of(
        st.none(),
        st.booleans(),
        st.integers(min_value=-1000000, max_value=1000000),
        st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
        st.text(max_size=1000),
        st.lists(st.integers(min_value=-1000, max_value=1000), max_size=100),
        st.dictionaries(
            st.text(min_size=1, max_size=50),
            st.one_of(st.integers(), st.text(max_size=100), st.booleans()),
            max_size=20
        )
    ))


@contextmanager
def temp_database():
    """Context manager for temporary database"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    # Initialize database
    db = initialize_database(db_path)
    
    try:
        yield db
    finally:
        # Cleanup
        db.close()
        Path(db_path).unlink(missing_ok=True)


class TestPluginStorageIsolation:
    """
    Property-Based Tests for Plugin Storage Isolation
    
    Feature: third-party-plugin-system, Property 20: Database isolation
    Validates: Requirements 10.1
    """
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        plugin1_name=valid_plugin_name(),
        plugin2_name=valid_plugin_name(),
        key=valid_storage_key(),
        value1=json_serializable_value(),
        value2=json_serializable_value()
    )
    @pytest.mark.asyncio
    async def test_plugin_data_isolation(self,
                                         plugin1_name, plugin2_name, key,
                                         value1, value2):
        """
        Property 20: Database isolation
        
        For any two different plugins storing data with the same key,
        each plugin should only be able to access its own data, not the other plugin's data.
        
        This ensures that plugins cannot interfere with each other's storage.
        """
        # Skip if plugin names are the same (not testing isolation in that case)
        if plugin1_name == plugin2_name:
            return
        
        with temp_database() as db:
            mock_plugin_manager = Mock(spec=PluginManager)
            
            # Create storage instances for two different plugins
            storage1 = PluginStorage(plugin1_name, mock_plugin_manager)
            storage2 = PluginStorage(plugin2_name, mock_plugin_manager)
            
            # Both plugins store data with the same key
            await storage1.store_data(key, value1)
            await storage2.store_data(key, value2)
            
            # Each plugin should retrieve only its own data
            retrieved1 = await storage1.retrieve_data(key)
            retrieved2 = await storage2.retrieve_data(key)
            
            # Verify isolation: each plugin gets its own value
            assert retrieved1 == value1, f"Plugin 1 should retrieve its own value"
            assert retrieved2 == value2, f"Plugin 2 should retrieve its own value"
            
            # Verify that the values are different (unless they happen to be equal)
            # The key point is that they're stored separately
            if value1 != value2:
                assert retrieved1 != retrieved2, "Different plugins should have isolated data"
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        plugin1_name=valid_plugin_name(),
        plugin2_name=valid_plugin_name(),
        key=valid_storage_key(),
        value=json_serializable_value()
    )
    @pytest.mark.asyncio
    async def test_plugin_delete_isolation(self,
                                           plugin1_name, plugin2_name, key, value):
        """
        Property 20: Database isolation (delete operations)
        
        For any two different plugins, when one plugin deletes its data,
        it should not affect the other plugin's data with the same key.
        """
        # Skip if plugin names are the same
        if plugin1_name == plugin2_name:
            return
        
        with temp_database() as db:
            mock_plugin_manager = Mock(spec=PluginManager)
            
            # Create storage instances for two different plugins
            storage1 = PluginStorage(plugin1_name, mock_plugin_manager)
            storage2 = PluginStorage(plugin2_name, mock_plugin_manager)
            
            # Both plugins store data with the same key
            await storage1.store_data(key, value)
            await storage2.store_data(key, value)
            
            # Plugin 1 deletes its data
            deleted = await storage1.delete_data(key)
            assert deleted is True, "Delete should succeed"
            
            # Plugin 1's data should be gone
            retrieved1 = await storage1.retrieve_data(key)
            assert retrieved1 is None, "Plugin 1's data should be deleted"
            
            # Plugin 2's data should still exist
            retrieved2 = await storage2.retrieve_data(key)
            assert retrieved2 == value, "Plugin 2's data should remain intact"
    
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    @given(
        plugin1_name=valid_plugin_name(),
        plugin2_name=valid_plugin_name(),
        prefix=st.text(min_size=1, max_size=20).filter(lambda x: x.strip()),
        keys1=st.lists(valid_storage_key(), min_size=1, max_size=10, unique=True),
        keys2=st.lists(valid_storage_key(), min_size=1, max_size=10, unique=True)
    )
    @pytest.mark.asyncio
    async def test_plugin_list_keys_isolation(self,
                                              plugin1_name, plugin2_name,
                                              prefix, keys1, keys2):
        """
        Property 20: Database isolation (list operations)
        
        For any two different plugins, when listing keys,
        each plugin should only see its own keys, not the other plugin's keys.
        """
        # Skip if plugin names are the same
        if plugin1_name == plugin2_name:
            return
        
        with temp_database() as db:
            mock_plugin_manager = Mock(spec=PluginManager)
            
            # Create storage instances for two different plugins
            storage1 = PluginStorage(plugin1_name, mock_plugin_manager)
            storage2 = PluginStorage(plugin2_name, mock_plugin_manager)
            
            # Add prefix to keys to test prefix filtering
            prefixed_keys1 = [f"{prefix}:{key}" for key in keys1]
            prefixed_keys2 = [f"{prefix}:{key}" for key in keys2]
            
            # Store data for both plugins
            for key in prefixed_keys1:
                await storage1.store_data(key, "value1")
            
            for key in prefixed_keys2:
                await storage2.store_data(key, "value2")
            
            # List keys with prefix for each plugin
            listed_keys1 = await storage1.list_keys(prefix)
            listed_keys2 = await storage2.list_keys(prefix)
            
            # Each plugin should only see its own keys
            assert len(listed_keys1) == len(prefixed_keys1), \
                f"Plugin 1 should see {len(prefixed_keys1)} keys, saw {len(listed_keys1)}"
            assert len(listed_keys2) == len(prefixed_keys2), \
                f"Plugin 2 should see {len(prefixed_keys2)} keys, saw {len(listed_keys2)}"
            
            # Verify that the keys match what was stored
            assert set(listed_keys1) == set(prefixed_keys1), \
                "Plugin 1 should see exactly its own keys"
            assert set(listed_keys2) == set(prefixed_keys2), \
                "Plugin 2 should see exactly its own keys"
            
            # The key isolation property: each plugin sees exactly what it stored,
            # no more, no less. The fact that both assertions above pass proves isolation.
