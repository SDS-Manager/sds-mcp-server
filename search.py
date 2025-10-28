from mcp.server.fastmcp import FastMCP
from cache import redis_client
from typing import Dict, Any, List, Optional
from config import BACKEND_URL, SDS_HEADER_NAME, DOMAIN
from models import (
    SubstanceDetail,
    SubstanceListApiResponse,
    GetExtractionStatusApiResponse,
    SearchGlobalDatabaseResponse,
    SdsRequestResponse,
)
import logging
import requests
import uuid
import pandas as pd
import json
import os

logger = logging.getLogger(__name__)

LONG_DESCRIPTION = """
The purpose of this MCP is to help new customers set up and manage their Safety Data Sheet (SDS) Library using SDS Manager.
The APIs in this collection allow an AI assistant to guide users through the entire onboarding process — from understanding their organization’s needs to creating a structured, compliant, and accessible SDS library.

The assistant should begin by gathering key context from the user:
- What type of business they operate
- Whether they have multiple locations or sites
- Approximately how many chemicals they use that require SDSs

Based on the answers, the assistant will determine which setup method fits best. There are four primary ways to create an SDS library using these APIs:
1. Import existing SDS PDF files – if the customer already has their SDSs, the assistant can upload them directly using add_sds_by_uploading_sds_pdf_file or add_sds_by_url.
2. Import a product list from Excel – when the customer has a spreadsheet of chemicals, the assistant can use upload_product_list_excel_file to upload the file.
    - Each row in the imported Excel file creates an SDS Request (if user not allow auto matching or system unable to find matching SDS), representing a product that requires an SDS but doesn’t yet have one linked.
    - The assistant can retrieve pending SDS Requests using get_sds_request, search for matching SDSs in the global database using search_sds_from_sds_managers_database, and link them using match_sds_request.
    - When a match is confirmed, the SDS is automatically added to the customer’s SDS library.
3. Digitize paper binders – if the user has printed SDSs, they can search for each product in the SDS Manager database and add it when a match is found, or scan and upload missing ones using add_sds_by_uploading_sds_pdf_file.
4. Build from scratch – if no overview exists, the user can take photos of product labels, extract text with OCR, and search for each product using search_sds_from_sds_managers_database before adding it with add_sds.

For organizations with multiple sites, the assistant can use get_locations and add_location to create and manage a hierarchical structure. Each SDS can be assigned to a location or moved and copied between sites using move_sds and copy_sds_to_another_location.

The remaining APIs support the complete SDS management lifecycle:
- Authentication and access control: get_login_url, check_auth_status
- SDS retrieval and detail viewing: search_sds_from_sds_managers_database, show_sds_detail, search_customer_sds_library, show_customer_sds_detail
- File and data import management: validate_upload_product_list_excel_data, process_upload_product_list_excel_data, check_upload_product_list_excel_data_status
- Maintenance and compliance: archive_sds, get_sdss_with_ingredients_on_restricted_lists, edit_sds_data, get_sds_request, match_sds_request
- Fallback search and acquisition: find_sds_pdf_links_from_external_web (when SDS not found in the 16 million global database)

When an SDS is not found in SDS Manager's 16 million global database, the assistant can use find_sds_pdf_links_from_external_web to automatically search the web for the SDS PDF, get the URL, and upload it to the customer's library. This ensures comprehensive coverage even for rare or specialty chemicals.

The AI assistant's primary objectives are to:
1. Collect setup information and guide the user through the correct onboarding path
2. Automate the import and linking of SDSs through uploads, database searches, or web search fallback
3. Organize SDSs by site and chemical type
4. Ensure the resulting SDS library is complete, accessible, and compliant with chemical safety regulations.

The assistant should always aim to simplify the user experience — automating manual tasks like file import, SDS matching, web search, and location setup — while ensuring the user ends with a properly organized, searchable SDS library ready for employee access.
"""

# Initialize MCP server with proper description
mcp = FastMCP(
    name="SDS Manager",
    stateless_http=True,
    instructions="MCP tools for guiding users in setting up their Safety Data Sheet (SDS) library in SDS Manager. This MCP includes tools for uploading SDS PDFs, importing Excel product lists that create SDS Requests, matching SDSs from the global database, and organizing them by location for full regulatory compliance and accessibility.",
)


@mcp.tool()
def get_mcp_overview() -> str:
    """
    This tool is used to get an overview of this MCP and its purpose to guide the AI agent.

    Important Guidelines:
        - Call this tool at the beginning of the conversation

    Return an overview of this MCP and its purpose to guide the AI agent.
    """
    return LONG_DESCRIPTION


@mcp.tool()
async def get_login_url() -> Dict[str, Any]:
    """
    To login to SDS Manager, you need to get session ID and login URL first.
    This tool initialize session ID & generate an login URL for user to login with their API key.

    Prerequisites:
        - Must call get_mcp_overview tool at the beginning of the conversation

    Important Guidelines:
        - After user confirm finished login, pass session_handle for all other tools

    Returns:
        Dict containing:
        - status (str): "success" or "error"
        - message (str): Welcome message on success
        - session_handle (UUID): Session UUID used for all other tools
        - login_url (str): URL for user to login with their API key
        - instruction (str): User-friendly guidance
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    session_handle = str(uuid.uuid4())
    return {
        "status": "success",
        "message": "Login URL generated! Please login with your API key.",
        "session_handle": session_handle,
        "login_url": f"{DOMAIN}/login?session_id={session_handle}",
        "instruction": [
            "1. Click or copy the login_url link to access the login form",
            "2. Type your API key in the input field and click 'Login' to login",
            "3. After user confirm finished login, call check_auth_status with session_handle"
        ]
    }


@mcp.tool()
async def check_auth_status(session_handle: uuid.UUID) -> Dict[str, Any]:
    """
    Check if the current session is authenticated.

    Prerequisites:
        - Must have session_handle from get_login_url tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool

    Returns:
        Dict containing:
        - On success: Session information with user_id, email, name, ...
        - On error:
            - status (str): "not_initialized" or "not_authenticated"
            - error (str): error message
            - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")

    if info:
        return {
            "status": "success",
            "message": "Login successful! Welcome to SDS Manager.",
            "user_info": {
                "id": info.get("id"),
                "email": info.get("email"),
                "name": info.get("first_name", "") + " " + info.get("last_name", ""),
                "language": info.get("language"),
                "country": info.get("country"),
                "phone_number": info.get("phone_number"),
                "customer": info.get("customer"),
            },
        }
    else:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }


@mcp.tool(title="Search SDSs from SDS Managers 16 millions global SDS database")
async def search_sds_from_sds_managers_database(
    session_handle: uuid.UUID,
    keyword: str, 
    page: int = 1, 
    page_size: int = 10, 
    language_code: Optional[str] = None,
    region_code: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search for Safety Data Sheets (SDS) in the SDS Managers 16 millions global SDS database.

    Prerequisites:
        - Must have session_handle from get_login_url tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        keyword (str): Search term (product name, manufacturer, etc.)
        page (int, optional): Page number for pagination. Default: 1
        page_size (int, optional): Results per page. Default: 10
        language_code (str, optional): Language filter (e.g., "en", "es")
        region_code (str, optional): Region filter (e.g., "US", "EU")

    Important Guidelines:
        - If user asks to search without specifying global or their SDS library, search BOTH databases:
          call search_sds_from_sds_managers_database AND search_customer_sds_library
        - Display results in a table with columns: ID, Product Name, Product Code, 
          Manufacturer Name, Revision Date, Language, Regulation Area, Public Link, Discovery Link
        - Auto-convert language/region names to codes (e.g., "English" → "en", "Europe" → "eu")
        - Do not use IDs as search keywords

    Returns:
        Dict containing:
        - status (str): "success" or "error"
        - results (list): List of SDS records matching search
        - count (int): Total number of results
        - next_page (int|None): Next page number if available
        - previous_page (int|None): Previous page number if available
        - page (int): Current page number
        - page_size (int): Results per page
        - instruction (str): User-friendly guidance
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    try:
        search_param = f"?search={keyword}&page={page}&page_size={page_size}"
        if language_code:
            search_param += f"&language_code={language_code}"
        if region_code:
            search_param += f"&region={region_code.upper()}"

        response = requests.get(
            f"{BACKEND_URL}/pdfs/{search_param}",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            res = SearchGlobalDatabaseResponse(**data)
      
            return {
                "status": "success",
                "results": [substance.model_dump(by_alias=True) for substance in res.results],
                "count": res.count,
                "next_page": int(page) + 1 if res.next else None,
                "previous_page": int(page) - 1 if res.previous else None,
                "page": page,
                "page_size": page_size,
                "instruction": "Suggest user to do external web search using find_sds_pdf_links_from_external_web tool if not found the SDS they want"
            }
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg if error_msg else response.text,
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


@mcp.tool(title="Show SDS details")
async def show_sds_detail(session_handle: uuid.UUID, sds_id: str) -> Dict[str, Any]:
    """
    Retrieve detailed information for a specific SDS from the global database.

    Prerequisites:
        - Must have session_handle from get_login_url tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        sds_id (str): Unique identifier of the SDS to retrieve

    Important Guidelines:
        - If SDS ID is not available, ask user to provide the SDS name
        - When user provides SDS name, call search_sds_from_sds_managers_database with the name as keyword
        - Always ask user to choose which SDS if multiple results are found
        - Display any error messages to the user

    Returns:
        Dict containing:
        - status (str): "success" or "error"
        - data (dict): Complete SDS information including product details, manufacturer, 
          revision date, hazards, ingredients, etc.
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    endpoint = f"{BACKEND_URL}/pdfs/{sds_id}/"
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            return {
                "status": "success",
                "data": response.json()
            }
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg if error_msg else response.text,
                }
            except:
                return {
                    "status": "error",
                    "error": f"Failed to get substance with status {response.status_code}",
                    "instruction": "Failed to get SDS. Please verify the SDS."
                }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to service. Please try again."
        }


@mcp.tool(title="Find SDS pdf links from external web")
async def find_sds_pdf_links_from_external_web(
    session_handle: uuid.UUID,
    links: List[str],
) -> Dict[str, Any]:
    """
    You will become an excellent SDS search engine expert, especially for hunting SDS direct pdf links. This tool is an endpoint for receiving web search result of SDS or MSDS pdf links from the you.

    Prerequisites:
        - Must have session_handle from get_login_url tool

    Parameters:
        session_handle (UUID): Session UUID from the get_login_url tool.
        links (List[str]): The list of SDS PDF links found by you during your web search.

    Important Guidelines:
        - Search google with query "Safety data sheet <keyword>" that use advanced search for filetype:pdf and give user the top 10 links you found.
        - Prioritize newest version of the SDS/MSDS PDF.
        - Search from all alternative sources in all languages, all regions, all regulations.
        - Ensure the links is a valid pdf when passing to links parameter.

    Returns:
        Dict[str, Any]: {
            "status": "success",
            "found_links": [list of found SDS PDF links],
            "instruction": User-friendly guidance
        }

        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance

    Example Workflow:
        1. User: "Find SDS for NANO ACID CLEANER by ERRECOM SPA"
        2. Agent searches web for SDS/MSDS PDFs.
        3. Agent calls this tool with:
           find_sds_pdf_links_from_external_web(session_handle, [
               "https://shop.errecom.com/wp-content/uploads/.../MSDS.U.NANO-ACID-CLEANER.EN_05-08-2021.pdf"
           ])
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    return {
        "status": "success",
        "found_links": links,
        "instruction": [
            "Ask user if they want to add the SDS pdf link to customer's inventory by calling add_sds_by_url tool (If multiple links are found, ask user to choose)"
        ]
    }


@mcp.tool(title="Search customer SDS library")
async def search_customer_sds_library(
    session_handle: uuid.UUID, 
    keyword: str, 
    page: int = 1, 
    page_size: int = 10
) -> Dict[str, Any]:
    """
    Search for substances (SDSs assigned to locations) in the customer's library/inventory.

    Prerequisites:
        - Must have session_handle from get_login_url tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        keyword (str): Search term (product name, location, etc.)
        page (int, optional): Page number for pagination. Default: 1
        page_size (int, optional): Results per page. Default: 10

    Important Guidelines:
        - If user asks to search without specifying global/internal, search BOTH databases:
          call search_sds_from_sds_managers_database AND search_customer_sds_library
        - Do not use IDs as search keywords

    Returns:
        Dict containing:
        - status (str): "success" or "error"
        - results (list): List of substance records in customer's inventory
        - count (int): Total number of results
        - next_page (int|None): Next page number if available
        - previous_page (int|None): Previous page number if available
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

    try:
        response = requests.get(
            f"{BACKEND_URL}/substance/?search={keyword}&page={page}&page_size={page_size}",
            headers=headers,
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            try:
                res = SubstanceListApiResponse(**data)
                
                return {
                    "status": "success",
                    "results": [substance.model_dump(by_alias=True) for substance in res.results],
                    "count": res.count,
                    "next_page": int(page) + 1 if res.next else None,
                    "previous_page": int(page) - 1 if res.previous else None,
                }
            except ValueError as e:
                return {
                    "status": "success",
                    "results": data.get("results", []),
                    "count": data.get("count", 0),
                    "next_page": int(page) + 1 if data.get("next") else None,
                    "previous_page": int(page) - 1 if data.get("previous") else None,
                }
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg if error_msg else response.text,
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


@mcp.tool(title="Show customer SDS detail")
async def show_customer_sds_detail(
    session_handle: uuid.UUID, 
    substance_id: str
) -> Dict[str, Any]:
    """
    Retrieve detailed information for a specific substance (SDS assigned to a location) in the customer's inventory.

    Prerequisites:
        - Must have session_handle from get_login_url tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        substance_id (str): Unique identifier of the substance in customer's inventory

    Important Guidelines:
        - If substance ID is not available, ask user to provide the SDS/substance name
        - When user provides name, call search_customer_sds_library with the name as keyword
        - Always ask user to choose which substance if multiple results are found
        - Display any error messages to the user

    Returns:
        Dict containing:
        - status (str): "success" or "error"
        - result (dict): Complete substance information including SDS details, location,
          product name, manufacturer, hazards, ingredients, etc.
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    endpoint = f"{BACKEND_URL}/substance/{substance_id}/"
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            try:
                # Create DTO from API response
                substance_dto = SubstanceDetail(**data)
                
                return {
                    "status": "success",
                    "result": substance_dto.model_dump(by_alias=True)
                }
            except ValueError as e:
                # Fallback to raw data if DTO creation fails
                return {
                    "status": "success",
                    "result": data,
                    "dto_warning": "Failed to validate data structure, returning raw data"
                }
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg if error_msg else response.text,
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


@mcp.tool(title="Add SDS")
async def add_sds(
    session_handle: uuid.UUID, 
    sds_id: str, 
    location_id: str
) -> Dict[str, Any]:
    """
    Add an SDS from the global database to a specific location in the customer's inventory.

    Prerequisites:
        - Must have session_handle from get_login_url tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        sds_id (str): Unique identifier of the SDS from global database
        location_id (str): Unique identifier of the target location

    Important Guidelines:
        - If location ID is not available, ask user to provide location name
          Then call get_locations to retrieve all locations and filter by name
          Always ask user to choose if multiple locations match
        - If SDS ID is not available, ask user to provide SDS name
          Then call search_sds_from_sds_managers_database with the name as keyword
          Always ask user to choose if multiple SDSs are found

    Returns:
        Dict containing:
        - Information of the newly added substance in customer's inventory
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    endpoint = f"{BACKEND_URL}/location/{location_id}/addSDS/"
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json={"sds_id": sds_id},
            timeout=10
        )

        if response.status_code in [200, 201]:
            return response.json()
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg if error_msg else response.text,
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


@mcp.tool(title="Move SDS")
async def move_sds(
    session_handle: uuid.UUID, 
    substance_id: str, 
    location_id: str
) -> Dict[str, Any]:
    """
    Move a substance (SDS assigned to a location) to a different location.
    
    Prerequisites:
        - Must have session_handle from get_login_url tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        substance_id (str): Unique identifier of the substance to move
        location_id (str): Unique identifier of the target location

    Important Guidelines:
        - If location ID is not available, ask user to provide location name
          Then call get_locations to retrieve all locations and filter by name
          Always ask user to choose if multiple locations match
        - If substance ID is not available, ask user to provide SDS/substance name
          Then call search_customer_sds_library with the name as keyword
          Always ask user to choose if multiple substances are found
    
    Returns:
        Dict containing:
        - Information of the moved substance with updated location
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }
        
    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }
        
    endpoint = f"{BACKEND_URL}/substance/{substance_id}/move/"
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    
    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json={"department_id": location_id},
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg if error_msg else response.text,
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


@mcp.tool(title="Copy SDS to another location")
async def copy_sds_to_another_location(
    session_handle: uuid.UUID, 
    substance_id: str, 
    location_id: str
) -> Dict[str, Any]:
    """
    Copy a substance (SDS assigned to a location) to another location, creating a duplicate with similar information.

    Prerequisites:
        - Must have session_handle from get_login_url tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        substance_id (str): Unique identifier of the substance to copy
        location_id (str): Unique identifier of the target location

    Important Guidelines:
        - If location ID is not available, ask user to provide location name
          Then call get_locations to retrieve all locations and filter by name
          Always ask user to choose if multiple locations match
        - If substance ID is not available, ask user to provide SDS/substance name
          Then call search_customer_sds_library with the name as keyword
          Always ask user to choose if multiple substances are found

    Returns:
        Dict containing:
        - Information of the newly added substance in the target location
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    endpoint = f"{BACKEND_URL}/substance/{substance_id}/copy/"
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json={"department_id": location_id},
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg if error_msg else response.text,
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


@mcp.tool(title="Archive SDS")
async def archive_sds(session_handle: uuid.UUID, substance_id: str) -> Dict[str, Any]:
    """
    Archive a substance (SDS assigned to a location), removing it from active inventory.
    Synonyms: delete substance, remove substance.

    Prerequisites:
        - Must have session_handle from get_login_url tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        substance_id (str): Unique identifier of the substance to archive

    Important Guidelines:
        - If substance ID is not available, ask user to provide SDS/substance name
          Then call search_customer_sds_library with the name as keyword
          Always ask user to choose if multiple substances are found
        - Confirm with user before archiving

    Returns:
        Dict containing:
        - Information of the archived substance
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    endpoint = f"{BACKEND_URL}/substance/{substance_id}/archive/"
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg if error_msg else response.text,
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


@mcp.tool(title="Get location")
async def get_locations(session_handle: uuid.UUID) -> List[Dict[str, Any]]:
    """
    Retrieve the complete location hierarchy (tree structure) for the current user's organization.

    Prerequisites:
        - Must have session_handle from get_login_url tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool

    Important Guidelines:
        - Display results in a tree/hierarchical structure (similar to file explorer)
        - Each location contains: id, name, parent relationship, and child locations

    Returns:
        List of location dictionaries representing the organization's location hierarchy
        Each location includes: id, name, parent_id, children (nested locations)
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

    try:
        response = requests.get(
            f"{BACKEND_URL}/location/",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg if error_msg else response.text,
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


@mcp.tool(title="Add location")
async def add_location(
    session_handle: uuid.UUID, 
    name: str, 
    parent_department_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new location in the organization's location hierarchy.

    Prerequisites:
        - Must have session_handle from get_login_url tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        name (str): Name of the new location (e.g., "Warehouse A", "Lab 3")
        parent_department_id (str, optional): ID of parent location. None for root-level locations.

    Important Guidelines:
        - parent_department_id should be None when creating a root location
        - If user doesn't mention parent location, ask whether it's a root location
        - If not root, ask user to provide parent location name
          Then call get_locations to retrieve all locations and filter by name
          Always ask user to choose if multiple parent locations match

    Returns:
        Dict containing:
        - Complete information of the newly created location (id, name, parent_id, etc.)
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

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
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg if error_msg else response.text,
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


@mcp.tool(title="Get SDSs with ingredients on restricted lists")
async def get_sdss_with_ingredients_on_restricted_lists(
    session_handle: uuid.UUID, 
    keyword: str = "", 
    page: int = 1, 
    page_size: int = 10
) -> Dict[str, Any]:
    """
    Retrieve or search for hazardous SDSs containing ingredients/components on regulatory restriction lists.

    Prerequisites:
        - Must have session_handle from get_login_url tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        keyword (str, optional): Search term to filter hazardous substances. Default: "" (all hazardous)
        page (int, optional): Page number for pagination. Default: 1
        page_size (int, optional): Results per page. Default: 10

    Important Guidelines:
        - If user doesn't specify a keyword, use empty string to retrieve all hazardous SDSs
        - Display detailed information on restricted ingredients/components in results
        - Highlight which specific regulations each ingredient violates

    Returns:
        Dict containing:
        - status (str): "success" or "error"
        - data (list): List of hazardous substances with:
            - product_name, product_code, supplier_name, revision_date, location
            - components: List of restricted chemical ingredients
            - matched_regulations: List of violated regulations
        - page (int): Current page number
        - page_size (int): Results per page
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    endpoint = f"{BACKEND_URL}/substance/?hazardous=true&search={keyword}&page={page}&page_size={page_size}"
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

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
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg if error_msg else response.text,
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


@mcp.tool(title="Add SDS by uploading SDS PDF file")
async def add_sds_by_uploading_sds_pdf_file(
    session_handle: uuid.UUID, 
    department_id: str
):
    """
    Generate an upload URL for user to upload an SDS PDF file to a specific location.

    Prerequisites:
        - Must have session_handle from get_login_url tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        department_id (str): Unique identifier of the target location for the SDS

    Important Guidelines:
        - If location ID is not available, ask user to provide location name
          Then call get_locations to retrieve all locations and filter by name
          Always ask user to choose if multiple locations match
        - Provide the upload_url to user and wait for confirmation that upload is complete
        - After user confirms upload, call check_upload_sds_pdf_status with request_id 
          to monitor the extraction and processing status

    Returns:
        Dict containing:
        - status (str): "success"
        - upload_url (str): URL for user to access upload form
        - request_id (str): Unique identifier to track this upload
        - instructions (list): Step-by-step guidance for uploading

        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }
    
    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }
        
    request_id = str(uuid.uuid4())
    upload_url = f"{DOMAIN}/upload?session_id={session_handle}&department_id={department_id}&request_id={request_id}"

    return {
        "status": "success",
        "upload_url": upload_url,
        "request_id": request_id,
        "instructions": [
            "1. Click or copy the upload_url link to access the upload form",
            "2. Select your PDF file using the file input and click 'Upload SDS File' to upload",
            "3. After the file is uploaded, call check_upload_sds_pdf_status tool with request_id to check the status of the upload process"
        ]
    }
    

@mcp.tool(title="Add SDS by URL")
async def add_sds_by_url(
    session_handle: uuid.UUID, 
    url: str, 
    department_id: str
):
    """
    Adding SDS by URL to a specific location.

    Prerequisites:
        - Must have session_handle from get_login_url tool
        - The URL content must be a pdf 

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        url (str): SDS pdf URL
        department_id (str): Unique identifier of the target location for the SDS

    Important Guidelines:
        - If location ID is not available, ask user to provide location name
          Then call get_locations to retrieve all locations and filter by name
          Always ask user to choose if multiple locations match
        - After user confirms upload, call check_upload_sds_pdf_status with request_id 
          to monitor the extraction and processing status

    Returns:
        Dict containing:
        - status (str): "success" or "error"
        - data (dict): Extraction status details
        - progress (int): Completion percentage (0-100)
        - instruction (list): Next steps based on current progress

        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }
        
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    request_id = str(uuid.uuid4())
    endpoint = f"{BACKEND_URL}/location/{department_id}/uploadSDSFromUrl/"

    try:
        response = requests.post(
            endpoint, 
            headers=headers, 
            timeout=30,
            json={
                "id": request_id,
                "sds_url": url
            }, 
        )
        if response.status_code == 200:
            data = GetExtractionStatusApiResponse(**response.json())
            progress = data.progress
            return {
                "status": "success", 
                "data": data.model_dump(by_alias=True),
                "progress": progress,
                "instruction": ["call check_upload_status tool with request_id"]
            }
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg if error_msg else response.text,
                }
            except:
                return {
                    "status": "error",
                    "error": f"Failed to add location with status {response.status_code}",
                    "instruction": "Failed to upload SDS. Please verify upload URL."
                }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to service. Please try again."
        }


@mcp.tool(title="Check upload SDS file status")
async def check_upload_sds_pdf_status(session_handle: uuid.UUID, request_id: str) -> dict:
    """
    Check the processing status for an uploaded SDS PDF file.

    Prerequisites:
        - Must have session_handle from get_login_url tool
        - Must be called after add_sds_by_uploading_sds_pdf_file or add_sds_by_url tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        request_id (str): Upload request identifier from add_sds_by_uploading_sds_pdf_file

    Important Guidelines:
        - Only call this after user has uploaded file via add_sds_by_uploading_sds_pdf_file
        - If request not found, ask user to provide request_id or restart upload process
        - If progress is 100%, display completion information to user
        - If progress < 100%, show current progress and call this tool again after a brief wait

    Returns:
        Dict containing:
        - status (str): "success" or "error"
        - data (dict): Extraction status details
        - progress (int): Completion percentage (0-100)
        - instruction (list): Next steps based on current progress
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    endpoint = f"{BACKEND_URL}/binder/getExtractionStatus/?id={request_id}"

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            data = GetExtractionStatusApiResponse(**response.json())
            progress = data.progress
            return {
                "status": "success", 
                "data": data.model_dump(by_alias=True),
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


@mcp.tool(title="Upload Product List")
async def upload_product_list_excel_file(session_handle: uuid.UUID) -> Dict[str, Any]:
    """
    Generate an upload URL for user to upload a Product List Excel file for bulk SDS import.

    Prerequisites:
        - Must have session_handle from get_login_url tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool

    Important Guidelines:
        - Display the upload_url to user for accessing the upload form
        - Wait for user confirmation that they have finished uploading the Excel file
        - After user confirms upload, call validate_upload_product_list_excel_data with request_id
          to validate and map the Excel columns

    Returns:
        Dict containing:
        - status (str): "success"
        - upload_url (str): URL for user to access upload form
        - request_id (str): Unique identifier to track this upload

        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    request_id = str(uuid.uuid4())
    upload_url = f"{DOMAIN}/uploadProductList?session_id={session_handle}&request_id={request_id}"

    return {
        "status": "success",
        "upload_url": upload_url,
        "request_id": request_id,
    }


@mcp.tool(title="Validate uploaded Product List")
async def validate_upload_product_list_excel_data(
    session_handle: uuid.UUID, 
    request_id: str
) -> Dict[str, Any]:
    """
    Validate and extract column information from uploaded Product List Excel file.

    Prerequisites:
        - Must have session_handle from get_login_url tool
        - Must be called after upload_product_list_excel_file tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        request_id (str): Upload request identifier from upload_product_list_excel_file

    Important Guidelines:
        - Only call this after user has uploaded Excel file via upload_product_list_excel_file
        - If request not found, ask user to follow upload_product_list_excel_file instructions again
        - Automatically map extracted columns to required fields (product_name, supplier_of_sds, etc.)
        - If unable to auto-map, ask user to manually select matching columns
        - After mapping confirmation, call process_upload_product_list_excel_data

    Returns:
        Dict containing:
        - status (str): "success" or "error"
        - extracted_columns (list): Column names found in Excel file
        - file_path (str): Stored file location
        - request_id (str): Request identifier
        - instruction (list): Steps for column mapping and next actions
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    data_key =  redis_client.get(f"upload_product_list:{session_handle}:{request_id}")
    if not data_key:
        return {
            "status": "error",
            "error": "Not found upload session",
            "instruction": "Ask user to follow the step in upload_product_list tool"
        }

    file_name = data_key.get("file_name")
    file_path = data_key.get("file_path")
    if not file_path or not file_name:
        return {
            "status": "error",
            "error": "Error when accessing file",
            "instruction": "Ask user to follow the step in upload_product_list_excel_file tool again"
        }

    total_rows = data_key.get("total_row")
    if not total_rows:
        return {
            "status": "error",
            "error": "Not found any data from uploaded file",
            "instruction": "Ask user to verify the uploaded file and follow the step in upload_product_list_excel_file tool again"
        }

    extracted_columns = data_key.get("extracted_columns")
    if not extracted_columns:
        return {
            "status": "error",
            "error": "Unable to extract columns from uploaded file",
            "instruction": "Ask user to verify the uploaded file and follow the step in upload_product_list_excel_file tool again"
        }

    return {
        "status": "success",
        "extracted_columns": extracted_columns,
        "file_path": file_path,
        "request_id": request_id,
        "instruction": [
            "Auto map columns name in extracted_columns to a dictionary. The dictionary must have keys: product_name, supplier_of_sds. The dictionary can optionally have: location, location_id, product_code, cas_no, vendor_email, amount, amount_unit, link_to_sds, sku, external_system_id. Example: {'product_name': 'PRODUCT NAME', 'supplier_of_sds': 'SUPPLIER OF SDS', 'location': 'LOCATION', 'location_id': 'DEPARTMENT ID', 'product_code': 'PRODUCT CODE', 'cas_no': 'CAS NUMBER', 'vendor_email': 'VENDOR EMAIL', 'amount': 'AMOUNT VALUE', 'amount_unit': 'AMOUNT UNIT', 'link_to_sds': 'EXTERNAL SYSTEM URL', 'sku': 'SKU', 'external_system_id': 'EXTERNAL SYSTEM ID'}. If not found required key or exist column name not able to match, ask user to choose key that match with column name in extracted_columns.",
            "Ask user to confirm mapped data whether it is correct.",
            "If user confirmed correct, call and pass the mapped data to process_upload_product_list_excel_data tool",
        ]
    }


@mcp.tool(title="Process uploaded Product List")
async def process_upload_product_list_excel_data(
    session_handle: uuid.UUID, 
    request_id: str,
    mapped_data: dict, 
    auto_match_substance: bool,
) -> Dict[str, Any]:
    """
    Process validated Product List Excel data and import substances into inventory.

    Prerequisites:
        - Must have session_handle from get_login_url tool
        - Must be called after validate_upload_product_list_excel_data tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        request_id (str): Upload request identifier from validate step
        mapped_data (dict): Column mapping from Excel columns to system fields from validate step
        auto_match_substance (bool): Whether to automatically match products to SDSs in global database

    Important Guidelines:
        - Only call after validate_upload_product_list_excel_data has confirmed column mapping
        - If request_id or mapped_data missing, restart from upload_product_list_excel_file
        - Always ask user if they want automatic matching enabled
        - After processing, call check_upload_product_list_excel_data_status to monitor progress

    Returns:
        Dict containing:
        - status (str): "success" or "error"
        - uploaded_file_name (str): Name of processed file
        - uploaded_file_path (str): Server path to file
        - wish_list_id (str): Identifier to track import job
        - instruction (list): Next steps for monitoring progress
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    data_key =  redis_client.get(f"upload_product_list:{session_handle}:{request_id}")
    if not data_key:
        return {
            "status": "error",
            "error": "Not found upload session",
            "instruction": "Ask user to follow the step in upload_product_list tool"
        }
    
    file_name = data_key.get("file_name")
    file_path = data_key.get("file_path")
    if not file_path or not file_name:
        return {
            "status": "error",
            "error": "Error when accessing file",
            "instruction": "Ask user to follow the step in upload_product_list_excel_file tool again"
        }

    if not mapped_data:
        return {
            "status": "error",
            "error": "Not found data",
            "instruction": "Ask user to follow the step in upload_product_list_excel_file tool again"
        }

    column_mapping = {}
    for key, value in mapped_data.items():
        column_mapping[value] = key

    df = pd.read_excel(file_path)
    data_list = df.to_dict('records')
    extracted_data = []
    for data in data_list:
        extracted_row = {}
        for key, value in data.items():
            if not value or pd.isna(value):
                continue
            converted_key = key.lower()
            if converted_key in column_mapping:
                extracted_row[column_mapping[converted_key].upper()] = value
        if extracted_row:
            extracted_data.append(extracted_row)

    try:
        converted_data = json.dumps(extracted_data)
    except Exception as e:
        return {
            "status": "error",
            "error": f"Error extracting data: {str(e)}",
            "instruction": "Ask user to follow the step in upload_product_list_excel_file tool again"
        }

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    try:
        with open(file_path, "rb") as f:
            response = requests.post(
                f"{BACKEND_URL}/substance/uploadProductList/",
                headers=headers,
                data={
                    "extracted": converted_data,
                    "auto_match": str(auto_match_substance).lower(),
                },
                files={"file": (file_name, f, "application/pdf")},
                timeout=10,
            )

        if response.status_code == 200:
            os.remove(file_path)
            response_data = response.json()
            return {
                "status": "success",
                "uploaded_file_name": response_data.get("file_name"),
                "uploaded_file_path": response_data.get("file_path"),
                "wish_list_id": response_data.get("wish_list_id"),
                "instruction": [
                    "Show information for uploaded data",
                    "Call check_upload_product_list_excel_data_status with wish_list_id for checking status of the upload process"
                ]
            }
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg if error_msg else response.text,
                }
            except:
                return {
                    "status": "error",
                    "error": f"Failed to upload product list with status {response.status_code}",
                    "instruction": "Ask user to verify the uploaded file and follow the step in upload_product_list_excel_file tool again"
                }
    except Exception as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to service. Please try again."
        }


@mcp.tool(title="Check upload Product List status")
async def check_upload_product_list_excel_data_status(
    session_handle: uuid.UUID, 
    wish_list_id: str
) -> dict:
    """
    Monitor the processing status for imported Product List Excel data.

    Prerequisites:
        - Must have session_handle from get_login_url tool
        - Must be called after process_upload_product_list_excel_data tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        wish_list_id (str): Import job identifier from process_upload_product_list_excel_data

    Important Guidelines:
        - Only call after process_upload_product_list_excel_data has started import
        - If wish_list_id not found, restart from upload_product_list_excel_file
        - If progress shows completion (N/N substances processed), display final results
        - If progress incomplete, show current status and call this tool again after brief wait
        - If unmatched substances exist, suggest calling get_sds_request to list them

    Returns:
        Dict containing:
        - status (str): "success" or "error"
        - data (dict): Import progress and statistics
        - progress (str): Processing status (e.g., "45/100")
        - instruction (list): Next steps based on current status
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    endpoint = f"{BACKEND_URL}/binder/getImportProductListStatus/?id={wish_list_id}"

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            progress = data.get("progress")
            return {
                "status": "success", 
                "data": data,
                "progress": progress,
                "instruction": [
                    "Show information for current progress in data",
                    "If progress is not finished, call check_upload_product_list_excel_data_status tool with wish_list_id again.",
                    "If there are unmatched substances, suggest user to list them by calling get_sds_request tool with wish_list_id from data."
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
    
    
@mcp.tool(title="Get list of SDS Requests (Unmatched Substances)")
async def get_sds_request(
    session_handle: uuid.UUID, 
    search: str = "", 
    wish_list_id: str = "",
    page: int = 1, 
    page_size: int = 10
):
    """
    Retrieve SDS requests that have not been matched to any SDS in the global database.
    Synonyms: Unmatched SDSs, unmatched substances, SDS requests, substance requests.

    Prerequisites:
        - Must have session_handle from get_login_url tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        search (str, optional): Search term to filter requests. Default: "" (all requests)
        wish_list_id (str, optional): Filter by specific import job ID. Default: "" (all jobs)
        page (int, optional): Page number for pagination. Default: 1
        page_size (int, optional): Results per page. Default: 10

    Important Guidelines:
        - If user wants to match substances, call search_sds_from_sds_managers_database with keyword:
          "supplier_name + product_name" from the request
        - Display product_name, supplier_name, and other request details clearly
        - Guide user through match_sds_request tool to link found SDSs

    Returns:
        Dict containing:
        - status (str): "success" or "error"
        - results (list): List of unmatched substance requests
        - count (int): Total number of requests
        - next_page (int|None): Next page number if available
        - previous_page (int|None): Previous page number if available
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }
        
    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }
    
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    endpoint = f"{BACKEND_URL}/substance/sdsRequests?page={page}&page_size={page_size}"

    if search:
        endpoint += f"&search={search}"

    if wish_list_id:
        endpoint += f"&wish_list_id={wish_list_id}"

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            try:
                res = SdsRequestResponse(**data)
                return {
                    "status": "success",
                    "results": [item.model_dump(by_alias=True) for item in res.results],
                    "count": res.count,
                    "next_page": int(page) + 1 if res.next else None,
                    "previous_page": int(page) - 1 if res.previous else None,
                }
            except ValueError as e:
                return {
                    "status": "success",
                    "results": data.get("results", []),
                    "count": data.get("count", 0),
                    "next_page": int(page) + 1 if data.get("next") else None,
                    "previous_page": int(page) - 1 if data.get("previous") else None,
                }
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg,
                }
            except:  # noqa: E722
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


@mcp.tool(title="Match substance request to a SDS")
async def match_sds_request(
    session_handle: uuid.UUID, 
    substance_request_id: str, 
    sds_id: str, 
    use_sds_data: bool
) -> Dict[str, Any]:
    """
    Link a SDS request (unmatched product) to an SDS from the SDS Managers 16 millions SDS global database.
    Synonyms: Match unmatched SDS, link substance request.

    Prerequisites:
        - Must have session_handle from get_login_url tool

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        substance_request_id (str): ID of the unmatched substance request
        sds_id (str): ID of the SDS to match from global database
        use_sds_data (bool): Whether to use SDS data or keep original request data

    Important Guidelines:
        - If substance_request_id is not available, ask user to provide SDS/substance name
          Then call get_sds_request with the name as search keyword
          Always ask user to choose if multiple results are found
        - If sds_id is not available, ask user to provide SDS/substance name
          Then call search_sds_from_sds_managers_database with the name as keyword
          Always ask user to choose if multiple results are found
        - Show comparison of product name and supplier between request and SDS
        - Ask user whether to use SDS data (more accurate) or keep request data

    Returns:
        Dict containing:
        - Information of the successfully matched substance now in customer's inventory
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    endpoint = f"{BACKEND_URL}/substance/{substance_request_id}/matchSdsRequest/"
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json={
                "sds_id": sds_id,
                "use_sds_data": use_sds_data
            },
            timeout=10
        )

        if response.status_code == 200:
            return response.json()
        else:
            try:
                error_msg = response.json().get("error_message", None)
                return {
                    "status": "error",
                    "error": error_msg if error_msg else response.text,
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


@mcp.tool(title="Update SDS data")
async def edit_sds_data(
    session_handle: uuid.UUID,
    substance_id: str,
    sds_pdf_product_name: Optional[str] = None,
    chemical_name_synonyms: Optional[str] = None,
    external_system_id: Optional[str] = None,
) -> dict:
    """
    Edit editable fields of an SDS (Safety Data Sheet) in the customer's inventory.

    Prerequisites:
        - Must have session_handle from get_login_url tool
        - substance_id should be obtained via search_customer_sds_library
        - If user provides substance_id directly, validate first using show_customer_sds_detail

    Parameters:
        session_handle (UUID): Session UUID from get_login_url tool
        substance_id (str): Unique ID of substance in customer's inventory
        sds_pdf_product_name (str, optional): Product name override/custom name
        chemical_name_synonyms (str, optional): Alternative names/synonyms for the chemical
        external_system_id (str, optional): External reference/integration identifier

    Update Rules:
        - To add or change a field: Provide the new value
        - To remove a field: Set value to empty string ""
        - At least one field must be provided for update
        - Example: sds_pdf_product_name="" will clear the custom product name

    Supported Actions:
        - Add/change/remove custom product name
        - Add/change/remove chemical synonyms
        - Add/change/remove external system ID

    Returns:
        Dict containing:
        - status (str): "success" or "error"
        - message (str): Success confirmation
        - instruction (str): Guidance to verify update via show_customer_sds_detail
        - next_action (dict): Details for verification step
        
        On error:
        - status (str): "error"
        - error (str): Error message
        - instruction (str): User-friendly guidance
    """

    if not session_handle:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }
        
    info = redis_client.get(f"sds_mcp:{session_handle}")
    if not info:
        return {
            "status": "not_initialized",
            "error": "No active session found",
            "instruction": "No session found. Please use the get_login_url tool to authenticate."
        }

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    endpoint = f"{BACKEND_URL}/substance/{substance_id}/updateSDS/"

    is_valid = (
        sds_pdf_product_name is not None or
        chemical_name_synonyms is not None or
        external_system_id is not None
    )
    if not is_valid:
        return {
            "status": "error",
            "error": "At least one field must be provided",
            "instruction": "Please provide at least one field to update."
        }
    data = {}
    try:

        if sds_pdf_product_name is not None:
            data["sds_pdf_product_name"] = sds_pdf_product_name
        if chemical_name_synonyms is not None:
            data["chemical_name_synonyms"] = chemical_name_synonyms
        if external_system_id is not None:
            data["external_system_id"] = external_system_id

        response = requests.patch(
            endpoint,
            headers=headers,
            timeout=30,
            json=data
        )
        if response.status_code == 200:
            return {
                "status": "success",
                "message": "SDS updated successfully",
                "instruction": (
                    "Immediately call tool `retrieve_substance_detail` with the same "
                    f"`session_handle={session_handle}` and `substance_id={substance_id}` to verify the update. "
                    "Compare the returned record against the submitted payload to confirm: "
                    "• `sds_pdf_product_name` matches the new value (and is removed if empty string was sent). "
                    "• `chemical_name_synonyms` matches the new value (and is removed if empty string was sent). "
                    "• `external_system_id` matches the new value (and is removed if empty string was sent). "
                    "If the values match, tell the user: 'Update verified in customer library.' "
                    "If any mismatch is found, report which fields differ and suggest retrying the edit."
                ),
                "next_action": {
                    "tool": "retrieve_substance_detail",
                    "args": {
                        "session_handle": session_handle,
                        "substance_id": substance_id,
                    },
                    "verify_fields": [
                        "sds_pdf_product_name",
                        "chemical_name_synonyms",
                        "external_system_id",
                    ],
                    "on_success_message": "Update verified in customer library.",
                    "on_mismatch_message": "Update applied but could not be fully verified. The following fields differ:",
                },
            }
        else:
            return {
                "status": "error",
                "error": f"Failed to update SDS with status {response.status_code}",
                "instruction": "Failed to update SDS. Please try again."
            }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "error": f"Connection error: {str(e)}",
            "instruction": "Failed to connect to update service. Please try again."
        }
