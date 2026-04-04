#!/usr/bin/env python3
"""
Test suite for FreeRouter v3.

Tests the slim LiteLLM task router: config routes, server endpoints,
resolve logic, version, and FastAPI app.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_version():
    """Test that __version__ is 3.0.0."""
    print("\n" + "=" * 60)
    print("Testing Version")
    print("=" * 60)

    import freerouter
    assert freerouter.__version__ == "3.0.0", f"Expected 3.0.0, got {freerouter.__version__}"
    print(f"  [PASS] freerouter.__version__ = {freerouter.__version__}")
    return True


def test_routes():
    """Test that ROUTES has the expected keys and structure."""
    print("\n" + "=" * 60)
    print("Testing ROUTES Config")
    print("=" * 60)

    from freerouter.config import ROUTES

    expected_keys = {"auto", "researcher", "topic_finder", "script_writer", "scorer", "challenger", "annotator"}
    actual_keys = set(ROUTES.keys())

    missing = expected_keys - actual_keys
    extra = actual_keys - expected_keys

    if missing:
        print(f"  [FAIL] Missing routes: {missing}")
        return False
    if extra:
        print(f"  [FAIL] Extra routes: {extra}")
        return False

    print(f"  [PASS] All 7 route keys present: {sorted(expected_keys)}")

    # Check structure
    for name, route in ROUTES.items():
        assert "model" in route, f"Route '{name}' missing 'model' key"
        assert "fallback" in route, f"Route '{name}' missing 'fallback' key"
        print(f"  [PASS] {name}: model={route['model']}, fallback={route['fallback']}")

    return True


def test_resolve():
    """Test _resolve() function from server.py."""
    print("\n" + "=" * 60)
    print("Testing _resolve()")
    print("=" * 60)

    from freerouter.server import _resolve

    all_passed = True

    # Known task name
    primary, fallback = _resolve("scorer")
    expected_primary = "groq/compound-beta-mini"
    expected_fallback = "groq/llama-3.1-8b-instant"
    if primary == expected_primary and fallback == expected_fallback:
        print(f"  [PASS] _resolve('scorer') -> ({primary}, {fallback})")
    else:
        print(f"  [FAIL] _resolve('scorer') expected ({expected_primary}, {expected_fallback}), got ({primary}, {fallback})")
        all_passed = False

    # Auto route
    primary, fallback = _resolve("auto")
    if primary == "openrouter/stepfun/step-3.5-flash:free" and fallback == "groq/llama-3.3-70b-versatile":
        print(f"  [PASS] _resolve('auto') -> ({primary}, {fallback})")
    else:
        print(f"  [FAIL] _resolve('auto') unexpected result: ({primary}, {fallback})")
        all_passed = False

    # Direct litellm string (pass-through)
    direct = "groq/llama-3.3-70b-versatile"
    primary, fallback = _resolve(direct)
    if primary == direct and fallback == "groq/llama-3.3-70b-versatile":
        print(f"  [PASS] _resolve('{direct}') -> pass-through with auto fallback")
    else:
        print(f"  [FAIL] _resolve('{direct}') expected pass-through, got ({primary}, {fallback})")
        all_passed = False

    return all_passed


def test_app_is_fastapi():
    """Test that freerouter.server.app is a FastAPI instance."""
    print("\n" + "=" * 60)
    print("Testing FastAPI App")
    print("=" * 60)

    from freerouter.server import app
    from fastapi import FastAPI

    assert isinstance(app, FastAPI), f"Expected FastAPI instance, got {type(app)}"
    print(f"  [PASS] app is FastAPI instance")
    print(f"  [PASS] app.title = {app.title}")
    print(f"  [PASS] app.version = {app.version}")
    return True


def test_health_endpoint():
    """Test /health endpoint with TestClient."""
    print("\n" + "=" * 60)
    print("Testing /health Endpoint")
    print("=" * 60)

    from fastapi.testclient import TestClient
    from freerouter.server import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()

    assert data["status"] == "ok", f"Expected status='ok', got {data['status']}"
    assert data["version"] == "3.0.0", f"Expected version='3.0.0', got {data['version']}"
    assert isinstance(data["tasks"], list), f"Expected tasks to be list, got {type(data['tasks'])}"

    print(f"  [PASS] GET /health -> 200")
    print(f"  [PASS] status = {data['status']}")
    print(f"  [PASS] version = {data['version']}")
    print(f"  [PASS] tasks = {data['tasks']}")
    return True


def test_models_endpoint():
    """Test /v1/models endpoint with TestClient."""
    print("\n" + "=" * 60)
    print("Testing /v1/models Endpoint")
    print("=" * 60)

    from fastapi.testclient import TestClient
    from freerouter.server import app

    client = TestClient(app)
    response = client.get("/v1/models")

    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()

    assert data["object"] == "list", f"Expected object='list', got {data['object']}"
    assert isinstance(data["data"], list), f"Expected data to be list"

    model_ids = {m["id"] for m in data["data"]}
    expected = {"auto", "researcher", "topic_finder", "script_writer", "scorer", "challenger", "annotator"}
    if model_ids == expected:
        print(f"  [PASS] GET /v1/models -> 200, {len(data['data'])} models")
        for m in data["data"]:
            print(f"    {m['id']}: owned_by={m['owned_by']}, primary={m['primary']}")
    else:
        missing = expected - model_ids
        extra = model_ids - expected
        print(f"  [FAIL] Expected {expected}, got {model_ids}, missing={missing}, extra={extra}")
        return False

    return True


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("FreeRouter v3 Test Suite")
    print("=" * 60)

    results = {}

    tests = [
        ("Version", test_version),
        ("ROUTES Config", test_routes),
        ("_resolve()", test_resolve),
        ("FastAPI App", test_app_is_fastapi),
        ("/health Endpoint", test_health_endpoint),
        ("/v1/models Endpoint", test_models_endpoint),
    ]

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

    all_passed = True
    for name, passed in results.items():
        status = "[PASS]" if passed else "[FAIL]"
        print(f"  {status}: {name}")
        if not passed:
            all_passed = False

    print(f"\n{sum(results.values())}/{len(results)} tests passed")

    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
