# MCP Server Patterns

## Tool Definition

All MCP tools are async functions decorated with `@mcp.tool()` in `tools.py`:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("SDS Manager")

@mcp.tool()
async def search_sds(query: str, language: str = "en") -> list[dict]:
    """
    Search for Safety Data Sheets by product name, CAS number, or supplier.
    """
    cache_key = f"search:{query}:{language}"
    cached = await cache_client.get(cache_key)
    if cached:
        return cached

    result = await call_backend_api("/api/sds/search/", params={"q": query, "lang": language})
    await cache_client.set(cache_key, result)
    return result
```

### Rules

- Every tool **must** have a complete docstring — it is surfaced to the AI client.
- All tools should check the Redis cache before calling the backend.
- Return serializable data (`list[dict]` or `dict`) — not Pydantic models directly.
- Tool names use `snake_case` imperative verbs: `search_sds`, `get_sds_by_id`, `list_suppliers`.

## Caching Pattern

```python
from cache import cache_client
from config import config

async def get_with_cache(key: str, fetch_fn):
    cached = await cache_client.get(key)
    if cached:
        return cached
    data = await fetch_fn()
    await cache_client.set(key, data, ttl=config.CACHE_TTL)
    return data
```

Default TTL: `config.CACHE_TTL` (default 3600s). Do not cache real-time or user-specific data.

## Backend API Integration

```python
import requests
from config import config

def call_backend_api(path: str, params: dict = None, token: str = None) -> dict:
    headers = {}
    if token:
        headers["Authorization"] = f"JWT {token}"

    response = requests.get(
        f"{config.BACKEND_API_URL}{path}",
        params=params,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()
```

- Always set `timeout=30` — never let requests hang indefinitely.
- Use `raise_for_status()` and catch `requests.HTTPError` specifically.
- Never log auth tokens or session keys.

## Authentication Flow

- Client passes API key in request header.
- Key is validated via Redis session lookup.
- Authenticated sessions stored in Redis with TTL.

```python
async def validate_session(session_key: str) -> bool:
    session = await cache_client.get(f"session:{session_key}")
    return session is not None
```

## Error Responses

MCP tools return structured dicts — never raise exceptions to the AI client:

```python
@mcp.tool()
async def get_sds(sds_id: int) -> dict:
    """Get a single SDS document by ID."""
    try:
        return call_backend_api(f"/api/sds/{sds_id}/")
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            return {"error": f"SDS {sds_id} not found"}
        return {"error": "Backend error", "status": e.response.status_code}
    except requests.Timeout:
        return {"error": "Request timed out"}
```

## FastAPI + MCP Mount

The MCP server is mounted on the FastAPI app:

```python
# main.py
from fastapi import FastAPI
from mcp.server.fastmcp import FastMCP

app = FastAPI()
mcp = FastMCP("SDS Manager")

# Mount MCP server
app.mount("/support", mcp.get_asgi_app())
```

Do not add business logic directly to FastAPI routes — all logic goes in MCP tools or helper modules.
