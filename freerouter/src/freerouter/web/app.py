"""
FreeRouter Web Dashboard - FastAPI Application.

Provides a browser-based UI for managing providers, testing chat,
and viewing usage statistics.
"""

import os
import asyncio
import json
import base64
import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel
import httpx

from freerouter.providers import (
    KNOWN_PROVIDERS, PROVIDER_MAP, get_linked_providers, 
    save_api_key, check_provider_reachable, get_all_usage, ProviderType
)
from freerouter.provider_instances import (
    get_manager, ProviderInstance, InstanceType, PROVIDER_DEFAULTS
)
from freerouter.config_manager import (
    get_config_manager, ModelAlias, FallbackChain
)

logger = logging.getLogger(__name__)



# ─── Pydantic Models ────────────────────────────────────────────────────────────

class CreateInstanceRequest(BaseModel):
    provider_type: str
    name: str
    instance_type: str  # "local" or "cloud"
    base_url: str
    api_key: Optional[str] = None
    priority: int = 100
    is_active: bool = True


class UpdateInstanceRequest(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None


class PullModelRequest(BaseModel):
    model_name: str


# ─── App Factory ────────────────────────────────────────────────────────────────

def create_web_app() -> FastAPI:
    """Create and configure the FastAPI web application."""
    app = FastAPI(
        title="FreeRouter Dashboard",
        description="Web dashboard for FreeRouter - AI Provider Management",
        version="1.0.0",
    )
    
    # Mount static files
    static_dir = Path(__file__).parent / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    
    # ─── HTML Routes ────────────────────────────────────────────────────────────
    
    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        """Serve the main dashboard HTML."""
        html_path = static_dir / "index.html"
        if html_path.exists():
            return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
        
        # Return inline HTML if file doesn't exist
        return HTMLResponse(content=get_dashboard_html())
    
    # ─── Provider Types API ─────────────────────────────────────────────────────
    
    @app.get("/api/providers/types")
    async def get_provider_types():
        """Get all supported provider types with their configurations."""
        manager = get_manager()
        return {
            "types": manager.get_provider_types()
        }
    
    # ─── Legacy Provider API (for backwards compatibility) ─────────────────────
    
    @app.get("/api/providers")
    async def list_providers_legacy():
        """List all providers with their status (legacy endpoint)."""
        linked = get_linked_providers()
        return {
            "providers": [
                {
                    "name": p.name,
                    "display_name": p.display_name,
                    "provider_type": "local" if p.provider_type == ProviderType.LOCAL else "cloud",
                    "requires_auth": p.requires_auth,
                    "is_configured": is_configured,
                    "signup_url": p.signup_url,
                    "env_key": p.env_key,
                }
                for p, is_configured in linked
            ]
        }
    
    @app.get("/api/providers/status")
    async def get_providers_status_legacy():
        """Get health status for all providers (legacy endpoint)."""
        linked = get_linked_providers()
        results = []
        
        for p, is_configured in linked:
            if not is_configured and p.requires_auth:
                results.append({
                    "name": p.name,
                    "is_configured": False,
                    "requires_auth": p.requires_auth,
                    "health": {"ok": False, "message": "Not configured"},
                })
            else:
                # Run health check
                ok, msg = await check_provider_reachable(p.name)
                results.append({
                    "name": p.name,
                    "is_configured": is_configured,
                    "requires_auth": p.requires_auth,
                    "health": {"ok": ok, "message": msg},
                })
        
        return {"providers": results}
    
    @app.post("/api/providers/{provider_name}/key")
    async def save_provider_key_legacy(provider_name: str, data: dict):
        """Save an API key for a provider (legacy endpoint)."""
        if "api_key" not in data:
            raise HTTPException(status_code=400, detail="api_key required")
        
        try:
            save_api_key(provider_name, data["api_key"])
            return {"success": True, "message": f"API key saved for {provider_name}"}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    @app.post("/api/providers/{provider_name}/test")
    async def test_provider_legacy(provider_name: str):
        """Test connection to a provider (legacy endpoint)."""
        ok, msg = await check_provider_reachable(provider_name)
        return {"ok": ok, "message": msg}
    
    # ─── Instance Management API ────────────────────────────────────────────────
    
    @app.get("/api/instances")
    async def list_instances(provider_type: Optional[str] = None):
        """List all provider instances."""
        manager = get_manager()
        instances = manager.list_instances(provider_type)
        return {
            "instances": [inst.to_dict(mask_key=True) for inst in instances]
        }
    
    @app.get("/api/instances/{instance_id}")
    async def get_instance(instance_id: str):
        """Get a specific provider instance."""
        manager = get_manager()
        instance = manager.get_instance(instance_id)
        if not instance:
            raise HTTPException(status_code=404, detail="Instance not found")
        return instance.to_dict(mask_key=True)
    
    @app.post("/api/instances")
    async def create_instance(data: CreateInstanceRequest):
        """Create a new provider instance."""
        manager = get_manager()
        
        # Validate provider type
        if data.provider_type not in PROVIDER_DEFAULTS:
            raise HTTPException(
                status_code=400, 
                detail=f"Unknown provider type: {data.provider_type}"
            )
        
        # Validate instance type
        try:
            inst_type = InstanceType(data.instance_type)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid instance type: {data.instance_type}. Must be 'local' or 'cloud'"
            )
        
        # Create instance
        instance = manager.create_instance(
            provider_type=data.provider_type,
            name=data.name,
            instance_type=inst_type,
            base_url=data.base_url,
            api_key=data.api_key,
            priority=data.priority,
            is_active=data.is_active,
        )
        
        return {"success": True, "instance": instance.to_dict(mask_key=True)}
    
    @app.put("/api/instances/{instance_id}")
    async def update_instance(instance_id: str, data: UpdateInstanceRequest):
        """Update a provider instance."""
        manager = get_manager()
        instance = manager.update_instance(
            instance_id=instance_id,
            name=data.name,
            base_url=data.base_url,
            api_key=data.api_key,
            priority=data.priority,
            is_active=data.is_active,
        )
        if not instance:
            raise HTTPException(status_code=404, detail="Instance not found")
        return {"success": True, "instance": instance.to_dict(mask_key=True)}
    
    @app.delete("/api/instances/{instance_id}")
    async def delete_instance(instance_id: str):
        """Delete a provider instance."""
        manager = get_manager()
        if manager.delete_instance(instance_id):
            return {"success": True, "message": "Instance deleted"}
        raise HTTPException(status_code=404, detail="Instance not found")
    
    @app.post("/api/instances/{instance_id}/test")
    async def test_instance(instance_id: str):
        """Test connection to a provider instance."""
        manager = get_manager()
        ok, msg = await manager.check_health(instance_id)
        return {"ok": ok, "message": msg}
    
    @app.get("/api/instances/{instance_id}/models")
    async def get_instance_models(instance_id: str):
        """Fetch available models from a provider instance."""
        manager = get_manager()
        models = await manager.fetch_models(instance_id)
        return {"models": models}
    
    @app.post("/api/instances/{instance_id}/pull")
    async def pull_model(instance_id: str, data: PullModelRequest):
        """Pull a model on an Ollama instance."""
        manager = get_manager()
        ok, msg = await manager.pull_model(instance_id, data.model_name)
        if ok:
            return {"success": True, "message": msg}
        else:
            return {"success": False, "message": msg}
    
    # ─── Health & Usage API ──────────────────────────────────────────────────────
    
    @app.get("/api/health/summary")
    async def get_health_summary():
        """Get a summary of provider health."""
        manager = get_manager()
        instances = manager.list_instances()
        
        healthy = sum(1 for i in instances if i.is_healthy)
        unhealthy = sum(1 for i in instances if not i.is_healthy and i.last_health_check)
        unconfigured = sum(1 for i in instances if not i.last_health_check)
        
        return {
            "healthy": healthy,
            "unhealthy": unhealthy,
            "unconfigured": unconfigured,
            "details": [
                {
                    "name": i.name,
                    "type": i.provider_type,
                    "status": "healthy" if i.is_healthy else ("unhealthy" if i.last_health_check else "unknown"),
                    "message": i.health_message or "Not checked",
                }
                for i in instances
            ]
        }
    
    @app.get("/api/usage")
    async def get_usage():
        """Get rate limit usage for all providers."""
        usage = get_all_usage()
        return {
            "usage": {
                name: {
                    "requests_limit": u.requests_limit,
                    "requests_remaining": u.requests_remaining,
                    "used_pct": u.requests_used_pct,
                    "is_soft_limited": u.is_soft_limited,
                    "is_hard_limited": u.is_hard_limited,
                }
                for name, u in usage.items()
            }
        }
    
    # ─── Models API ──────────────────────────────────────────────────────────────
    
    @app.get("/api/models")
    async def list_models():
        """List available model aliases from the config."""
        try:
            config_mgr = get_config_manager()
            aliases = config_mgr.list_aliases()
            return {
                "models": {a.name: a.description or a.model for a in aliases}
            }
        except Exception as e:
            # Fallback to hardcoded models
            return {
                "models": {
                    "free-router/auto": "Auto-routed based on task",
                    "free-router/fast": "Fast local models",
                    "free-router/coder": "Code-optimized models",
                    "free-router/smart": "Smart models for complex tasks",
                    "free-router/vision": "Vision-capable models",
                    "free-router/reasoning": "Reasoning-optimized models",
                }
            }
    
    # ─── Config Export API ──────────────────────────────────────────────────────
    
    @app.get("/api/config/export")
    async def export_config():
        """Export configuration for various tools."""
        proxy_url = os.getenv("FREEROUTER_PROXY_URL", "http://localhost:4000/v1")
        
        return {
            "export": {
                "cursor": {
                    "instructions": [
                        "Open Cursor Settings (Ctrl/Cmd + ,)",
                        "Go to the 'Models' section",
                        "Set 'OpenAI API Key' to: any_key",
                        "Set 'Override OpenAI Base URL' to the URL below",
                    ],
                    "config_example": {
                        "openaiApiKey": "any_key",
                        "openaiBaseURL": proxy_url,
                    }
                },
                "continue": {
                    "instructions": [
                        "Open Continue extension settings",
                        "Edit the config.json file",
                        "Add the model configuration below",
                    ],
                    "config_example": {
                        "models": [
                            {
                                "title": "FreeRouter Auto",
                                "provider": "openai",
                                "model": "free-router/auto",
                                "apiBase": proxy_url,
                                "apiKey": "any_key",
                            }
                        ]
                    }
                },
                "python": {
                    "instructions": [
                        "Install the OpenAI Python SDK: pip install openai",
                        "Use the code example below",
                    ],
                    "code_example": f'''from openai import OpenAI

client = OpenAI(
    base_url="{proxy_url}",
    api_key="any_key"
)

response = client.chat.completions.create(
    model="free-router/auto",
    messages=[{{"role": "user", "content": "Hello!"}}]
)
print(response.choices[0].message.content)'''
                },
                "curl": {
                    "instructions": [
                        "Use the curl command below to test the API",
                    ],
                    "command_example": f'''curl {proxy_url}/chat/completions \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer any_key" \\
  -d '{{"model": "free-router/auto", "messages": [{{"role": "user", "content": "Hello!"}}]}}'''
                }
            }
        }
    
    # ─── Refresh Health Check ─────────────────────────────────────────────────────
    
    @app.post("/api/instances/refresh-health")
    async def refresh_all_health():
        """Refresh health status for all instances."""
        manager = get_manager()
        instances = manager.list_instances()
        results = []
        
        for instance in instances:
            ok, msg = await manager.check_health(instance.id)
            results.append({
                "id": instance.id,
                "name": instance.name,
                "healthy": ok,
                "message": msg,
            })
        
        return {"results": results}
    
    # ─── Config Management API ────────────────────────────────────────────────────
    
    @app.get("/api/config")
    async def get_full_config():
        """Get the full configuration."""
        config_mgr = get_config_manager()
        return config_mgr.export_config()
    
    @app.get("/api/config/info")
    async def get_config_info():
        """Get information about the current configuration."""
        config_mgr = get_config_manager()
        return config_mgr.get_config_info()
    
    @app.post("/api/config/backup")
    async def create_config_backup():
        """Create a backup of the current configuration."""
        config_mgr = get_config_manager()
        backup_path = config_mgr.create_backup()
        return {"success": True, "backup_path": backup_path}
    
    @app.get("/api/config/backups")
    async def list_config_backups():
        """List all available configuration backups."""
        config_mgr = get_config_manager()
        backups = config_mgr.list_backups()
        return {"backups": backups}
    
    @app.post("/api/config/restore")
    async def restore_config_backup(data: dict):
        """Restore configuration from a backup."""
        if "backup_path" not in data:
            raise HTTPException(status_code=400, detail="backup_path required")
        
        config_mgr = get_config_manager()
        if config_mgr.restore_backup(data["backup_path"]):
            return {"success": True, "message": "Configuration restored"}
        raise HTTPException(status_code=404, detail="Backup not found")
    
    # ─── Model Alias Management API ──────────────────────────────────────────────
    
    @app.get("/api/aliases")
    async def list_model_aliases():
        """List all model aliases."""
        config_mgr = get_config_manager()
        aliases = config_mgr.list_aliases()
        return {
            "aliases": [
                {
                    "name": a.name,
                    "model": a.model,
                    "provider": a.provider,
                    "api_base": a.api_base,
                    "timeout": a.timeout,
                    "max_tokens": a.max_tokens,
                    "description": a.description,
                    "supports_vision": a.supports_vision,
                    "is_fallback": a.is_fallback,
                }
                for a in aliases
            ]
        }
    
    @app.get("/api/aliases/groups")
    async def get_model_groups():
        """Get models grouped by type."""
        config_mgr = get_config_manager()
        groups = config_mgr.get_model_groups()
        return {
            "groups": {
                group_name: [
                    {
                        "name": a.name,
                        "model": a.model,
                        "provider": a.provider,
                        "description": a.description,
                        "is_fallback": a.is_fallback,
                    }
                    for a in aliases
                ]
                for group_name, aliases in groups.items()
            }
        }
    
    @app.get("/api/aliases/{alias_name}")
    async def get_model_alias(alias_name: str):
        """Get a specific model alias."""
        config_mgr = get_config_manager()
        alias = config_mgr.get_alias(alias_name)
        if not alias:
            raise HTTPException(status_code=404, detail="Alias not found")
        return {
            "name": alias.name,
            "model": alias.model,
            "provider": alias.provider,
            "api_base": alias.api_base,
            "api_key": alias.api_key,
            "timeout": alias.timeout,
            "max_tokens": alias.max_tokens,
            "description": alias.description,
            "supports_vision": alias.supports_vision,
            "is_fallback": alias.is_fallback,
        }
    
    class CreateAliasRequest(BaseModel):
        name: str
        model: str
        api_base: Optional[str] = None
        api_key: Optional[str] = None
        timeout: int = 60
        max_tokens: int = 8192
        description: str = ""
        supports_vision: bool = False
    
    @app.post("/api/aliases")
    async def create_model_alias(data: CreateAliasRequest):
        """Create a new model alias."""
        config_mgr = get_config_manager()
        
        # Determine provider from model
        provider = ""
        if data.model.startswith("ollama/"):
            provider = "ollama"
        elif data.model.startswith("groq/"):
            provider = "groq"
        elif data.model.startswith("openrouter/"):
            provider = "openrouter"
        
        alias = ModelAlias(
            name=data.name,
            model=data.model,
            provider=provider,
            api_base=data.api_base,
            api_key=data.api_key,
            timeout=data.timeout,
            max_tokens=data.max_tokens,
            description=data.description,
            supports_vision=data.supports_vision,
        )
        
        try:
            config_mgr.create_alias(alias)
            return {"success": True, "alias": alias.name}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    class UpdateAliasRequest(BaseModel):
        model: Optional[str] = None
        api_base: Optional[str] = None
        api_key: Optional[str] = None
        timeout: Optional[int] = None
        max_tokens: Optional[int] = None
        description: Optional[str] = None
        supports_vision: Optional[bool] = None
    
    @app.put("/api/aliases/{alias_name}")
    async def update_model_alias(alias_name: str, data: UpdateAliasRequest):
        """Update a model alias."""
        config_mgr = get_config_manager()
        
        # Build update dict with only non-None values
        updates = {}
        if data.model is not None:
            updates["model"] = data.model
            # Update provider
            if data.model.startswith("ollama/"):
                updates["provider"] = "ollama"
            elif data.model.startswith("groq/"):
                updates["provider"] = "groq"
            elif data.model.startswith("openrouter/"):
                updates["provider"] = "openrouter"
        if data.api_base is not None:
            updates["api_base"] = data.api_base
        if data.api_key is not None:
            updates["api_key"] = data.api_key
        if data.timeout is not None:
            updates["timeout"] = data.timeout
        if data.max_tokens is not None:
            updates["max_tokens"] = data.max_tokens
        if data.description is not None:
            updates["description"] = data.description
        if data.supports_vision is not None:
            updates["supports_vision"] = data.supports_vision
        
        alias = config_mgr.update_alias(alias_name, **updates)
        if not alias:
            raise HTTPException(status_code=404, detail="Alias not found")
        return {"success": True, "alias": alias.name}
    
    @app.delete("/api/aliases/{alias_name}")
    async def delete_model_alias(alias_name: str):
        """Delete a model alias."""
        config_mgr = get_config_manager()
        if config_mgr.delete_alias(alias_name):
            return {"success": True, "message": f"Alias '{alias_name}' deleted"}
        raise HTTPException(status_code=404, detail="Alias not found")
    
    # ─── Fallback Chain Management API ───────────────────────────────────────────
    
    @app.get("/api/fallbacks")
    async def list_fallback_chains():
        """List all fallback chains."""
        config_mgr = get_config_manager()
        chains = config_mgr.list_fallback_chains()
        return {
            "fallbacks": [
                {
                    "primary_model": c.primary_model,
                    "fallbacks": c.fallbacks,
                }
                for c in chains
            ]
        }
    
    @app.get("/api/fallbacks/{model_name}")
    async def get_fallback_chain(model_name: str):
        """Get the fallback chain for a specific model."""
        config_mgr = get_config_manager()
        chain = config_mgr.get_fallback_chain(model_name)
        if not chain:
            raise HTTPException(status_code=404, detail="Fallback chain not found")
        return {
            "primary_model": chain.primary_model,
            "fallbacks": chain.fallbacks,
        }
    
    class SetFallbackChainRequest(BaseModel):
        fallbacks: List[str]
    
    @app.put("/api/fallbacks/{model_name}")
    async def set_fallback_chain(model_name: str, data: SetFallbackChainRequest):
        """Set the fallback chain for a model."""
        config_mgr = get_config_manager()
        chain = config_mgr.set_fallback_chain(model_name, data.fallbacks)
        return {
            "success": True,
            "primary_model": chain.primary_model,
            "fallbacks": chain.fallbacks,
        }
    
    @app.delete("/api/fallbacks/{model_name}")
    async def delete_fallback_chain(model_name: str):
        """Delete a fallback chain."""
        config_mgr = get_config_manager()
        if config_mgr.delete_fallback_chain(model_name):
            return {"success": True, "message": f"Fallback chain for '{model_name}' deleted"}
        raise HTTPException(status_code=404, detail="Fallback chain not found")
    
    @app.get("/api/primary-models")
    async def get_primary_models():
        """Get all primary (non-fallback) models."""
        config_mgr = get_config_manager()
        models = config_mgr.get_primary_models()
        return {
            "models": [
                {
                    "name": m.name,
                    "model": m.model,
                    "provider": m.provider,
                    "description": m.description,
                }
                for m in models
            ]
        }
    
    # ─── Chat Playground API ─────────────────────────────────────────────────────
    
    # In-memory conversation storage (for demo; use database in production)
    _conversations: Dict[str, Dict[str, Any]] = {}
    
    @app.get("/api/chat/conversations")
    async def list_conversations():
        """List all saved conversations."""
        return {
            "conversations": [
                {
                    "id": conv_id,
                    "title": conv.get("title", "Untitled"),
                    "created_at": conv.get("created_at"),
                    "updated_at": conv.get("updated_at"),
                    "message_count": len(conv.get("messages", [])),
                }
                for conv_id, conv in _conversations.items()
            ]
        }
    
    @app.post("/api/chat/conversations")
    async def create_conversation(data: dict):
        """Create a new conversation."""
        conv_id = str(uuid.uuid4())
        _conversations[conv_id] = {
            "id": conv_id,
            "title": data.get("title", "New Chat"),
            "messages": [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }
        return {"success": True, "conversation_id": conv_id}
    
    @app.get("/api/chat/conversations/{conv_id}")
    async def get_conversation(conv_id: str):
        """Get a specific conversation with all messages."""
        if conv_id not in _conversations:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return _conversations[conv_id]
    
    @app.delete("/api/chat/conversations/{conv_id}")
    async def delete_conversation(conv_id: str):
        """Delete a conversation."""
        if conv_id in _conversations:
            del _conversations[conv_id]
            return {"success": True}
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    @app.post("/api/chat/conversations/{conv_id}/messages")
    async def add_message(conv_id: str, data: dict):
        """Add a message to a conversation."""
        if conv_id not in _conversations:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        message = {
            "id": str(uuid.uuid4()),
            "role": data.get("role", "user"),
            "content": data.get("content", ""),
            "timestamp": datetime.now().isoformat(),
        }
        
        # Handle image if provided
        if "image" in data:
            message["image"] = data["image"]
        
        _conversations[conv_id]["messages"].append(message)
        _conversations[conv_id]["updated_at"] = datetime.now().isoformat()
        
        # Update title from first user message
        if len(_conversations[conv_id]["messages"]) == 1 and data.get("role") == "user":
            title = data.get("content", "")[:50]
            if len(data.get("content", "")) > 50:
                title += "..."
            _conversations[conv_id]["title"] = title
        
        return {"success": True, "message": message}
    
    class ChatRequest(BaseModel):
        model: str
        messages: List[Dict[str, Any]]
        stream: bool = True
        temperature: float = 0.7
        max_tokens: int = 4096
    
    @app.post("/api/chat/completions")
    async def chat_completions(data: ChatRequest):
        """Non-streaming chat completion (for comparison mode)."""
        
        # Get proxy URL
        proxy_url = os.getenv("FREEROUTER_PROXY_URL", "http://localhost:4000/v1")
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{proxy_url}/chat/completions",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": "Bearer any_key",
                    },
                    json={
                        "model": data.model,
                        "messages": data.messages,
                        "temperature": data.temperature,
                        "max_tokens": data.max_tokens,
                        "stream": False,
                    }
                )
                
                if response.status_code != 200:
                    return {"error": f"Proxy error: {response.status_code}", "detail": response.text}
                
                return response.json()
        except Exception as e:
            return {"error": str(e)}
    
    @app.post("/api/chat/stream")
    async def chat_stream(data: ChatRequest):
        """Streaming chat completion."""
        
        proxy_url = os.getenv("FREEROUTER_PROXY_URL", "http://localhost:4000/v1")
        
        async def generate_stream():
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    async with client.stream(
                        "POST",
                        f"{proxy_url}/chat/completions",
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": "Bearer any_key",
                        },
                        json={
                            "model": data.model,
                            "messages": data.messages,
                            "temperature": data.temperature,
                            "max_tokens": data.max_tokens,
                            "stream": True,
                        },
                    ) as response:
                        async for chunk in response.aiter_bytes():
                            yield chunk
            except Exception as e:
                error_msg = f"data: {json.dumps({'error': str(e)})}\n\n"
                yield error_msg.encode()
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            }
        )
    
    class CompareRequest(BaseModel):
        models: List[str]
        messages: List[Dict[str, Any]]
        temperature: float = 0.7
        max_tokens: int = 1024
    
    @app.post("/api/chat/compare")
    async def compare_models(data: CompareRequest):
        """Compare responses from multiple models."""
        
        proxy_url = os.getenv("FREEROUTER_PROXY_URL", "http://localhost:4000/v1")
        
        async def get_response(model: str) -> Dict[str, Any]:
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{proxy_url}/chat/completions",
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": "Bearer any_key",
                        },
                        json={
                            "model": model,
                            "messages": data.messages,
                            "temperature": data.temperature,
                            "max_tokens": data.max_tokens,
                            "stream": False,
                        }
                    )
                    
                    if response.status_code != 200:
                        return {
                            "model": model,
                            "error": f"HTTP {response.status_code}",
                            "response": None,
                        }
                    
                    result = response.json()
                    return {
                        "model": model,
                        "response": result.get("choices", [{}])[0].get("message", {}).get("content", ""),
                        "usage": result.get("usage", {}),
                    }
            except Exception as e:
                return {
                    "model": model,
                    "error": str(e),
                    "response": None,
                }
        
        # Run all model requests in parallel
        tasks = [get_response(model) for model in data.models]
        results = await asyncio.gather(*tasks)
        
        return {"results": results}
    
    @app.post("/api/chat/image")
    async def process_image(data: dict):
        """Process an uploaded image for vision models."""
        if "image" not in data:
            raise HTTPException(status_code=400, detail="Image data required")
        
        try:
            # Handle base64 image
            image_data = data["image"]
            if image_data.startswith("data:image"):
                # Extract base64 part
                image_data = image_data.split(",", 1)[1]
            
            # Validate it's valid base64
            base64.b64decode(image_data)
            
            # Return formatted for OpenAI vision API
            return {
                "success": True,
                "image_url": {
                    "url": f"data:image/png;base64,{image_data}" if not data["image"].startswith("data:image") else data["image"]
                }
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid image: {str(e)}")
    
    return app


# ─── Dashboard HTML Template ─────────────────────────────────────────────────────

def get_dashboard_html() -> str:
    """Return the dashboard HTML content."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FreeRouter Dashboard</title>
    <link rel="stylesheet" href="/static/css/styles.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>⚡ FreeRouter</h1>
            <p class="subtitle">AI Provider Management Dashboard</p>
        </header>
        
        <nav class="tabs">
            <button class="tab-btn active" data-tab="providers">🔑 Providers</button>
            <button class="tab-btn" data-tab="instances">🖥️ Instances</button>
            <button class="tab-btn" data-tab="chat">💬 Test Chat</button>
            <button class="tab-btn" data-tab="models">📦 Models</button>
            <button class="tab-btn" data-tab="config">📋 Config</button>
            <button class="tab-btn" data-tab="usage">📊 Usage</button>

        </nav>
        
        <main id="content">
            <div class="loading"><div class="spinner"></div></div>
        </main>
        
        <footer>
            <p>FreeRouter - Smart AI Proxy</p>
            <p><a href="https://github.com/freerouter/freerouter" target="_blank">GitHub</a></p>
        </footer>
    </div>
    
    <div id="toast-container" class="toast-container"></div>
    
    <script src="/static/js/app.js"></script>
</body>
</html>"""