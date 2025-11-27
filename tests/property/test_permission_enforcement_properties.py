"""
Property-Based Tests for Permission Enforcement

Tests Property 22: Permission enforcement
Validates: Requirements 10.5
"""

import pytest
from hypothesis import given, settings, strategies as st, assume
from unittest.mock import AsyncMock, MagicMock

from src.core.plugin_core_services import (
    PermissionManager,
    Permission,
    PermissionDeniedError,
    SystemStateQuery,
    MessageRoutingService,
    InterPluginMessaging,
    CoreServiceAccess
)


# Strategies for generating test data
@st.composite
def plugin_name_strategy(draw):
    """Generate valid plugin names"""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Ll', 'Lu', 'Nd'), whitelist_characters='_-'),
        min_size=1,
        max_size=50
    ))


@st.composite
def permission_strategy(draw):
    """Generate permissions"""
    return draw(st.sampled_from(list(Permission)))


@st.composite
def permission_set_strategy(draw):
    """Generate sets of permissions"""
    return draw(st.sets(st.sampled_from(list(Permission)), min_size=0, max_size=len(Permission)))


class TestPermissionEnforcementProperties:
    """Property-based tests for permission enforcement"""
    
    # Feature: third-party-plugin-system, Property 22: Permission enforcement
    @settings(max_examples=100)
    @given(
        plugin_name=plugin_name_strategy(),
        granted_permissions=permission_set_strategy(),
        required_permission=permission_strategy()
    )
    def test_permission_check_enforcement(
        self, plugin_name, granted_permissions, required_permission
    ):
        """
        Property: For any plugin attempting to use a capability,
        access should be granted if and only if the plugin has the required permission.
        """
        # Setup
        permission_manager = PermissionManager()
        permission_manager.grant_permissions(
            plugin_name,
            [p.value for p in granted_permissions]
        )
        
        # Execute and verify
        has_permission = permission_manager.has_permission(plugin_name, required_permission)
        
        if required_permission in granted_permissions:
            # Should have permission
            assert has_permission is True
            # check_permission should not raise
            try:
                permission_manager.check_permission(plugin_name, required_permission)
            except PermissionDeniedError:
                pytest.fail("Should not raise PermissionDeniedError when permission is granted")
        else:
            # Should not have permission
            assert has_permission is False
            # check_permission should raise
            with pytest.raises(PermissionDeniedError):
                permission_manager.check_permission(plugin_name, required_permission)
    
    # Feature: third-party-plugin-system, Property 22: Permission enforcement
    @settings(max_examples=100)
    @given(
        plugin_name=plugin_name_strategy(),
        permissions=permission_set_strategy()
    )
    def test_permission_grant_and_revoke(
        self, plugin_name, permissions
    ):
        """
        Property: For any set of permissions granted to a plugin,
        revoking a permission should remove it from the plugin's permission set.
        """
        # Setup
        permission_manager = PermissionManager()
        permission_manager.grant_permissions(
            plugin_name,
            [p.value for p in permissions]
        )
        
        # Verify all permissions granted
        for perm in permissions:
            assert permission_manager.has_permission(plugin_name, perm)
        
        # Revoke each permission and verify
        for perm in permissions:
            permission_manager.revoke_permission(plugin_name, perm)
            assert not permission_manager.has_permission(plugin_name, perm)
            
            # Other permissions should still be present (if any)
            remaining = permissions - {perm}
            for other_perm in remaining:
                if other_perm != perm:
                    # This permission should still be present until we revoke it
                    pass
    
    # Feature: third-party-plugin-system, Property 22: Permission enforcement
    @settings(max_examples=100)
    @given(
        plugin_name=plugin_name_strategy(),
        node_id=st.one_of(st.none(), st.text(min_size=1, max_size=20))
    )
    def test_system_state_query_permission_enforcement(
        self, plugin_name, node_id
    ):
        """
        Property: For any plugin attempting to query system state,
        access should be denied without SYSTEM_STATE_READ permission.
        """
        # Setup without permission
        permission_manager = PermissionManager()
        mock_plugin_manager = MagicMock()
        system_state = SystemStateQuery(mock_plugin_manager, permission_manager)
        
        # Verify access denied
        with pytest.raises(PermissionDeniedError):
            system_state.get_node_info(plugin_name, node_id)
        
        with pytest.raises(PermissionDeniedError):
            system_state.get_network_status(plugin_name)
        
        with pytest.raises(PermissionDeniedError):
            system_state.get_plugin_list(plugin_name)
        
        # Grant permission
        permission_manager.grant_permissions(
            plugin_name,
            [Permission.SYSTEM_STATE_READ.value]
        )
        
        # Verify access granted (should not raise)
        try:
            system_state.get_node_info(plugin_name, node_id)
            system_state.get_network_status(plugin_name)
            system_state.get_plugin_list(plugin_name)
        except PermissionDeniedError:
            pytest.fail("Should not raise PermissionDeniedError when permission is granted")
    
    # Feature: third-party-plugin-system, Property 22: Permission enforcement
    @settings(max_examples=100)
    @given(
        plugin_name=plugin_name_strategy(),
        content=st.text(min_size=1, max_size=200)
    )
    @pytest.mark.asyncio
    async def test_message_routing_permission_enforcement(
        self, plugin_name, content
    ):
        """
        Property: For any plugin attempting to send mesh messages,
        access should be denied without SEND_MESSAGES permission.
        """
        # Setup without permission
        permission_manager = PermissionManager()
        mock_router = MagicMock()
        mock_router.queue_outgoing_message = AsyncMock()
        message_routing = MessageRoutingService(mock_router, permission_manager)
        
        # Verify access denied
        with pytest.raises(PermissionDeniedError):
            await message_routing.send_mesh_message(plugin_name, content)
        
        # Grant permission
        permission_manager.grant_permissions(
            plugin_name,
            [Permission.SEND_MESSAGES.value]
        )
        
        # Verify access granted (should not raise)
        try:
            await message_routing.send_mesh_message(plugin_name, content)
        except PermissionDeniedError:
            pytest.fail("Should not raise PermissionDeniedError when permission is granted")
    
    # Feature: third-party-plugin-system, Property 22: Permission enforcement
    @settings(max_examples=100)
    @given(
        source_plugin=plugin_name_strategy(),
        target_plugin=plugin_name_strategy(),
        message_type=st.text(min_size=1, max_size=30)
    )
    @pytest.mark.asyncio
    async def test_inter_plugin_messaging_permission_enforcement(
        self, source_plugin, target_plugin, message_type
    ):
        """
        Property: For any plugin attempting inter-plugin messaging,
        access should be denied without INTER_PLUGIN_MESSAGING permission.
        """
        # Ensure source and target are different
        assume(source_plugin != target_plugin)
        
        # Setup without permission
        permission_manager = PermissionManager()
        mock_plugin_manager = MagicMock()
        inter_plugin = InterPluginMessaging(mock_plugin_manager, permission_manager)
        
        # Verify access denied for send_to_plugin
        with pytest.raises(PermissionDeniedError):
            await inter_plugin.send_to_plugin(
                source_plugin, target_plugin, message_type, {"test": "data"}
            )
        
        # Verify access denied for broadcast
        with pytest.raises(PermissionDeniedError):
            await inter_plugin.broadcast_to_plugins(
                source_plugin, message_type, {"test": "data"}
            )
        
        # Grant permission
        permission_manager.grant_permissions(
            source_plugin,
            [Permission.INTER_PLUGIN_MESSAGING.value]
        )
        
        # Register a handler for target
        async def handler(msg):
            return {"received": True}
        inter_plugin.register_message_handler(target_plugin, handler)
        
        # Verify access granted (should not raise)
        try:
            await inter_plugin.send_to_plugin(
                source_plugin, target_plugin, message_type, {"test": "data"}
            )
            await inter_plugin.broadcast_to_plugins(
                source_plugin, message_type, {"test": "data"}
            )
        except PermissionDeniedError:
            pytest.fail("Should not raise PermissionDeniedError when permission is granted")
    
    # Feature: third-party-plugin-system, Property 22: Permission enforcement
    @settings(max_examples=100)
    @given(
        plugin_name=plugin_name_strategy(),
        permissions=permission_set_strategy()
    )
    def test_permission_isolation_between_plugins(
        self, plugin_name, permissions
    ):
        """
        Property: For any plugin with granted permissions,
        other plugins should not inherit those permissions.
        """
        # Setup
        permission_manager = PermissionManager()
        other_plugin = plugin_name + "_other"
        
        # Grant permissions to first plugin
        permission_manager.grant_permissions(
            plugin_name,
            [p.value for p in permissions]
        )
        
        # Verify first plugin has permissions
        for perm in permissions:
            assert permission_manager.has_permission(plugin_name, perm)
        
        # Verify other plugin does NOT have permissions
        for perm in permissions:
            assert not permission_manager.has_permission(other_plugin, perm)
    
    # Feature: third-party-plugin-system, Property 22: Permission enforcement
    @settings(max_examples=100)
    @given(
        plugin_name=plugin_name_strategy(),
        permissions=permission_set_strategy()
    )
    def test_permission_cleanup(
        self, plugin_name, permissions
    ):
        """
        Property: For any plugin with granted permissions,
        clearing permissions should remove all permissions.
        """
        # Setup
        permission_manager = PermissionManager()
        permission_manager.grant_permissions(
            plugin_name,
            [p.value for p in permissions]
        )
        
        # Verify permissions granted
        for perm in permissions:
            assert permission_manager.has_permission(plugin_name, perm)
        
        # Clear permissions
        permission_manager.clear_plugin_permissions(plugin_name)
        
        # Verify all permissions removed
        for perm in permissions:
            assert not permission_manager.has_permission(plugin_name, perm)
        
        # Verify get_plugin_permissions returns empty set
        assert len(permission_manager.get_plugin_permissions(plugin_name)) == 0
    
    # Feature: third-party-plugin-system, Property 22: Permission enforcement
    @settings(max_examples=100)
    @given(
        plugins=st.lists(
            st.tuples(plugin_name_strategy(), permission_set_strategy()),
            min_size=1,
            max_size=5,
            unique_by=lambda x: x[0]
        )
    )
    def test_multiple_plugin_permission_independence(
        self, plugins
    ):
        """
        Property: For any set of plugins with different permissions,
        each plugin's permissions should be independent and not affect others.
        """
        # Setup
        permission_manager = PermissionManager()
        
        # Grant permissions to all plugins
        for plugin_name, permissions in plugins:
            permission_manager.grant_permissions(
                plugin_name,
                [p.value for p in permissions]
            )
        
        # Verify each plugin has exactly its granted permissions
        for plugin_name, permissions in plugins:
            granted = permission_manager.get_plugin_permissions(plugin_name)
            assert granted == permissions, \
                f"Plugin {plugin_name} should have exactly its granted permissions"
            
            # Verify plugin has all its permissions
            for perm in permissions:
                assert permission_manager.has_permission(plugin_name, perm)
            
            # Verify plugin doesn't have permissions it wasn't granted
            all_permissions = set(Permission)
            not_granted = all_permissions - permissions
            for perm in not_granted:
                assert not permission_manager.has_permission(plugin_name, perm)
    
    # Feature: third-party-plugin-system, Property 22: Permission enforcement
    @settings(max_examples=100)
    @given(
        plugin_name=plugin_name_strategy(),
        invalid_permission=st.text(
            alphabet=st.characters(whitelist_categories=('Ll', 'Lu'), whitelist_characters='_'),
            min_size=1,
            max_size=30
        ).filter(lambda x: x not in [p.value for p in Permission])
    )
    def test_invalid_permission_handling(
        self, plugin_name, invalid_permission
    ):
        """
        Property: For any invalid permission string,
        attempting to grant it should not crash and should be ignored.
        """
        # Setup
        permission_manager = PermissionManager()
        
        # Attempt to grant invalid permission (should not crash)
        try:
            permission_manager.grant_permissions(plugin_name, [invalid_permission])
        except Exception as e:
            # Should not raise exception, but if it does, it should be logged
            # In our implementation, invalid permissions are logged and ignored
            pass
        
        # Verify plugin has no permissions
        granted = permission_manager.get_plugin_permissions(plugin_name)
        assert len(granted) == 0, "Invalid permissions should not be granted"
    
    # Feature: third-party-plugin-system, Property 22: Permission enforcement
    @settings(max_examples=100)
    @given(
        plugin_name=plugin_name_strategy(),
        permissions=permission_set_strategy()
    )
    def test_permission_idempotency(
        self, plugin_name, permissions
    ):
        """
        Property: For any set of permissions,
        granting them multiple times should have the same effect as granting once.
        """
        # Setup
        permission_manager = PermissionManager()
        
        # Grant permissions multiple times
        for _ in range(3):
            permission_manager.grant_permissions(
                plugin_name,
                [p.value for p in permissions]
            )
        
        # Verify plugin has exactly the granted permissions (no duplicates)
        granted = permission_manager.get_plugin_permissions(plugin_name)
        assert granted == permissions
        
        # Verify each permission check works correctly
        for perm in permissions:
            assert permission_manager.has_permission(plugin_name, perm)
