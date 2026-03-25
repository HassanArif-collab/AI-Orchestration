# P0 Critical Issues - Detailed Fix Plans

**Branch:** `Explaining-FinalRefactoring`
**Created:** 2025-03-25
**Priority:** CRITICAL - Must fix before any production use

---

## Table of Contents

1. [P0-01: No API Authentication](#p0-01-no-api-authentication)
2. [P0-02: No FreeRouter Startup Health Check](#p0-02-no-freerouter-startup-health-check)
3. [P0-03: No API Key Validation](#p0-03-no-api-key-validation)
4. [P0-04: No Explicit Resume Method](#p0-04-no-explicit-resume-method)
5. [P0-05: No Quality Floor Check](#p0-05-no-quality-floor-check)
6. [P0-06: Web Search Fallback Generates Fake URLs](#p0-06-web-search-fallback-generates-fake-urls)
7. [P0-07: CORS Wildcard](#p0-07-cors-wildcard)
8. [P0-08: No Retry Logic for Publish](#p0-08-no-retry-logic-for-publish)

---

## P0-01: No API Authentication

### Issue Description
The API is completely open with no authentication. Anyone can:
- Create/delete pipeline runs
- Access environment settings (including API keys)
- Modify the topic reservoir
- Access all conversation history

**Security Risk: CRITICAL**

### Current Code (Problem)

```python
# apps/api/main.py
app = FastAPI(title="AI Orchestration API")

# No authentication middleware!
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Also a P0 issue
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Proposed Fix

#### Step 1: Add API Key Configuration

```python
# packages/core/config.py - Add to Settings class

class Settings(BaseSettings):
    # ... existing settings ...
    
    # API Authentication
    API_KEYS: str = ""  # Comma-separated list of valid API keys
    API_KEY_HEADER: str = "X-API-Key"  # Header name for API key
    
    @property
    def valid_api_keys(self) -> set[str]:
        """Return set of valid API keys."""
        if not self.API_KEYS:
            return set()
        return {k.strip() for k in self.API_KEYS.split(",") if k.strip()}
    
    def is_auth_enabled(self) -> bool:
        """Check if authentication is configured."""
        return len(self.valid_api_keys) > 0
```

#### Step 2: Create Authentication Middleware

```python
# apps/api/middleware/auth.py (NEW FILE)

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from packages.core.config import get_settings


class AuthMiddleware(BaseHTTPMiddleware):
    """
    API Key authentication middleware.
    
    Skips authentication for:
    - Health check endpoints (/health, /api/health)
    - When no API keys are configured (dev mode)
    """
    
    # Endpoints that don't require authentication
    PUBLIC_PATHS = {
        "/health",
        "/api/health",
        "/",
        "/favicon.ico",
    }
    
    # Paths that start with these prefixes are public
    PUBLIC_PREFIXES = [
        "/static/",  # Static files
    ]
    
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        
        # Skip auth for public paths
        if self._is_public_path(request.url.path):
            return await call_next(request)
        
        # Skip auth if not configured (dev mode)
        if not settings.is_auth_enabled():
            return await call_next(request)
        
        # Validate API key
        api_key = request.headers.get(settings.API_KEY_HEADER)
        
        if not api_key:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "Unauthorized",
                    "message": f"Missing {settings.API_KEY_HEADER} header"
                }
            )
        
        if api_key not in settings.valid_api_keys:
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Forbidden",
                    "message": "Invalid API key"
                }
            )
        
        # Add API key to request state for logging
        request.state.api_key = api_key[:8] + "..."  # Truncated for logs
        
        return await call_next(request)
    
    def _is_public_path(self, path: str) -> bool:
        """Check if path is public (no auth required)."""
        # Exact match
        if path in self.PUBLIC_PATHS:
            return True
        
        # Prefix match
        for prefix in self.PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return True
        
        return False
```

#### Step 3: Apply Middleware in main.py

```python
# apps/api/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.middleware.auth import AuthMiddleware

app = FastAPI(title="AI Orchestration API")

# Add authentication middleware (before CORS)
app.add_middleware(AuthMiddleware)

# CORS (will be fixed in P0-07)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Fixed in P0-07
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

#### Step 4: Add Health Endpoint

```python
# apps/api/routers/health_routes.py (NEW FILE)

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Public health check endpoint."""
    return {"status": "ok", "service": "ai-orchestration"}
```

```python
# apps/api/main.py - Add router

from apps.api.routers.health_routes import router as health_router

app.include_router(health_router)
```

### Implementation Steps

| Step | File | Action |
|------|------|--------|
| 1 | `packages/core/config.py` | Add API_KEYS setting |
| 2 | `apps/api/middleware/auth.py` | Create new file |
| 3 | `apps/api/main.py` | Import and apply middleware |
| 4 | `apps/api/routers/health_routes.py` | Create health endpoint |
| 5 | `.env` | Add `API_KEYS=key1,key2,key3` |

### Testing

```bash
# Test 1: No API key (should fail)
curl http://localhost:8000/api/pipeline/runs
# Expected: 401 Unauthorized

# Test 2: Invalid API key (should fail)
curl -H "X-API-Key: invalid" http://localhost:8000/api/pipeline/runs
# Expected: 403 Forbidden

# Test 3: Valid API key (should succeed)
curl -H "X-API-Key: your-valid-key" http://localhost:8000/api/pipeline/runs
# Expected: 200 OK

# Test 4: Health endpoint (should always succeed)
curl http://localhost:8000/health
# Expected: {"status": "ok", "service": "ai-orchestration"}
```

### Environment Configuration

```bash
# .env
API_KEYS=sk-prod-abc123,sk-dev-xyz789
API_KEY_HEADER=X-API-Key
```

---

## P0-02: No FreeRouter Startup Health Check

### Issue Description
The RouterClient doesn't verify FreeRouter is running before making requests. If FreeRouter is down, the first sign is a cryptic connection error during a pipeline run.

### Current Code (Problem)

```python
# packages/router/client.py

class RouterClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.FREEROUTER_URL
        # No health check!
        
    async def complete_text(self, prompt: str, ...):
        # First call fails if FreeRouter not running
        async with httpx.AsyncClient() as client:
            response = await client.post(...)  # Connection error!
```

### Proposed Fix

#### Step 1: Add Health Check Method

```python
# packages/router/client.py

import httpx
from packages.core.config import get_settings
from packages.core.errors import LLMClientError

class RouterClient:
    """Async client for FreeRouter proxy with health checking."""
    
    def __init__(
        self,
        base_url: str = None,
        timeout: float = 90.0,
        startup_check: bool = True,
    ):
        settings = get_settings()
        self.base_url = base_url or settings.FREEROUTER_URL
        self.timeout = timeout
        self._healthy = None
        self._last_health_check = None
        
        if startup_check:
            self._startup_health_check()
    
    def _startup_health_check(self) -> None:
        """
        Synchronous health check at initialization.
        Raises LLMClientError if FreeRouter is not running.
        """
        import requests
        
        try:
            response = requests.get(
                f"{self.base_url}/health",
                timeout=5.0  # Quick timeout for startup
            )
            if response.status_code == 200:
                self._healthy = True
                self._last_health_check = datetime.now(timezone.utc)
                return
        except requests.exceptions.ConnectionError:
            pass
        except requests.exceptions.Timeout:
            pass
        except Exception as e:
            pass
        
        # If we get here, health check failed
        raise LLMClientError(
            f"FreeRouter is not running at {self.base_url}. "
            f"Please start it with: cd freerouter && python -m freerouter"
        )
    
    async def health_check(self) -> dict:
        """
        Async health check (can be called at runtime).
        
        Returns:
            dict with 'healthy' bool and 'latency_ms' float
        """
        start = datetime.now(timezone.utc)
        
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                
                if response.status_code == 200:
                    latency = (datetime.now(timezone.utc) - start).total_seconds() * 1000
                    self._healthy = True
                    self._last_health_check = datetime.now(timezone.utc)
                    return {"healthy": True, "latency_ms": latency}
        except Exception:
            pass
        
        self._healthy = False
        return {"healthy": False, "latency_ms": None}
    
    @property
    def is_healthy(self) -> bool:
        """Return last known health status."""
        return self._healthy or False
    
    async def complete_text(self, prompt: str, ...) -> str:
        """Complete text with health-aware error messages."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # ... existing code ...
        except httpx.ConnectError as e:
            # Provide helpful error message
            raise LLMClientError(
                f"Cannot connect to FreeRouter at {self.base_url}. "
                f"Is it running? Start with: cd freerouter && python -m freerouter"
            ) from e
```

#### Step 2: Add to Config

```python
# packages/core/config.py

class Settings(BaseSettings):
    # ... existing ...
    
    # FreeRouter options
    FREEROUTER_STARTUP_CHECK: bool = True  # Enable startup health check
    FREEROUTER_HEALTH_TIMEOUT: float = 5.0  # Seconds to wait for health check
```

#### Step 3: Update Context Manager

```python
# packages/router/client.py

@asynccontextmanager
async def RouterClient(*args, **kwargs):
    """
    Async context manager for RouterClient.
    
    Usage:
        async with RouterClient() as client:
            response = await client.complete_text("Hello")
    """
    client = RouterClientSync(*args, **kwargs)
    try:
        yield client
    finally:
        pass  # No cleanup needed


class RouterClientSync:
    """Synchronous wrapper for RouterClient with startup check."""
    
    def __init__(
        self,
        base_url: str = None,
        timeout: float = 90.0,
        skip_health_check: bool = False,
    ):
        settings = get_settings()
        self.base_url = base_url or settings.FREEROUTER_URL
        self.timeout = timeout
        
        # Skip health check if requested (for testing)
        if not skip_health_check and settings.FREEROUTER_STARTUP_CHECK:
            self._do_startup_check()
```

### Implementation Steps

| Step | File | Action |
|------|------|--------|
| 1 | `packages/router/client.py` | Add `_startup_health_check()` method |
| 2 | `packages/router/client.py` | Add `health_check()` async method |
| 3 | `packages/router/client.py` | Update `complete_text()` error handling |
| 4 | `packages/core/config.py` | Add `FREEROUTER_STARTUP_CHECK` setting |
| 5 | `packages/core/errors.py` | Verify `LLMClientError` has helpful message |

### Testing

```python
# tests/test_router_health.py

import pytest
from packages.router.client import RouterClient
from packages.core.errors import LLMClientError


def test_startup_check_fails_without_freerouter():
    """Should raise LLMClientError if FreeRouter not running."""
    with pytest.raises(LLMClientError) as exc_info:
        RouterClient(base_url="http://localhost:9999")  # Non-existent
    
    assert "FreeRouter is not running" in str(exc_info.value)
    assert "localhost:9999" in str(exc_info.value)


def test_skip_startup_check():
    """Should not raise if skip_health_check=True."""
    client = RouterClient(
        base_url="http://localhost:9999",
        skip_health_check=True
    )
    assert client is not None


@pytest.mark.asyncio
async def test_health_check_method():
    """Should return health status."""
    client = RouterClient(skip_health_check=True)
    result = await client.health_check()
    assert "healthy" in result
    assert "latency_ms" in result
```

---

## P0-03: No API Key Validation

### Issue Description
All API keys in config default to empty strings. Operations fail at runtime with cryptic errors instead of clear "missing API key" messages.

### Current Code (Problem)

```python
# packages/core/config.py

class Settings(BaseSettings):
    ZEP_API_KEY: str = ""
    YOUTUBE_API_KEY: str = ""
    NOTION_API_KEY: str = ""
    # No validation - all empty by default
```

### Proposed Fix

#### Step 1: Add Validation Method

```python
# packages/core/config.py

from typing import Optional
from enum import Enum


class ServiceStatus(str, Enum):
    """Service availability status."""
    AVAILABLE = "available"
    NOT_CONFIGURED = "not_configured"
    MISCONFIGURED = "misconfigured"


class Settings(BaseSettings):
    # ... existing settings ...
    
    def validate_service(self, service: str) -> ServiceStatus:
        """
        Validate if a service is properly configured.
        
        Args:
            service: Service name (zep, youtube, notion, etc.)
        
        Returns:
            ServiceStatus enum value
        """
        validators = {
            "zep": self._validate_zep,
            "youtube": self._validate_youtube,
            "notion": self._validate_notion,
            "freerouter": self._validate_freerouter,
        }
        
        validator = validators.get(service.lower())
        if not validator:
            raise ValueError(f"Unknown service: {service}")
        
        return validator()
    
    def _validate_zep(self) -> ServiceStatus:
        """Validate Zep Cloud configuration."""
        if not self.ZEP_API_KEY:
            return ServiceStatus.NOT_CONFIGURED
        if not self.ZEP_API_KEY.startswith("zep_"):
            return ServiceStatus.MISCONFIGURED
        return ServiceStatus.AVAILABLE
    
    def _validate_youtube(self) -> ServiceStatus:
        """Validate YouTube API configuration."""
        if not self.YOUTUBE_API_KEY:
            return ServiceStatus.NOT_CONFIGURED
        if len(self.YOUTUBE_API_KEY) < 20:
            return ServiceStatus.MISCONFIGURED
        return ServiceStatus.AVAILABLE
    
    def _validate_notion(self) -> ServiceStatus:
        """Validate Notion API configuration."""
        if not self.NOTION_API_KEY:
            return ServiceStatus.NOT_CONFIGURED
        if not self.NOTION_API_KEY.startswith("secret_"):
            return ServiceStatus.MISCONFIGURED
        return ServiceStatus.AVAILABLE
    
    def _validate_freerouter(self) -> ServiceStatus:
        """Validate FreeRouter configuration."""
        if not self.FREEROUTER_URL:
            return ServiceStatus.NOT_CONFIGURED
        return ServiceStatus.AVAILABLE
    
    def get_service_status(self) -> dict[str, str]:
        """Get status of all services."""
        services = ["zep", "youtube", "notion", "freerouter"]
        return {s: self.validate_service(s).value for s in services}
```

#### Step 2: Add Integration Checks

```python
# packages/integrations/notion/client.py

class NotionClient:
    def __init__(self):
        settings = get_settings()
        
        # Validate configuration
        status = settings.validate_service("notion")
        if status == ServiceStatus.NOT_CONFIGURED:
            logger.warning("notion_not_configured: Set NOTION_API_KEY to enable")
            self._client = None
            return
        elif status == ServiceStatus.MISCONFIGURED:
            logger.error("notion_misconfigured: NOTION_API_KEY should start with 'secret_'")
            self._client = None
            return
        
        # Initialize client
        self._client = Client(auth=settings.NOTION_API_KEY)
```

#### Step 3: Add Settings Validation Endpoint

```python
# apps/api/routers/settings_routes.py

@router.get("/status")
async def get_service_status():
    """
    Get configuration status of all services.
    
    Returns which services are available, not configured, or misconfigured.
    """
    settings = get_settings()
    return settings.get_service_status()


@router.post("/validate")
async def validate_configuration():
    """
    Validate all configuration and return detailed report.
    """
    settings = get_settings()
    issues = []
    
    # Check each service
    for service in ["zep", "youtube", "notion", "freerouter"]:
        status = settings.validate_service(service)
        if status != ServiceStatus.AVAILABLE:
            issues.append({
                "service": service,
                "status": status.value,
                "recommendation": _get_recommendation(service, status)
            })
    
    return {
        "valid": len(issues) == 0,
        "issues": issues
    }


def _get_recommendation(service: str, status: ServiceStatus) -> str:
    """Get recommendation for fixing service configuration."""
    recommendations = {
        ("zep", ServiceStatus.NOT_CONFIGURED): "Set ZEP_API_KEY environment variable",
        ("zep", ServiceStatus.MISCONFIGURED): "ZEP_API_KEY should start with 'zep_'",
        ("youtube", ServiceStatus.NOT_CONFIGURED): "Set YOUTUBE_API_KEY environment variable",
        ("youtube", ServiceStatus.MISCONFIGURED): "YOUTUBE_API_KEY appears invalid",
        ("notion", ServiceStatus.NOT_CONFIGURED): "Set NOTION_API_KEY environment variable",
        ("notion", ServiceStatus.MISCONFIGURED): "NOTION_API_KEY should start with 'secret_'",
        ("freerouter", ServiceStatus.NOT_CONFIGURED): "Set FREEROUTER_URL or start FreeRouter",
    }
    return recommendations.get((service, status), "Check configuration")
```

### Implementation Steps

| Step | File | Action |
|------|------|--------|
| 1 | `packages/core/config.py` | Add `ServiceStatus` enum |
| 2 | `packages/core/config.py` | Add validation methods |
| 3 | `packages/integrations/*/client.py` | Use validation before init |
| 4 | `apps/api/routers/settings_routes.py` | Add status endpoints |

### Testing

```python
# tests/test_config_validation.py

def test_zep_not_configured():
    """Should detect missing ZEP_API_KEY."""
    settings = Settings(ZEP_API_KEY="")
    assert settings.validate_service("zep") == ServiceStatus.NOT_CONFIGURED


def test_zep_misconfigured():
    """Should detect invalid ZEP_API_KEY format."""
    settings = Settings(ZEP_API_KEY="invalid-key")
    assert settings.validate_service("zep") == ServiceStatus.MISCONFIGURED


def test_zep_available():
    """Should detect valid ZEP_API_KEY."""
    settings = Settings(ZEP_API_KEY="zep_valid_key_here")
    assert settings.validate_service("zep") == ServiceStatus.AVAILABLE


def test_get_service_status():
    """Should return status of all services."""
    settings = Settings()
    status = settings.get_service_status()
    assert "zep" in status
    assert "youtube" in status
    assert "notion" in status
```

---

## P0-04: No Explicit Resume Method

### Issue Description
When a pipeline crashes, there's no way to resume from where it stopped. The `PipelineRun` state is persisted, but no API method exists to restart it.

### Current Code (Problem)

```python
# packages/pipeline/runner.py

class PipelineRunner:
    async def run_until_gate(self, run: PipelineRun) -> Optional[Stage]:
        # Runs until hitting a human gate or completion
        # But no resume_run() method!
        pass
```

### Proposed Fix

#### Step 1: Add Resume Method

```python
# packages/pipeline/runner.py

from packages.core.errors import PipelineError
from packages.core.logger import get_logger

log = get_logger(__name__)


class PipelineRunner:
    """Pipeline execution engine with crash recovery."""
    
    async def resume_run(self, run_id: str) -> Optional[Stage]:
        """
        Resume a crashed or paused pipeline run.
        
        This method:
        1. Loads the run state from the database
        2. Validates the run can be resumed
        3. Resets the failed stage if needed
        4. Continues execution from the current stage
        
        Args:
            run_id: ID of the run to resume
        
        Returns:
            Stage where execution stopped (gate or completion)
            None if run cannot be resumed or doesn't exist
        
        Raises:
            PipelineError: If run is in an unrecoverable state
        """
        # Load run from database
        run = self.store.load(run_id)
        if not run:
            log.warning(f"resume_run_not_found: run_id={run_id}")
            return None
        
        # Check if run can be resumed
        if run.status == "completed":
            log.info(f"resume_run_already_completed: run_id={run_id}")
            return None
        
        if run.status == "waiting_human":
            log.info(f"resume_run_waiting_gate: run_id={run_id}")
            return run.current_stage
        
        # Run is in error or running state - attempt recovery
        if run.status == "error":
            log.info(f"resume_run_recovering: run_id={run_id} from error")
            
            # Reset the failed stage
            failed_stage = run.current_stage
            if failed_stage:
                run.stage_status[failed_stage.value] = "pending"
                run.error_message = None
            
            run.status = "running"
            self.store.save(run)
        
        # Continue execution
        log.info(
            f"resume_run_continuing: run_id={run_id} "
            f"stage={run.current_stage.value if run.current_stage else 'none'}"
        )
        
        return await self.run_until_gate(run)
    
    def list_resumable_runs(self) -> list[dict]:
        """
        List all runs that can be resumed.
        
        Returns:
            List of runs with status 'error' or 'waiting_human'
        """
        runs = self.store.list_all()
        resumable = []
        
        for run in runs:
            if run.status in ("error", "waiting_human"):
                resumable.append({
                    "run_id": run.run_id,
                    "status": run.status,
                    "current_stage": run.current_stage.value if run.current_stage else None,
                    "error_message": run.error_message,
                    "created_at": run.created_at,
                    "topic": run.stage_outputs.get("human_topic_approval", {}).get("topic_statement", "Unknown"),
                })
        
        return resumable
    
    async def recover_all_failed(self) -> dict:
        """
        Attempt to resume all failed runs.
        
        Returns:
            Summary of recovery attempts
        """
        resumable = self.list_resumable_runs()
        results = {"recovered": 0, "failed": 0, "still_waiting": 0}
        
        for run_info in resumable:
            if run_info["status"] == "error":
                result = await self.resume_run(run_info["run_id"])
                if result:
                    results["recovered"] += 1
                else:
                    results["failed"] += 1
            else:
                results["still_waiting"] += 1
        
        log.info(f"recover_all_failed: {results}")
        return results
```

#### Step 2: Add API Endpoint

```python
# apps/api/routers/pipeline_routes.py

@router.post("/runs/{run_id}/resume")
async def resume_pipeline_run(run_id: str):
    """
    Resume a crashed or paused pipeline run.
    
    Use this when a pipeline failed due to:
    - Transient errors (network, API limits)
    - Service restarts
    - Manual intervention needed
    """
    runner = PipelineRunner()
    
    try:
        result = await runner.resume_run(run_id)
        
        if result is None:
            raise HTTPException(
                status_code=400,
                detail=f"Run {run_id} cannot be resumed (may be completed or not found)"
            )
        
        return {
            "status": "resumed",
            "run_id": run_id,
            "current_stage": result.value if result else None
        }
    
    except PipelineError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/runs/resumable")
async def list_resumable_runs():
    """
    List all pipeline runs that can be resumed.
    
    Returns runs with status 'error' or 'waiting_human'.
    """
    runner = PipelineRunner()
    return {"runs": runner.list_resumable_runs()}


@router.post("/runs/recover-all")
async def recover_all_failed_runs():
    """
    Attempt to resume all failed pipeline runs.
    
    This is useful after a system restart to recover interrupted work.
    """
    runner = PipelineRunner()
    results = await runner.recover_all_failed()
    return results
```

#### Step 3: Add Error Recovery Decorator

```python
# packages/pipeline/recovery.py (NEW FILE)

from functools import wraps
from packages.core.logger import get_logger

log = get_logger(__name__)


def recoverable(f):
    """
    Decorator that marks a stage handler as recoverable.
    
    Recoverable handlers can be safely retried after failure.
    They should be idempotent (safe to run multiple times).
    """
    @wraps(f)
    async def wrapper(*args, **kwargs):
        try:
            return await f(*args, **kwargs)
        except Exception as e:
            log.error(
                f"stage_handler_failed: handler={f.__name__} error={e}",
                exc_info=True
            )
            # Re-raise for pipeline to handle
            raise
    
    wrapper._recoverable = True
    return wrapper
```

### Implementation Steps

| Step | File | Action |
|------|------|--------|
| 1 | `packages/pipeline/runner.py` | Add `resume_run()` method |
| 2 | `packages/pipeline/runner.py` | Add `list_resumable_runs()` method |
| 3 | `packages/pipeline/runner.py` | Add `recover_all_failed()` method |
| 4 | `apps/api/routers/pipeline_routes.py` | Add resume endpoints |
| 5 | `packages/pipeline/recovery.py` | Create recovery utilities |

### Testing

```python
# tests/test_pipeline_recovery.py

import pytest
from packages.pipeline.runner import PipelineRunner
from packages.pipeline.state import PipelineRun, Stage


@pytest.mark.asyncio
async def test_resume_completed_run():
    """Should return None for completed runs."""
    runner = PipelineRunner()
    # Create and complete a run
    run = PipelineRun(run_id="test-completed")
    run.status = "completed"
    runner.store.save(run)
    
    result = await runner.resume_run("test-completed")
    assert result is None


@pytest.mark.asyncio
async def test_resume_failed_run():
    """Should reset failed stage and continue."""
    runner = PipelineRunner()
    
    # Create a failed run
    run = PipelineRun(run_id="test-failed")
    run.status = "error"
    run.current_stage = Stage.RESEARCH
    run.stage_status = {"research": "error"}
    run.error_message = "Connection failed"
    runner.store.save(run)
    
    # Resume should reset and continue
    result = await runner.resume_run("test-failed")
    
    # Check run was updated
    updated_run = runner.store.load("test-failed")
    assert updated_run.status == "running"
    assert updated_run.error_message is None


def test_list_resumable_runs():
    """Should list runs that can be resumed."""
    runner = PipelineRunner()
    
    # Create test runs
    error_run = PipelineRun(run_id="error-run")
    error_run.status = "error"
    
    waiting_run = PipelineRun(run_id="waiting-run")
    waiting_run.status = "waiting_human"
    
    completed_run = PipelineRun(run_id="completed-run")
    completed_run.status = "completed"
    
    runner.store.save(error_run)
    runner.store.save(waiting_run)
    runner.store.save(completed_run)
    
    resumable = runner.list_resumable_runs()
    
    assert len(resumable) == 2
    assert any(r["run_id"] == "error-run" for r in resumable)
    assert any(r["run_id"] == "waiting-run" for r in resumable)
    assert not any(r["run_id"] == "completed-run" for r in resumable)
```

---

## P0-05: No Quality Floor Check

### Issue Description
The evaluation loop can return scripts that never reached the 85% threshold. There's no minimum quality enforcement.

### Current Code (Problem)

```python
# packages/content_factory/evaluation/loop.py

async def run_with_threshold(self, script, threshold=85.0, max_iterations=20):
    # Returns best script found, even if below threshold!
    return await self.run_iterations(script, iterations=max_iterations, ...)
```

### Proposed Fix

#### Step 1: Add Quality Floor Configuration

```python
# packages/core/config.py

class Settings(BaseSettings):
    # ... existing ...
    
    # Quality thresholds
    SCRIPT_QUALITY_THRESHOLD: float = 85.0  # Target threshold
    SCRIPT_QUALITY_FLOOR: float = 60.0      # Minimum acceptable score
    SCRIPT_MAX_ITERATIONS: int = 20         # Max evolution iterations
    SCRIPT_ESCALATION_THRESHOLD: int = 3    # Failures before escalation
```

#### Step 2: Add Quality Floor Enforcement

```python
# packages/content_factory/evaluation/loop.py

from packages.core.errors import QualityGateError
from packages.core.config import get_settings

class ExperimentLoop:
    def __init__(self, ...):
        settings = get_settings()
        self.threshold = settings.SCRIPT_QUALITY_THRESHOLD
        self.floor = settings.SCRIPT_QUALITY_FLOOR
        self.max_iterations = settings.SCRIPT_MAX_ITERATIONS
    
    async def run_with_quality_gate(
        self,
        script: AdaptedScript,
        enforce_floor: bool = True,
    ) -> AdaptedScript:
        """
        Run evolution loop with quality floor enforcement.
        
        Args:
            script: Initial script to evolve
            enforce_floor: If True, raise error if floor not met
        
        Returns:
            Script that meets threshold or best found
        
        Raises:
            QualityGateError: If score below floor and enforce_floor=True
        """
        # Run evolution
        best_script = await self.run_with_threshold(
            script,
            threshold=self.threshold,
            max_iterations=self.max_iterations
        )
        
        final_score = best_script.production_readiness_score
        
        # Check threshold met
        if final_score >= self.threshold:
            log.info(
                f"quality_gate_passed: score={final_score:.1f}% "
                f"threshold={self.threshold}%"
            )
            return best_script
        
        # Check floor
        if final_score < self.floor:
            log.error(
                f"quality_floor_failed: score={final_score:.1f}% "
                f"floor={self.floor}% threshold={self.threshold}%"
            )
            
            if enforce_floor:
                raise QualityGateError(
                    f"Script quality {final_score:.1f}% below minimum floor {self.floor}%. "
                    f"Consider: (1) more research, (2) simpler topic, (3) manual review"
                )
        
        # Between floor and threshold - acceptable but not ideal
        log.warning(
            f"quality_below_threshold: score={final_score:.1f}% "
            f"threshold={self.threshold}% floor={self.floor}%"
        )
        
        return best_script
    
    def get_quality_report(self, script: AdaptedScript) -> dict:
        """Generate quality report for a script."""
        score = script.production_readiness_score
        
        return {
            "score": score,
            "threshold": self.threshold,
            "floor": self.floor,
            "status": self._get_status(score),
            "failed_checks": [
                {
                    "id": c.question_id,
                    "question": c.question_text,
                    "reason": c.failure_reason
                }
                for c in script.self_check_results
                if not c.passed
            ],
            "iterations": self.iteration_count if hasattr(self, 'iteration_count') else 0,
        }
    
    def _get_status(self, score: float) -> str:
        """Get quality status string."""
        if score >= self.threshold:
            return "production_ready"
        elif score >= self.floor:
            return "acceptable_below_threshold"
        else:
            return "below_quality_floor"
```

#### Step 3: Add Quality Gate Error

```python
# packages/core/errors.py

class QualityGateError(Exception):
    """Raised when script quality is below minimum acceptable threshold."""
    
    def __init__(self, message: str, score: float = None, floor: float = None):
        super().__init__(message)
        self.score = score
        self.floor = floor
```

#### Step 4: Update Pipeline Handler

```python
# packages/pipeline/handlers.py

async def handle_script_writing(run: PipelineRun) -> dict:
    """Handle script writing with quality gate enforcement."""
    
    # ... existing setup ...
    
    try:
        # Use quality gate enforcement
        final_script = await loop.run_with_quality_gate(
            script=initial_script,
            enforce_floor=True
        )
        
        return {
            "status": "completed",
            "script": final_script.model_dump(),
            "quality_report": loop.get_quality_report(final_script),
        }
    
    except QualityGateError as e:
        log.error(f"script_quality_failed: {e}")
        
        # Check if we should escalate
        if await _should_escalate(run):
            await _create_escalation(run, e)
        
        return {
            "status": "quality_failed",
            "error": str(e),
            "score": e.score,
            "floor": e.floor,
            "escalated": True,
        }
```

#### Step 5: Add Escalation System

```python
# packages/pipeline/escalation.py (NEW FILE)

from pathlib import Path
import json
from datetime import datetime, timezone

from packages.core.config import get_settings
from packages.core.logger import get_logger

log = get_logger(__name__)


async def _should_escalate(run: PipelineRun) -> bool:
    """Check if this run has too many quality failures."""
    settings = get_settings()
    
    # Count previous failures
    failure_count = run.stage_outputs.get("script_writing", {}).get("failure_count", 0)
    
    return failure_count >= settings.SCRIPT_ESCALATION_THRESHOLD


async def _create_escalation(run: PipelineRun, error: QualityGateError) -> None:
    """Create escalation record for human review."""
    settings = get_settings()
    
    escalation_dir = Path(settings.DATA_DIR) / "escalations"
    escalation_dir.mkdir(parents=True, exist_ok=True)
    
    escalation = {
        "run_id": run.run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "type": "quality_gate_failure",
        "score": error.score,
        "floor": error.floor,
        "message": str(error),
        "topic": run.stage_outputs.get("human_topic_approval", {}).get("topic_statement"),
        "requires_action": True,
    }
    
    escalation_file = escalation_dir / f"{run.run_id}_quality.json"
    with open(escalation_file, "w") as f:
        json.dump(escalation, f, indent=2)
    
    log.info(f"escalation_created: run_id={run.run_id} score={error.score}")


def list_escalations() -> list[dict]:
    """List all pending escalations."""
    settings = get_settings()
    escalation_dir = Path(settings.DATA_DIR) / "escalations"
    
    escalations = []
    for f in escalation_dir.glob("*.json"):
        try:
            with open(f) as fp:
                escalation = json.load(fp)
                if escalation.get("requires_action"):
                    escalations.append(escalation)
        except Exception:
            pass
    
    return sorted(escalations, key=lambda x: x.get("created_at", ""), reverse=True)
```

### Implementation Steps

| Step | File | Action |
|------|------|--------|
| 1 | `packages/core/config.py` | Add quality threshold settings |
| 2 | `packages/core/errors.py` | Add `QualityGateError` |
| 3 | `packages/content_factory/evaluation/loop.py` | Add `run_with_quality_gate()` |
| 4 | `packages/pipeline/handlers.py` | Use quality gate in handler |
| 5 | `packages/pipeline/escalation.py` | Create escalation system |

### Testing

```python
# tests/test_quality_gate.py

import pytest
from packages.content_factory.evaluation.loop import ExperimentLoop
from packages.core.errors import QualityGateError


@pytest.mark.asyncio
async def test_quality_gate_passes_above_threshold():
    """Should pass when score >= threshold."""
    loop = ExperimentLoop()
    loop.threshold = 85.0
    loop.floor = 60.0
    
    # Mock script with high score
    script = create_mock_script(score=90.0)
    
    result = await loop.run_with_quality_gate(script, enforce_floor=True)
    
    assert result.production_readiness_score >= 85.0


@pytest.mark.asyncio
async def test_quality_gate_accepts_between_floor_and_threshold():
    """Should accept when floor <= score < threshold."""
    loop = ExperimentLoop()
    loop.threshold = 85.0
    loop.floor = 60.0
    
    script = create_mock_script(score=75.0)
    
    result = await loop.run_with_quality_gate(script, enforce_floor=True)
    
    assert result.production_readiness_score >= 60.0


@pytest.mark.asyncio
async def test_quality_gate_rejects_below_floor():
    """Should raise error when score < floor."""
    loop = ExperimentLoop()
    loop.threshold = 85.0
    loop.floor = 60.0
    
    script = create_mock_script(score=50.0)
    
    with pytest.raises(QualityGateError) as exc:
        await loop.run_with_quality_gate(script, enforce_floor=True)
    
    assert exc.value.score == 50.0
    assert exc.value.floor == 60.0
```

---

## P0-06: Web Search Fallback Generates Fake URLs

### Issue Description
When web search fails, there's a fallback that generates hallucinated/fake URLs instead of returning empty results.

### Current Code (Problem)

```python
# packages/router/web_search.py (assumed - check actual implementation)

async def search(self, query: str) -> list[SearchResult]:
    try:
        results = await self._do_search(query)
        return results
    except Exception:
        # BAD: Returns fake URLs instead of empty list!
        return [
            SearchResult(url="https://example.com/placeholder", ...)
        ]
```

### Proposed Fix

#### Step 1: Remove Fallback Hallucination

```python
# packages/router/web_search.py

import asyncio
from typing import Optional
from dataclasses import dataclass

from packages.core.logger import get_logger
from packages.core.config import get_settings

log = get_logger(__name__)


@dataclass
class SearchResult:
    """Web search result."""
    url: str
    title: str
    snippet: str
    source: str = "web_search"
    rank: int = 0


class WebSearchClient:
    """Web search client with proper error handling."""
    
    def __init__(self):
        settings = get_settings()
        self._rate_limit_delay = 0.5  # Seconds between searches
        self._semaphore = asyncio.Semaphore(2)  # Max concurrent searches
        self._initialized = False
        self._sdk = None
    
    async def _ensure_initialized(self) -> bool:
        """Initialize the search SDK. Returns True if successful."""
        if self._initialized:
            return self._sdk is not None
        
        try:
            # Try to import z-ai-web-dev-sdk
            import z_ai_web_dev_sdk as zai
            self._sdk = zai
            self._initialized = True
            log.info("web_search_initialized: sdk=z-ai-web-dev-sdk")
            return True
        except ImportError:
            log.warning(
                "web_search_sdk_not_available: "
                "Install z-ai-web-dev-sdk or set up alternative search provider"
            )
            self._initialized = True
            return False
    
    async def search(
        self,
        query: str,
        num_results: int = 10,
    ) -> list[SearchResult]:
        """
        Execute a web search.
        
        Args:
            query: Search query
            num_results: Maximum results to return
        
        Returns:
            List of SearchResult objects (may be empty)
        
        Note:
            Returns EMPTY LIST on failure, never fake URLs.
        """
        # Initialize if needed
        if not await self._ensure_initialized():
            log.warning(f"web_search_unavailable: query='{query[:50]}...' sdk_not_installed")
            return []
        
        # Use semaphore for rate limiting
        async with self._semaphore:
            try:
                results = await self._execute_search(query, num_results)
                
                if not results:
                    log.info(f"web_search_empty: query='{query[:50]}...'")
                else:
                    log.info(f"web_search_success: query='{query[:50]}...' count={len(results)}")
                
                return results
            
            except Exception as e:
                log.error(f"web_search_failed: query='{query[:50]}...' error={e}")
                # CRITICAL: Return empty list, NOT fake URLs
                return []
    
    async def _execute_search(
        self,
        query: str,
        num_results: int,
    ) -> list[SearchResult]:
        """Execute search using SDK."""
        if self._sdk is None:
            return []
        
        try:
            zai = await self._sdk.create()
            results = await zai.functions.invoke(
                "web_search",
                {"query": query, "num": num_results}
            )
            
            # Convert to SearchResult objects
            search_results = []
            for i, item in enumerate(results):
                search_results.append(SearchResult(
                    url=item.get("url", ""),
                    title=item.get("name", ""),
                    snippet=item.get("snippet", ""),
                    source="web_search",
                    rank=i,
                ))
            
            return search_results
        
        except Exception as e:
            log.error(f"web_search_sdk_error: {e}")
            return []
    
    async def multi_search(
        self,
        queries: list[str],
        num_per_query: int = 5,
        delay: float = None,
    ) -> dict[str, list[SearchResult]]:
        """
        Execute multiple searches with rate limiting.
        
        Args:
            queries: List of search queries
            num_per_query: Results per query
            delay: Delay between searches (default from config)
        
        Returns:
            Dict mapping query to results
        """
        delay = delay or self._rate_limit_delay
        results = {}
        
        for query in queries:
            results[query] = await self.search(query, num_per_query)
            await asyncio.sleep(delay)  # Rate limiting
        
        return results
```

#### Step 2: Add Fallback to LLM Knowledge (Optional)

```python
# packages/router/web_search.py

class WebSearchClient:
    # ... existing code ...
    
    async def search_with_fallback(
        self,
        query: str,
        fallback_to_llm: bool = False,
        llm_client = None,
    ) -> tuple[list[SearchResult], str]:
        """
        Search with optional LLM knowledge fallback.
        
        Args:
            query: Search query
            fallback_to_llm: If True, use LLM when web search fails
            llm_client: RouterClient for LLM fallback
        
        Returns:
            Tuple of (results, source) where source is "web_search" or "llm_knowledge"
        """
        # Try web search first
        results = await self.search(query)
        
        if results:
            return results, "web_search"
        
        # Web search failed or returned empty
        if fallback_to_llm and llm_client:
            log.info(f"web_search_fallback_llm: query='{query[:50]}...'")
            
            llm_result = await self._search_via_llm(query, llm_client)
            return llm_result, "llm_knowledge"
        
        # No fallback available
        return [], "web_search"
    
    async def _search_via_llm(
        self,
        query: str,
        llm_client,
    ) -> list[SearchResult]:
        """
        Use LLM's knowledge as fallback.
        
        IMPORTANT: Results are marked as "llm_knowledge" to distinguish
        from actual web search results.
        """
        prompt = f"""I need information about: {query}

Please provide 3-5 key facts or pieces of information you know about this topic.
Format each as a separate point. Only include information you're confident about.

If you don't have reliable information about this specific topic, say so."""

        try:
            response = await llm_client.complete_text(prompt)
            
            # Parse response into pseudo-results
            # These are marked as LLM knowledge, not web URLs
            return [
                SearchResult(
                    url="llm://knowledge",  # Special URL to indicate LLM source
                    title=f"LLM Knowledge: {query[:50]}",
                    snippet=response,
                    source="llm_knowledge",
                )
            ]
        except Exception as e:
            log.error(f"llm_fallback_failed: {e}")
            return []
```

#### Step 3: Update Research Engine

```python
# packages/content_factory/production/deep_research.py

class DeepResearchEngine:
    async def _search_for_facts(
        self,
        query: str,
        dimension: str,
    ) -> list[ResearchFact]:
        """Search for facts with proper handling of empty results."""
        
        results, source = await self.web_search.search_with_fallback(
            query=query,
            fallback_to_llm=self.config.get("fallback_to_llm", False),
            llm_client=self.router_client,
        )
        
        if not results:
            log.warning(
                f"research_no_results: dimension={dimension} query='{query[:50]}...'"
            )
            return []
        
        # Extract facts from results
        facts = []
        for result in results:
            if result.source == "llm_knowledge":
                # Mark LLM-sourced facts with lower confidence
                facts.append(ResearchFact(
                    statement=result.snippet,
                    source="llm_knowledge",
                    confidence=0.6,  # Lower confidence for LLM knowledge
                ))
            else:
                facts.append(ResearchFact(
                    statement=result.snippet,
                    source=result.url,
                    confidence=0.8,
                ))
        
        return facts
```

### Implementation Steps

| Step | File | Action |
|------|------|--------|
| 1 | `packages/router/web_search.py` | Remove fake URL fallback |
| 2 | `packages/router/web_search.py` | Add `search_with_fallback()` method |
| 3 | `packages/router/web_search.py` | Add LLM knowledge fallback (optional) |
| 4 | `packages/content_factory/production/deep_research.py` | Handle empty results |
| 5 | Add logging for empty results | Debug visibility |

### Testing

```python
# tests/test_web_search.py

import pytest
from packages.router.web_search import WebSearchClient


@pytest.mark.asyncio
async def test_search_returns_empty_on_failure():
    """Should return empty list, not fake URLs."""
    client = WebSearchClient()
    client._sdk = None  # Force failure
    
    results = await client.search("test query")
    
    assert results == []
    assert not any("example.com" in r.url for r in results)


@pytest.mark.asyncio
async def test_search_result_has_source():
    """All results should have valid source."""
    client = WebSearchClient()
    
    results = await client.search("test query")
    
    for result in results:
        assert result.source in ["web_search", "llm_knowledge"]
        if result.source == "llm_knowledge":
            assert "llm://" in result.url


@pytest.mark.asyncio
async def test_multi_search_rate_limits():
    """Multi-search should delay between queries."""
    client = WebSearchClient()
    
    import time
    start = time.time()
    
    await client.multi_search(["query1", "query2", "query3"], delay=0.1)
    
    elapsed = time.time() - start
    
    # Should have delays between queries
    assert elapsed >= 0.2  # At least 2 delays of 0.1s
```

---

## P0-07: CORS Wildcard

### Issue Description
CORS is configured with `allow_origins=["*"]` which permits any origin. This is a security risk.

### Current Code (Problem)

```python
# apps/api/main.py

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # DANGEROUS!
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Proposed Fix

#### Step 1: Add CORS Configuration

```python
# packages/core/config.py

class Settings(BaseSettings):
    # ... existing ...
    
    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8000"
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "GET,POST,PUT,DELETE,OPTIONS"
    CORS_ALLOW_HEADERS: str = "*"
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins into list."""
        if not self.CORS_ORIGINS:
            return []
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]
    
    @property
    def cors_methods_list(self) -> list[str]:
        """Parse CORS methods into list."""
        if not self.CORS_ALLOW_METHODS:
            return ["*"]
        return [m.strip() for m in self.CORS_ALLOW_METHODS.split(",") if m.strip()]
```

#### Step 2: Update Main App

```python
# apps/api/main.py

from fastapi.middleware.cors import CORSMiddleware

from packages.core.config import get_settings

settings = get_settings()

app = FastAPI(title="AI Orchestration API")

# CORS with proper origin restriction
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.cors_methods_list,
    allow_headers=["*"],  # Headers are okay to allow all
)
```

#### Step 3: Add Environment Configuration

```bash
# .env

# CORS - Comma-separated list of allowed origins
# For development:
CORS_ORIGINS=http://localhost:3000,http://localhost:8000

# For production:
# CORS_ORIGINS=https://your-domain.com,https://app.your-domain.com

# For testing (if needed):
# CORS_ORIGINS=*
```

#### Step 4: Add CORS Debug Endpoint

```python
# apps/api/routers/settings_routes.py

@router.get("/cors")
async def get_cors_settings():
    """
    Get current CORS configuration.
    
    Useful for debugging CORS issues.
    """
    settings = get_settings()
    return {
        "allowed_origins": settings.cors_origins_list,
        "allowed_methods": settings.cors_methods_list,
        "allow_credentials": settings.CORS_ALLOW_CREDENTIALS,
    }
```

### Implementation Steps

| Step | File | Action |
|------|------|--------|
| 1 | `packages/core/config.py` | Add CORS settings |
| 2 | `apps/api/main.py` | Use configured CORS origins |
| 3 | `.env.example` | Add CORS_ORIGINS example |
| 4 | `apps/api/routers/settings_routes.py` | Add CORS debug endpoint |

### Testing

```bash
# Test 1: Allowed origin
curl -H "Origin: http://localhost:3000" \
     -H "Access-Control-Request-Method: GET" \
     -X OPTIONS http://localhost:8000/api/pipeline/runs
# Expected: 200 with Access-Control-Allow-Origin header

# Test 2: Disallowed origin
curl -H "Origin: https://evil.com" \
     -H "Access-Control-Request-Method: GET" \
     -X OPTIONS http://localhost:8000/api/pipeline/runs
# Expected: No Access-Control-Allow-Origin header
```

---

## P0-08: No Retry Logic for Publish

### Issue Description
When Notion publish fails (rate limit, network error), there's no retry mechanism. The entire pipeline must be re-run.

### Current Code (Problem)

```python
# packages/pipeline/handlers.py

async def handle_publish(run: PipelineRun) -> dict:
    # One-shot attempt - no retry!
    result = await notion_client.create_script_page(...)
    return result
```

### Proposed Fix

#### Step 1: Add Retry Decorator

```python
# packages/core/retry.py (NEW FILE)

import asyncio
import random
from functools import wraps
from typing import Callable, Type, Tuple

from packages.core.logger import get_logger

log = get_logger(__name__)


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Callable = None,
):
    """
    Retry decorator with exponential backoff.
    
    Args:
        max_attempts: Maximum number of attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap
        exponential_base: Base for exponential calculation
        jitter: Add random jitter to prevent thundering herd
        exceptions: Exception types to catch
        on_retry: Callback function on retry (attempt, exception, delay)
    
    Usage:
        @retry_with_backoff(max_attempts=3, exceptions=(httpx.HTTPError,))
        async def my_function():
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts:
                        log.error(
                            f"retry_exhausted: func={func.__name__} "
                            f"attempts={max_attempts} error={e}"
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(
                        base_delay * (exponential_base ** (attempt - 1)),
                        max_delay
                    )
                    
                    # Add jitter
                    if jitter:
                        delay = delay * (0.5 + random.random())
                    
                    log.warning(
                        f"retry_attempt: func={func.__name__} "
                        f"attempt={attempt}/{max_attempts} "
                        f"delay={delay:.2f}s error={e}"
                    )
                    
                    # Callback
                    if on_retry:
                        on_retry(attempt, e, delay)
                    
                    await asyncio.sleep(delay)
            
            # Should not reach here, but just in case
            raise last_exception
        
        return wrapper
    return decorator


def retry_on_rate_limit(func):
    """Convenience decorator for rate-limited APIs."""
    return retry_with_backoff(
        max_attempts=5,
        base_delay=2.0,
        max_delay=60.0,
        exceptions=(Exception,),  # Catch all, let function decide
    )(func)
```

#### Step 2: Update Notion Client

```python
# packages/integrations/notion/client.py

from packages.core.retry import retry_with_backoff
import httpx


class NotionClient:
    # ... existing code ...
    
    @retry_with_backoff(
        max_attempts=3,
        base_delay=2.0,
        max_delay=30.0,
        exceptions=(httpx.HTTPStatusError, httpx.NetworkError),
    )
    async def create_script_page(
        self,
        title: str,
        script_data: dict,
        seo_data: dict = None,
    ) -> dict:
        """
        Create a script page in Notion with retry logic.
        
        Retries on:
        - Rate limits (429)
        - Server errors (5xx)
        - Network errors
        
        Does NOT retry on:
        - Authentication errors (401, 403)
        - Not found errors (404)
        - Validation errors (400)
        """
        if not self._check_client():
            log.warning("notion_not_configured: skipping publish")
            return {"status": "skipped", "reason": "not_configured"}
        
        try:
            # Create page
            response = await self._client.pages.create(
                parent={"database_id": self.database_id},
                properties=self._build_properties(title, script_data, seo_data),
                children=self._build_blocks(script_data),
            )
            
            log.info(f"notion_page_created: page_id={response['id']}")
            return {
                "status": "success",
                "page_id": response["id"],
                "url": response.get("url"),
            }
        
        except httpx.HTTPStatusError as e:
            # Don't retry client errors
            if e.response.status_code in (400, 401, 403, 404):
                log.error(f"notion_client_error: {e.response.status_code} - {e}")
                return {
                    "status": "error",
                    "error": f"Client error: {e.response.status_code}",
                    "retryable": False,
                }
            
            # Retry server errors and rate limits
            log.warning(f"notion_retryable_error: {e.response.status_code}")
            raise  # Let retry decorator handle it
        
        except httpx.NetworkError as e:
            log.warning(f"notion_network_error: {e}")
            raise  # Let retry decorator handle it
```

#### Step 3: Update Pipeline Handler

```python
# packages/pipeline/handlers.py

async def handle_publish(run: PipelineRun) -> dict:
    """
    Handle publishing with retry and dead letter queue.
    """
    script = run.stage_outputs.get("script_writing", {}).get("script")
    seo_data = run.stage_outputs.get("seo_optimization", {})
    
    if not script:
        return {"status": "error", "error": "No script to publish"}
    
    notion_client = NotionClient()
    
    try:
        result = await notion_client.create_script_page(
            title=script.get("adapted_title", "Untitled"),
            script_data=script,
            seo_data=seo_data,
        )
        
        if result.get("status") == "success":
            return {
                "status": "published",
                "notion_page_id": result["page_id"],
                "notion_url": result.get("url"),
            }
        
        # Non-retryable error
        if not result.get("retryable", True):
            # Queue for later retry
            await queue_for_retry("notion_publish", {
                "run_id": run.run_id,
                "script": script,
                "seo_data": seo_data,
            })
            
            return {
                "status": "queued_for_retry",
                "error": result.get("error"),
            }
        
        return result
    
    except Exception as e:
        log.error(f"publish_failed_all_retries: {e}")
        
        # Queue for manual retry
        await queue_for_retry("notion_publish", {
            "run_id": run.run_id,
            "script": script,
            "seo_data": seo_data,
            "error": str(e),
        })
        
        return {
            "status": "failed",
            "error": str(e),
            "queued_for_retry": True,
        }
```

#### Step 4: Add Dead Letter Queue

```python
# packages/core/dead_letter.py (NEW FILE)

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from packages.core.config import get_settings
from packages.core.logger import get_logger

log = get_logger(__name__)


def queue_for_retry(operation: str, payload: dict[str, Any]) -> None:
    """
    Queue a failed operation for later retry.
    
    Args:
        operation: Operation type (e.g., "notion_publish")
        payload: Data needed to retry the operation
    """
    settings = get_settings()
    dlq_path = Path(settings.DATA_DIR) / "dead_letter_queue.jsonl"
    dlq_path.parent.mkdir(parents=True, exist_ok=True)
    
    entry = {
        "operation": operation,
        "payload": payload,
        "queued_at": datetime.now(timezone.utc).isoformat(),
        "retry_count": 0,
        "status": "pending",
    }
    
    with open(dlq_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    
    log.info(f"dead_letter_queued: operation={operation}")


def get_pending_retries(operation: str = None) -> list[dict]:
    """
    Get all pending retry operations.
    
    Args:
        operation: Filter by operation type (optional)
    
    Returns:
        List of pending retry entries
    """
    settings = get_settings()
    dlq_path = Path(settings.DATA_DIR) / "dead_letter_queue.jsonl"
    
    if not dlq_path.exists():
        return []
    
    entries = []
    with open(dlq_path) as f:
        for line in f:
            if line.strip():
                entry = json.loads(line)
                if entry.get("status") == "pending":
                    if operation is None or entry.get("operation") == operation:
                        entries.append(entry)
    
    return entries


async def process_retry_queue() -> dict:
    """
    Process all pending retry operations.
    
    Returns:
        Summary of processed entries
    """
    from packages.integrations.notion.client import NotionClient
    
    results = {"processed": 0, "succeeded": 0, "failed": 0}
    
    pending = get_pending_retries()
    
    for entry in pending:
        operation = entry.get("operation")
        payload = entry.get("payload", {})
        
        try:
            if operation == "notion_publish":
                client = NotionClient()
                result = await client.create_script_page(
                    title=payload.get("script", {}).get("adapted_title", "Untitled"),
                    script_data=payload.get("script", {}),
                    seo_data=payload.get("seo_data"),
                )
                
                if result.get("status") == "success":
                    results["succeeded"] += 1
                    entry["status"] = "completed"
                else:
                    results["failed"] += 1
                    entry["retry_count"] += 1
            
            results["processed"] += 1
        
        except Exception as e:
            log.error(f"retry_failed: operation={operation} error={e}")
            results["failed"] += 1
            entry["retry_count"] += 1
    
    log.info(f"retry_queue_processed: {results}")
    return results
```

#### Step 5: Add API Endpoints

```python
# apps/api/routers/pipeline_routes.py

@router.get("/retry-queue")
async def get_retry_queue():
    """Get pending operations in the retry queue."""
    from packages.core.dead_letter import get_pending_retries
    return {"pending": get_pending_retries()}


@router.post("/retry-queue/process")
async def process_retry_queue():
    """Manually trigger processing of retry queue."""
    from packages.core.dead_letter import process_retry_queue
    results = await process_retry_queue()
    return results
```

### Implementation Steps

| Step | File | Action |
|------|------|--------|
| 1 | `packages/core/retry.py` | Create retry decorator |
| 2 | `packages/integrations/notion/client.py` | Add retry to publish |
| 3 | `packages/core/dead_letter.py` | Create dead letter queue |
| 4 | `packages/pipeline/handlers.py` | Use retry + DLQ |
| 5 | `apps/api/routers/pipeline_routes.py` | Add retry queue endpoints |

### Testing

```python
# tests/test_retry_logic.py

import pytest
from packages.core.retry import retry_with_backoff


class MockError(Exception):
    pass


@pytest.mark.asyncio
async def test_retry_succeeds_after_failures():
    """Should retry and succeed after failures."""
    call_count = 0
    
    @retry_with_backoff(max_attempts=3, base_delay=0.1, exceptions=(MockError,))
    async def failing_then_succeeding():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise MockError("Not yet")
        return "success"
    
    result = await failing_then_succeeding()
    
    assert result == "success"
    assert call_count == 3


@pytest.mark.asyncio
async def test_retry_exhausted():
    """Should raise after max attempts."""
    @retry_with_backoff(max_attempts=3, base_delay=0.1, exceptions=(MockError,))
    async def always_fails():
        raise MockError("Always fails")
    
    with pytest.raises(MockError):
        await always_fails()


@pytest.mark.asyncio
async def test_dead_letter_queue():
    """Should queue failed operations."""
    from packages.core.dead_letter import queue_for_retry, get_pending_retries
    
    queue_for_retry("test_operation", {"test": "data"})
    
    pending = get_pending_retries("test_operation")
    
    assert len(pending) > 0
    assert pending[0]["operation"] == "test_operation"
```

---

## Summary

| P0 Issue | Estimated Time | Complexity |
|----------|---------------|------------|
| 01 - No API Authentication | 4 hours | Medium |
| 02 - No FreeRouter Health Check | 2 hours | Low |
| 03 - No API Key Validation | 2 hours | Low |
| 04 - No Resume Method | 4 hours | Medium |
| 05 - No Quality Floor | 3 hours | Medium |
| 06 - Web Search Hallucinations | 2 hours | Low |
| 07 - CORS Wildcard | 1 hour | Low |
| 08 - No Retry Logic | 3 hours | Medium |

**Total Estimated Time:** ~21 hours (3 days)

**Recommended Order:**
1. P0-01 (Auth) - Blocks production use
2. P0-07 (CORS) - Related to auth
3. P0-02 (Health Check) - Improves reliability
4. P0-04 (Resume) - Enables recovery
5. P0-05 (Quality Floor) - Ensures output quality
6. P0-06 (Web Search) - Data integrity
7. P0-03 (API Key Validation) - Better UX
8. P0-08 (Retry) - Resilience
