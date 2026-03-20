"""Configuration management for FreeRouter."""

import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_config_path() -> Path:
    """Get the path to the proxy configuration file."""
    # Check for custom config path
    custom_path = os.getenv("FREEROUTER_CONFIG")
    if custom_path:
        return Path(custom_path)

    # Default locations
    possible_paths = [
        Path.cwd() / "proxy_server_config.yaml",
        Path(__file__).parent.parent.parent / "config" / "proxy_server_config.yaml",
        Path(__file__).parent.parent.parent / "proxy_server_config.yaml",
    ]

    for path in possible_paths:
        if path.exists():
            return path

    # Return default if none found
    return Path(__file__).parent.parent.parent / "config" / "proxy_server_config.yaml"


def load_config() -> dict:
    """Load and parse the configuration file."""
    config_path = get_config_path()

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    return config


def get_model_aliases() -> dict[str, str]:
    """Get all available model aliases."""
    config = load_config()
    aliases = {}

    for model in config.get("model_list", []):
        model_alias = model.get("model_name")
        actual_model = model.get("litellm_params", {}).get("model")
        if model_alias and actual_model:
            aliases[model_alias] = actual_model

    return aliases


def validate_environment() -> dict[str, bool]:
    """Validate that required environment variables are set."""
    required_vars = {
        "OPENROUTER_API_KEY": os.getenv("OPENROUTER_API_KEY"),
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY"),
    }

    optional_vars = {
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY"),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "TOGETHER_AI_API_KEY": os.getenv("TOGETHER_AI_API_KEY"),
        "DEEPINFRA_API_KEY": os.getenv("DEEPINFRA_API_KEY"),
    }

    return {
        "required_set": all(required_vars.values()),
        "openrouter": bool(required_vars["OPENROUTER_API_KEY"]),
        "groq": bool(required_vars["GROQ_API_KEY"]),
        "anthropic": bool(optional_vars["ANTHROPIC_API_KEY"]),
        "openai": bool(optional_vars["OPENAI_API_KEY"]),
        "together": bool(optional_vars["TOGETHER_AI_API_KEY"]),
        "deepinfra": bool(optional_vars["DEEPINFRA_API_KEY"]),
    }