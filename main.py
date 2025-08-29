import contextlib
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import requests
from search import mcp as search_mcp
from config import PORT, BACKEND_URL, SDS_HEADER_NAME
from cache import redis_client
import json
# Create templates directory
templates = Jinja2Templates(directory="templates")

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


@app.get("/upload", response_class=HTMLResponse)
async def upload_form(request: Request, session_id: str, department_id: str, request_id: str):
    """
    Display file upload form for SDS files
    
    Query parameters:
    - session_id: User session ID from login
    - department_id: Target department/location ID
    """
    # Validate session
    info = redis_client.get(f"sds_mcp:{session_id}")
    if not info:
        return HTMLResponse(
            content="<h1>Session Expired</h1><p>Please login again to upload files.</p>",
            status_code=401
        )
    
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "session_id": session_id,
        "department_id": department_id,
        "user_name": info.get("name", "User"),
        "request_id": request_id
    })


@app.post("/upload")
async def upload_file(
    session_id: str = Form(...),
    request_id: str = Form(...),
    department_id: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Handle SDS file upload to specified location
    """
    # Validate session
    info = redis_client.get(f"sds_mcp:{session_id}")
    if not info:
        return {"status": "error", "message": "Session expired. Please login again."}
    
    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        return {"status": "error", "message": "Only PDF files are allowed."}
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Upload to SDS Manager
        headers = {SDS_HEADER_NAME: f"{info.get('access_token')}"}
        
        response = requests.post(
            f"{BACKEND_URL}/location/{department_id}/uploadSDS/",
            headers=headers,
            data={"id": request_id},
            files={"imported_file": (file.filename, file_content, "application/pdf")}
        )

        if response.status_code == 200:
            result = response.json()
            return {
                "status": "success", 
                "message": f"Successfully uploaded {file.filename} to location {department_id}",
                "data": result
            }
        else:
            return {
                "status": "error", 
                "message": f"Upload failed with status {response.status_code}",
                "details": response.text
            }
    except Exception as e:
        return {"status": "error", "message": f"Upload error: {str(e)}"}


    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
