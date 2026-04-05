#!/usr/bin/env python3
"""
Integration tests for FreeRouter v3 gap fixes.

Tests the four critical fixes applied during v3 migration:
  GAP FIX 1: HTTPException(503) on failure (not RuntimeError)
  GAP FIX 2: .env loading from freerouter/.env
  GAP FIX 3: /v1/models endpoint exists
  GAP FIX 4: version "3.0.0" in health response
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient


def test_gap_fix_1_http_503_on_failure():
    """GAP FIX 1: Server returns HTTPException(503) when all models fail."""
    print("\n" + "=" * 60)
    print("GAP FIX 1: HTTPException(503) on Failure")
    print("=" * 60)

    from freerouter.server import app

    with patch("freerouter.server.litellm") as mock_litellm:
        # Make both primary and fallback raise exceptions
        mock_litellm.acompletion.side_effect = [
            Exception("primary failed"),
            Exception("fallback failed"),
        ]

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/v1/chat/completions", json={
            "model": "scorer",
            "messages": [{"role": "user", "content": "test"}],
        })

        if response.status_code == 503:
            print(f"  [PASS] Returns 503 when both models fail")
            print(f"  [PASS] Detail: {response.json().get('detail', '')[:80]}")
            return True
        else:
            print(f"  [FAIL] Expected 503, got {response.status_code}")
            return False


def test_gap_fix_2_env_loading():
    """GAP FIX 2: .env loads from freerouter/.env (not cwd)."""
    print("\n" + "=" * 60)
    print("GAP FIX 2: .env Loading")
    print("=" * 60)

    # Check that _env_candidates in server.py includes the right path
    from freerouter.server import _env_candidates

    # At least one candidate should resolve to freerouter/.env
    found_project_env = False
    for candidate in _env_candidates:
        normalized = Path(candidate).resolve()
        # The candidate should point up two levels from server.py to freerouter/.env
        parts = normalized.parts
        # Should end with freerouter/.env or src/freerouter/.env
        if "freerouter" in parts and normalized.name == ".env":
            found_project_env = True
            print(f"  [PASS] Candidate: {normalized}")

    if found_project_env:
        print(f"  [PASS] .env path candidates include freerouter/.env")
        return True
    else:
        print(f"  [FAIL] No freerouter/.env candidate found")
        print(f"  Candidates: {_env_candidates}")
        return False


def test_gap_fix_3_models_endpoint():
    """GAP FIX 3: /v1/models endpoint exists and returns correct data."""
    print("\n" + "=" * 60)
    print("GAP FIX 3: /v1/models Endpoint")
    print("=" * 60)

    from freerouter.server import app

    client = TestClient(app)
    response = client.get("/v1/models")

    if response.status_code != 200:
        print(f"  [FAIL] Expected 200, got {response.status_code}")
        return False

    data = response.json()
    if data["object"] != "list":
        print(f"  [FAIL] Expected object='list', got {data['object']}")
        return False

    if not isinstance(data["data"], list) or len(data["data"]) == 0:
        print(f"  [FAIL] Expected non-empty data list")
        return False

    # Verify each model entry has required fields
    for model in data["data"]:
        for key in ("id", "object", "owned_by", "primary", "fallback"):
            if key not in model:
                print(f"  [FAIL] Model entry missing '{key}': {model}")
                return False

    print(f"  [PASS] GET /v1/models -> 200")
    print(f"  [PASS] Returns {len(data['data'])} models with all required fields")
    return True


def test_gap_fix_4_version_in_health():
    """GAP FIX 4: Health response includes version 3.1.0."""
    print("\n" + "=" * 60)
    print("GAP FIX 4: Version in Health Response")
    print("=" * 60)

    from freerouter.server import app

    client = TestClient(app)
    response = client.get("/health")

    if response.status_code != 200:
        print(f"  [FAIL] Expected 200, got {response.status_code}")
        return False

    data = response.json()

    if "version" not in data:
        print(f"  [FAIL] No 'version' key in health response")
        return False

    if data["version"] != "3.1.0":
        print(f"  [FAIL] Expected version='3.1.0', got {data['version']}")
        return False

    print(f"  [PASS] GET /health -> 200")
    print(f"  [PASS] version = {data['version']}")

    if "tasks" in data and isinstance(data["tasks"], list):
        print(f"  [PASS] tasks list present with {len(data['tasks'])} entries")
    else:
        print(f"  [WARN] 'tasks' key missing or not a list")

    return True


def run_all_tests():
    """Run all gap fix tests."""
    print("\n" + "=" * 60)
    print("FreeRouter v3 Gap Fix Tests")
    print("=" * 60)

    tests = [
        ("GAP FIX 1: HTTP 503 on failure", test_gap_fix_1_http_503_on_failure),
        ("GAP FIX 2: .env loading", test_gap_fix_2_env_loading),
        ("GAP FIX 3: /v1/models endpoint", test_gap_fix_3_models_endpoint),
        ("GAP FIX 4: version in health", test_gap_fix_4_version_in_health),
    ]

    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    for name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status}: {name}")

    passed = sum(results.values())
    total = len(results)
    print(f"\n{passed}/{total} tests passed")

    return all(results.values())


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
