"""
Dynamic Configuration Manager for FreeRouter.

Allows runtime modification of model aliases and fallback chains.
Changes are persisted to the YAML config file.
"""

import os
import json
import yaml
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class ModelAlias:
    """Represents a model alias configuration."""
    name: str  # e.g., "free-router/coder"
    model: str  # e.g., "ollama/qwen2.5-coder:32b"
    api_base: Optional[str] = None  # e.g., "http://localhost:11434"
    api_key: Optional[str] = None  # e.g., "os.environ/GROQ_API_KEY"
    timeout: int = 60
    max_tokens: int = 8192
    description: str = ""
    supports_vision: bool = False
    provider: str = ""  # Derived from model prefix
    is_fallback: bool = False  # Is this a fallback model?
    

@dataclass
class FallbackChain:
    """Represents a fallback chain for a model."""
    primary_model: str
    fallbacks: List[str] = field(default_factory=list)


class ConfigManager:
    """Manages dynamic configuration for FreeRouter."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or self._find_config_path()
        self._config: Dict[str, Any] = {}
        self._model_aliases: Dict[str, ModelAlias] = {}
        self._fallback_chains: Dict[str, FallbackChain] = {}
        self._backups_dir = self.config_path.parent / "backups"
        self._load_config()
    
    def _find_config_path(self) -> Path:
        """Find the configuration file path."""
        custom_path = os.getenv("FREEROUTER_CONFIG")
        if custom_path:
            return Path(custom_path)
        
        possible_paths = [
            Path.cwd() / "config" / "proxy_server_config.yaml",
            Path(__file__).parent.parent.parent / "config" / "proxy_server_config.yaml",
            Path(__file__).parent.parent.parent.parent / "config" / "proxy_server_config.yaml",
        ]
        
        for path in possible_paths:
            if path.exists():
                return path
        
        # Default
        return Path(__file__).parent.parent.parent / "config" / "proxy_server_config.yaml"
    
    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            self._create_default_config()
            return
        
        with open(self.config_path, 'r') as f:
            self._config = yaml.safe_load(f) or {}
        
        # Parse model list
        self._parse_model_list()
        
        # Parse fallbacks
        self._parse_fallbacks()
    
    def _create_default_config(self) -> None:
        """Create a default configuration file."""
        self._config = {
            'model_list': [],
            'fallbacks': [],
            'router_settings': {
                'routing_strategy': 'simple-shuffle',
                'num_retries': 3,
                'timeout': 300,
            },
            'general_settings': {
                'master_key': 'os.environ/FREEROUTER_API_KEY',
            },
            'litellm_settings': {
                'set_verbose': True,
                'drop_params': True,
            },
        }
        self._save_config()
    
    def _parse_model_list(self) -> None:
        """Parse model_list into ModelAlias objects."""
        self._model_aliases = {}
        
        for model_entry in self._config.get('model_list', []):
            model_name = model_entry.get('model_name', '')
            litellm_params = model_entry.get('litellm_params', {})
            model_info = model_entry.get('model_info', {})
            
            # Extract model string
            model = litellm_params.get('model', '')
            
            # Determine provider from model prefix
            provider = self._get_provider_from_model(model)
            
            alias = ModelAlias(
                name=model_name,
                model=model,
                api_base=litellm_params.get('api_base'),
                api_key=litellm_params.get('api_key'),
                timeout=litellm_params.get('timeout', 60),
                max_tokens=model_info.get('max_tokens', 8192),
                description=model_info.get('description', ''),
                supports_vision=model_info.get('supports_vision', False),
                provider=provider,
                is_fallback=self._is_fallback_model(model_name),
            )
            
            self._model_aliases[model_name] = alias
    
    def _parse_fallbacks(self) -> None:
        """Parse fallbacks into FallbackChain objects."""
        self._fallback_chains = {}
        
        for fallback_entry in self._config.get('fallbacks', []):
            primary = fallback_entry.get('model', '')
            fallback_list = fallback_entry.get('fallbacks', [])
            
            if primary:
                self._fallback_chains[primary] = FallbackChain(
                    primary_model=primary,
                    fallbacks=fallback_list,
                )
    
    def _get_provider_from_model(self, model: str) -> str:
        """Extract provider from model string."""
        if model.startswith('ollama/'):
            return 'ollama'
        elif model.startswith('groq/'):
            return 'groq'
        elif model.startswith('openrouter/'):
            return 'openrouter'
        elif model.startswith('anthropic/'):
            return 'anthropic'
        elif model.startswith('openai/'):
            return 'openai'
        elif model.startswith('together_ai/'):
            return 'together'
        elif model.startswith('deepinfra/'):
            return 'deepinfra'
        return 'unknown'
    
    def _is_fallback_model(self, model_name: str) -> bool:
        """Check if a model is only used as a fallback."""
        # A model is a fallback if it's not a primary model in any fallback chain
        # and its name contains a suffix like "-groq", "-openrouter", etc.
        primary_models = set(self._fallback_chains.keys())
        return model_name not in primary_models and '-' in model_name.split('/')[-1]
    
    # ─── Backup Management ─────────────────────────────────────────────────────
    
    def create_backup(self) -> str:
        """Create a backup of the current configuration."""
        self._backups_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"config_backup_{timestamp}.yaml"
        backup_path = self._backups_dir / backup_name
        
        shutil.copy2(self.config_path, backup_path)
        
        return str(backup_path)
    
    def restore_backup(self, backup_path: str) -> bool:
        """Restore configuration from a backup."""
        backup = Path(backup_path)
        if not backup.exists():
            return False
        
        shutil.copy2(backup, self.config_path)
        self._load_config()
        return True
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups."""
        if not self._backups_dir.exists():
            return []
        
        backups = []
        for backup_file in sorted(self._backups_dir.glob("config_backup_*.yaml"), reverse=True):
            stat = backup_file.stat()
            backups.append({
                'path': str(backup_file),
                'name': backup_file.name,
                'created': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'size': stat.st_size,
            })
        
        return backups
    
    # ─── Model Alias Management ─────────────────────────────────────────────────
    
    def list_aliases(self) -> List[ModelAlias]:
        """List all model aliases."""
        return list(self._model_aliases.values())
    
    def get_alias(self, name: str) -> Optional[ModelAlias]:
        """Get a specific model alias."""
        return self._model_aliases.get(name)
    
    def create_alias(self, alias: ModelAlias) -> ModelAlias:
        """Create a new model alias."""
        if alias.name in self._model_aliases:
            raise ValueError(f"Alias '{alias.name}' already exists")
        
        self._model_aliases[alias.name] = alias
        self._sync_to_config()
        self._save_config()
        
        return alias
    
    def update_alias(self, name: str, **kwargs) -> Optional[ModelAlias]:
        """Update an existing model alias."""
        if name not in self._model_aliases:
            return None
        
        alias = self._model_aliases[name]
        
        for key, value in kwargs.items():
            if hasattr(alias, key) and value is not None:
                setattr(alias, key, value)
        
        self._sync_to_config()
        self._save_config()
        
        return alias
    
    def delete_alias(self, name: str) -> bool:
        """Delete a model alias."""
        if name not in self._model_aliases:
            return False
        
        del self._model_aliases[name]
        
        # Also remove from fallback chains
        if name in self._fallback_chains:
            del self._fallback_chains[name]
        
        for chain in self._fallback_chains.values():
            if name in chain.fallbacks:
                chain.fallbacks.remove(name)
        
        self._sync_to_config()
        self._save_config()
        
        return True
    
    # ─── Fallback Chain Management ──────────────────────────────────────────────
    
    def list_fallback_chains(self) -> List[FallbackChain]:
        """List all fallback chains."""
        return list(self._fallback_chains.values())
    
    def get_fallback_chain(self, model: str) -> Optional[FallbackChain]:
        """Get the fallback chain for a specific model."""
        return self._fallback_chains.get(model)
    
    def set_fallback_chain(self, primary_model: str, fallbacks: List[str]) -> FallbackChain:
        """Set the fallback chain for a model."""
        chain = FallbackChain(
            primary_model=primary_model,
            fallbacks=fallbacks,
        )
        self._fallback_chains[primary_model] = chain
        self._sync_to_config()
        self._save_config()
        
        return chain
    
    def delete_fallback_chain(self, model: str) -> bool:
        """Delete a fallback chain."""
        if model not in self._fallback_chains:
            return False
        
        del self._fallback_chains[model]
        self._sync_to_config()
        self._save_config()
        
        return True
    
    # ─── Config Synchronization ──────────────────────────────────────────────────
    
    def _sync_to_config(self) -> None:
        """Sync model aliases and fallback chains back to config dict."""
        # Rebuild model_list
        model_list = []
        
        for alias in self._model_aliases.values():
            model_entry = {
                'model_name': alias.name,
                'litellm_params': {
                    'model': alias.model,
                    'timeout': alias.timeout,
                },
                'model_info': {
                    'description': alias.description,
                    'max_tokens': alias.max_tokens,
                    'supports_vision': alias.supports_vision,
                },
            }
            
            if alias.api_base:
                model_entry['litellm_params']['api_base'] = alias.api_base
            if alias.api_key:
                model_entry['litellm_params']['api_key'] = alias.api_key
            
            model_list.append(model_entry)
        
        self._config['model_list'] = model_list
        
        # Rebuild fallbacks
        fallbacks = []
        for chain in self._fallback_chains.values():
            fallbacks.append({
                'model': chain.primary_model,
                'fallbacks': chain.fallbacks,
            })
        
        self._config['fallbacks'] = fallbacks
    
    def _save_config(self) -> None:
        """Save configuration to YAML file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.config_path, 'w') as f:
            yaml.dump(self._config, f, default_flow_style=False, sort_keys=False)
    
    # ─── Export/Import ───────────────────────────────────────────────────────────
    
    def export_config(self) -> Dict[str, Any]:
        """Export the full configuration as a dictionary."""
        return {
            'model_aliases': {
                name: {
                    'name': alias.name,
                    'model': alias.model,
                    'provider': alias.provider,
                    'api_base': alias.api_base,
                    'timeout': alias.timeout,
                    'max_tokens': alias.max_tokens,
                    'description': alias.description,
                    'supports_vision': alias.supports_vision,
                    'is_fallback': alias.is_fallback,
                }
                for name, alias in self._model_aliases.items()
            },
            'fallback_chains': {
                model: {
                    'primary_model': chain.primary_model,
                    'fallbacks': chain.fallbacks,
                }
                for model, chain in self._fallback_chains.items()
            },
            'router_settings': self._config.get('router_settings', {}),
            'general_settings': self._config.get('general_settings', {}),
        }
    
    def import_aliases(self, aliases_data: List[Dict[str, Any]]) -> int:
        """Import multiple model aliases."""
        count = 0
        for alias_data in aliases_data:
            try:
                alias = ModelAlias(
                    name=alias_data['name'],
                    model=alias_data['model'],
                    api_base=alias_data.get('api_base'),
                    api_key=alias_data.get('api_key'),
                    timeout=alias_data.get('timeout', 60),
                    max_tokens=alias_data.get('max_tokens', 8192),
                    description=alias_data.get('description', ''),
                    supports_vision=alias_data.get('supports_vision', False),
                    provider=alias_data.get('provider', ''),
                )
                self._model_aliases[alias.name] = alias
                count += 1
            except Exception as e:
                print(f"Error importing alias {alias_data.get('name')}: {e}")
        
        self._sync_to_config()
        self._save_config()
        
        return count
    
    # ─── Grouped Model Listing ───────────────────────────────────────────────────
    
    def get_model_groups(self) -> Dict[str, List[ModelAlias]]:
        """Get models grouped by their base type (fast, coder, etc.)."""
        groups: Dict[str, List[ModelAlias]] = {}
        
        for alias in self._model_aliases.values():
            # Extract base name (e.g., "fast" from "free-router/fast-groq")
            name_parts = alias.name.replace('free-router/', '').split('-')
            base_name = name_parts[0] if name_parts else 'other'
            
            if base_name not in groups:
                groups[base_name] = []
            
            groups[base_name].append(alias)
        
        return groups
    
    def get_primary_models(self) -> List[ModelAlias]:
        """Get all primary (non-fallback) models."""
        return [a for a in self._model_aliases.values() if not a.is_fallback]
    
    def get_available_providers(self) -> List[str]:
        """Get list of all providers used in configuration."""
        providers = set()
        for alias in self._model_aliases.values():
            if alias.provider:
                providers.add(alias.provider)
        return sorted(list(providers))
    
    # ─── Runtime Info ───────────────────────────────────────────────────────────
    
    def get_config_info(self) -> Dict[str, Any]:
        """Get information about the current configuration."""
        return {
            'config_path': str(self.config_path),
            'total_models': len(self._model_aliases),
            'primary_models': len(self.get_primary_models()),
            'fallback_chains': len(self._fallback_chains),
            'providers': self.get_available_providers(),
            'model_groups': list(self.get_model_groups().keys()),
            'backups': len(self.list_backups()),
        }


# ─── Global Instance ────────────────────────────────────────────────────────────

_config_manager: Optional[ConfigManager] = None

def get_config_manager() -> ConfigManager:
    """Get the global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager