"""Tests for async ZepMemoryClient refactor.

This test module verifies that:
1. The sync ZepMemoryClient has been removed
2. The run_async helper has been removed
3. The AsyncZepMemoryClient exists with async methods
"""

import inspect


def test_sync_zep_client_is_removed():
    """Verify that ZepMemoryClient (sync) and run_async are removed."""
    import packages.memory.client as m
    
    assert not hasattr(m, "ZepMemoryClient"), "ZepMemoryClient (sync) must be removed"
    assert not hasattr(m, "run_async"), "run_async must be removed"


def test_async_zep_client_exists():
    """Verify that AsyncZepMemoryClient exists with async methods."""
    from packages.memory.client import AsyncZepMemoryClient, get_async_zep_client
    
    # Check that search_memory is an async method
    assert inspect.iscoroutinefunction(AsyncZepMemoryClient.search_memory), \
        "AsyncZepMemoryClient.search_memory must be async"
    
    # Check that add_facts is an async method
    assert inspect.iscoroutinefunction(AsyncZepMemoryClient.add_facts), \
        "AsyncZepMemoryClient.add_facts must be async"
    
    # Check that create_user is an async method
    assert inspect.iscoroutinefunction(AsyncZepMemoryClient.create_user), \
        "AsyncZepMemoryClient.create_user must be async"
    
    # Check that create_session is an async method
    assert inspect.iscoroutinefunction(AsyncZepMemoryClient.create_session), \
        "AsyncZepMemoryClient.create_session must be async"
    
    # Check factory function works
    client = get_async_zep_client()
    assert isinstance(client, AsyncZepMemoryClient), \
        "get_async_zep_client must return AsyncZepMemoryClient"
