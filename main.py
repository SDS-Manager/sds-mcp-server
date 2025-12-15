import contextlib
import os
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import requests
from typing import Optional
from tools import mcp as tools_mcp
from config import PORT, BACKEND_URL, SDS_HEADER_NAME
from cache import redis_client
import pandas as pd
import tempfile

# Create templates directory
templates = Jinja2Templates(directory="templates")

# Create a combined lifespan to manage both session managers


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with contextlib.AsyncExitStack() as stack:
        await stack.enter_async_context(tools_mcp.session_manager.run())
        yield


app = FastAPI(
    title="SDS Manager",
    description="SDS Manager MCP Server with Authentication",
    version="0.1.0",
    lifespan=lifespan
)

# Mount tools MCP
app.mount("/support", tools_mcp.streamable_http_app())


@app.get("/")
async def root():
    """Redirect to login page"""
    return {"message": "SDS Manager API", "login": "/auth/login"}


@app.get("/login", response_class=HTMLResponse)
async def login_form(request: Request, session_id: Optional[str] = None):
    """
    Display login form for SDS Manager
    
    Query parameters:
    - session_id: User session ID from login
    """
    
    if not session_id:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "session_id": None,
            "session_not_found": True,
        })

    info = redis_client.get(f"sds_mcp:{session_id}")
    if not info:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "session_id": None,
            "session_expired": True,
        })

    return templates.TemplateResponse("login.html", {
        "request": request,
        "session_id": session_id,
    })


@app.post("/login")
async def login(
    session_id: str = Form(...),
    api_key: str = Form(...),
):
    """
    Handle login form submission
    """
    try:
        headers = {SDS_HEADER_NAME: f"{api_key}"}
        response = requests.get(
            f"{BACKEND_URL}/user/",
            headers=headers,
        )

        if response.status_code == 200:
            result = response.json()
            redis_client.set(f"sds_mcp:{session_id}", {
                "logged_in": True,
                "api_key": api_key,
                "user_id": result.get("id"),
                "email": result.get("email"),
                "first_name": result.get("first_name", ""),
                "last_name": result.get("last_name", ""),
                "language": result.get("language"),
                "country": result.get("country"),
                "phone_number": result.get("phone_number"),
                "customer": result.get("customer"),
            })
            return {
                "status": "success", 
                "message": f"Login successfully!",
            }
        else:
            redis_client.set(f"sds_mcp:{session_id}", {
                "logged_in": False,
                "login_error": True,
                "error_message": response.text,
            })
            error_data = response.json()
            return {
                "status": "error", 
                "error_code": 400,
                "message": error_data.get("error_message") or response.text
            }
    except Exception as e:
        return {"status": "error", "message": f"Login error: {str(e)}"}


@app.get("/upload", response_class=HTMLResponse)
async def upload_form(
    request: Request, 
    session_id: str, 
    department_id: str, 
    request_id: str
):
    """
    Display file upload form for SDS files
    
    Query parameters:
    - session_id: User session ID from login
    - department_id: Target department/location ID
    """
    # Validate session
    info = redis_client.get(f"sds_mcp:{session_id}")
    if not info:
        return templates.TemplateResponse("upload.html", {
            "request": request,
            "session_id": None,
        })

    upload_info = redis_client.get(f"upload_sds_pdf:{session_id}:{request_id}")
    if not upload_info:
        return templates.TemplateResponse("upload.html", {
            "request": request,
            "session_id": session_id,
            "request_id": None,
        })
    
    return templates.TemplateResponse("upload.html", {
        "request": request,
        "session_id": session_id,
        "department_id": department_id,
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
        return {
            "status": "error", 
            "message": "Session expired. Please get new login URL from the Chat Agent and login again."
        }
    
    upload_info = redis_client.get(f"upload_sds_pdf:{session_id}:{request_id}")
    if not upload_info:
        return {
            "status": "error", 
            "message": "Upload session expired. Please get new upload URL from the Chat Agent and upload again."
        }

    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        return {"status": "error", "message": "Only PDF files are allowed."}
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Upload to SDS Manager
        headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
        
        response = requests.post(
            f"{BACKEND_URL}/location/{department_id}/uploadSDS/",
            headers=headers,
            data={"id": request_id},
            files={"imported_file": (file.filename, file_content, "application/pdf")}
        )

        if response.status_code == 200:
            result = response.json()
            redis_client.set(f"upload_sds_pdf:{session_id}:{request_id}", {
                "session_id": session_id,
                "request_id": request_id,
                "location_id": department_id,
                "status": "uploaded",
                "file": file.filename,
                "data": result,
            })

            return {
                "status": "success", 
                "message": f"Successfully uploaded {file.filename} to location {department_id}",
                "data": result
            }
        else:
            redis_client.set(f"upload_sds_pdf:{session_id}:{request_id}", {
                "session_id": session_id,
                "request_id": request_id,
                "location_id": department_id,
                "status": "error",
                "status_code": response.status_code,
                "error_message": response.text,
                "file": file.filename,
            })

            return {
                "status": "error", 
                "message": f"Upload failed with status {response.status_code}",
                "details": response.text
            }
    except Exception as e:
        return {"status": "error", "message": f"Upload error: {str(e)}"}


@app.get("/uploadProductList", response_class=HTMLResponse)
async def upload_product_list_form(request: Request, session_id: str, request_id: str):
    """
    Display file upload form for product list
    """
    # Validate session
    info = redis_client.get(f"sds_mcp:{session_id}")
    if not info:
        return templates.TemplateResponse("upload_product_list.html", {
            "request": request,
            "session_id": None,
        })

    upload_info = redis_client.get(f"upload_product_list:{session_id}:{request_id}")
    if not upload_info:
        return templates.TemplateResponse("upload_product_list.html", {
            "request": request,
            "session_id": session_id,
            "request_id": None,
        })

    return templates.TemplateResponse("upload_product_list.html", {
        "request": request,
        "session_id": session_id,
        "request_id": request_id
    })


@app.post("/uploadProductList")
async def upload_product_list(
    session_id: str = Form(...),
    request_id: str = Form(...),
    file: UploadFile = File(...)
):
    """
    Handle product list upload
    """
    # Validate session
    info = redis_client.get(f"sds_mcp:{session_id}")
    if not info:
        return {
            "status": "error", 
            "message": "Session expired. Please get new login URL from the Chat Agent and login again."
        }
    
    upload_key = f"upload_product_list:{session_id}:{request_id}"
    upload_info = redis_client.get(upload_key)
    if not upload_info:
        return {
            "status": "error", 
            "message": "Upload session expired. Please get new upload URL from the Chat Agent and upload again."
        }

    file_name = file.filename
    tmpdirname = f"tmp/{request_id}"
    if not os.path.exists(tmpdirname):
        os.makedirs(tmpdirname)

    with tempfile.NamedTemporaryFile(delete=False, dir=tmpdirname, suffix='.xlsx') as tmp_file:
        # Write uploaded content to temp file
        content = await file.read()
        tmp_file.write(content)
        tmp_file_path = tmp_file.name
    
    try:
        # Read from the temp file
        df = pd.read_excel(tmp_file_path)
        data_list = df.to_dict('records')
        total_data = len(data_list)
        columns_list = df.columns.tolist()
        extracted_columns = []
        for item in columns_list:
            extracted_columns.append(item.lower())
        
        # Set processing status
        record = {
            "status": "uploaded",
            "session_id": session_id,
            "request_id": request_id,
            "extracted_columns": extracted_columns,
            "total_row": total_data,
            "file_name": file_name,
            "file_path": tmp_file_path,
        }
        redis_client.set(upload_key, record)
        
        return {
            "status": "success",
            "message": "Product list upload processing started",
            "filename": file.filename,
        }
    except Exception as e:
        error_message = f"Error processing product list: {str(e)}"
        redis_client.set(upload_key, {
            "status": "error",
            "session_id": session_id,
            "request_id": request_id,
            "file_name": file_name,
            "file_path": tmp_file_path,
            "error_message": error_message,
        })
        return {
            "status": "error",
            "message": error_message
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
