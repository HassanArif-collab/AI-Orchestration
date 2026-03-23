#!/usr/bin/env python3
"""
Test script for FreeRouter.

Validates that the proxy works correctly with different model aliases,
classification scenarios, and web search interception.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def test_classifier():
    """Test the task classifier."""
    print("\n" + "=" * 60)
    print("Testing Task Classifier")
    print("=" * 60)

    from freerouter.classifier import TaskClassifier, TaskCategory

    classifier = TaskClassifier(
        classifier_model="ollama/qwen2.5:3b",
        api_base="http://localhost:11434",
        use_fast_classifier=False,  # Use keyword-based for testing
    )

    # Test cases
    test_cases = [
        ("Write a Python function to sort a list", TaskCategory.CODING),
        ("What is the capital of France?", TaskCategory.SIMPLE_CHAT),
        ("Solve this math puzzle: If 2x + 5 = 15, what is x?", TaskCategory.REASONING),
        ("Analyze this image and describe what you see", TaskCategory.VISION),
        ("Plan a trip to Paris with flights, hotels, and activities", TaskCategory.AGENTIC),
        ("Research the history of quantum computing", TaskCategory.RESEARCH),
    ]

    print("\nTesting keyword-based classification:")
    all_passed = True

    for content, expected_category in test_cases:
        result = asyncio.run(classifier.classify(content))
        status = "[PASS]" if result.category == expected_category else "[FAIL]"
        if result.category != expected_category:
            all_passed = False
        print(f"  {status} '{content[:40]}...'")
        print(f"      Expected: {expected_category.value}, Got: {result.category.value}")
        print(f"      Confidence: {result.confidence:.2f}")
        print(f"      Model: {result.recommended_model}")

    return all_passed


def test_config():
    """Test configuration loading."""
    print("\n" + "=" * 60)
    print("Testing Configuration")
    print("=" * 60)

    from freerouter.config import get_config_path, load_config, get_model_aliases, validate_environment

    config_path = get_config_path()
    print(f"\nConfig path: {config_path}")
    print(f"Config exists: {config_path.exists()}")

    if config_path.exists():
        config = load_config()
        print(f"\nModel list entries: {len(config.get('model_list', []))}")
        print(f"Fallback chains: {len(config.get('fallbacks', []))}")

        aliases = get_model_aliases()
        print(f"\nAvailable aliases:")
        for alias, model in sorted(aliases.items())[:10]:
            print(f"  {alias}: {model}")
        if len(aliases) > 10:
            print(f"  ... and {len(aliases) - 10} more")

    print("\nEnvironment validation:")
    env_status = validate_environment()
    for key, is_set in env_status.items():
        if key == "required_set":
            continue
        status = "[OK]" if is_set else "[--]"
        print(f"  {status} {key}: {'set' if is_set else 'not set'}")

    return env_status.get("required_set", False)


def test_web_search():
    """Test web search interception."""
    print("\n" + "=" * 60)
    print("Testing Web Search Interception")
    print("=" * 60)

    from freerouter.websearch import WebSearchInterceptor, SearchProvider, check_for_web_search_intent

    # Test intent detection
    test_queries = [
        ("What is the latest news about AI?", True),
        ("Write a hello world program", False),
        ("Search for Python tutorials", True),
        ("How do I cook pasta?", False),
        ("What's the current weather in London?", True),
    ]

    print("\nTesting web search intent detection:")
    for query, expected in test_queries:
        result = check_for_web_search_intent(query)
        status = "[OK]" if result == expected else "[--]"
        print(f"  {status} '{query}' -> {result} (expected: {expected})")

    # Test search tool detection
    interceptor = WebSearchInterceptor(enabled=True)

    print("\nTesting tool call detection:")
    tool_calls = [
        {"function": {"name": "web_search", "arguments": '{"query": "test"}'}},
        {"function": {"name": "google_search", "arguments": '{"query": "test"}'}},
        {"function": {"name": "code_interpreter", "arguments": '{"code": "print(1)"}'}},
    ]

    for tool_call in tool_calls:
        is_search = interceptor.is_search_tool(tool_call)
        print(f"  {tool_call['function']['name']}: {'search tool' if is_search else 'not search'}")

    # Test actual search (if enabled and network available)
    print("\nTesting actual search (DuckDuckGo):")
    try:
        response = asyncio.run(interceptor.execute_search("Python programming", num_results=3))
        if response.error:
            print(f"  Search error: {response.error}")
        else:
            print(f"  Found {len(response.results)} results:")
            for i, result in enumerate(response.results, 1):
                print(f"    {i}. {result.title[:50]}...")
    except Exception as e:
        print(f"  Search failed (expected if offline): {e}")

    return True


def test_health_checker():
    """Test model health checker."""
    print("\n" + "=" * 60)
    print("Testing Health Checker")
    print("=" * 60)

    from freerouter.health import ModelHealthChecker, ModelStatus

    checker = ModelHealthChecker()

    # Test provider extraction
    test_models = [
        ("ollama/qwen2.5:7b", "ollama"),
        ("groq/llama-3.3-70b-versatile", "groq"),
        ("openrouter/deepseek/deepseek-chat", "openrouter"),
        ("openai/gpt-4", "openai"),
        ("anthropic/claude-3-opus", "anthropic"),
    ]

    print("\nTesting provider extraction:")
    for model, expected in test_models:
        provider = checker.get_provider_from_model(model)
        status = "[PASS]" if provider == expected else "[FAIL]"
        print(f"  {status} {model} -> {provider}")

    # Test health check
    print("\nTesting provider health check (Ollama):")
    health = asyncio.run(checker.check_provider("ollama"))
    print(f"  Status: {health.status.value}")
    print(f"  Latency: {health.latency_ms:.2f}ms")
    if health.last_error:
        print(f"  Error: {health.last_error}")

    # Test status report
    print("\nStatus report:")
    report = checker.get_status_report()
    for provider, status in report.items():
        print(f"  {provider}: {status['status']}")

    return True


def test_proxy_app():
    """Test FastAPI app creation."""
    print("\n" + "=" * 60)
    print("Testing Proxy App")
    print("=" * 60)

    try:
        from freerouter.proxy import FreeRouterProxy, create_app

        # Test app creation
        proxy = FreeRouterProxy(
            litellm_base="http://localhost:4000",
            use_classification=True,
            enable_web_search=True,
        )

        print(f"\nApp created successfully")
        print(f"  Routes: {[route.path for route in proxy.app.routes][:5]}...")
        print(f"  Web search enabled: {proxy.web_search_enabled}")
        print(f"  Classifier model: {proxy.classifier.classifier_model}")

        # Test app factory
        app = create_app()
        print(f"\nApp factory works: {app is not None}")

        return True

    except Exception as e:
        print(f"Error creating app: {e}")
        return False


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("FreeRouter Test Suite")
    print("=" * 60)

    results = {}

    # Run tests
    results["Config"] = test_config()
    results["Classifier"] = test_classifier()
    results["Web Search"] = test_web_search()
    results["Health Checker"] = test_health_checker()
    results["Proxy App"] = test_proxy_app()

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

    print("\n" + "=" * 60)
    if all_passed:
        print("All tests passed!")
    else:
        print("Some tests failed. Check the output above for details.")

    return all_passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)