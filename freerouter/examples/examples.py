#!/usr/bin/env python3
"""
FreeRouter v3 Example Usage

Demonstrates how to use FreeRouter with the OpenAI SDK.
Make sure FreeRouter is running: python -m freerouter
"""

import os
import sys

os.environ.setdefault("OPENAI_API_KEY", "any_key")
os.environ.setdefault("OPENAI_BASE_URL", "http://localhost:4000/v1")

from openai import OpenAI


def example_basic_chat():
    """Basic chat using auto route."""
    print("\n" + "=" * 60)
    print("Example 1: Basic Chat (auto route)")
    print("=" * 60)

    client = OpenAI(
        base_url="http://localhost:4000/v1",
        api_key="any_key"
    )

    response = client.chat.completions.create(
        model="auto",
        messages=[
            {"role": "user", "content": "What is the capital of France?"}
        ]
    )

    print(f"Question: What is the capital of France?")
    print(f"Answer: {response.choices[0].message.content}")


def example_script_writing():
    """Script writing example."""
    print("\n" + "=" * 60)
    print("Example 2: Script Writing")
    print("=" * 60)

    client = OpenAI(
        base_url="http://localhost:4000/v1",
        api_key="any_key"
    )

    response = client.chat.completions.create(
        model="script_writer",
        messages=[
            {"role": "user", "content": "Write a YouTube intro about black holes (2 paragraphs)"}
        ]
    )

    print("Question: Write a YouTube intro about black holes")
    print(f"\n{response.choices[0].message.content}")


def example_scoring():
    """Content scoring example."""
    print("\n" + "=" * 60)
    print("Example 3: Content Scoring")
    print("=" * 60)

    client = OpenAI(
        base_url="http://localhost:4000/v1",
        api_key="any_key"
    )

    response = client.chat.completions.create(
        model="scorer",
        messages=[
            {"role": "user", "content": "Rate this script on a scale of 1-10 and explain why:\n\nBlack holes are cool. They eat stars."}
        ]
    )

    print("Question: Rate a sample script")
    print(f"\n{response.choices[0].message.content}")


def example_topic_finding():
    """Topic finding example."""
    print("\n" + "=" * 60)
    print("Example 4: Topic Finding")
    print("=" * 60)

    client = OpenAI(
        base_url="http://localhost:4000/v1",
        api_key="any_key"
    )

    response = client.chat.completions.create(
        model="topic_finder",
        messages=[
            {"role": "user", "content": "Suggest 5 trending YouTube topics about artificial intelligence in 2025"}
        ]
    )

    print("Question: Suggest 5 trending AI topics")
    print(f"\n{response.choices[0].message.content}")


def example_streaming():
    """Streaming response example."""
    print("\n" + "=" * 60)
    print("Example 5: Streaming")
    print("=" * 60)

    client = OpenAI(
        base_url="http://localhost:4000/v1",
        api_key="any_key"
    )

    print("Question: Tell me a short story about a robot")
    print("\nResponse (streaming):\n")

    stream = client.chat.completions.create(
        model="auto",
        messages=[
            {"role": "user", "content": "Tell me a short story about a robot (3 sentences)"}
        ],
        stream=True
    )

    for chunk in stream:
        if chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print()


def example_annotator():
    """Annotator example — generates visual cues."""
    print("\n" + "=" * 60)
    print("Example 6: Visual Annotation")
    print("=" * 60)

    client = OpenAI(
        base_url="http://localhost:4000/v1",
        api_key="any_key"
    )

    response = client.chat.completions.create(
        model="annotator",
        messages=[
            {"role": "user", "content": "Generate a one-sentence visual cue for: \"The camera zooms into a galaxy\""}
        ]
    )

    print("Question: Generate visual cue for a galaxy zoom")
    print(f"\n{response.choices[0].message.content}")


def example_list_models():
    """List available models."""
    print("\n" + "=" * 60)
    print("Example 7: List Available Models")
    print("=" * 60)

    import httpx

    response = httpx.get("http://localhost:4000/v1/models")
    data = response.json()

    print("Available models:\n")
    for model in data.get("data", []):
        print(f"  {model['id']:15s} provider={model['owned_by']:12s} primary={model['primary']}")


def example_health_check():
    """Health check example."""
    print("\n" + "=" * 60)
    print("Example 8: Health Check")
    print("=" * 60)

    import httpx

    response = httpx.get("http://localhost:4000/health")
    health = response.json()

    print(f"Status:  {health.get('status')}")
    print(f"Version: {health.get('version')}")
    print(f"Tasks:   {', '.join(health.get('tasks', []))}")


def main():
    """Run all examples."""
    print("""
========================================================
  FreeRouter v3 Usage Examples
========================================================

Make sure FreeRouter is running:
  python -m freerouter

Available examples:
  1. Basic Chat (auto route)
  2. Script Writing
  3. Content Scoring
  4. Topic Finding
  5. Streaming
  6. Visual Annotation
  7. List Models
  8. Health Check
  0. Run all examples

""")

    choice = input("Select example (0-8, or 'q' to quit): ").strip().lower()

    if choice == 'q':
        return 0

    examples = {
        '1': example_basic_chat,
        '2': example_script_writing,
        '3': example_scoring,
        '4': example_topic_finding,
        '5': example_streaming,
        '6': example_annotator,
        '7': example_list_models,
        '8': example_health_check,
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
        print("  python -m freerouter")
        return 1

    print("\n" + "=" * 60)
    print("Examples completed!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
