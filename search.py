from mcp.server.fastmcp import FastMCP
from cache import redis_client
from typing import Dict, Any
from config import BACKEND_URL, SDS_HEADER_NAME
import logging
import requests
import uuid

logger = logging.getLogger(__name__)

# Initialize MCP server with proper description
mcp = FastMCP(
    name="SDS Manager Search",
    instructions="SDS Manager Search API - Authentication required. Please login with your access token first using the login tool.",
    stateless_http=True,
)


@mcp.tool(
    description="REQUIRED FIRST: Authenticate with your access token. This must be called before using any other tools."
)
async def login(access_token: str) -> Dict[str, Any]:
    """
    Authenticate user with JWT access token.

    This tool MUST be called first before any other operations.

    Arguments:
        access_token: Your JWT access token for authentication

    Returns:
        Dictionary with authentication status and user information
    """
    session_id = str(uuid.uuid4())

    # Validate access token format (basic check)
    if not access_token or not isinstance(access_token, str) or len(access_token) < 10:
        return {
            "error": "Invalid access token format",
            "instruction": "Please provide a valid JWT access token"
        }

    headers = {SDS_HEADER_NAME: f"{access_token}"}

    try:
        response = requests.get(
            f"{BACKEND_URL}/user/", headers=headers, timeout=10
        )

        if response.status_code == 200:
            user_info = response.json()
            redis_client.set(f"sds_mcp:{session_id}", {
                "access_token": access_token,
                "user_id": user_info.get("id"),
                "email": user_info.get("email"),
                "name": user_info.get("name", "User")
            })

            return {
                "status": "success",
                "message": "Login successful! You can now use other tools.",
                "user_info": {
                    "id": user_info.get("id"),
                    "email": user_info.get("email"),
                    "name": user_info.get("name", "User")
                },
                "available_tools": ["search"],
                "session_id": session_id
            }
        elif response.status_code == 401:

            return {
                "status": "error",
                "error": "Authentication failed",
                "instruction": "Invalid or expired access token. Please provide a valid access token."
            }
        else:
            return {
                "status": "error",
                "error": f"Authentication failed with status {response.status_code}",
                "instruction": "Please check your access token and try again."
            }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to authentication server. Please try again."
        }


@mcp.tool(
    description="Search customer SDS by text query. Requires authentication via login tool first."
)
async def search(query: str, session_id: str, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    """
    Search for Safety Data Sheets (SDS) by product name or keywords.

    REQUIRES: User must be authenticated using the login tool first.
    Let user know if they want to load more results, they can use the same tool with different page number.
    Arguments:
        query: Search query string for finding SDS documents

    Returns:
        Dictionary containing search results with:
        - results: Array of matching SDS documents
          - id: Unique document identifier
          - product_name: Product name
          - producer_name: Producer/manufacturer name
          - count: Total number of results
    """
    if not session_id:
        return {
            "status": "error",
            "error": "No active session found",
            "instruction": "Please login first using the login tool with your access token"
        }

    info = redis_client.get(f"sds_mcp:{session_id}")
    if not info:
        return {
            "status": "error",
            "error": "Access token not found in session",
            "instruction": "Session expired. Please login again using the login tool."
        }

    headers = {SDS_HEADER_NAME: f"{info.get('access_token')}"}

    try:
        response = requests.get(
            f"{BACKEND_URL}/substance/?search={query}&page={page}&page_size={page_size}",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            return {
                "status": "success",
                "query": query,
                "results": data.get("results", []),
                "count": data.get("count", 0)
            }
        elif response.status_code == 401:
            redis_client.delete(f"sds_mcp:{session_id}")
            return {
                "status": "error",
                "error": "Authentication expired",
                "instruction": "Your session has expired. Please login again with your access token."
            }
        else:
            return {
                "status": "error",
                "error": f"Search failed with status {response.status_code}",
                "instruction": "Failed to perform search. Please try again or contact support."
            }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to search service. Please try again."
        }


@mcp.tool(
    description="Check current authentication status and session information"
)
async def check_auth_status(session_id: str) -> Dict[str, Any]:
    """
    Check if the current session is authenticated.

    Returns:
        Dictionary with current authentication status and available actions
    """

    if not session_id:
        return {
            "status": "not_initialized",
            "authenticated": False,
            "instruction": "No session found. Please use the login tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_id}")

    if info:
        return info
    else:
        return {
            "status": "not_authenticated",
            "authenticated": False,
            "instruction": "Please use the login tool with your access token to authenticate.",
            "example": "login(access_token='your_jwt_token_here')"
        }
