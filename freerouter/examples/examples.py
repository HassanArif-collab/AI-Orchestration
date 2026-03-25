#!/usr/bin/env python3
"""
FreeRouter Example Usage

This file demonstrates how to use FreeRouter with OpenAI SDK.
Make sure FreeRouter is running: freerouter start
"""

import os
import sys

# You can also set these as environment variables
os.environ.setdefault("OPENAI_API_KEY", "any_key")  # FreeRouter doesn't require this
os.environ.setdefault("OPENAI_BASE_URL", "http://localhost:4000/v1")

from openai import OpenAI


def example_basic_chat():
    """Basic chat completion example."""
    print("\n" + "=" * 60)
    print("Example 1: Basic Chat")
    print("=" * 60)

    client = OpenAI(
        base_url="http://localhost:4000/v1",
        api_key="any_key"
    )

    response = client.chat.completions.create(
        model="free-router/fast",
        messages=[
            {"role": "user", "content": "What is the capital of France?"}
        ]
    )

    print(f"Question: What is the capital of France?")
    print(f"Answer: {response.choices[0].message.content}")


def example_coding():
    """Code generation example."""
    print("\n" + "=" * 60)
    print("Example 2: Code Generation")
    print("=" * 60)

    client = OpenAI(
        base_url="http://localhost:4000/v1",
        api_key="any_key"
    )

    response = client.chat.completions.create(
        model="free-router/coder",
        messages=[
            {"role": "user", "content": "Write a Python function to implement binary search"}
        ]
    )

    print("Question: Write a Python function to implement binary search")
    print(f"\n{response.choices[0].message.content}")


def example_auto_routing():
    """Auto-routing example - let FreeRouter choose the model."""
    print("\n" + "=" * 60)
    print("Example 3: Auto-Routing")
    print("=" * 60)

    client = OpenAI(
        base_url="http://localhost:4000/v1",
        api_key="any_key"
    )

    test_messages = [
        "What's the weather like today?",  # simple_chat -> fast
        "Write a function to sort a list",  # coding -> coder
        "If x + 5 = 15, what is x?",       # reasoning -> reasoning
    ]

    for msg in test_messages:
        response = client.chat.completions.create(
            model="free-router/auto",  # Auto-select model
            messages=[{"role": "user", "content": msg}]
        )
        print(f"\nUser: {msg}")
        print(f"Response: {response.choices[0].message.content[:100]}...")


def example_streaming():
    """Streaming response example."""
    print("\n" + "=" * 60)
    print("Example 4: Streaming")
    print("=" * 60)

    client = OpenAI(
        base_url="http://localhost:4000/v1",
        api_key="any_key"
    )

    print("Question: Tell me a short story about a robot")
    print("\nResponse (streaming):\n")

    stream = client.chat.completions.create(
        model="free-router/fast",
        messages=[
            {"role": "user", "content": "Tell me a short story about a robot (3 sentences)"}
        ],
        stream=True
    )

    for chunk in stream:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print()


def example_conversation():
    """Multi-turn conversation example."""
    print("\n" + "=" * 60)
    print("Example 5: Multi-Turn Conversation")
    print("=" * 60)

    client = OpenAI(
        base_url="http://localhost:4000/v1",
        api_key="any_key"
    )

    messages = [
        {"role": "system", "content": "You are a helpful coding assistant."},
        {"role": "user", "content": "What is a linked list?"},
    ]

    response = client.chat.completions.create(
        model="free-router/smart",
        messages=messages
    )

    print("User: What is a linked list?")
    print(f"Assistant: {response.choices[0].message.content[:200]}...")

    # Continue conversation
    messages.append({"role": "assistant", "content": response.choices[0].message.content})
    messages.append({"role": "user", "content": "Can you show me how to implement one in Python?"})

    response = client.chat.completions.create(
        model="free-router/smart",
        messages=messages
    )

    print("\nUser: Can you show me how to implement one in Python?")
    print(f"Assistant: {response.choices[0].message.content[:300]}...")


def example_list_models():
    """List available models."""
    print("\n" + "=" * 60)
    print("Example 6: List Available Models")
    print("=" * 60)

    import httpx

    response = httpx.get("http://localhost:4000/v1/models")
    models = response.json()

    print("Available models:\n")
    for model in models.get("data", [])[:10]:
        model_id = model.get("id", "unknown")
        print(f"  - {model_id}")

    if len(models.get("data", [])) > 10:
        print(f"  ... and {len(models['data']) - 10} more")


def example_health_check():
    """Health check example."""
    print("\n" + "=" * 60)
    print("Example 7: Health Check")
    print("=" * 60)

    import httpx

    response = httpx.get("http://localhost:4000/health")
    health = response.json()

    print(f"Status: {health.get('status')}")
    print(f"Version: {health.get('version')}")

    providers = health.get("providers", {})
    for provider, status in providers.items():
        print(f"  {provider}: {status.get('status')} ({status.get('latency_ms', 0):.1f}ms)")


def example_vision():
    """Vision example (requires vision-capable model and Ollama)."""
    print("\n" + "=" * 60)
    print("Example 8: Vision (Image Analysis)")
    print("=" * 60)

    client = OpenAI(
        base_url="http://localhost:4000/v1",
        api_key="any_key"
    )

    # Example with a URL
    response = client.chat.completions.create(
        model="free-router/vision",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "What's in this image?"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg"
                        }
                    }
                ]
            }
        ]
    )

    print("Question: What's in this image?")
    print(f"Answer: {response.choices[0].message.content[:200]}...")


def main():
    """Run all examples."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                  FreeRouter Usage Examples                   ║
╚══════════════════════════════════════════════════════════════╝

Make sure FreeRouter is running: freerouter start

Available examples:
  1. Basic Chat
  2. Code Generation
  3. Auto-Routing
  4. Streaming
  5. Multi-Turn Conversation
  6. List Models
  7. Health Check
  8. Vision (requires Ollama with vision model)
  0. Run all examples

""")

    choice = input("Select example (0-8, or 'q' to quit): ").strip().lower()

    if choice == 'q':
        return 0

    examples = {
        '1': example_basic_chat,
        '2': example_coding,
        '3': example_auto_routing,
        '4': example_streaming,
        '5': example_conversation,
        '6': example_list_models,
        '7': example_health_check,
        '8': example_vision,
    }

    try:
        if choice == '0':
            for example in examples.values():
                example()
        elif choice in examples:
            examples[choice]()
        else:
            print("Invalid choice. Running basic chat example...")
            example_basic_chat()
    except Exception as e:
        print(f"\nError: {e}")
        print("\nMake sure FreeRouter is running:")
        print("  freerouter start")
        return 1

    print("\n" + "=" * 60)
    print("Examples completed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())