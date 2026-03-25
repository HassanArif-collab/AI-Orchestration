#!/usr/bin/env python3
"""
FreeRouter Quick Start Script

This script helps you get started with FreeRouter quickly.
Run it to set up your environment and start the proxy.
"""

import os
import sys
import subprocess
from pathlib import Path


def print_banner():
    """Print startup banner."""
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ███████╗██████╗ ██╗  ██╗███████╗                           ║
║   ██╔════╝██╔══██╗██║  ██║██╔════╝                           ║
║   █████╗  ██████╔╝███████║█████╗                             ║
║   ██╔══╝  ██╔══██╗██╔══██║██╔══╝                             ║
║   ██║     ██║  ██║██║  ██║███████╗                           ║
║   ╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝                           ║
║                                                              ║
║   Smart LLM Proxy • Always Free First                       ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


def check_python_version():
    """Check Python version."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print("❌ Python 3.10+ is required. You have:", sys.version)
        return False
    print(f"✓ Python version: {version.major}.{version.minor}.{version.micro}")
    return True


def check_ollama():
    """Check if Ollama is installed and running."""
    try:
        import httpx
        response = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        if response.status_code == 200:
            print("✓ Ollama is running")
            return True
    except Exception:
        pass

    print("⚠ Ollama is not running. Start it with: ollama serve")
    return False


def check_env_file():
    """Check if .env file exists."""
    env_path = Path(__file__).parent / ".env"
    env_example = Path(__file__).parent / ".env.example"

    if env_path.exists():
        print("✓ .env file found")
        return True

    if env_example.exists():
        print("⚠ .env file not found. Creating from .env.example...")
        import shutil
        shutil.copy(env_example, env_path)
        print("✓ Created .env file. Please edit it to add your API keys.")
        return True

    print("⚠ No .env file found. Create one with your API keys.")
    return False


def check_api_keys():
    """Check for required API keys."""
    from dotenv import load_dotenv
    load_dotenv()

    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")

    keys_found = []

    if openrouter_key and openrouter_key != "your_openrouter_api_key_here":
        print("✓ OPENROUTER_API_KEY is set")
        keys_found.append("openrouter")

    if groq_key and groq_key != "your_groq_api_key_here":
        print("✓ GROQ_API_KEY is set")
        keys_found.append("groq")

    if not keys_found:
        print("⚠ No API keys found. Edit .env file to add:")
        print("  - OPENROUTER_API_KEY (get free key at https://openrouter.ai/keys)")
        print("  - GROQ_API_KEY (get free key at https://console.groq.com/keys)")
        return False

    return True


def install_dependencies():
    """Install dependencies if needed."""
    try:
        import litellm
        print("✓ Dependencies installed")
        return True
    except ImportError:
        print("Installing dependencies...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-e", "."], check=True)
        print("✓ Dependencies installed")
        return True


def pull_ollama_models():
    """Pull recommended Ollama models."""
    print("\nRecommended Ollama models:")
    print("  - qwen2.5:7b       (fast chat)")
    print("  - qwen2.5:14b     (smart chat)")
    print("  - qwen2.5-coder:32b (coding)")
    print("  - llama3.2-vision:11b (vision)")

    choice = input("\nPull recommended models now? (y/N): ").strip().lower()
    if choice == 'y':
        models = ["qwen2.5:7b", "qwen2.5-coder:32b"]
        for model in models:
            print(f"Pulling {model}...")
            subprocess.run(["ollama", "pull", model], check=False)
        print("✓ Models pulled")


def start_server():
    """Start the FreeRouter server."""
    print("\n" + "=" * 60)
    print("Starting FreeRouter...")
    print("=" * 60)
    print("\nServer will be available at: http://localhost:4000")
    print("API endpoint: http://localhost:4000/v1/chat/completions")
    print("Documentation: http://localhost:4000/docs")
    print("\nPress Ctrl+C to stop\n")

    # Import and run
    from freerouter.cli import app
    app(["start"])


def main():
    """Main entry point."""
    print_banner()

    checks = [
        ("Python version", check_python_version),
        ("Dependencies", install_dependencies),
        ("Environment file", check_env_file),
        ("API keys", check_api_keys),
        ("Ollama", check_ollama),
    ]

    print("\nChecking setup...\n")

    all_passed = True
    for name, check_func in checks:
        try:
            if not check_func():
                all_passed = False
        except Exception as e:
            print(f"✗ {name}: {e}")
            all_passed = False

    if not all_passed:
        print("\n⚠ Some checks failed. Fix issues above and try again.")
        print("Run: python quickstart.py")
        return 1

    print("\n✓ All checks passed!")

    # Pull models
    pull_ollama_models()

    # Start server
    try:
        start_server()
    except KeyboardInterrupt:
        print("\n\nFreeRouter stopped.")
    except Exception as e:
        print(f"\nError starting server: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())