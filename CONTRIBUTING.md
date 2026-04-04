# Contributing to AI-Orchestration

Thank you for contributing! This document explains how to set up, develop, and submit changes.

---

## Development Setup

### Prerequisites

- **Python 3.10+** (3.11 recommended)
- **Git**
- An LLM API key (Groq or OpenRouter)

### Why These Requirements?

- **Python 3.10+**: We use modern async/await patterns and type hints
- **LLM API key**: The system needs an LLM for content generation
- **No database setup**: SQLite is zero-config and file-based

### Quick Setup

```bash
# 1. Clone the repository
git clone https://github.com/HassanArif-collab/AI-Orchestration.git
cd AI-Orchestration

# 2. Install in development mode
pip install -e ".[dev]"

# 3. Configure FreeRouter (port 4000)
cd freerouter
cp .env.example .env
# Edit .env: Add GROQ_API_KEY or OPENROUTER_API_KEY

# 4. Configure main app
cd ..
cp .env.example .env
# Add optional keys: ZEP_API_KEY, YOUTUBE_API_KEY

# 5. Start services (two terminals)
python -m freerouter proxy          # Terminal 1
python -m apps.api.main             # Terminal 2
```

### Verify Setup

```bash
# Run tests
pytest tests/ -q

# Check code style
ruff check packages/ apps/
```

---

## Architecture Overview

Before contributing, understand the key architectural decisions:

| Decision | Reason |
|----------|--------|
| Two services | LLM complexity isolated from business logic |
| All LLM calls through RouterClient | Centralized failover, rate limiting, cost tracking |
| SQLite for state | Zero-config, concurrent-safe with WAL |
| 9 stages with human gates | Oversight at critical decisions |

See [docs/archive/DECISIONS.md](docs/archive/DECISIONS.md) for detailed reasoning.

---

## Code Style

### Naming

Use descriptive names. Code should be self-documenting.

```python
# ❌ BAD
x = get_data()
tmp = process(d)

# ✅ GOOD
topic_brief = get_topic_brief()
adapted_script = adapt_for_local_audience(source_content)
```

### Docstrings

Every public function should have a docstring explaining "why":

```python
async def create_task_internal(title: str, stage: int = 1) -> str:
    """Create a Kanban task directly in SQLite.

    Why this exists:
        Pipeline routes used to make HTTP calls to themselves,
        which was fragile and failed silently. This function
        provides direct database access for reliability.

    Args:
        title: Task title
        stage: Kanban column (1-6)

    Returns:
        The task ID
    """
```

### Imports

Follow this order:
1. Standard library
2. Third-party packages
3. Local packages (`packages.*`, `apps.*`)

```python
# Standard library
import asyncio
from pathlib import Path

# Third-party
import httpx
from pydantic import BaseModel

# Local packages
from packages.core.config import get_settings
from packages.router.client import RouterClient
```

---

## Adding a New Pipeline Stage

### Why Follow This Process

Pipeline stages are LangGraph nodes. Adding one requires updates in multiple places to maintain consistency across the system.

### Steps

1. **Add node function** in `packages/content_factory/orchestration/nodes.py`:
```python
async def your_new_stage(state: PipelineState) -> dict:
    """Handle the your_new_stage stage."""
    # Your implementation — update state and return partial state dict
    return {"your_key": result}
```

2. **Wire into LangGraph graph** in `packages/content_factory/orchestration/graphs.py`:
```python
# Add the node to the graph
graph.add_node("your_new_stage", your_new_stage)
# Add edges to connect it
graph.add_edge("previous_stage", "your_new_stage")
```

3. **Add stage definition** in `apps/api/routers/pipeline_routes.py`:
```python
STAGE_DEFINITIONS["stages"].append({
    "name": "your_new_stage",
    "label": "Your Stage",
    "is_human_gate": False,  # Set True if human approval needed
    "dependencies": ["previous_stage"],
    "feedback_targets": []
})
```

4. **Add frontend UI** in the React app (`apps/web/src/`):
```typescript
// Add to stage labels/constants
// Add UI components for the new stage
```

5. **Add tests** in `tests/`

---

## Adding a New Agent

### Why Follow This Process

Agents inherit from BaseAgent and must register with the AgentRegistry for discovery. This ensures consistent LLM routing and skill loading.

### Steps

1. **Create the agent class** in `packages/agents/your_agent.py`:
```python
from packages.agents.base import BaseAgent

class YourAgent(BaseAgent):
    """Agent that does X.

    Why this exists:
        Explain the problem this agent solves and why
        this approach was chosen.
    """
    name = "your_agent"
    role = "Does X for the pipeline"
    capability = "your_capability"  # Maps to model selection
    skills_path = "data/skills/your_agent.md"

    async def execute(self, task: str, context: dict) -> str:
        """Execute the agent's task."""
        skills = self.load_skills()
        prompt = f"{skills}\n\nTask: {task}"
        return await self.call_llm(prompt, system="You are a helpful assistant.")
```

2. **Register the agent** in `packages/agents/__init__.py`:
```python
from packages.agents.your_agent import YourAgent

__all__ = ["YourAgent", ...]
```

3. **Create skill file** at `data/skills/your_agent.md`:
```markdown
# Your Agent

## Role
You are an AI assistant that does X.

## Rules
1. Always validate input
2. Return structured JSON
3. Handle errors gracefully

## Examples
User: [example input]
Assistant: [example output]
```

4. **Add capability mapping** in `packages/router/capabilities.py`:
```python
CAPABILITY_MODEL_MAP = {
    # ... existing mappings ...
    "your_capability": "groq/llama-3.3-70b-versatile",
}
```

5. **Add tests** in `tests/test_your_agent.py`

---

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/ -q

# Run specific test file
pytest tests/test_pipeline.py -v

# Run with coverage
pytest tests/ --cov=packages --cov=apps
```

### Writing Tests

```python
import pytest
from packages.content_factory.orchestration.nodes import your_new_stage

class TestYourFeature:
    """Tests for your feature.

    Why these tests exist:
        Explain what behavior is being verified and why it matters.
    """

    async def test_feature_works(self):
        """Test that the feature produces expected output."""
        result = await your_new_stage(state)
        assert result["your_key"] == expected_value
```

---

## Pull Request Process

### Before Submitting

1. **Run tests**: `pytest tests/ -q`
2. **Check style**: `ruff check packages/ apps/`
3. **Update documentation** if needed
4. **Add changelog entry** in `CHANGELOG.md`

### PR Template

```markdown
## What This Changes
[One-sentence summary]

## Why This Change
[Explain the problem and why this approach was chosen]

## How to Test
[Steps to verify the change works]

## Documentation Updates
- [ ] Updated relevant .md files
- [ ] Updated docstrings
- [ ] Updated CHANGELOG.md

## Screenshots (if UI change)
[Before/after if applicable]
```

### Review Criteria

PRs are reviewed for:
1. **Correctness**: Does it solve the problem?
2. **Architecture**: Does it follow the patterns?
3. **Documentation**: Is "why" explained?
4. **Tests**: Is behavior verified?

---

## Getting Help

- Open an issue for bugs or feature requests
- Check [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design
- Check [docs/archive/DECISIONS.md](docs/archive/DECISIONS.md) for decision reasoning

---

## Key Rules

1. **All LLM calls through RouterClient** — Never call provider APIs directly
2. **Config from get_settings()** — Never hardcode values
3. **No hardcoded API keys** — Always use environment variables
4. **Document "why"** — Code shows what, docs show why
5. **Test your changes** — All new code needs tests
