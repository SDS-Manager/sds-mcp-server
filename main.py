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


app = FastAPI(lifespan=lifespan)
app.mount("/search", search_mcp.streamable_http_app())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)