# SDS Manager MCP Server

A Model Context Protocol (MCP) server that provides search and document retrieval capabilities for SDS Manager.

## 🛠 Quickstart

### Prerequisites

Install uv (recommended Python package manager):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Installation

1. **Set up virtual environment and install dependencies:**
   ```bash
   uv venv && source .venv/bin/activate
   uv pip install -r pyproject.toml
   ```

2. **Configure environment variables:**
   Create a `.env` file in the project root:
   ```env
   # Redis Configuration
   REDIS_HOST=localhost
   REDIS_PORT=6379
   REDIS_DB=0
   REDIS_PASSWORD=
   REDIS_TTL=3600
   
   # Server Configuration
   PORT=10000
   SECRET_KEY=your_secret_key_here

   # SDS Manager Backend (defaults to http://localhost:8000/api)
   BACKEND_URL=http://localhost:8000/api
   ```

### Running the Server

#### Option 1: Basic MCP Server
Run the standalone MCP server:
```bash
uv run main.py
```

#### Option 2: FastAPI App with Multiple MCP Servers
This will mount the MCP server as a FastAPI application:
```bash
uvicorn main:app --host 0.0.0.0 --port 10000
```

The server will be available at:
- **MCP Endpoint:** `http://localhost:10000/search/mcp`
- **Main App:** `http://localhost:10000`



### Available Tools

Note: This server is stateless for HTTP usage. Pass your SDS access token on every call via the `access_token` parameter.

#### 1. `search(access_token: str, query: str)`
- **Purpose:** Search customer SDS documents
- **Parameters:**
  - `access_token` (string): SDS Manager JWT (e.g., obtained from your app)
  - `query` (string): Search text
- **Returns:** `{ results: [...] }` where `results` is the API result list

Example call (conceptual):
```json
{
  "tool": "search",
  "arguments": {
    "access_token": "<JWT>",
    "query": "acetone"
  }
}
```

#### 2. `fetch(access_token: str, id: str)`
- **Purpose:** Fetch a specific customer SDS document by ID
- **Parameters:**
  - `access_token` (string): SDS Manager JWT
  - `id` (string): SDS document identifier
- **Returns:** The SDS document payload from the API

Example call (conceptual):
```json
{
  "tool": "fetch",
  "arguments": {
    "access_token": "<JWT>",
    "id": "12345"
  }
}
```

### Using with ChatGPT (GPTs) / MCP Clients

1. Ensure the server is running and reachable at `http://localhost:10000/search/mcp`.
2. In ChatGPT (with MCP support) or another MCP-compatible client, add a new MCP server connection pointing to that URL.
3. The client will discover two tools: `search` and `fetch`.
4. When invoking either tool, include your SDS `access_token` in the arguments. No separate `authenticate` or session handling is required.




