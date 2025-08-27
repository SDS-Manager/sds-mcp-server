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

3. **Set up Redis server:**
   Make sure you have Redis running locally or update the Redis configuration in your `.env` file to point to your Redis instance.


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
