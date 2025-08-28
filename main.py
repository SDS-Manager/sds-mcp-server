import contextlib
from fastapi import FastAPI
from search import mcp as search_mcp
from config import PORT

# Create a combined lifespan to manage both session managers


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with contextlib.AsyncExitStack() as stack:
        await stack.enter_async_context(search_mcp.session_manager.run())
        yield


app = FastAPI(
    title="SDS Manager",
    description="SDS Manager MCP Server with Authentication",
    version="0.1.0",
    lifespan=lifespan
)

# Mount search MCP
app.mount("/search", search_mcp.streamable_http_app())


@app.get("/")
async def root():
    """Redirect to login page"""
    return {"message": "SDS Manager API", "login": "/auth/login"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
