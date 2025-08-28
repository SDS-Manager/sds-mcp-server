from mcp.server.fastmcp import FastMCP
from cache import redis_client
from typing import Dict, Any, List, Optional
from config import BACKEND_URL, SDS_HEADER_NAME
import logging
import requests
import uuid
import base64
import tempfile
import os

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
    Authenticate user with API key.

    This tool MUST be called first before any other operations.

    Arguments:
        access_token: Your API key for authentication

    Returns:
        Dictionary with authentication status, user information, and available actions:
        - status: "success" or "error"
        - message: Welcome message or error details
        - user_info: User details (id, email, name)
        - session_id: Session identifier for subsequent operations
        - available_actions: Structured list of available operations:
          - search_options: Customer library and global database searches
          - management_options: Location and SDS management tasks
          - information_options: Authentication and status checking
        - next_steps: Guidance on what users can do next
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
                "available_actions": {
                    "search_options": [
                        "Search Your Customer Library - Find SDS documents in your organization's inventory",
                        "Search Global Database - Find SDS documents from the broader global database",
                        "Search SDS with Ingredients - Find SDS documents with specific ingredients"
                    ],
                    "management_options": [
                        "View Your Locations - See your organization's location/department structure",
                        "Add New Location - Create a new department or location",
                        "Add SDS to Location - Add an SDS document from global database to a specific location",
                        "Move SDS Between Locations - Move existing SDS substances to different locations",
                        "Copy SDS to Additional Locations - Duplicate SDS substances to multiple locations",
                        "Archive SDS Substance - Archive an SDS substance"
                    ],
                    "information_options": [
                        "Check Authentication Status - Verify your current session status"
                    ]
                },
                "next_steps": "What would you like to do? You can search for chemicals by name, manage your locations, or perform SDS management tasks."
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
    description="Search customer SDS Library. Requires authentication via login tool first."
)
async def search_customer_library(query: str, session_id: str, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    """
    Search for Safety Data Sheets (SDS) from customer's library by product name or keywords.

    REQUIRES: User must be authenticated using the login tool first.
    This searches the customer's specific SDS library/inventory.
    Let user know if they want to load more results, they can use the same tool with different page number.
    
    Arguments:
        query: Search query string for finding SDS documents
        session_id: Session ID from authentication
        page: Page number for pagination (default: 1)
        page_size: Number of results per page (default: 10)

    Returns:
        Dictionary containing search results with:
        - results: Array of matching SDS documents with:
          - id: Substance ID (unique identifier for this substance record)
          - is_archived: Boolean indicating if the SDS is archived
          - sds_id: SDS PDF ID - use this for adding to location via move_sds_to_location tool
          - public_view_url: URL for public viewing of the SDS
          - safety_summary_url: URL for safety information summary
          - language: Document language code (e.g., "en", "no")
          - product_name: Product/chemical name
          - supplier_name: Supplier/manufacturer name
          - product_code: Product code from manufacturer
          - revision_date: SDS revision date (YYYY-MM-DD)
          - created_date: Date added to system (YYYY-MM-DD)
          - ean_code: EAN barcode (if available)
          - upc_code: UPC barcode (if available)
          - external_system_id: External system identifier
          - external_system_url: External system URL
          - hazard_sentences: Comma-separated H-codes (e.g., "H302,H317,H319")
          - euh_sentences: EUH hazard codes
          - prevention_sentences: P-codes for prevention measures
          - location: Object with location info {id, name}
          - substance_amount: Amount/quantity information
          - substance_approval: Approval status
          - nfpa: NFPA rating information
          - hmis: HMIS rating information
          - icons: Array of GHS pictogram objects {url, description, type}
          - highest_risks: Risk assessment data {health_risk, safety_risk, environment_risk}
          - highest_storage_risks: Storage risk data {storage_safety_risk, storage_environment_risk}
          - info_msg: Additional information messages
          - attachments: Array of attached files
          - sds_info: Detailed SDS information object with chemical data, CAS numbers, etc.
          - sds_other_info: Section-specific SDS content organized by sections (2-16)
        - count: Total number of results available
        - next: URL for next page (if available)
        - previous: URL for previous page (if available)
        - page: Current page number
        - page_size: Results per page
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
    description="Add an SDS document to a specific location/department. Requires authentication via login tool first."
)
async def add_sds_to_location(sds_id: str, department_id: str, session_id: str) -> Dict[str, Any]:
    """
    Add an existing SDS document from the global database to a specific location/department in the customer's inventory.

    This tool allows you to take an SDS document that exists in the global SDS database 
    and add it to a specific location or department within your organization's inventory system.
    The SDS document will become available as a "substance" in that location.

    REQUIRES: User must be authenticated using the login tool first.

    Arguments:
        sds_id: The SDS document ID from the global database (obtained from search_global_database results)
        department_id: The target department/location ID where the SDS should be added
        session_id: Session ID from authentication

    Returns:
        Dictionary with operation status:
        - status: "success" or "error"
        - message: Human-readable success message or error details
        - instruction: Guidance when operation fails (error cases only)

    Example Usage:
        # First search the global database
        results = search_global_database("Acetone", session_id)
        sds_id = results["results"][0]["id"]  # Get SDS ID from search results
        
        # Then add it to your location
        add_sds_to_location(
            sds_id=sds_id,
            department_id="12345", 
            session_id=session_id
        )

    Related Tools:
        - search_global_database: Find SDS documents to add
        - search_customer_library: View your existing SDS inventory
        - move_sds_to_location: Move existing substances between locations
        - copy_sds_substance: Copy substances to additional locations
    """

    endpoint = f"{BACKEND_URL}/location/{department_id}/addSDS/"

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
            return {
                "status": "success",
                "message": f"SDS {sds_id} added to location {department_id} successfully"
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
                "error": f"Failed to add SDS to location with status {response.status_code}",
                "instruction": "Failed to add SDS to location. Please verify the sds_id and department_id are correct."
            }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to location service. Please try again."
        }


@mcp.tool(
    description="Move SDS substance to a specific location. Requires authentication via login tool first."
)
async def move_sds_to_location(substance_id: str, department_id: str, session_id: str) -> Dict[str, Any]:
    """
    Move an SDS substance to a specific location within the customer's inventory.
    
    REQUIRES: User must be authenticated using the login tool first.
    
    Arguments:
        substance_id: The substance ID (from search results)
        location_id: The target location ID to move the substance to
        session_id: Session ID from authentication

    Returns:
        Dictionary with operation status:
        - status: "success" or "error"
        - message: Success message or error details
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
            json={"department_id": department_id},
            timeout=10
        )
        
        if response.status_code == 200:
            return {
                "status": "success",
                "message": f"SDS substance {substance_id} moved to location {location_id} successfully"
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
                "error": f"Failed to move SDS to location with status {response.status_code}",
                "instruction": "Failed to move SDS to location. Please verify the substance_id and location_id are correct."
            }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to location service. Please try again."
        }


@mcp.tool()
async def copy_sds_substance(substance_id: str, department_id: str, session_id: str) -> Dict[str, Any]:
    """
    Copy a substance (SDS assigned to a location) to another location/department.

    In SDS Manager, an SDS in a location is called a "substance". To add the same SDS
    to a different location, this tool creates a duplicate of the source substance at
    the target location. The original substance is not modified or removed.

    Requires:
        - User must be authenticated via the login tool first.

    Arguments:
        - substance_id: ID of the source substance to copy (from customer library search)
        - department_id: ID of the target location/department
        - session_id: Authentication session ID

    Returns:
        - status: "success" or "error"
        - message: Human-readable result
        - new_substance_id: ID of the created substance (if provided by API)
        - instruction: Guidance when operation fails
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
            timeout=10
        )

        if response.status_code == 200:
            return {
                "status": "success",
                "message": f"SDS substance {substance_id} copied successfully"
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
                "error": f"Failed to copy SDS substance with status {response.status_code}",
                "instruction": "Failed to copy SDS substance. Please verify the substance_id is correct."
            }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to copy service. Please try again."
        }

@mcp.tool(
    description="Get SDS substance details. Requires authentication via login tool first."
)
async def archive_sds_substance(substance_id: str, session_id: str) -> Dict[str, Any]:
    """
    Archive an SDS substance.
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
            return {
                "status": "success",
                "message": f"SDS substance {substance_id} archived successfully"
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
                "error": f"Failed to archive SDS substance with status {response.status_code}",
                "instruction": "Failed to archive SDS substance. Please verify the substance_id is correct."
            }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to archive service. Please try again."
        }

@mcp.tool(
    description="Search for SDS documents from the global database. Requires authentication via login tool first."
)
async def search_global_database(query: str, session_id: str, page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    """
    Search for Safety Data Sheets (SDS) from the global database by product name, manufacturer, or keywords.

    REQUIRES: User must be authenticated using the login tool first.
    This searches the broader global SDS database, which contains more documents than the customer-specific search.
    
    Arguments:
        query: Search query string for finding SDS documents
        session_id: Session ID from authentication
        page: Page number for pagination (default: 1)
        page_size: Number of results per page (default: 10)

    Returns:
        Dictionary containing search results with:
        - results: Array of matching SDS documents
          - id: SDS ID - use this for adding to location via add_sds_to_location tool
          - sds_pdf_product_name: Product name
          - sds_pdf_manufacture_name: Manufacturer name
          - sds_pdf_revision_date: Document revision date
          - language: Document language
          - regulation_area: Regulatory area (EU, US, etc.)
          - cas_no: CAS number (if available)
          - link_to_public_view: Public view URL
          - link_to_discovery: Discovery URL
          - product_code: Product code
          - language_code: Language code
        - count: Total number of results
        - next: URL for next page (if available)
        - previous: URL for previous page (if available)
        - next_action_suggestion: Suggestion to add SDS to location (when results found)
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
            f"{BACKEND_URL}/pdfs/?search={query}&page={page}&page_size={page_size}",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            count = data.get("count", 0)
            
            # Prepare response
            response_data = {
                "status": "success",
                "query": query,
                "results": results,
                "count": count,
                "next": data.get("next"),
                "previous": data.get("previous"),
                "facets": data.get("facets", {}),
                "page": page,
                "page_size": page_size
            }
            
            # Add suggestion if results are found
            if results and count > 0:
                response_data["next_action_suggestion"] = {
                    "action": "add_to_location",
                    "message": f"Found {count} SDS document(s) for '{query}'. Would you like to add any of these to a location?",
                    "instructions": [
                        "1. Choose an SDS document from the results above",
                        "2. Use the 'id' field from your chosen result",
                        "3. Call add_sds_to_location(sds_id=<chosen_id>, department_id=<your_department_id>, session_id=<session_id>)",
                        "4. Replace <chosen_id> with the SDS ID and <your_department_id> with your target location ID"
                    ],
                    "example": f"add_sds_to_location(sds_id='{results[0].get('id', 'EXAMPLE_ID')}', department_id='YOUR_DEPT_ID', session_id='{session_id}')" if results else None
                }
            
            return response_data
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
                "error": f"Global search failed with status {response.status_code}",
                "instruction": "Failed to perform global search. Please try again or contact support."
            }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error", 
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to global search service. Please try again."
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


@mcp.tool()
async def get_location(session_id: str) -> List[Dict[str, Any]]:
    """
    Get location tree list for the current user.

    REQUIRES: User must be authenticated using the login tool first.
    RETURN: A tree (similar to a tree structure in a file system) of locations constructed from an array of root location with the following structure:
        - id: Unique location identifier
        - name: Location name
        - children: Array of child locations
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
        else:
            return {
                "status": "error",
                "error": f"Get location structure error with status {response.status_code}",
                "instruction": "Failed to get location structure. Please try again or contact support."
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
    ARGUMENTS:
        - name: Location name
        - parent_department_id: Parent location id (Optional)
    RETURN: A dictionary of the newly added location

    When user not mentioning parent location, ask user to clarify whether it is root location or not.
    - If it is root location, parent_department_id is None.
    - If it is not root location, ask user to provide parent location.
    When user provide only location name, Get id from get_location tool and convert to string.
    After checking from get_location tool, if multiple locations with same name, ask user to choose.
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
        else:
            return {
                "status": "error",
                "error": f"Add location error with status {response.status_code}",
                "instruction": "Failed to add location. Please try again or contact support."
            }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to service. Please try again."
        }


@mcp.tool(
    description="Get detailed information about an SDS substance in your inventory. Requires authentication via login tool first."
)
async def retrieve_substance_detail(substance_id: str, session_id: str) -> Dict[str, Any]:
    """
    Get comprehensive details about a specific SDS substance in your organization's inventory.

    This tool provides complete information about an SDS substance that's already been added to your 
    organization's locations. Use this to view detailed chemical information, hazard data, location details,
    and all other properties of a substance.

    REQUIRES: User must be authenticated using the login tool first.

    Arguments:
        substance_id: The unique identifier of the substance (obtained from customer library search results)
        session_id: Session ID from authentication

    Returns:
        Dictionary containing comprehensive substance details:
        
        Top-level fields:
        - id: Substance ID (int)
        - is_archived: Archive status (bool)
        - sds_id: SDS document ID (int)
        - public_view_url: Public viewing URL (str)
        - safety_summary_url: Safety summary URL (str)
        - language: Document language code (str, e.g. "no", "en")
        - product_name: Product/chemical name (str)
        - supplier_name: Supplier/manufacturer name (str)
        - product_code: Product code/catalog number (str)
        - revision_date: SDS revision date (str, YYYY-MM-DD format)
        - created_date: Record creation date (str, YYYY-MM-DD format)
        - hazard_sentences: H-codes comma-separated (str, e.g. "H302,H317,H319")
        - euh_sentences: EUH codes (str)
        - prevention_sentences: P-codes comma-separated (str)
        - substance_amount: Amount of substance (nullable)
        - substance_approval: Approval status (nullable)
        - nfpa: NFPA rating (nullable)
        - hmis: HMIS rating (nullable)
        - info_msg: Information message (nullable)
        - attachments: List of attached files (list)
        
        location: Dict with location information
        - id: Location ID (int)
        - name: Location name (str)
        
        icons: List of GHS pictogram icons
        - url: Icon image URL (str)
        - description: Icon description (str, e.g. "GHS07")
        - type: Icon type (str, typically "GHS")
        
        highest_risks: Dict with risk assessments
        - health_risk, safety_risk, environment_risk: Base risk levels (nullable)
        - health_risk_incl_ppe, safety_risk_incl_ppe, environment_risk_incl_ppe: Risk levels including PPE (nullable)
        
        highest_storage_risks: Dict with storage risk assessments
        - storage_safety_risk, storage_environment_risk: Storage risk levels (nullable)
        
        sds_info: Comprehensive SDS document information dict
        - uuid: SDS document UUID (str)
        - cas_no: CAS number (str)
        - ec_no: EC number (nullable str)
        - chemical_formula: Chemical formula (str)
        - version: SDS version (str)
        - health_risk, safety_risk, environment_risk: Numeric risk ratings (int)
        - signal_word: GHS signal word (str, e.g. "Fare", "Danger")
        - hazard_codes: List of detailed H-codes with descriptions
        - precautionary_codes: List of detailed P-codes with descriptions
        - sds_chemical: List of chemical components with CAS numbers and concentrations
        - regulations: List of regulatory listings (Prop 65, ECHA, SIN List, etc.)
        - ghs_pictogram_code: GHS codes comma-separated (str)
        - reach_reg_no: REACH registration number (str)
        - emergency_telephone_number: Emergency contact (str)
        - Many other technical and regulatory fields...
        
        sds_other_info: Detailed SDS sections breakdown by section numbers (2-16)
        - Keys are section numbers as strings ("2", "3", "4", etc.)
        - Values are lists of section content with tags, values, and literals
        - Contains parsed content from all 16 sections of the SDS document
        - Includes composition, first aid, fire fighting, handling, physical properties, toxicology, etc.

    Example Usage:
        # First search your customer library
        results = search_customer_library("acetone", session_id)
        substance_id = results["results"][0]["id"]  # Get substance ID from search
        
        # Then get detailed information
        details = retrieve_substance_detail(substance_id, session_id)

    Related Tools:
        - search_customer_library: Find substances to get their IDs
        - move_sds_to_location: Move substances between locations
        - copy_sds_substance: Copy substances to additional locations
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
            data = response.json()
            return {
                "status": "success",
                "substance_details": data,
                "message": f"Successfully retrieved details for substance {substance_id}"
            }
        else:
            try:
                data = response.json()
            except ValueError:
                data = {}
            return {
                    "status": "error",
                    "error_code": data.get("error_code", "Unknown error"),
                    "error_message": data.get("error_message", "Unknown error"),
                    "instruction": (
                        f"Something went wrong. {data.get('error_message', 'Unknown error')}"
                    )
                }

    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to service. Please try again."
        }


@mcp.tool()
async def get_sdss_with_ingredients(session_id: str, query: str = "", page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    """
    Get a paginated list of SDSs (Safety Data Sheets) that contain ingredients 
    on the restricted list.

    ARGUMENTS:
        session_id (str): Session ID obtained after authentication.
        query (str, optional): Search term to filter SDSs. 
            - If empty (""), returns all SDSs with restricted ingredients.
            - If provided, returns only matching SDSs with restricted ingredients.
        page (int, optional): Page number of results to fetch. Defaults to 1.
        page_size (int, optional): Number of SDSs per page. Defaults to 10.

    RETURN:
        dict: 
            - "results": List of SDSs with restricted ingredients
            - "page": Current page number
            - "page_size": Number of items per page
            - "has_more": Boolean flag indicating if more results are available

    NOTES FOR USERS:
        - Leave `query` empty to see all SDSs with restricted ingredients.
        - Provide a `query` to search only within restricted SDSs.
        - Use `page` and `page_size` to control pagination.
        - If `has_more` is True, you can load additional results by increasing `page`.
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

    endpoint = f"{BACKEND_URL}/substance/?hazardous=true&search={query}&page={page}&page_size={page_size}"
    headers = {SDS_HEADER_NAME: f"{info.get('access_token')}"}

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            try:
                data = response.json()
            except ValueError:
                data = {}

            return {
                    "status": "error",
                    "error_code": data.get("error_code", "Unknown error"),
                    "error_message": data.get("error_message", "Unknown error"),
                    "instruction": (
                        f"Something went wrong. {data.get('error_message', 'Unknown error')}"
                    )
                }

    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to service. Please try again."
        }

@mcp.tool()
async def upload_sds_file_to_location(
    session_id: str,
    department_id: str,
    pdf_content: str,
    file_name: str,
) -> Dict[str, Any]:
    """
    Upload the SDS file to the specified location using the base64 content:
    ARGUMENTS:
        session_id (str): Session ID obtained after authentication.
        department_id (str): ID of the department to upload the SDS file to. need to get from get_location tool to get correct department id.
        pdf_content (str): Content of the SDS file to upload.
        file_name (str): Name of the SDS file to upload.

    The user must provide the SDS file content in pdf format.
    The use must provide the department_id of the location to upload the SDS file to.
    If the user provide location name, use get_location tool to get the department_id.
    If the user provide location id, use it directly.
    If the user provide both, use the location id.
    If the user provide neither, ask user to provide the location name or id.
    """

    if not session_id:
        return {
            "status": "error",
            "error": "No active session found",
            "instruction": "Please login first using the login tool with your access token",
        }

    info = redis_client.get(f"sds_mcp:{session_id}")
    if not info:
        return {
            "status": "error",
            "error": "Access token not found in session",
            "instruction": "Session expired. Please login again using the login tool.",
        }

    access_token = info.get("access_token")
    if not access_token:
        return {
            "status": "error",
            "error": "Missing access token in session",
            "instruction": "Please login again using the login tool.",
        }


    try:
        pdf_bytes = base64.b64decode(pdf_content, validate=True)
    except Exception:
        return {
            "status": "error",
            "error": "Invalid base64 PDF content",
            "instruction": "Ensure `pdf_content` is base64-encoded PDF data.",
        }

    if not file_name or "." not in file_name:
        file_name = "sds.pdf"

    # --- Prepare request ---
    headers = {SDS_HEADER_NAME: access_token}

    # Save to temp file
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file_path = temp_file.name
    temp_file.close()

    try:
        with open(temp_file_path, "wb") as f:
            f.write(pdf_bytes)

        with open(temp_file_path, "rb") as f:
            files = {
                # (filename, fileobj, content_type)
                "imported_file": (file_name, f, "application/pdf"),
            }
            response = requests.post(
                f"{BACKEND_URL}/location/{department_id}/uploadSDS/",
                headers=headers,
                files=files,
                timeout=30,
            )
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to service. Please try again.",
        }
    finally:
        # Clean up temp file
        if os.path.exists(temp_file_path):
            os.unlink(temp_file_path)

    # --- Handle response ---
    if response.status_code == 200:
        res = response.json()
        

        return {
            "status": "success",
            "file_info": res.get("file_info", ""),
            "request_id": res.get("request_id", ""),
            "step": res.get("step", ""),
            "instruction": "Successfully uploaded the SDS file. Processing will begin shortly.",
        }

    err = response.json()

    return {
        "status": "error",
        "error_code": err.get("error_code", f"HTTP_{response.status_code}"),
        "error_message": err.get("error_message", "Unknown error"),
        "instruction": f"Upload failed: {err.get('error_message', 'Unknown error')}",
    }
