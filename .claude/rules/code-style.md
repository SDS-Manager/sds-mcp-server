# Code Style

## Tools

| Tool | Purpose |
|------|---------|
| Ruff | Linting + formatting |
| isort | Import sorting |

```bash
ruff check .
ruff format .
```

## Import Order (PEP 8 / isort)

1. Standard library (`os`, `json`, `logging`, etc.)
2. Third-party packages (`fastapi`, `mcp`, `redis`, `requests`, `pydantic`, etc.)
3. Local app imports (use **absolute paths** — no relative imports)

```python
# Good
from config import config
from cache import cache_client

# Bad
from .config import config
```

## Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Variables / functions | `snake_case` | `search_sds_by_name` |
| Classes | `PascalCase` | `SdsResponse` |
| Constants | `UPPER_SNAKE_CASE` | `DEFAULT_CACHE_TTL` |
| MCP tool functions | `snake_case` verb_noun | `search_sds`, `get_sds_by_id` |

## General Rules

- Follow PEP 8. Prefer explicit over implicit.
- No `print()` in production code — use `logging`.
- Type hints on all public function signatures and return types.
- All config via `config.py` — never `os.environ` directly.

## Pydantic Models

- Define request/response schemas in `models.py`.
- Use Pydantic v2 syntax (the project uses `pydantic>=2.0`):

```python
from pydantic import BaseModel

class SdsSearchResult(BaseModel):
    id: int
    name: str
    language: str
    supplier: str | None = None
```

## MCP Tool Docstrings

Every `@mcp.tool()` function **must** have a clear docstring — it is surfaced to AI clients as the tool description:

```python
@mcp.tool()
async def search_sds(query: str, language: str = "en") -> list[dict]:
    """
    Search for Safety Data Sheets by product name, CAS number, or supplier.

    Args:
        query: Product name, CAS number, or keyword to search for.
        language: ISO language code (default: "en"). Supported: en, no, de, etc.

    Returns:
        List of matching SDS documents with id, name, language, and supplier.
    """
```

## Error Handling

- Catch specific exceptions — never bare `except`.
- Return structured error responses for MCP tools, not raw exceptions.
- Log errors with context — include request IDs where available.

```python
try:
    result = await fetch_from_backend(query)
except requests.Timeout:
    logger.error("Backend timeout for query: %s", query)
    return {"error": "Backend request timed out"}
except requests.RequestException as e:
    logger.error("Backend request failed: %s", e)
    return {"error": "Backend unavailable"}
```
