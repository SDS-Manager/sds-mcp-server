from mcp.server.fastmcp import FastMCP
from cache import redis_client
from typing import Dict, Any, List, Optional
from config import BACKEND_URL, SDS_HEADER_NAME, PORT, DOMAIN
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


@mcp.tool()
async def login(access_token: str) -> Dict[str, Any]:
    """
    Authenticate user with API key.

    Returns: Dictionary with authentication status, user information, and available actions:
        - status: "success" or "error"
        - message: Welcome message or error details
        - user_info: User details (id, email, name)
        - session_id: Session identifier for subsequent operations
        - next_action_suggestion: List of suggestion (Do not perform action, just show to user)
        - instruction: Error guidance (only for error cases)
    """
    session_id = str(uuid.uuid4())

    # Validate access token format (basic check)
    if not access_token or not isinstance(access_token, str) or len(access_token) < 10:
        return {
            "error": "Invalid access token format",
            "instruction": "Please provide a valid API key"
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
                "message": "Login successful! Welcome to SDS Manager.",
                "user_info": {
                    "id": user_info.get("id"),
                    "email": user_info.get("email"),
                    "name": user_info.get("first_name", "") + " " + user_info.get("last_name", "")
                },
                "session_id": session_id,
                "next_action_suggestion": [
                    "Search action: search_global_database tool, search_customer_library tool",
                    "Location action: get_location tool, add_location tool, add_sds_to_location tool",
                    "Substance action: move_sds_to_location tool, copy_sds_substance tool, archive_sds_substance tool, archive_sds_substance tool",
                    "User action: check_auth_status tool"
                ],
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


@mcp.tool()
async def check_auth_status(session_id: str) -> Dict[str, Any]:
    """
    Check if the current session is authenticated.

    REQUIRED: User must be authenticated using the login tool first.
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


@mcp.tool()
async def search_global_database(
    keyword: str, 
    page: int = 1, 
    page_size: int = 10, 
    language_code: Optional[str] = None,
    region_code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search for Safety Data Sheets (SDS) from the global database by keywords (Do not need authentication).
    
    IMPORTANT GUIDELINES:
    - If user ask to search without mentioning internally or globally, do search_global_database tool and search_customer_library tool (if authenticated).
    - Do not perform broader search. If no results, only show suggestion for user to choose.
    - Display in a table for the response results with columns: "ID", "Product Name", "Product Code", "Manufacturer Name", "Revision Date", "Language", "Regulation Area", "Public Link", "Discovery Link".
    - Auto convert to language/region code if user input language/region name (e.g., "English" -> "en", "Europe" -> "EU", etc.).
    - Do not use ID as search keyword.
    """
    try:
        search_param = f"?search={keyword}&page={page}&page_size={page_size}"
        if language_code:
            search_param += f"&language_code={language_code}"
        if region_code:
            search_param += f"&region={region_code.upper()}"

        response = requests.get(
            f"{BACKEND_URL}/pdfs/{search_param}",
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            count = data.get("count", 0)
            return {
                "status": "success",
                "keyword": keyword,
                "results": results,
                "count": count,
                "next": data.get("next"),
                "previous": data.get("previous"),
                "facets": data.get("facets", {}),
                "page": page,
                "page_size": page_size
            }
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg,
                }
            except:
                return {
                    "status": "error",
                    "error": f"Failed to search SDS with status {response.status_code}",
                    "instruction": "Failed to search SDS. Please try again."
                }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error", 
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to global search service. Please try again."
        }


@mcp.tool()
async def search_customer_library(session_id: str, keyword: str, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    """
    Search for substances (SDS assigned to a location) from customer's library by keywords.

    REQUIRED: User must be authenticated using the login tool first.

    IMPORTANT GUIDELINES:
    - If user ask to search without mentioning internally or globally, do search_global_database tool and search_customer_library tool (if authenticated).
    - Do not use ID as search keyword.

    Returns: List of substance information
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
            f"{BACKEND_URL}/substance/?search={keyword}&page={page}&page_size={page_size}",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            return {
                "status": "success",
                "keyword": keyword,
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
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg,
                }
            except:
                return {
                    "status": "error",
                    "error": f"Failed to search SDS with status {response.status_code}",
                    "instruction": "Failed to search SDS. Please try again."
                }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to search service. Please try again."
        }


@mcp.tool()
async def add_sds_to_location(session_id: str, sds_id: str, location_id: str) -> Dict[str, Any]:
    """
    Add an SDS document from the global database to a specific location.

    REQUIRED: User must be authenticated using the login tool first.

    IMPORTANT GUIDELINES:
    - If not found any information of location, ask user to provide location name.
    - If not found any information of SDS, ask user to provide SDS name.
    - When user input location name, call get_location tool to get all locations and filter with location name.
    - Always ask user to choose which location if multiple locations found.
    - When user input SDS name, call search_global_database tool with keyword as SDS name.
    - Always ask user to choose which SDS if multiple SDS found.

    RETURN: Information of the newly added substance
    """

    endpoint = f"{BACKEND_URL}/location/{location_id}/addSDS/"

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
        response = requests.post(
            endpoint,
            headers=headers,
            json={"sds_id": sds_id},
            timeout=10
        )

        if response.status_code in [200, 201]:
            return response.json()
        elif response.status_code == 401:
            redis_client.delete(f"sds_mcp:{session_id}")
            return {
                "status": "error",
                "error": "Authentication expired",
                "instruction": "Your session has expired. Please login again with your access token."
            }
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg,
                }
            except:
                return {
                    "status": "error",
                    "error": f"Failed to add SDS to location with status {response.status_code}",
                    "instruction": "Failed to add SDS to location. Please verify the SDS and location."
                }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to location service. Please try again."
        }


@mcp.tool()
async def move_sds_to_location(session_id: str, substance_id: str, location_id: str) -> Dict[str, Any]:
    """
    Move a substance (SDS assigned to a location) to a specific location.
    
    REQUIRED: User must be authenticated using the login tool first.

    IMPORTANT GUIDELINES:
    - If not found any information of location, ask user to provide location name.
    - If not found any information of SDS, ask user to provide SDS name.
    - When user input location name, call get_location tool to get all locations and filter with location name.
    - Always ask user to choose which location if multiple locations found.
    - When user input SDS name, call search_customer_library tool with keyword as SDS name.
    - Always ask user to choose which substance if multiple substance found.
    
    Return: Information of the moved substance
    """

    endpoint = f"{BACKEND_URL}/substance/{substance_id}/move/"

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
        response = requests.post(
            endpoint,
            headers=headers,
            json={"department_id": location_id},
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            redis_client.delete(f"sds_mcp:{session_id}")
            return {
                "status": "error",
                "error": "Authentication expired",
                "instruction": "Your session has expired. Please login again with your access token."
            }
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg,
                }
            except:
                return {
                    "status": "error",
                    "error": f"Failed to add SDS to move SDS with status {response.status_code}",
                    "instruction": "Failed to move SDS to location. Please verify the SDS and location."
                }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to location service. Please try again."
        }


@mcp.tool()
async def copy_sds_substance(session_id: str, substance_id: str, location_id: str) -> Dict[str, Any]:
    """
    Add the selected substance (SDS assigned to a location) to the target location/department with similar information.

    Requires: User must be authenticated via the login tool first.

    IMPORTANT GUIDELINES:
    - If not found any information of location, ask user to provide location name.
    - If not found any information of SDS, ask user to provide SDS name.
    - When user input location name, call get_location tool to get all locations and filter with location name.
    - Always ask user to choose which location if multiple locations found.
    - When user input SDS name, call search_customer_library tool with keyword as SDS name.
    - Always ask user to choose which substance if multiple substance found.

    Return: Information of the added substance
    """

    endpoint = f"{BACKEND_URL}/substance/{substance_id}/copy/"

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
        response = requests.post(
            endpoint,
            headers=headers,
            json={"department_id": location_id},
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            redis_client.delete(f"sds_mcp:{session_id}")
            return {
                "status": "error",
                "error": "Authentication expired",
                "instruction": "Your session has expired. Please login again with your access token."
            }
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg,
                }
            except:
                return {
                    "status": "error",
                    "error": f"Failed to copy SDS to location with status {response.status_code}",
                    "instruction": "Failed to copy SDS to location. Please verify the SDS and location."
                }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to copy service. Please try again."
        }


@mcp.tool()
async def archive_sds_substance(session_id: str, substance_id: str) -> Dict[str, Any]:
    """
    Move a substance (SDS assigned to a location) to archive.
    Synonyms: delete substance, remove substance, etc.

    REQUIRED: User must be authenticated using the login tool first.

    IMPORTANT GUIDELINES:
    - If not found any information of SDS, ask user to provide SDS name.
    - When user input SDS name, call search_customer_library tool with keyword as SDS name.
    - Always ask user to choose which substance if multiple substance found.

    Return: Information of the archived substance
    """

    endpoint = f"{BACKEND_URL}/substance/{substance_id}/archive/"

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
        response = requests.post(
            endpoint,
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            redis_client.delete(f"sds_mcp:{session_id}")
            return {
                "status": "error",
                "error": "Authentication expired",
                "instruction": "Your session has expired. Please login again with your access token."
            }
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg,
                }
            except:
                return {
                    "status": "error",
                    "error": f"Failed to archive substance with status {response.status_code}",
                    "instruction": "Failed to archive substance. Please verify the Substance."
                }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to archive service. Please try again."
        }


@mcp.tool()
async def get_location(session_id: str) -> List[Dict[str, Any]]:
    """
    Get location tree list for the current user.

    REQUIRED: User must be authenticated using the login tool first.

    IMPORTANT GUIDELINES:
    - Display in a tree structure (Similar to file explorer).
    """

    if not session_id:
        return {
            "status": "not_initialized",
            "authenticated": False,
            "instruction": "You haven't logged in yet. Please provide me your access token to authenticate."
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
            f"{BACKEND_URL}/location/",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            redis_client.delete(f"sds_mcp:{session_id}")
            return {
                "status": "error",
                "error": "Authentication expired",
                "instruction": "Your session has expired. Please login again with your access token."
            }
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg,
                }
            except:
                return {
                    "status": "error",
                    "error": f"Failed to get locations with status {response.status_code}",
                    "instruction": "Failed to get locations. Please try again."
                }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to service. Please try again."
        }


@mcp.tool()
async def add_location(session_id: str, name: str, parent_department_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Add new location.

    REQUIRES: User must be authenticated using the login tool first.

    IMPORTANT GUIDELINES:
    - parent_department_id is None when creating root location.
    - When user not mentioning parent location, ask user to clarify whether it is root location or not.
    - If it is not root location, ask user to provide parent location.
    - When user input location name, call get_location tool to get all locations and filter with location name.
    - Always ask user to choose which location if multiple locations found.

    RETURN: A dictionary of the newly added location
    """
    if not session_id:
        return {
            "status": "not_initialized",
            "authenticated": False,
            "instruction": "You haven't logged in yet. Please provide me your access token to authenticate."
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
        response = requests.post(
            f"{BACKEND_URL}/location/",
            headers=headers,
            json={
                "name": name,
                "parent_department_id": parent_department_id
            },
            timeout=10
        )

        if response.status_code == 201:
            return response.json()
        elif response.status_code == 401:
            redis_client.delete(f"sds_mcp:{session_id}")
            return {
                "status": "error",
                "error": "Authentication expired",
                "instruction": "Your session has expired. Please login again with your access token."
            }
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg,
                }
            except:
                return {
                    "status": "error",
                    "error": f"Failed to add location with status {response.status_code}",
                    "instruction": "Failed to add location. Please verify location information."
                }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to service. Please try again."
        }


@mcp.tool()
async def retrieve_substance_detail(session_id: str, substance_id: str) -> Dict[str, Any]:
    """
    Get details for a specific substance (SDS assigned to a location) in the customer's inventory.

    REQUIRES: User must be authenticated using the login tool first.

    IMPORTANT GUIDELINES:
    - If not found any information of the substance, ask user to provide SDS name.
    - When user input SDS name, call search_customer_library tool with keyword as SDS name.
    - Always ask user to choose which substance if multiple substance found.
    - If seeing error message, display the error message to user.

    Returns: Detail information of the substance
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

    endpoint = f"{BACKEND_URL}/substance/{substance_id}/"
    headers = {SDS_HEADER_NAME: f"{info.get('access_token')}"}

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            redis_client.delete(f"sds_mcp:{session_id}")
            return {
                "status": "error",
                "error": "Authentication expired",
                "instruction": "Your session has expired. Please login again with your access token."
            }
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg,
                }
            except:
                return {
                    "status": "error",
                    "error": f"Failed to get substance with status {response.status_code}",
                    "instruction": "Failed to get substance. Please verify the substance."
                }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to service. Please try again."
        }


@mcp.tool()
async def get_sdss_with_ingredients(session_id: str, keyword: str = "", page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    """
    Get or Search hazardous SDSs with detail information on ingredients/components that restricted on regulation list.

    REQUIRES: User must be authenticated using the login tool first.

    IMPORTANT GUIDELINES:
    - If user not mentioning keyword, call get_sdss_with_ingredients tool with keyword as empty string.
    - When displaying response, show more detail on ingredients/components.
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

    endpoint = f"{BACKEND_URL}/substance/?hazardous=true&search={keyword}&page={page}&page_size={page_size}"
    headers = {SDS_HEADER_NAME: f"{info.get('access_token')}"}

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            substance_list = []
            for substance in data.get("results", []):
                substance_info = substance.get("sds_info")
                substance_list.append({
                    "product_name": substance.get("product_name"),
                    "product_code": substance.get("product_code"),
                    "supplier_name": substance.get("supplier_name"),
                    "revision_date": substance.get("revision_date"),
                    "location": substance.get("location"),
                    "components": (
                        substance_info.get("sds_chemical", []) 
                        if substance_info else []
                    ),
                    "matched_regulations": (
                        substance_info.get("regulations", []) 
                        if substance_info else []
                    )
                })

            return {
                "status": "success",
                "data": substance_list,
                "page": page,
                "page_size": page_size,
            }
        elif response.status_code == 401:
            redis_client.delete(f"sds_mcp:{session_id}")
            return {
                "status": "error",
                "error": "Authentication expired",
                "instruction": "Your session has expired. Please login again with your access token."
            }
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg,
                }
            except:
                return {
                    "status": "error",
                    "error": f"Failed to get SDSs with status {response.status_code}",
                    "instruction": "Failed to get SDSs. Please try again."
                }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to service. Please try again."
        }


@mcp.tool()
async def upload_sds_file_to_location(session_id: str, department_id: str):
    """
    Upload SDS file to the specified location.

    REQUIRED: User must be authenticated using the login tool first.
    
    IMPORTANT GUIDELINES:
    - If not found any information of location, ask user to provide location name.
    - When user input location name, call get_location tool to get all locations and filter with location name.
    - Always ask user to choose which location if multiple locations found.
    - Ask user to clarify they have finished uploading the SDS file.
    - If user confirm they have finished uploading the SDS file, call check_upload_status tool with request_id to check the status of the upload process.
    """
    # Validate session
    info = redis_client.get(f"sds_mcp:{session_id}")
    if not info:
        return {
            "status": "error",
            "error": "Access token not found in session",
            "instruction": "Session expired. Please login again using the login tool."
        }
        
    request_id = str(uuid.uuid4())
    upload_url = f"{DOMAIN}/upload?session_id={session_id}&department_id={department_id}&request_id={request_id}"

    return {
        "status": "success",
        "upload_url": upload_url,
        "request_id": request_id,
        "instructions": [
            "1. Click or copy the upload_url link to access the upload form",
            "2. Select your PDF file using the file input and click 'Upload SDS File' to upload",
            "3. After the file is uploaded, call check_upload_status tool with request_id to check the status of the upload process"
        ]
    }
    

@mcp.tool()
async def check_upload_status(session_id: str, request_id: str) -> dict:
    """
    Check and notify the status of the upload SDS file process.

    REQUIRED: User must be authenticated using the login tool first.

    IMPORTANT GUIDELINES:
    - If not found request, ask user to provide request_id or follow the instruction to upload SDS file again.
    - If progress is 100, show information.
    - If progress is not 100, show information for current progres and call check_upload_status tool with request_id again.
    """

    info = redis_client.get(f"sds_mcp:{session_id}")
    if not info:
        return {
            "status": "error",
            "error": "Access token not found in session",
            "instruction": "Session expired. Please login again using the login tool."
        }

    headers = {SDS_HEADER_NAME: f"{info.get('access_token')}"}
    endpoint = f"{BACKEND_URL}/binder/getExtractionStatus/?id={request_id}"

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            progress = data.get("progress", 0)
            return {
                "status": "success" if progress == 100 else "pending", 
                "data": data,
                "progress": progress,
                "instruction": [
                    "Show information for current progress in data",
                    "If progress is not 100, call check_upload_status tool with request_id again"
                ]
            }
        else:
            return {
                "status": "error", 
                "error": f"Request failed with status {response.status_code}",
                "instruction": "Failed to get upload status. Please try again."
            }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to service. Please try again."
        }



@mcp.tool()
async def upload_product_list(session_id: str) -> Dict[str, Any]:
    """
    When user upload the product list, call this tool to upload the product list to the backend server.
    
    REQUIRED: User must be authenticated using the login tool first.
    IMPORTANT GUIDELINES:
    """


    request_id = str(uuid.uuid4())

    key = f"upload_product_list:{session_id}:{request_id}"
    redis_client.set(key, "pending")

    upload_url = f"{DOMAIN}/uploadProductList?session_id={session_id}&request_id={request_id}"

    return {
        "status": "success",
        "request_id": request_id,
        "upload_url": upload_url,
        "instruction": [
            "1. Click or copy the upload_url link to access the upload form",
            "2. Select your excel file using the file input and click 'Upload' to upload",
            "3. After the file is uploaded, call get_upload_product_list_status tool with request_id to check the status of the upload process"
        ]
    }


@mcp.tool()
async def get_upload_product_list_status(session_id: str, request_id: str) -> dict:
    """
    Get the status of the upload product list process.

    REQUIRED: User must be authenticated using the login tool first.
    """
    
    info = redis_client.get(f"sds_mcp:{session_id}")
    if not info:
        return {
            "status": "error",
            "error": "Access token not found in session",
            "instruction": "Session expired. Please login again using the login tool."
        }

    key = f"upload_product_list:{session_id}:{request_id}"
    status = redis_client.get(key)

    if not status:
        return {
            "status": "error",
            "error": "Status not found",
            "instruction": "Please check the request ID and try again."
        }


@mcp.tool()
async def map(session_id: str, request_id: str) -> dict:
    """
    Get the product list from the specified request ID.

    REQUIRED: User must be authenticated using the login tool first.
    """
    
    