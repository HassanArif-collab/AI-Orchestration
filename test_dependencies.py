#!/usr/bin/env python3
"""
Test script to verify dependency compatibility.
Run this after installing dependencies to check if everything works.
"""

import sys

print(f"Python version: {sys.version}")
print()

# Test core imports
print("Testing core imports...")
try:
    import pydantic
    print(f"✓ pydantic {pydantic.__version__}")
except ImportError as e:
    print(f"✗ pydantic: {e}")

try:
    import httpx
    print(f"✓ httpx {httpx.__version__}")
except ImportError as e:
    print(f"✗ httpx: {e}")

try:
    from packages.core.config import get_settings
    print("✓ packages.core.config")
except ImportError as e:
    print(f"✗ packages.core.config: {e}")

# Test LangGraph imports
print("\nTesting LangGraph imports...")
try:
    from langgraph.graph import StateGraph
    print("✓ langgraph")
except ImportError as e:
    print(f"✗ langgraph: {e}")

try:
    from langchain_core import __version__ as lc_version
    print(f"✓ langchain-core {lc_version}")
except ImportError as e:
    print(f"✗ langchain-core: {e}")

# Test CrewAI imports (optional)
print("\nTesting CrewAI imports (optional)...")
try:
    from crewai import Agent
    print("✓ crewai")
except ImportError as e:
    print(f"✗ crewai: {e} (optional)")

try:
    import litellm
    print(f"✓ litellm {litellm.__version__}")
except ImportError as e:
    print(f"✗ litellm: {e} (optional)")

# Test psycopg
print("\nTesting PostgreSQL driver...")
try:
    import psycopg
    print(f"✓ psycopg")
except ImportError as e:
    print(f"✗ psycopg: {e}")

try:
    from psycopg_pool import AsyncConnectionPool
    print("✓ psycopg-pool")
except ImportError as e:
    print(f"✗ psycopg-pool: {e}")

print("\n" + "="*50)
print("Dependency test complete!")
print("="*50)
