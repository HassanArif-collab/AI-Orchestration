#!/usr/bin/env python3
"""
Integration tests for FreeRouter fixes.

Tests the critical fixes applied to ensure reliability, performance, and security.
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv()

from freerouter.proxy import FreeRouterProxy, AuthMiddleware
from freerouter.classifier import TaskClassifier, TaskCategory
from freerouter.health import ModelHealthChecker
from freerouter.providers import should_skip_provider, mark_hard_limited, get_all_usage


def test_health_based_fallback():
    """Test that unhealthy providers are excluded from fallback chains."""
    print("\n" + "=" * 60)
    print("Testing Health-Based Fallback Adjustment")
    print("=" * 60)
    
    proxy = FreeRouterProxy()
    
    # Simulate provider state
    from freerouter.providers import _usage_state
    from freerouter.providers import ProviderUsage
    
    # Mark groq as hard limited
    mark_hard_limited("groq")
    
    # Test fallback chain for coder
    fallback_chain = proxy._get_healthy_fallback_chain("free-router/coder")
    
    # Verify groq provider models are excluded
    groq_models = [m for m in fallback_chain if "groq" in m]
    if groq_models:
        print(f"  [FAIL] Unhealthy provider (groq) still in fallback chain: {groq_models}")
        return False
    
    print(f"  [PASS] Unhealthy providers excluded from fallback chain")
    print(f"  Healthy chain: {fallback_chain}")
    
    # Reset for next test
    _usage_state.clear()
    return True


def test_classification_caching():
    """Test that classification results are cached."""
    print("\n" + "=" * 60)
    print("Testing Classification Caching")
    print("=" * 60)
    
    proxy = FreeRouterProxy(use_classification=False)
    
    # First classification (should miss cache)
    content = "Write a Python function to sort a list"
    result1 = asyncio.run(proxy._classify_with_cache(content))
    
    # Second classification (should hit cache)
    result2 = asyncio.run(proxy._classify_with_cache(content))
    
    if result1.recommended_model == result2.recommended_model:
        print(f"  [PASS] Cached classification returns same result")
        print(f"  Model: {result1.recommended_model}")
        return True
    else:
        print(f"  [FAIL] Cache returned different results")
        return False


def test_shared_state():
    """Test shared state mechanism for multi-worker."""
    print("\n" + "=" * 60)
    print("Testing Shared State Mechanism")
    print("=" * 60)
    
    # Create temporary state directory
    with tempfile.TemporaryDirectory() as tmpdir:
        proxy1 = FreeRouterProxy(state_dir=tmpdir)
        
        # Build a fallback chain
        chain = ["free-router/coder", "free-router/smart"]
        proxy1._save_shared_cache({"free-router/coder": chain})
        
        # Create second proxy instance
        proxy2 = FreeRouterProxy(state_dir=tmpdir)
        cached = proxy2._load_shared_cache()
        
        if "free-router/coder" in cached and cached["free-router/coder"] == chain:
            print(f"  [PASS] Shared state loaded correctly")
            print(f"  Chain: {cached['free-router/coder']}")
            return True
        else:
            print(f"  [FAIL] Shared state not loaded")
            print(f"  Expected: {chain}, Got: {cached.get('free-router/coder')}")
            return False


def test_auth_middleware():
    """Test API key authentication."""
    print("\n" + "=" * 60)
    print("Testing API Key Authentication")
    print("=" * 60)
    
    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient
    from freerouter.proxy import AuthMiddleware
    
    app = FastAPI()
    
    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}
    
    # Add middleware standard way
    app.add_middleware(AuthMiddleware, api_key="test-key")
    
    client = TestClient(app)
    
    # Test without key
    response = client.get("/test")
    if response.status_code != 401:
        print(f"  [FAIL] Expected 401 without key, got {response.status_code}")
        return False
    
    # Test with correct key in header
    response = client.get("/test", headers={"Authorization": "Bearer test-key"})
    if response.status_code != 200:
        print(f"  [FAIL] Expected 200 with correct key, got {response.status_code}")
        return False
    
    print(f"  [PASS] Authentication working correctly")
    return True


def test_health_checker():
    """Test health checker basic functionality."""
    print("\n" + "=" * 60)
    print("Testing Health Checker")
    print("=" * 60)
    
    checker = ModelHealthChecker()
    
    # Test provider extraction
    test_cases = [
        ("ollama/qwen2.5:7b", "ollama"),
        ("groq/llama-3.3-70b", "groq"),
        ("openrouter/deepseek/deepseek-chat", "openrouter"),
    ]
    
    for model, expected in test_cases:
        provider = checker.get_provider_from_model(model)
        if provider != expected:
            print(f"  [FAIL] {model} -> {provider} (expected {expected})")
            return False
    
    print(f"  [PASS] Provider extraction correct")
    
    # Test health check doesn't crash
    try:
        health = asyncio.run(checker.check_provider("ollama"))
        print(f"  [PASS] Health check runs without crash")
        print(f"    Status: {health.status.value}")
        return True
    except Exception as e:
        print(f"  [FAIL] Health check failed: {e}")
        return False


def test_web_search_robustness():
    """Test that web search handles errors gracefully."""
    print("\n" + "=" * 60)
    print("Testing Web Search Robustness")
    print("=" * 60)
    
    from freerouter.websearch import WebSearchInterceptor
    
    interceptor = WebSearchInterceptor(enabled=True)
    
    # Test with empty query
    response = asyncio.run(interceptor.execute_search(""))
    if response.error:
        print(f"  [PASS] Empty query returns error: {response.error}")
    else:
        print(f"  [FAIL] Empty query should return error")
        return False
    
    # Test tool detection
    tool_call = {"function": {"name": "web_search", "arguments": '{"query": "test"}'}}
    if interceptor.is_search_tool(tool_call):
        print(f"  [PASS] Web search tool detected")
    else:
        print(f"  [FAIL] Web search tool not detected")
        return False
    
    # Test non-search tool
    tool_call = {"function": {"name": "code_interpreter", "arguments": '{"code": "print(1)"}'}}
    if not interceptor.is_search_tool(tool_call):
        print(f"  [PASS] Non-search tool correctly ignored")
        return True
    else:
        print(f"  [FAIL] Non-search tool incorrectly detected as search")
        return False


def test_streaming_enhancements():
    """Test streaming response handling."""
    print("\n" + "=" * 60)
    print("Testing Streaming Enhancements")
    print("=" * 60)
    
    # This would require a running LiteLLM instance
    # For now, just test that the method exists and has correct signature
    proxy = FreeRouterProxy()
    
    import inspect
    sig = inspect.signature(proxy._forward_streaming)
    params = list(sig.parameters.keys())
    
    expected = ['client', 'body', 'headers']
    if params == expected:
        print(f"  [PASS] _forward_streaming has correct parameters")
        return True
    else:
        print(f"  [FAIL] Expected {expected}, got {params}")
        return False


def test_provider_usage_tracking():
    """Test rate-limit usage tracking."""
    print("\n" + "=" * 60)
    print("Testing Provider Usage Tracking")
    print("=" * 60)
    
    from freerouter.providers import update_usage_from_headers, get_usage
    
    # Simulate headers
    headers = {
        "x-ratelimit-remaining-requests": "50",
        "x-ratelimit-limit-requests": "100",
    }
    
    usage = update_usage_from_headers("groq", headers)
    
    if usage.requests_remaining == 50 and usage.requests_limit == 100:
        print(f"  [PASS] Usage tracking parsed headers correctly")
        print(f"    Remaining: {usage.requests_remaining}/{usage.requests_limit}")
        return True
    else:
        print(f"  [FAIL] Usage tracking incorrect")
        print(f"    Remaining: {usage.requests_remaining}, Limit: {usage.requests_limit}")
        return False


def run_all_tests():
    """Run all integration tests."""
    print("\n" + "=" * 60)
    print("FreeRouter Integration Tests")
    print("=" * 60)
    
    tests = [
        ("Health-Based Fallback", test_health_based_fallback),
        ("Classification Caching", test_classification_caching),
        ("Shared State", test_shared_state),
        ("Authentication", test_auth_middleware),
        ("Health Checker", test_health_checker),
        ("Web Search Robustness", test_web_search_robustness),
        ("Streaming Enhancements", test_streaming_enhancements),
        ("Usage Tracking", test_provider_usage_tracking),
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"  [ERROR] {e}")
            results[name] = False
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    
    for name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status}: {name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    return all(results.values())


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)