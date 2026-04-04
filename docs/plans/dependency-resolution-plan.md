# Dependency Resolution Plan

## Problem Summary

The project had conflicting dependencies between **CrewAI** and **LangGraph**, both of which depend on the `langchain` ecosystem with incompatible version requirements.

### Original Conflict

| Package | Old Requirement | Problem |
|---------|-----------------|---------|
| `crewai` | `langchain-core < 0.3` | Required older langchain |
| `langgraph` | `langchain-core >= 0.3` | Required newer langchain |

This made it **impossible** to install both packages together.

---

## Solution: Updated CrewAI Version

**CrewAI >= 0.86.0 now supports `langchain-core 0.3.x`**, making it compatible with LangGraph!

### Compatible Version Matrix

| Package | Minimum Version | Works With |
|---------|-----------------|------------|
| `crewai` | >= 0.86.0 | langchain-core 0.3.x ✅ |
| `crewai-tools` | >= 0.14.0 | langchain-core 0.3.x ✅ |
| `langgraph` | >= 0.2.0 | langchain-core 0.3.x ✅ |
| `langchain-core` | >= 0.3.0 | **Both!** ✅ |
| `langchain` | >= 0.3.0 | **Both!** ✅ |

---

## Implementation

### Updated `pyproject.toml`

```toml
[project.optional-dependencies]
# LangGraph state machine with PostgreSQL checkpointer
# Compatible with CrewAI when using langchain-core 0.3.x
langgraph-deps = [
    "langgraph>=0.2.0",
    "langchain-core>=0.3.0",
    "langchain>=0.3.0",
    "psycopg[binary]>=3.1.0",
    "psycopg-pool>=3.2.0",
]

# CrewAI agents - updated versions that support langchain-core 0.3.x
# IMPORTANT: CrewAI >= 0.86.0 is required for langchain-core 0.3.x compatibility
crewai-deps = [
    "crewai>=0.86.0",
    "crewai-tools>=0.14.0",
    "litellm>=1.52.0",
]

# Full installation with BOTH CrewAI and LangGraph
all = [
    "ai-orchestration[dev,memory,youtube,notion,pipeline,langgraph-deps,crewai-deps]",
]
```

### Version Strategy

We use **minimum version requirements** (not pinned versions) so pip will always install the latest compatible versions:

- `crewai>=0.86.0` → Installs latest CrewAI (0.90+, 0.95+, etc.)
- `langgraph>=0.2.0` → Installs latest LangGraph
- `langchain-core>=0.3.0` → Installs latest langchain-core

This ensures you get bug fixes and new features automatically while maintaining compatibility.

---

## Installation Commands

### Standard Installation (Recommended)

```bash
# Install everything (CrewAI + LangGraph)
pip install -e ".[all]"

# Or use the Makefile
make install
```

### Windows Installation

```bash
# Use Windows-specific requirements if psycopg[binary] fails
pip install -r requirements-windows.txt
pip install -e ".[all]"

# Or use the Makefile
make install-windows
```

### Clean Install (if you have conflicts)

```bash
# Remove old packages and reinstall
make install-clean
```

### Minimal Installation (no CrewAI/LangGraph)

```bash
# Core only - for FreeRouter proxy usage
pip install -e "."

# Or use the Makefile
make install-minimal
```

---

## Files Created

| File | Purpose |
|------|---------|
| [`pyproject.toml`](../pyproject.toml) | Updated with compatible dependency groups (minimum versions) |
| [`requirements.txt`](../requirements.txt) | Minimum version requirements for pip |
| [`requirements-windows.txt`](../requirements-windows.txt) | Windows-specific (uses `psycopg-binary`) |
| [`Makefile`](../Makefile) | New install commands (`make install`, `make status`) |

---

## Verification

After installation, verify everything works:

```bash
# Check installation status
make status

# Expected output:
# CrewAI: OK
# LangGraph: OK
# psycopg: OK
```

Or manually:

```python
# Test CrewAI
from crewai import Agent
print("CrewAI: OK")

# Test LangGraph
from langgraph.graph import StateGraph
print("LangGraph: OK")

# Test psycopg
from psycopg_pool import AsyncConnectionPool
print("psycopg: OK")
```

---

## Troubleshooting

### Issue: `psycopg[binary]` fails on Windows

**Solution**: Use `psycopg-binary` instead:

```bash
pip uninstall psycopg
pip install psycopg-binary>=3.1.0
```

Or use `requirements-windows.txt`:

```bash
pip install -r requirements-windows.txt
```

### Issue: CrewAI import errors

**Solution**: Ensure you have CrewAI >= 0.86.0:

```bash
pip install crewai>=0.86.0 --upgrade
```

### Issue: LangGraph import errors

**Solution**: Ensure langchain-core is >= 0.3.0:

```bash
pip install langchain-core>=0.3.0 --upgrade
```

### Issue: Version conflicts after upgrade

**Solution**: Clean install:

```bash
make install-clean
```

### Issue: "No matching distribution found"

**Solution**: Upgrade pip and setuptools:

```bash
pip install --upgrade pip setuptools wheel
pip install -e ".[all]"
```

---

## Summary

| Installation | Command | CrewAI | LangGraph | Use Case |
|--------------|---------|--------|-----------|----------|
| Full | `make install` | ✅ | ✅ | Development (recommended) |
| Minimal | `make install-minimal` | ❌ | ❌ | FreeRouter proxy only |
| Windows | `make install-windows` | ✅ | ✅ | Windows compatibility |
| Clean | `make install-clean` | ✅ | ✅ | Fix broken installs |

**Both CrewAI and LangGraph can now coexist!** The key is using CrewAI >= 0.86.0 which supports `langchain-core 0.3.x`.

---

## Why Minimum Versions (Not Pinned)?

Using `>=` instead of `==` allows pip to:

1. **Get latest bug fixes** automatically
2. **Resolve conflicts** by finding compatible versions
3. **Stay current** without manual updates

If you need exact reproducibility, create a lock file:

```bash
pip install -e ".[all]"
pip freeze > requirements-lock.txt
```

Then use `requirements-lock.txt` for deployments.