"""
Provider Instance Management for FreeRouter.

Supports multiple instances of the same provider type (e.g., Ollama Local + Ollama Cloud).
This allows users to configure both local and cloud versions of providers.
"""

import os
import json
import time
import uuid
import asyncio
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum

import httpx


# ─── Provider Instance Model ────────────────────────────────────────────────────

class InstanceType(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"


@dataclass
class ProviderInstance:
    """A configured instance of a provider (e.g., 'Ollama Local', 'Ollama Cloud')."""
    id: str  # Unique identifier (UUID)
    provider_type: str  # Base provider type: "ollama", "groq", "openrouter", etc.
    name: str  # User-friendly name: "Ollama Local", "My Groq Account"
    instance_type: InstanceType  # local or cloud
    base_url: str  # API endpoint URL
    api_key: Optional[str] = None  # API key (masked when returned)
    is_active: bool = True  # Whether this instance is enabled
    priority: int = 100  # Lower = higher priority (used for fallback ordering)
    models: List[str] = field(default_factory=list)  # Available models (cached)
    last_health_check: Optional[float] = None
    is_healthy: bool = False
    health_message: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self, mask_key: bool = True) -> Dict[str, Any]:
        """Convert to dictionary, optionally masking the API key."""
        data = asdict(self)
        data['instance_type'] = self.instance_type.value
        if mask_key and self.api_key:
            # Show only first 8 and last 4 characters
            if len(self.api_key) > 12:
                data['api_key'] = f"{self.api_key[:8]}...{self.api_key[-4:]}"
            else:
                data['api_key'] = "****"
        return data


# ─── Default Provider Configurations ────────────────────────────────────────────

# Default configurations for each provider type
PROVIDER_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "ollama": {
        "name": "Ollama",
        "instance_types": {
            "local": {
                "base_url": "http://localhost:11434",
                "requires_auth": False,
            },
            "cloud": {
                "base_url": "https://api.ollama.ai",  # Hypothetical cloud API
                "requires_auth": True,
            }
        },
        "litellm_prefix": "ollama/",
        "health_endpoint": "/api/tags",
        "models_endpoint": "/api/tags",
        "signup_url": "https://ollama.ai",
        "cloud_signup_url": "https://ollama.ai/api-keys",  # Hypothetical
        "icon": "🖥️",
    },
    "groq": {
        "name": "Groq",
        "instance_types": {
            "cloud": {
                "base_url": "https://api.groq.com/openai/v1",
                "requires_auth": True,
            }
        },
        "litellm_prefix": "groq/",
        "health_endpoint": "/models",
        "models_endpoint": "/models",
        "signup_url": "https://console.groq.com/keys",
        "icon": "⚡",
    },
    "openrouter": {
        "name": "OpenRouter",
        "instance_types": {
            "cloud": {
                "base_url": "https://openrouter.ai/api/v1",
                "requires_auth": True,
            }
        },
        "litellm_prefix": "openrouter/",
        "health_endpoint": "/models",
        "models_endpoint": "/models",
        "signup_url": "https://openrouter.ai/keys",
        "icon": "☁️",
    },
    "anthropic": {
        "name": "Anthropic",
        "instance_types": {
            "cloud": {
                "base_url": "https://api.anthropic.com/v1",
                "requires_auth": True,
            }
        },
        "litellm_prefix": "anthropic/",
        "health_endpoint": "/models",
        "models_endpoint": "/models",
        "signup_url": "https://console.anthropic.com/account/keys",
        "icon": "🤖",
    },
    "openai": {
        "name": "OpenAI",
        "instance_types": {
            "cloud": {
                "base_url": "https://api.openai.com/v1",
                "requires_auth": True,
            }
        },
        "litellm_prefix": "openai/",
        "health_endpoint": "/models",
        "models_endpoint": "/models",
        "signup_url": "https://platform.openai.com/api-keys",
        "icon": "🧠",
    },
    "together": {
        "name": "Together AI",
        "instance_types": {
            "cloud": {
                "base_url": "https://api.together.xyz/v1",
                "requires_auth": True,
            }
        },
        "litellm_prefix": "together_ai/",
        "health_endpoint": "/models",
        "models_endpoint": "/models",
        "signup_url": "https://api.together.ai/settings/api-keys",
        "icon": "🔗",
    },
    "deepinfra": {
        "name": "DeepInfra",
        "instance_types": {
            "cloud": {
                "base_url": "https://api.deepinfra.com/v1/openai",
                "requires_auth": True,
            }
        },
        "litellm_prefix": "deepinfra/",
        "health_endpoint": "/models",
        "models_endpoint": "/models",
        "signup_url": "https://deepinfra.com/dash?ref=gh",
        "icon": "🔧",
    },
    "custom": {
        "name": "Custom Provider",
        "instance_types": {
            "cloud": {
                "base_url": "",
                "requires_auth": True,
            }
        },
        "litellm_prefix": "",
        "health_endpoint": "/models",
        "models_endpoint": "/models",
        "signup_url": "",
        "icon": "⚙️",
    },
}


# ─── Instance Manager ──────────────────────────────────────────────────────────

class ProviderInstanceManager:
    """Manages provider instances with CRUD operations."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or (Path(__file__).parent.parent.parent / "state")
        self.instances_file = self.config_dir / "provider_instances.json"
        self._instances: Dict[str, ProviderInstance] = {}
        self._load_instances()
    
    def _load_instances(self) -> None:
        """Load instances from JSON file."""
        if self.instances_file.exists():
            try:
                with open(self.instances_file, 'r') as f:
                    data = json.load(f)
                    for item in data.get('instances', []):
                        instance = ProviderInstance(
                            id=item['id'],
                            provider_type=item['provider_type'],
                            name=item['name'],
                            instance_type=InstanceType(item['instance_type']),
                            base_url=item['base_url'],
                            api_key=item.get('api_key'),
                            is_active=item.get('is_active', True),
                            priority=item.get('priority', 100),
                            models=item.get('models', []),
                            last_health_check=item.get('last_health_check'),
                            is_healthy=item.get('is_healthy', False),
                            health_message=item.get('health_message', ''),
                            created_at=item.get('created_at', time.time()),
                            updated_at=item.get('updated_at', time.time()),
                        )
                        self._instances[instance.id] = instance
            except Exception as e:
                print(f"Warning: Could not load instances: {e}")
        
        # Ensure default instances exist
        self._ensure_default_instances()
    
    def _ensure_default_instances(self) -> None:
        """Create default instances if none exist."""
        if not self._instances:
            # Create default Ollama local instance
            ollama_local = ProviderInstance(
                id=str(uuid.uuid4()),
                provider_type="ollama",
                name="Ollama Local",
                instance_type=InstanceType.LOCAL,
                base_url="http://localhost:11434",
                api_key=None,
                is_active=True,
                priority=10,  # Highest priority (local is free)
            )
            self._instances[ollama_local.id] = ollama_local
            self._save_instances()
    
    def _save_instances(self) -> None:
        """Save instances to JSON file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        data = {
            'instances': [inst.to_dict(mask_key=False) for inst in self._instances.values()],
            'version': 1,
        }
        with open(self.instances_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    # ─── CRUD Operations ────────────────────────────────────────────────────────
    
    def list_instances(self, provider_type: Optional[str] = None) -> List[ProviderInstance]:
        """List all instances, optionally filtered by provider type."""
        instances = list(self._instances.values())
        if provider_type:
            instances = [i for i in instances if i.provider_type == provider_type]
        return sorted(instances, key=lambda x: x.priority)
    
    def get_instance(self, instance_id: str) -> Optional[ProviderInstance]:
        """Get a specific instance by ID."""
        return self._instances.get(instance_id)
    
    def create_instance(
        self,
        provider_type: str,
        name: str,
        instance_type: InstanceType,
        base_url: str,
        api_key: Optional[str] = None,
        priority: int = 100,
        is_active: bool = True,
    ) -> ProviderInstance:
        """Create a new provider instance."""
        instance = ProviderInstance(
            id=str(uuid.uuid4()),
            provider_type=provider_type,
            name=name,
            instance_type=instance_type,
            base_url=base_url,
            api_key=api_key,
            priority=priority,
            is_active=is_active,
        )
        self._instances[instance.id] = instance
        self._save_instances()
        return instance
    
    def update_instance(
        self,
        instance_id: str,
        name: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        priority: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> Optional[ProviderInstance]:
        """Update an existing instance."""
        instance = self._instances.get(instance_id)
        if not instance:
            return None
        
        if name is not None:
            instance.name = name
        if base_url is not None:
            instance.base_url = base_url
        if api_key is not None:
            instance.api_key = api_key
        if priority is not None:
            instance.priority = priority
        if is_active is not None:
            instance.is_active = is_active
        
        instance.updated_at = time.time()
        self._save_instances()
        return instance
    
    def delete_instance(self, instance_id: str) -> bool:
        """Delete an instance."""
        if instance_id in self._instances:
            del self._instances[instance_id]
            self._save_instances()
            return True
        return False
    
    # ─── Health & Models ────────────────────────────────────────────────────────
    
    async def check_health(self, instance_id: str) -> tuple[bool, str]:
        """Check if a provider instance is healthy and reachable."""
        instance = self._instances.get(instance_id)
        if not instance:
            return False, "Instance not found"
        
        provider_defaults = PROVIDER_DEFAULTS.get(instance.provider_type, {})
        health_endpoint = provider_defaults.get('health_endpoint', '/health')
        
        headers = {}
        if instance.api_key:
            headers['Authorization'] = f'Bearer {instance.api_key}'
        
        url = f"{instance.base_url.rstrip('/')}{health_endpoint}"
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    instance.is_healthy = True
                    instance.health_message = "OK"
                    instance.last_health_check = time.time()
                    self._save_instances()
                    return True, "OK"
                elif response.status_code in (401, 403):
                    instance.is_healthy = False
                    instance.health_message = "Invalid API Key"
                    instance.last_health_check = time.time()
                    self._save_instances()
                    return False, "Invalid API Key"
                else:
                    instance.is_healthy = False
                    instance.health_message = f"HTTP {response.status_code}"
                    instance.last_health_check = time.time()
                    self._save_instances()
                    return False, f"HTTP {response.status_code}"
                    
        except httpx.ConnectError:
            instance.is_healthy = False
            instance.health_message = "Connection refused"
            instance.last_health_check = time.time()
            self._save_instances()
            return False, "Connection refused"
        except httpx.TimeoutException:
            instance.is_healthy = False
            instance.health_message = "Timeout"
            instance.last_health_check = time.time()
            self._save_instances()
            return False, "Timeout"
        except Exception as e:
            instance.is_healthy = False
            instance.health_message = str(e)
            instance.last_health_check = time.time()
            self._save_instances()
            return False, str(e)
    
    async def fetch_models(self, instance_id: str) -> List[Dict[str, Any]]:
        """Fetch available models from a provider instance."""
        instance = self._instances.get(instance_id)
        if not instance:
            return []
        
        provider_defaults = PROVIDER_DEFAULTS.get(instance.provider_type, {})
        models_endpoint = provider_defaults.get('models_endpoint', '/models')
        
        headers = {}
        if instance.api_key:
            headers['Authorization'] = f'Bearer {instance.api_key}'
        
        url = f"{instance.base_url.rstrip('/')}{models_endpoint}"
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Handle different response formats
                    models = []
                    if isinstance(data, list):
                        models = data
                    elif isinstance(data, dict):
                        if 'data' in data:
                            models = data['data']
                        elif 'models' in data:
                            models = data['models']
                    
                    # Extract model IDs
                    model_ids = []
                    for m in models:
                        if isinstance(m, dict):
                            model_ids.append({
                                'id': m.get('id') or m.get('name') or m.get('model'),
                                'name': m.get('name') or m.get('id'),
                                'size': m.get('size'),
                                'modified': m.get('modified_at') or m.get('modified'),
                            })
                        elif isinstance(m, str):
                            model_ids.append({'id': m, 'name': m})
                    
                    # Update instance cache
                    instance.models = [m['id'] for m in model_ids if m.get('id')]
                    self._save_instances()
                    
                    return model_ids
                else:
                    return []
                    
        except Exception as e:
            print(f"Error fetching models: {e}")
            return []
    
    async def pull_model(self, instance_id: str, model_name: str) -> tuple[bool, str]:
        """Pull a model on a provider instance (Ollama only for now)."""
        instance = self._instances.get(instance_id)
        if not instance:
            return False, "Instance not found"
        
        if instance.provider_type != "ollama":
            return False, "Model pulling is only supported for Ollama"
        
        url = f"{instance.base_url.rstrip('/')}/api/pull"
        
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(url, json={"name": model_name})
                
                if response.status_code == 200:
                    # Refresh models list
                    await self.fetch_models(instance_id)
                    return True, f"Model '{model_name}' pulled successfully"
                else:
                    return False, f"Failed to pull model: HTTP {response.status_code}"
                    
        except Exception as e:
            return False, f"Error pulling model: {str(e)}"
    
    # ─── Utility Methods ────────────────────────────────────────────────────────
    
    def get_active_instances(self, provider_type: Optional[str] = None) -> List[ProviderInstance]:
        """Get all active instances, optionally filtered by provider type."""
        instances = [i for i in self._instances.values() if i.is_active]
        if provider_type:
            instances = [i for i in instances if i.provider_type == provider_type]
        return sorted(instances, key=lambda x: x.priority)
    
    def get_healthy_instances(self, provider_type: Optional[str] = None) -> List[ProviderInstance]:
        """Get all healthy instances, optionally filtered by provider type."""
        instances = [i for i in self._instances.values() if i.is_active and i.is_healthy]
        if provider_type:
            instances = [i for i in instances if i.provider_type == provider_type]
        return sorted(instances, key=lambda x: x.priority)
    
    def get_provider_types(self) -> List[Dict[str, Any]]:
        """Get all supported provider types with their configurations."""
        return [
            {
                'type': ptype,
                'name': config['name'],
                'icon': config['icon'],
                'instance_types': list(config['instance_types'].keys()),
                'signup_url': config.get('signup_url', ''),
                'cloud_signup_url': config.get('cloud_signup_url', ''),
                'default_base_urls': config['instance_types'],
            }
            for ptype, config in PROVIDER_DEFAULTS.items()
        ]


# ─── Global Instance ────────────────────────────────────────────────────────────

_manager: Optional[ProviderInstanceManager] = None

def get_manager() -> ProviderInstanceManager:
    """Get the global provider instance manager."""
    global _manager
    if _manager is None:
        _manager = ProviderInstanceManager()
    return _manager