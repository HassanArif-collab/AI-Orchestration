## What This Changes

[One-sentence summary of the change]

## Why This Change

[Explain the problem and why this approach was chosen]

## How to Test

[Steps to verify the change works]

```bash
# Example commands
pytest tests/ -q
python -m apps.api.main
```

## Documentation Updates

- [ ] Updated relevant `.md` files
- [ ] Added/updated docstrings with "why" explanations
- [ ] Updated `CHANGELOG.md`

## Screenshots (if UI change)

[Before/after if applicable]

---

## Checklist for Reviewers

- [ ] Code follows project patterns
- [ ] All LLM calls go through RouterClient
- [ ] No hardcoded API keys or configuration
- [ ] Tests pass: `pytest tests/ -q`
- [ ] Documentation explains "why" not just "what"
