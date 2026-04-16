# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SDS MCP Server is a Python FastAPI + MCP (Model Context Protocol) server that exposes SDS Manager data and AI tooling to Claude agents and other MCP-compatible clients.

- **Entry point:** `main.py` (FastAPI app + MCP server mount)
- **MCP tools:** `tools.py` (all MCP tool implementations)
- **Config:** `config.py` (environment config loader — use this, never `os.environ` directly)
- **Models:** `models.py` (Pydantic response schemas)
- **Cache:** `cache.py` (Redis client)
- **Constants:** `constants.py`
- **Utils:** `utils.py`

## Core standards

- Keep all generated code production-ready and strongly typed with Pydantic schemas.
- All config read via `config.py` — never `os.environ` directly in business logic.
- Use Redis caching (`cache.py`) for responses that hit external APIs.
- Never hardcode API keys, secrets, or backend URLs in code.
- Log errors clearly — never swallow exceptions silently.

## Architecture conventions

- **FastAPI app** on configurable `PORT` (default 10000).
- **MCP server** mounted at `/support` via `fastapi-mcp`.
- **Redis** backs session state and response caching (default TTL: 3600s).
- **Backend integration** via HTTP requests to the SDS Manager backend API.
- **Auth** via API key header stored in Redis session.

## Rules

- [Git & PR Workflow](.claude/rules/git-workflow.md)
- [ClickUp Tasks](.claude/rules/clickup-tasks.md)
- [Code Style](.claude/rules/code-style.md)
- [MCP Patterns](.claude/rules/mcp-patterns.md)

---

## Common Commands

```bash
# Run locally with uv
uv run main.py

# Run with uvicorn
uvicorn main:app --host 0.0.0.0 --port 10000 --reload

# Docker
docker build -t sds-mcp-server . && docker run -p 10000:10000 sds-mcp-server

# Lint & format
ruff check . && ruff format .
```

---

## Architecture

### Key Files

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app factory, MCP mount, health routes |
| `tools.py` | All MCP tool implementations — one function per tool |
| `models.py` | Pydantic request/response schemas |
| `config.py` | Environment config — `Config` singleton loaded from `.env` |
| `cache.py` | Redis client with TTL-based get/set helpers |
| `constants.py` | Application-level constants |
| `utils.py` | Stateless utility functions |

### MCP Tool Pattern

Each MCP tool is a decorated async function in `tools.py`:

```python
@mcp.tool()
async def search_sds(query: str, language: str = "en") -> list[dict]:
    """Search for Safety Data Sheets by product name or CAS number."""
    cached = await cache.get(f"search:{query}:{language}")
    if cached:
        return cached
    result = await backend_api.search(query=query, language=language)
    await cache.set(f"search:{query}:{language}", result)
    return result
```

### Config Access

```python
from config import config

api_url = config.BACKEND_API_URL
redis_url = config.REDIS_URL
```

Never read `os.environ` directly in tool implementations or routes.

### Redis Caching

```python
from cache import cache_client

# Get with fallback
data = await cache_client.get("key")
if not data:
    data = await fetch_from_backend()
    await cache_client.set("key", data, ttl=3600)
```

### Authentication

- Clients authenticate via API key passed in request headers.
- Keys are validated against Redis-stored sessions.
- Never expose raw session data in MCP tool responses.

### Backend API Integration

```python
import requests

response = requests.get(
    f"{config.BACKEND_API_URL}/api/endpoint/",
    headers={"Authorization": f"JWT {token}"},
    timeout=30,
)
response.raise_for_status()
```

Always set explicit timeouts. Never catch all exceptions silently.
