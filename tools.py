from mcp.server.fastmcp import FastMCP
from cache import redis_client
from typing import Dict, Any, List, Optional, Literal
import logging
import requests
import uuid
import pandas as pd
import json
import os

from config import BACKEND_URL, SDS_HEADER_NAME, DOMAIN
from constants import (
    LONG_DESCRIPTION,
    SYNONYMS,
    AUTHORIZED_PREREQUISITES,
    PRODUCT_ID_REQUIRED_GUIDELINES,
    PRODUCT_NAME_TO_PRODUCT_ID_GUIDELINES,
    LOCATION_ID_REQUIRED_GUIDELINES,
    LOCATION_NAME_TO_LOCATION_ID_GUIDELINES,
    SESSION_HANDLE_PARAM_DESCRIPTION,
    SDS_ID_REQUIRED_GUIDELINES,
    SDS_NAME_TO_SDS_ID_GUIDELINES,
    UPLOAD_SDS_PDF_STEP_INSTRUCTIONS,
    UPLOAD_PRODUCT_LIST_EXCEL_FILE_INSTRUCTIONS,
    DRY_RUN_PARAM_DESCRIPTION,
    GENERAL_PERMISSION_MAPPING,
    LOCATION_PERMISSION_MAPPING,
    DEFAULT_RETURN_TEMPLATE,
    PRODUCT_RECOMMEND_INSTRUCTION,
    LOCATION_RECOMMEND_INSTRUCTION,
    PAGINATION_PARAM_DESCRIPTION,
    PRODUCT_LIST_ID_REQUIRED_GUIDELINES,
    PRODUCT_LIST_NAME_TO_PRODUCT_LIST_ID_GUIDELINES,
)
from models import (
    SubstanceDetail,
    SubstanceListApiResponse,
    GetExtractionStatusApiResponse,
    SearchGlobalDatabaseResponse,
    SdsRequestResponse,
    LimitsResponse,
    StatisticsResponse,
    GetImportProductListResponse,
    GetProductListSummaryResponse,
    ActivityLogResponse,
)
from utils import (
    handle_api_error, 
    validate_session, 
    reset_upload_session,
    connection_error_response,
    server_error_response,
)


logger = logging.getLogger(__name__)

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
async def get_login_url(session_handle: Optional[uuid.UUID]) -> Dict[str, Any]:
    f"""
    To login to SDS Manager, you need to get session ID and login URL first.
    This tool initialize session ID (If not provided) & generate an login URL for user to login with their API key.

    When to call:
        - User are not logged in
        - User ask for new login session
        - User want to change to different API key

    When not to call:
        - User has already logged in (Have session_handle from any previous tool)

    Usage example (One-line):
        - I need to login to SDS Manager
        - I want to change to different API key
        - How can I access to SDS Manager

    Parameters:
        - session_handle (Optional[UUID]): Session UUID from the previous tool. None for new session.

    Prerequisites:
        - Must call get_mcp_overview tool at the beginning of the conversation

    Important Guidelines:
        - After user confirm finished login, pass session_handle for all other tools

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    login_instruction = [
        "1. Click or copy the login_url link to access the login form",
        "2. Type your API key in the input field and click 'Login' to login",
        "3. After user confirm finished login, call check_auth_status with session_handle"
    ]

    if session_handle:
        info = redis_client.get(f"sds_mcp:{session_handle}")
        if info:
            if info.get("logged_in"):
                return {
                    "status": "success",
                    "code": "SESSION_REUSED",
                    "data": {
                        "session_handle": session_handle,
                        "message": "Session reused. You are already logged in.",
                    },
                    "instruction": [
                        "Show message to user and call check_auth_status with session_handle"
                    ],
                    "trace_id": session_handle,
                }
            else:
                return {
                    "status": "success",
                    "code": "SESSION_REUSED",
                    "data": {
                        "session_handle": session_handle,
                        "message": "Login URL re-generated! Please login with your API key.",
                        "login_url": f"{DOMAIN}/login?session_id={session_handle}",
                    },
                    "instruction": login_instruction,
                    "trace_id": session_handle,
                }

    new_session_handle = str(uuid.uuid4())
    redis_client.set(f"sds_mcp:{new_session_handle}", {
        "logged_in": False,
        "login_error": False,
    })
    return {
        "status": "success",
        "code": "SESSION_CREATED",
        "data": {
            "session_handle": new_session_handle,
            "message": "Login URL generated! Please login with your API key.",
            "login_url": f"{DOMAIN}/login?session_id={new_session_handle}",
        },
        "instruction": login_instruction,
        "trace_id": new_session_handle,
    }


@mcp.tool()
async def check_auth_status(session_handle: uuid.UUID) -> Dict[str, Any]:
    f"""
    Check if the current session is authenticated.

    When to call:
        - User has already logged in (Have session_handle from any previous tool)
        - User ask for their authentication status

    When not to call:
        - User are not logged in (Not have session_handle from any previous tool)

    Usage example (One-line):
        - Am I logged in?
        - Are you logged in?
        - What is my status on SDS Manager?
        - Can I use SDS Manager now?

    Parameters:
        - session_handle (Optional[UUID]): Session UUID from the previous tool.

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    if info.get("logged_in"):
        return {
            "status": "success",
            "code": "OK",
            "data": {
                "session_handle": session_handle,
                "user": {
                    "id": info.get("id"),
                    "email": info.get("email"),
                    "name": info.get("first_name", "") + " " + info.get("last_name", ""),
                    "language": info.get("language"),
                    "country": info.get("country"),
                    "phone_number": info.get("phone_number"),
                    "customer": info.get("customer"),
                }
            },
            "instruction": [
                "Authorization successful. Show welcome message and user information to the user",
                "Call tool get_permissions, get_limits to show, then call tool get_setup_onboarding_flow to guide user with onboarding checklist",
                "Ask user to choose where to start setup from the checklist",
            ],
            "trace_id": session_handle,
        }

    if info.get("login_error"):
        return {
            "status": "error",
            "code": "AUTHORIZATION_ERROR",
            "data": {
                "error_message": info.get("error_message"),
            },
            "instruction": [
                "Authorization error. Please login again using get_login_url tool with new session ID."
            ],
            "trace_id": session_handle,
        }

    return {
        "status": "error",
        "code": "NOT_AUTHENTICATED",
        "instruction": [
            "Not authenticated. Please use the get_login_url tool with new session ID to create a new session."
        ],
        "trace_id": session_handle,
    }


@mcp.tool()
async def get_permissions(
    session_handle: uuid.UUID, 
    location_id: Optional[str] = None,
) -> Dict[str, Any]:
    f"""
    Get permissions for the current user session generally or for a specific location.

    When to call:
        - After successfully logged in on check_auth_status tool
        - User ask for permissions
        - User ask for permissions for a specific location

    Usage example (One-line):
        - What can I do on SDS Manager?
        - What can I do on SDS Manager for a specific location?
        - Am I allowed to do <action> on SDS Manager?

    Note: General permission is different from location permission.

    - General permission: access_mcp_chat_agent, add_locations, import_product_list
    - Location permission: add_substance, allowed_to_archive_SDS, move_sds, edit_sds

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - location_id (str, optional): ID of the location to get permissions for. Default: None

    Important Guidelines:
        {LOCATION_NAME_TO_LOCATION_ID_GUIDELINES}

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    endpoint = f"{BACKEND_URL}/user/permissions/"
    if location_id:
        endpoint = f"{BACKEND_URL}/location/{location_id}/permissions/"

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return {
                "status": "success",
                "code": "OK",
                "data": {
                    "session_handle": session_handle,
                    "permissions": {
                        permission_key: (
                            GENERAL_PERMISSION_MAPPING[permission_key]
                            if not location_id else
                            LOCATION_PERMISSION_MAPPING[permission_key]
                        )
                        for permission_key in data
                    }
                },
                "instruction": [
                    "Show permissions to the user",
                    "Recommend some next actions based on the permissions"
                ],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool()
async def get_limits(session_handle: uuid.UUID) -> Dict[str, Any]:
    f"""
    Get total and used limits for the current user session.
    If not provided, the tool can be used unlimitedly.

    When to call:
        - After successfully logged in on check_auth_status tool
        - Tool search_sds got error with error code SUBSCRIPTION_CHAT_AGENT_SEARCH_LIMIT_EXCEEDED
        - Tool show_sds_detail got error with error code SUBSCRIPTION_CHAT_AGENT_GET_SDS_LIMIT_EXCEEDED
        - User ask for search limitations

    Usage example (One-line):
        - Why I got limitation error when searching SDSs?
        - Why I got limitation error when showing SDS details?
        - How many searches I can do?
        - How many SDS details I can show?
        - Show me all limits/threshold for my session

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    endpoint = f"{BACKEND_URL}/user/limits/"
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            res = LimitsResponse(**data)
            return {
                "status": "success",
                "code": "OK",
                "data": {
                    "session_handle": session_handle,
                    **res.model_dump(by_alias=True),
                },
                "instruction": [
                    "Show limits to the user",
                    "Recommend user to contact organization administrator if they are out of limits",
                    "Recommend search_sds tool for user to search if they still not reach the limits"
                ],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Get setup onboarding checklist")
async def get_setup_onboarding_flow(session_handle: uuid.UUID) -> Dict[str, Any]:
    f"""
    Suggest user the best onboarding flow in checklist format.

    When to call:
        - User ask for onboarding flow
        - User ask for what to do on SDS Manager

    Usage example (One-line):
        - Help me setup
        - What should I do next?
        - What can I do on SDS Manager?
        - Show me what can SDS Manager do?

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    endpoint = f"{BACKEND_URL}/user/statistics/"
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            res = StatisticsResponse(**data)
            statistics = res.model_dump()

            checklist = [
                {
                    "step_id": "location_setup",
                    "title": "Setup location hierarchy",
                },
                {
                    "step_id": "sds_file_setup",
                    "title": "Setup SDS files in library",
                },
                {
                    "step_id": "sds_manager_expert_setup",
                    "title": "Request SDS Manager expert to setup SDS library",
                },
            ]
            if statistics.get("products_count") > 1:
                checklist.append({
                    "step_id": "products_management",
                    "title": "Manage products/chemicals", 
                })

            return {
                "status": "success",
                "code": "OK",
                "data": {
                    "session_handle": session_handle,
                    "statistics": statistics,
                    "checklist": checklist,
                },
                "instruction": [
                    "Inform current statistics for SDS storage of user library",
                    "Display checklist for user to choose where to start setup",
                    "After user choose step, call tool get_setup_onboarding_step to get step instructions",
                ],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Get setup onboarding step from checklist")
async def get_setup_onboarding_step(session_handle: uuid.UUID, step_id: str) -> Dict[str, Any]:
    f"""
    Get setup onboarding step from checklist.

    When to call:
        - User ask for specific step in onboarding checklist

    When not to call:
        - User ask for step that is not in onboarding checklist (Call tool get_setup_onboarding_flow to get onboarding checklist first)

    Usage example (One-line):
        - Help me with step <step>?
        - Show me step <step> in onboarding checklist
        - How to setup location hierarchy?
        - How to import SDS files?
        - How to setup SDS files in library?
        - How to manage products/chemicals?
        - How to manage SDS requests?

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - step_id (str): Step id in onboarding checklist

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    if step_id == "location_setup":
        return {
            "status": "success",
            "code": "OK",
            "instruction": [
                "Ask user whether they have multiple locations or sites",
                "If user have single location, finish this step",
                "If user have multiple locations, call tool get_locations to show their current locations tree/hierarchy and recommend to create new location with add_location tool",
            ],
            "trace_id": session_handle,
        }
    elif step_id == "sds_file_setup":
        return {
            "status": "success",
            "code": "OK",
            "instruction": [
                "Ask if user want SDS Manager expert to setup their SDS library for them by using request_expert_setup tool",
                "If no, continue to ask user approximately how many products/chemicals they use that require SDSs",
                "If user have huge number of products/chemicals, recommend user to import product list from Excel file using upload_product_list_excel_file tool",
                "If user have small number of products/chemicals, recommend user to manually setup with search_sds, add_sds tool.",
                "If user can not find the SDS they want from search_sds, ask user whether they have SDS files in their local computer or online sources",
                "If user have SDS files, recommend user to upload SDS files from their local computer or online sources using add_sds_by_uploading_sds_pdf_file, add_sds_by_url tool",
                
            ],
            "trace_id": session_handle,
        }
    elif step_id == "products_management":
        return {
            "status": "success",
            "code": "OK",
            "instruction": [
                "Call tool get_customer_products to show user's products/chemicals",
                "Recommend user to manage products/chemicals with these actions: get_hazardous_sds_on_restricted_lists, show_customer_product_detail, move_sds, copy_sds_to_another_location, archive_sds, edit_product_data tools",
                "Call tool get_sds_request to show user's SDS requests",
                "If have request, recommend user to manage SDS requests with these actions: search_sds, match_sds_request tools to find and link SDSs to products/chemicals",
            ],
        }
    elif step_id == "sds_manager_expert_setup":
        return {
            "status": "success",
            "code": "OK",
            "instruction": [
                "Ask user for the link to their online SDS library if they have one, and any notes they want to share with the SDS Manager team.",
                "Call tool request_expert_setup to request SDS Manager expert to setup SDS library for them",
                "Finish all steps in onboarding checklist from get_setup_onboarding_flow tool",
            ],
        }

    return {
        "status": "error",
        "code": "STEP_NOT_FOUND",
        "instruction": [
            "Step not found. Call tool get_setup_onboarding_flow to get onboarding checklist with valid step ids",
        ],
        "trace_id": session_handle,
    }


@mcp.tool(title="Request expert setup SDS library for user")
async def request_expert_setup(
    session_handle: uuid.UUID,
    sds_library_link: Optional[str] = None,
    additional_notes: Optional[str] = None,
) -> Dict[str, Any]:
    f"""
    Request expert setup SDS library for user.

    When to call:
        - User wants to request SDS Manager expert to setup their SDS library.

    Usage example (One-line):
        - Can you help me setup SDS library for my organization?
        - I need help to setup SDS library for my organization.
        - I want to request SDS Manager expert to setup their SDS library.

    Example Workflow:
        1. User type "Can you help me setup SDS library for my organization?"
        2. Agent response "Yes, please give me the link to your online SDS library if you have one, and any notes you want to share with the SDS Manager team.".
        3. User provides contact email, phone number, link to their SDS library, and notes.
        4. Agent calls this tool with those information.

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - sds_library_link (str, optional): The link to the user's online SDS library (Ask if they want to provide).
        - additional_notes (str, optional): The notes from the user requesting expert setup (Ask if they want to provide).

    Important Guidelines:
        - Initially, ask user for the link to online SDS library if they have one, and any notes they want to share with the SDS Manager team.

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    endpoint = f"{BACKEND_URL}/user/requestSetup/"
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

    try:
        response = requests.post(endpoint, headers=headers, json={
            "sds_library_link": sds_library_link,
            "additional_notes": additional_notes,
        }, timeout=30)
        if response.status_code == 200:
            return {
                "status": "success",
                "code": "OK",
                "data": {
                    "session_handle": session_handle,
                    **response.json(),
                },
                "instruction": [
                    "Thank user for requesting expert setup",
                    "Introduce some next actions: search_sds, add_sds_by_uploading_sds_pdf_file, upload_product_list_excel_file, add_sds, get_customer_products, get_locations",
                ],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Get activity logs")
async def get_activity_logs(
    session_handle: uuid.UUID,
    location_id: Optional[str] = None,
    product_id: Optional[str] = None,
    page: int = 1, 
    page_size: int = 10,
) -> Dict[str, Any]:
    f"""
    Get the activity logs for the current user session generally or for a specific location or product.

    When to call:
        - User ask to get the activity logs for the current user session generally or for a specific location or product.
        - Automatically when previous tool requires it.

    Usage example (One-line):
        - Display my account activity history.
        - Show me all logs.
        - List me all my previous activities.
        - What happen on location <location name>?
        - History of product <product name>?

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        {PAGINATION_PARAM_DESCRIPTION}
        - location_id (str, optional): ID of the location to get activity logs for. Default: None
        - product_id (str, optional): ID of the product to get activity logs for. Default: None

    Important Guidelines:
        {LOCATION_NAME_TO_LOCATION_ID_GUIDELINES}
        {PRODUCT_NAME_TO_PRODUCT_ID_GUIDELINES}
        - This tools can only get 1 type of activity logs at a time (account_logs or product_logs or location_logs).
        - If user ask for all 3, should call this tool 3 times with different parameters.
        
    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    instruction = [
        "Display logs (account_logs or product_logs or location_logs) to the user",
    ]

    try:
        search_param = f"?page={page}&page_size={page_size}"
        log_type = "account_logs"
        if location_id:
            log_type = "location_logs"
            api_url = f"{BACKEND_URL}/location/{location_id}/activityLogs/{search_param}"
            instruction.append("Recommend with next actions: get_locations, add_sds, add_sds_by_uploading_sds_pdf_file, add_sds_by_url")
        elif product_id:
            log_type = "product_logs"
            api_url = f"{BACKEND_URL}/substance/{product_id}/activityLogs/{search_param}"
            instruction.append("Recommend with next actions: show_customer_product_detail, add_sds, move_sds, copy_sds_to_another_location, archive_sds")
        else:
            api_url = f"{BACKEND_URL}/user/activityLogs/{search_param}"
            instruction.append("Recommend with next actions: get_locations, get_customer_products, add_sds, add_sds_by_uploading_sds_pdf_file, add_sds_by_url")
        
        response = requests.get(
            api_url,
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            try:
                res = ActivityLogResponse(**data)
                return {
                    "status": "success",
                    "code": "OK",
                    "data": {
                        "session_handle": session_handle,
                        "log_type": log_type,
                        "results": [
                            item.model_dump(by_alias=True) 
                            for item in res.results
                        ],
                        "count": data.get("count", 0),
                    },
                    "instruction": instruction,
                    "trace_id": session_handle,
                }
            except ValueError as e:
                return {
                    "status": "success",
                    "code": "OK",
                    "data": {
                        "session_handle": session_handle,
                        "log_type": log_type,
                        "results": data.get("results", []),
                        "count": data.get("count", 0),
                    },
                    "instruction": instruction,
                    "trace_id": session_handle,
                }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Search SDSs from SDS Managers 16 millions global SDS database")
async def search_sds(
    session_handle: uuid.UUID,
    keyword: str, 
    scope: Literal["all", "in_used"] = "all",
    page: int = 1, 
    page_size: int = 10, 
    language_code: Optional[str] = None,
    region_code: Optional[str] = None,
    location_id: Optional[str] = None,
) -> Dict[str, Any]:
    f"""
    Search for Safety Data Sheets (SDS) in the SDS Managers 16 millions global SDS database.

    When to call:
        - User ask to search SDSs in the global database
        - Automatically called when previous tool need sds_id but user provide SDS name.

    When not to call:
        - User want to search SDSs in their own library/inventory (Call tool get_customer_products instead)
        - Search usage reach limits in get_limits tool (Call tool get_limits to check limits)

    Usage example (One-line):
        - Find SDS <SDS name>
        - Do you have SDS <SDS name>?
        - Search SDS <SDS name> in the global database
        - Find SDS <SDS name> of <manufacturer name>
        - Find SDS <SDS name> in <language> and <region>

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}
    - If scope is all, check limits with get_limits tool before calling this tool and display the limits to the user

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        {PAGINATION_PARAM_DESCRIPTION}
        - scope (Literal["all", "in_used"]): Search scope (all, in_used)
        - keyword (str): Search term (product name, manufacturer, etc.)
        - language_code (str, optional): Language filter (e.g., "en", "es")
        - region_code (str, optional): Region filter (e.g., "US", "EU")
        - location_id (str, optional): Location ID to filter results for in_used scope. Default: None

    Important Guidelines:
        - Auto set scope according to the user's request.
        - Display results in a table with columns: ID, Product Name, Product Code, 
          Manufacturer Name, Revision Date, Language, Regulation Area, Public Link, Discovery Link
        - Auto-convert language/region names to codes (e.g., "English" → "en", "Europe" → "eu")
        - Do not use IDs as search keywords
        - location_id is only available for in_used scope
        {LOCATION_NAME_TO_LOCATION_ID_GUIDELINES}

    Returns:
        {DEFAULT_RETURN_TEMPLATE}

    Decision workflow for scope:
        - If user says "search my library" -> scope=in_used
        - If user says "search in location <location name>" -> scope=in_used
        - If user says "search global database" -> scope=all
        - Otherwise -> scope=all
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    try:
        search_param = f"?search={keyword}&page={page}&page_size={page_size}"
        if language_code:
            search_param += f"&language_code={language_code}"
        if region_code:
            search_param += f"&region={region_code.upper()}"
        if scope == "in_used":
            search_param += f"&scope=in_used"
            if location_id:
                search_param += f"&department_id={location_id}"

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
                "code": "OK",
                "data": {
                    "session_handle": session_handle,
                    "results": [
                        substance.model_dump(by_alias=True) 
                        for substance in res.results
                    ],
                    "count": res.count,
                    "next_page": int(page) + 1 if res.next else None,
                    "previous_page": int(page) - 1 if res.previous else None,
                    "page": page,
                    "page_size": page_size,
                },
                "instruction": [
                    "Display results in table",
                    "Suggest user to do external web search using find_sds_pdf_links_from_external_web tool if not found the SDS they want",
                    "If user find the SDS they want, recommend user these next actions: show_sds_detail, add_sds, match_sds_request (If user want to match the SDS to a SDS request)"
                ],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Show SDS details")
async def show_sds_detail(session_handle: uuid.UUID, sds_id: str) -> Dict[str, Any]:
    f"""
    Retrieve detailed information for a specific SDS from the global database.

    When to call:
        - User ask to show details of a public SDS from global database.
        - Automatically called when previous tool need information of a specific SDS

    When not to call:
        - User want to show detail of a product in their own library/inventory instead of SDS details (Call tool show_customer_product_detail instead)
        - Show SDS details usage reach limits in get_limits tool (Call tool get_limits to check limits)
        - When can not define the sds_id from chat context (Ask user to provide).

    Usage example (One-line):
        - Show me details/information of the SDS <SDS name>

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}
    - Check limits with get_limits tool before calling this tool and display the limits to the user

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - sds_id (str): Unique identifier of the SDS to retrieve

    Important Guidelines:
        {SDS_ID_REQUIRED_GUIDELINES}
        {SDS_NAME_TO_SDS_ID_GUIDELINES}
        - Display any error messages to the user

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    endpoint = f"{BACKEND_URL}/pdfs/{sds_id}/"
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            return {
                "status": "success",
                "code": "OK",
                "data": response.json(),
                "instruction": [
                    "Recommend user these next actions: add_sds, match_sds_request (If user want to match the SDS to a SDS request), search_sds (If user want to search for another SDS)"
                ],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Find SDS pdf links from external web")
async def find_sds_pdf_links_from_external_web(
    session_handle: uuid.UUID,
    links: List[str],
) -> Dict[str, Any]:
    f"""
    You will become an excellent SDS search engine expert, especially for hunting SDS direct pdf links. This tool is an endpoint for receiving web search result of SDS or MSDS pdf links from the you.

    When to call:
        - User ask directly to find SDS pdf links from web/Google source instead.
        - Automatically called when no results found from global database after calling tool search_sds

    When not to call:
        - User just want to search SDS (Prior to call tool search_sds first)

    Usage example (One-line):
        - Find for me SDS pdf links for <keyword> from web/Google.

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - links (List[str]): The list of SDS PDF links found by you during your web search.

    Important Guidelines:
        - Search google with query "Safety data sheet <keyword>" that use advanced search for filetype:pdf and give user the top 10 links you found.
        - Prioritize newest version of the SDS/MSDS PDF.
        - Search from all alternative sources in all languages, all regions, all regulations.
        - Ensure the links is a valid pdf when passing to links parameter.

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
        - found_links (list): List of found SDS PDF links

    Example Workflow:
        1. User: "Find SDS for NANO ACID CLEANER by ERRECOM SPA"
        2. Agent searches web for SDS/MSDS PDFs.
        3. Agent calls this tool with:
           find_sds_pdf_links_from_external_web(session_handle, [
               "https://shop.errecom.com/wp-content/uploads/.../MSDS.U.NANO-ACID-CLEANER.EN_05-08-2021.pdf"
           ])
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    return {
        "status": "success",
        "code": "OK",
        "found_links": links,
        "instruction": [
            "Ask user if they want to add the SDS pdf link to customer's inventory by calling add_sds_by_url tool (If multiple links are found, ask user to choose)"
        ],
        "trace_id": session_handle,
    }


@mcp.tool(title="Get customer products")
async def get_customer_products(
    session_handle: uuid.UUID, 
    keyword: Optional[str] = None, 
    page: int = 1, 
    page_size: int = 10,
    language_code: Optional[str] = None,
    region_code: Optional[str] = None,
    location_id: Optional[str] = None,
) -> Dict[str, Any]:
    f"""
    Get all products (SDSs assigned to locations) in the customer's library/inventory.

    When to call:
        - User ask to search products in their own library/inventory
        - Automatically called when previous tool need product_id but user provide product name only.

    When not to call:
        - User ask for hazardous products/SDSs (Call tool get_hazardous_sds_on_restricted_lists instead).
        - User ask to find SDS without mentioning specific scope (Prior to call tool search_sds first)
        - User ask to find SDS from global database instead.

    Usage example (One-line):
        - Find me the SDS <SDS name> in my library/inventory
        - List me all products/SDSs in location <location name>
        - Do I have this SDS in my library/inventory?
        - Show me all SDSs in my library/inventory
        - What products do I have in my library/inventory?
        - How many products do I have in my library/inventory?

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        {PAGINATION_PARAM_DESCRIPTION}
        - keyword (str): Search term for filtering products (product name, manufacturer name, barcode, ufi, cas, product code, etc.)
        - language_code (str, optional): Language filter (e.g., "en", "es")
        - region_code (str, optional): Region filter (e.g., "US", "EU")
        - location_id (str, optional): Location ID to filter results. Default: None

    Important Guidelines:
        - Do not use ID as search keywords
        {LOCATION_NAME_TO_LOCATION_ID_GUIDELINES}

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    recommend_instruction = [
        "show results to the user",
        "If no results are found, recommend user to search_sds tool for finding SDS on global database",
        "If have results, recommend user these next actions: show_customer_product_detail, move_sds, copy_sds, archive_sds"
    ]

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

    try:
        search_param = f"?page={page}&page_size={page_size}"
        if keyword:
            search_param += f"&search={keyword}"
        if language_code:
            search_param += f"&language_code={language_code}"
        if region_code:
            search_param += f"&region={region_code.upper()}"
        if location_id:
            search_param += f"&department_id={location_id}"

        response = requests.get(
            f"{BACKEND_URL}/substance/{search_param}",
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            try:
                res = SubstanceListApiResponse(**data)
                return {
                    "status": "success",
                    "code": "OK",
                    "data": {
                        "session_handle": session_handle,
                        "results": [
                            substance.model_dump(by_alias=True) 
                            for substance in res.results
                        ],
                        "count": res.count,
                        "next_page": int(page) + 1 if res.next else None,
                        "previous_page": int(page) - 1 if res.previous else None,
                    },
                    "instruction": recommend_instruction,
                    "trace_id": session_handle,
                }
            except ValueError as e:
                return {
                    "status": "success",
                    "code": "OK",
                    "data": {
                        "session_handle": session_handle,
                        "results": data.get("results", []),
                        "count": data.get("count", 0),
                        "next_page": int(page) + 1 if data.get("next") else None,
                        "previous_page": int(page) - 1 if data.get("previous") else None,
                    },
                    "instruction": recommend_instruction,
                    "trace_id": session_handle,
                }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Show customer product detail")
async def show_customer_product_detail(
    session_handle: uuid.UUID, 
    product_id: str
) -> Dict[str, Any]:
    f"""
    Retrieve detailed information for a specific product (SDS assigned to a location) in the customer's inventory.

    When to call:
        - User ask to show details of a product in their own library/inventory
        - Automatically called when previous tool need information for a specific product..

    When not to call:
        - User ask to show details of a public SDS from global database instead.
        - When can not define the product_id from chat context (Ask user to provide).

    Usage example (One-line):
        - Show me details/information of the product
    
    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - product_id (str): Unique identifier of the product in customer's inventory

    Important Guidelines:
        {PRODUCT_ID_REQUIRED_GUIDELINES}
        {PRODUCT_NAME_TO_PRODUCT_ID_GUIDELINES}
        - Display any error messages to the user

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    recommend_instruction = [
        "show information to the user",
        PRODUCT_RECOMMEND_INSTRUCTION,
    ]

    endpoint = f"{BACKEND_URL}/substance/{product_id}/"
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            try:
                substance_dto = SubstanceDetail(**data)
                return {
                    "status": "success",
                    "code": "OK",
                    "data": {
                        "session_handle": session_handle,
                        **substance_dto.model_dump(by_alias=True),
                    },
                    "instruction": recommend_instruction,
                    "trace_id": session_handle,
                }
            except ValueError as e:
                # Fallback to raw data if DTO creation fails
                return {
                    "status": "success",
                    "code": "OK",
                    "data": {
                        "session_handle": session_handle,
                        **data,
                    },
                    "instruction": recommend_instruction,
                    "trace_id": session_handle,
                }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Add SDS")
async def add_sds(
    session_handle: uuid.UUID, 
    sds_id: str, 
    location_id: str,
    default_run: bool = True,
) -> Dict[str, Any]:
    f"""
    Add an SDS from the global database to a specific location in the customer's inventory.

    When to call:
        - User ask to add a SDS from global database to a specific location in their own library/inventory

    When not to call:
        - When can not define the global sds_id from chat context (Ask user to provide).
        - When can not define the location_id from chat context (Ask user to provide or create new).

    Usage example (One-line):
        - Add SDS <SDS name> to location/department/workplace <location name>

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - sds_id (str): Unique identifier of the SDS from global database
        - location_id (str): Unique identifier of the target location
        {DRY_RUN_PARAM_DESCRIPTION}

    Important Guidelines:
        {SDS_ID_REQUIRED_GUIDELINES}
        {SDS_NAME_TO_SDS_ID_GUIDELINES}
        {LOCATION_ID_REQUIRED_GUIDELINES}
        {LOCATION_NAME_TO_LOCATION_ID_GUIDELINES}

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    if default_run:
        return {
            "status": "success",
            "code": "NEED_CONFIRMATION",
            "instruction": [
                "Ask user to confirm adding SDS (get detail via show_sds_detail tool) to location info (get detail via get_locations tool)",
                "If user confirmed correct, call this tool again with default_run=False",
            ],
            "trace_id": session_handle,
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
            return {
                "status": "success",
                "code": "OK",
                "data": {
                    "session_handle": session_handle,
                    **response.json(),
                },
                "instruction": [
                    "Show information",
                    PRODUCT_RECOMMEND_INSTRUCTION,
                ],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Move SDS")
async def move_sds(
    session_handle: uuid.UUID, 
    product_id: str, 
    location_id: str,
    default_run: bool = True,
) -> Dict[str, Any]:
    f"""
    Move a product (SDS assigned to a location) to a different location.

    When to call:
        - User ask to move a SDS from a specific location to another location in their own library/inventory
        - User ask to move a product to different location.

    When not to call:
        - When can not define the product_id from chat context (Ask user to provide).
        - When can not define the location_id from chat context (Ask user to provide or create new).

    Usage example (One-line):
        - Move SDS/product <SDS name> from <selected location name> to <target location name>
        - Move this SDS to location <target location name>
    
    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - product_id (str): Unique identifier of the product to move
        - location_id (str): Unique identifier of the target location
        {DRY_RUN_PARAM_DESCRIPTION}

    Important Guidelines:
        {PRODUCT_ID_REQUIRED_GUIDELINES}
        {PRODUCT_NAME_TO_PRODUCT_ID_GUIDELINES}
        {LOCATION_ID_REQUIRED_GUIDELINES}
        {LOCATION_NAME_TO_LOCATION_ID_GUIDELINES}
    
    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """
        
    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info
        
    if default_run:
        return {
            "status": "success",
            "code": "NEED_CONFIRMATION",
            "instruction": [
                "Ask user to confirm moving product (get detail via show_customer_product_detail tool) to location info (get detail via get_locations tool)",
                "If user confirmed correct, call this tool again with default_run=False",
            ],
            "trace_id": session_handle,
        }

    endpoint = f"{BACKEND_URL}/substance/{product_id}/move/"
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    
    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json={"department_id": location_id},
            timeout=10
        )
        
        if response.status_code == 200:
            return {
                "status": "success",
                "code": "OK",
                "data": {
                    "session_handle": session_handle,
                    **response.json(),
                },
                "instruction": [
                    "Show information",
                    PRODUCT_RECOMMEND_INSTRUCTION,
                ],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Copy SDS to another location")
async def copy_sds_to_another_location(
    session_handle: uuid.UUID, 
    product_id: str, 
    location_id: str,
    default_run: bool = True,
) -> Dict[str, Any]:
    f"""
    Copy a product to another location, creating a duplicate with similar information.

    When to call:
        - User ask to copy a SDS from a specific location to another location in their own library/inventory
        - User ask to copy a product to different location.

    When not to call:
        - When can not define the product_id from chat context (Ask user to provide).
        - When can not define the location_id from chat context (Ask user to provide or create new).

    Usage example (One-line):
        - Copy SDS/product <SDS name> on <selected location name> to <target location name>
        - Copy this SDS to location <target location name>
        - Add this SDS to location <target location name> with exactly same information

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - product_id (str): Unique identifier of the product to copy
        - location_id (str): Unique identifier of the target location
        {DRY_RUN_PARAM_DESCRIPTION}

    Important Guidelines:
        {PRODUCT_ID_REQUIRED_GUIDELINES}
        {PRODUCT_NAME_TO_PRODUCT_ID_GUIDELINES}
        {LOCATION_ID_REQUIRED_GUIDELINES}
        {LOCATION_NAME_TO_LOCATION_ID_GUIDELINES}

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    if default_run:
        return {
            "status": "success",
            "code": "NEED_CONFIRMATION",
            "instruction": [
                "Ask user to confirm copying product (get detail via show_customer_product_detail tool) to location info (get detail via get_locations tool)",
                "If user confirmed correct, call this tool again with default_run=False",
            ],
            "trace_id": session_handle,
        }

    endpoint = f"{BACKEND_URL}/substance/{product_id}/copy/"
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            json={"department_id": location_id},
            timeout=10
        )

        if response.status_code == 200:
            return {
                "status": "success",
                "code": "OK",
                "data": {
                    "session_handle": session_handle,
                    **response.json(),
                },
                "instruction": [
                    "Show information",
                    PRODUCT_RECOMMEND_INSTRUCTION,
                ],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Archive SDS")
async def archive_sds(
    session_handle: uuid.UUID, 
    product_id: str,
    default_run: bool = True,
) -> Dict[str, Any]:
    f"""
    Archive a product (SDS assigned to a location), removing it from active inventory.

    When to call:
        - User ask to archive a SDS from a specific location in their own library/inventory
        - User ask to archive a product.

    When not to call:
        - When can not define the product_id from chat context (Ask user to provide).

    Usage example (One-line):
        - Archive SDS/product <SDS name> on <selected location name>
        - Remove this SDS/product
        - Delete this SDS/product
    
    Synonyms: 
    {SYNONYMS}
    - archive product, delete product, remove product.

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - product_id (str): Unique identifier of the product to archive
        {DRY_RUN_PARAM_DESCRIPTION}

    Important Guidelines:
        {PRODUCT_ID_REQUIRED_GUIDELINES}
        {PRODUCT_NAME_TO_PRODUCT_ID_GUIDELINES}
        - Confirm with user before archiving

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    if default_run:
        return {
            "status": "success",
            "code": "NEED_CONFIRMATION",
            "instruction": [
                "Ask user to confirm archiving product (get detail via show_customer_product_detail tool)",
                "If user confirmed correct, call this tool again with default_run=False",
            ],
            "trace_id": session_handle,
        }

    endpoint = f"{BACKEND_URL}/substance/{product_id}/archive/"
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

    try:
        response = requests.post(
            endpoint,
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            return {
                "status": "success",
                "code": "OK",
                "data": {
                    "session_handle": session_handle,
                    **response.json(),
                },
                "instruction": [
                    "Show information",
                    PRODUCT_RECOMMEND_INSTRUCTION,
                ],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Get location")
async def get_locations(
    session_handle: uuid.UUID, 
    location_name: Optional[str] = None,
    location_id: Optional[str] = None,
) -> Dict[str, Any]:
    f"""
    Retrieve the complete location hierarchy (tree structure) for the current user's organization.

    When to call:
        - User ask to get locations tree/hierarchy.
        - User want to find a specific location by name or id.

    Usage example (One-line):
        - List all locations
        - Show me my locations tree/hierarchy
        - Show me location <location name>

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - location_name (str, optional): Name of the location to filter. Default: None
        - location_id (str, optional): ID of the location to filter. Default: None

    Important Guidelines:
        - If success, display results from data field in a tree/hierarchical structure (similar to file explorer)
        - If error, notify user about the error and follow instruction field if existed.

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

    try:
        api_url = f"{BACKEND_URL}/location/"
        if location_name:
            api_url += f"?name={location_name}"
        if location_id:
            api_url += f"?id={location_id}"

        response = requests.get(
            api_url,
            headers=headers,
            timeout=10
        )

        if response.status_code == 200:
            return {
                "status": "success",
                "code": "OK",
                "data": response.json(),
                "instruction": [
                    "Show locations tree",
                    "If no locations are found, recommend user to add a new location",
                    f"If have locations, {LOCATION_RECOMMEND_INSTRUCTION}",
                ],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Add location")
async def add_location(
    session_handle: uuid.UUID, 
    name: str, 
    parent_location_id: Optional[str] = None
) -> Dict[str, Any]:
    f"""
    Create a new location in the organization's location hierarchy.

    When to call:
        - User ask to add/create a new location.

    When not to call:
        - User not providing the location name.
        - Unable to identify the created location is root or have parent location.

    Usage example (One-line):
        - Add new location <location name> to the location <parent location name>
        - Create a root location <location name>

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}
    
    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - name (str): Name of the new location (e.g., "Warehouse A", "Lab 3")
        - parent_location_id (str, optional): ID of parent location. None for root-level locations.

    Important Guidelines:
        - parent_location_id should be None when creating a root location
        - If user doesn't mention parent location, ask whether it's a root location
        - If not root, ask user to provide parent location name
        {LOCATION_NAME_TO_LOCATION_ID_GUIDELINES}

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}

    try:
        response = requests.post(
            f"{BACKEND_URL}/location/",
            headers=headers,
            json={
                "name": name,
                "parent_department_id": parent_location_id
            },
            timeout=10
        )

        if response.status_code == 201:
            return {
                "status": "success",
                "code": "OK",
                "data": {
                    "session_handle": session_handle,
                    **response.json(),
                },
                "instruction": [
                    "Show information",
                    LOCATION_RECOMMEND_INSTRUCTION,
                ],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Get hazardous products with ingredients on restricted lists")
async def get_hazardous_sds_on_restricted_lists(
    session_handle: uuid.UUID, 
    keyword: str = "", 
    page: int = 1, 
    page_size: int = 10
) -> Dict[str, Any]:
    f"""
    Retrieve or search for hazardous products (SDS assigned to a location) containing ingredients/components on regulatory restriction lists.

    When to call:
        - User ask to list/search hazardous products/SDSs.
        - User want to see/search products/SDSs that are restricted by regulations.

    Usage example (One-line):
        - Show me all hazardous products/SDSs
        - Find the hazardous product/SDS <product name>
        - List me all products/SDSs that are restricted by regulations

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        {PAGINATION_PARAM_DESCRIPTION}
        - keyword (str, optional): Search term to filter hazardous products. Default: "" (all hazardous)

    Important Guidelines:
        - If user doesn't specify a keyword, use empty string to retrieve all hazardous SDSs

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

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
                "code": "OK",
                "data": {
                    "session_handle": session_handle,
                    "results": substance_list,
                    "page": page,
                    "page_size": page_size,
                },
                "instruction": [
                    "Display detailed information on restricted ingredients/components in results",
                    "Highlight which specific regulations each ingredient violates",
                    "If no results are found, recommend user to search_sds tool for finding SDS on global database",
                    "If have results, recommend user these next actions: show_customer_product_detail, move_sds, copy_sds, archive_sds"
                ],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Add SDS by uploading SDS PDF file")
async def add_sds_by_uploading_sds_pdf_file(
    session_handle: uuid.UUID, 
    location_id: str
) -> Dict[str, Any]:
    f"""
    Generate an upload URL for user to upload an SDS PDF file to a specific location.

    When to call:
        - User ask to upload an SDS PDF file to a specific location.
        - User have a SDS pdf file and want to add it but does not find it on global database.

    When not to call:
        - When can not define the location_id from chat context (Ask user to provide or create new).
        - User does not have the SDS PDF file (Ask user first).

    Usage example (One-line):
        - I want to add a new SDS to <location name> but I do not find it on global database.
        - Upload this SDS file to <location name>.
        - I have a SDS file, help me add it to <location name>.

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - location_id (str): Unique identifier of the target location for the SDS

    Important Guidelines:
        {LOCATION_ID_REQUIRED_GUIDELINES}
        {LOCATION_NAME_TO_LOCATION_ID_GUIDELINES}
        - Provide the upload_url to user and wait for confirmation that upload is complete
        - After user confirms upload, call check_upload_sds_pdf_status with request_id 
          to monitor the extraction and processing status

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """
    
    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info
        
    request_id = str(uuid.uuid4())
    session_handle = str(session_handle)
    redis_client.set(f"upload_sds_pdf:{session_handle}:{request_id}", {
        "session_id": session_handle,
        "request_id": request_id,
        "location_id": location_id,
        "status": "inited",
    })

    upload_url = f"{DOMAIN}/upload?session_id={session_handle}&department_id={location_id}&request_id={request_id}"

    return {
        "status": "success",
        "code": "OK",
        "data": {
            "session_handle": session_handle,
            "request_id": request_id,
            "upload_url": upload_url,
        },
        "instruction": UPLOAD_SDS_PDF_STEP_INSTRUCTIONS,
        "trace_id": session_handle,
    }
    

@mcp.tool(title="Add SDS by URL")
async def add_sds_by_url(
    session_handle: uuid.UUID, 
    url: str, 
    location_id: str
) -> Dict[str, Any]:
    f"""
    Adding SDS by URL to a specific location.

    When to call:
        - User ask to upload an SDS link to a specific location.
        - User have a SDS pdf link/url and want to add it but does not find it on global database.

    When not to call:
        - When can not define the location_id from chat context (Ask user to provide or create new).
        - User does not have the SDS pdf link/url (Ask user first).

    Usage example (One-line):
        - Add this SDS link/url to <location name>.
        - Upload this SDS link/url to <location name>.
        - I have a SDS link/url, help me add it to <location name>.

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}
    - The URL content must be a pdf 

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - url (str): SDS pdf URL
        - location_id (str): Unique identifier of the target location for the SDS

    Important Guidelines:
        {LOCATION_ID_REQUIRED_GUIDELINES}
        {LOCATION_NAME_TO_LOCATION_ID_GUIDELINES}
        - After user confirms upload, call check_upload_sds_pdf_status with request_id 
          to monitor the extraction and processing status

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info
        
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    endpoint = f"{BACKEND_URL}/location/{location_id}/uploadSDSFromUrl/"
    request_id = str(uuid.uuid4())
    session_handle = str(session_handle)
    redis_client.set(f"upload_sds_pdf:{session_handle}:{request_id}", {
        "session_id": session_handle,
        "request_id": request_id,
        "location_id": location_id,
        "status": "inited",
    })

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
            redis_client.set(f"upload_sds_pdf:{session_handle}:{request_id}", {
                "session_id": session_handle,
                "request_id": request_id,
                "location_id": location_id,
                "status": "uploaded",
                "data": response.json(),
            })

            data = GetExtractionStatusApiResponse(**response.json())
            progress = data.progress
            return {
                "status": "success",
                "code": "OK",
                "data": {
                    "session_handle": session_handle,
                    "request_id": request_id,
                    "progress": progress,
                    **data.model_dump(by_alias=True),
                },
                "instruction": ["call check_upload_sds_pdf_status tool with request_id"],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Check upload SDS file status")
async def check_upload_sds_pdf_status(session_handle: uuid.UUID, request_id: str) -> Dict[str, Any]:
    f"""
    Check the processing status for an uploaded SDS PDF file.

    When to call:
        - User ask to check the status of the uploaded SDS PDF file.
        - Automatically called when previous tool need to check the status of the uploaded SDS PDF file.

    When not to call:
        - When can not define the request_id from chat context (Ask user to provide).
        - Do not use for checking the status of the uploaded Product List Excel file (Call tool check_upload_product_list_excel_data_status instead).

    Usage example (One-line):
        - Check the status of the uploaded SDS PDF file.
        - How is my previous upload progress?
        - Does the upload finished?
        - Are my SDS pdf file/link/url added to the location?

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}
    - Must be called after add_sds_by_uploading_sds_pdf_file or add_sds_by_url tool

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - request_id (str): Upload request identifier from add_sds_by_uploading_sds_pdf_file

    Important Guidelines:
        - Only call this after user has uploaded file via add_sds_by_uploading_sds_pdf_file
        - If request not found, ask user to provide request_id or restart upload process
        - If progress is 100%, display completion information to user
        - If progress < 100%, show current progress and call this tool again after a brief wait

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    session_handle = str(session_handle)
    upload_key = f"upload_sds_pdf:{session_handle}:{request_id}"
    upload_info = redis_client.get(upload_key)
    if not upload_info:
        return {
            "status": "error",
            "code": "UPLOAD_SESSION_EXPIRED",
            "instruction": [
                "Upload session expired. Please use the add_sds_by_uploading_sds_pdf_file or add_sds_by_url tool to create a new upload session."
            ],
            "trace_id": session_handle,
        }

    if upload_info.get("status") == "finished":
        return {
            "status": "success",
            "code": "UPLOAD_FINISHED",
            "data": {
                "session_handle": session_handle,
                "request_id": request_id,
                "progress": upload_info.get("progress"),
                **upload_info.get("data", {}),
            },
            "instruction": [
                "Upload finished. Show information for current progress in data",
                "Recommend user these next actions: show_customer_product_detail, add_sds_by_uploading_sds_pdf_file or add_sds_by_url (If user want to upload another SDS), copy_sds_to_another_location, archive_sds",
            ],
            "trace_id": session_handle,
        }
    elif not upload_info.get("status") in ["uploaded", "extracting"]:
        location_id = upload_info.get("location_id")
        if not location_id:
            return {
                "status": "error",
                "code": "UPLOAD_ERROR",
                "data": {
                    "error_message": "Not found location"
                },
                "instruction": [
                    "Not found location. Ask user to follow the step in add_sds_by_uploading_sds_pdf_file or add_sds_by_url tool."
                ],
                "trace_id": session_handle,
            }

        upload_url = f"{DOMAIN}/upload?session_id={session_handle}&department_id={location_id}&request_id={request_id}"

        error = "Upload not completed. Please try again."
        if upload_info.get("status") == "error":
            error = f"Upload error: {upload_info.get('error_message')}. Please try again."

        reset_upload_session(upload_key, session_handle, request_id, location_id)
        return {
            "status": "error",
            "code": "UPLOAD_ERROR",
            "data": {
                "error_message": error,
                "upload_url": upload_url,
            },
            "instruction": UPLOAD_SDS_PDF_STEP_INSTRUCTIONS,
            "trace_id": session_handle,
        }

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    endpoint = f"{BACKEND_URL}/binder/getExtractionStatus/?id={request_id}"

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            data = GetExtractionStatusApiResponse(**response.json())
            progress = data.progress

            redis_client.set(upload_key, {
                **upload_info,
                "status": "extracting" if progress < 100 else "finished",
                "data": data.model_dump(by_alias=True),
                "progress": progress,
            })

            return {
                "status": "success",
                "code": "UPLOAD_EXTRACTING",
                "data": {
                    "session_handle": session_handle,
                    "request_id": request_id,
                    "progress": progress,
                    **data.model_dump(by_alias=True),
                },
                "instruction": [
                    "Show information for current progress in data",
                    "If progress is not 100, call check_upload_status tool with request_id again",
                    "If progress is 100, recommend user these next actions: show_customer_product_detail, add_sds_by_uploading_sds_pdf_file or add_sds_by_url (If user want to upload another SDS), copy_sds_to_another_location, archive_sds",
                ],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Upload Product List")
async def upload_product_list_excel_file(session_handle: uuid.UUID) -> Dict[str, Any]:
    f"""
    Generate an upload URL for user to upload a Product List Excel file for bulk SDS import.

    When to call:
        - User ask to upload Excel file for their products/SDSs.
        - User want to import products/SDSs from Excel file.
        - User want to create product/SDS requests.

    When not to call:
        - User does not have the Excel file (Ask user first).

    Usage example (One-line):
        - Upload this Excel file of products/SDSs.
        - I have a Excel file of products/SDSs, help me import it.
        - Import products/SDSs from file.

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}

    Important Guidelines:
        - Display the upload_url to user for accessing the upload form
        - Wait for user confirmation that they have finished uploading the Excel file
        - After user confirms upload, call validate_upload_product_list_excel_data with request_id to validate and map the Excel columns

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    request_id = str(uuid.uuid4())
    session_handle = str(session_handle)
    redis_client.set(f"upload_product_list:{session_handle}:{request_id}", {
        "session_id": session_handle,
        "request_id": request_id,
        "status": "inited",
    })

    upload_url = f"{DOMAIN}/uploadProductList?session_id={session_handle}&request_id={request_id}"

    return {
        "status": "success",
        "code": "OK",
        "data": {
            "session_handle": session_handle,
            "request_id": request_id,
            "upload_url": upload_url,
        },
        "instruction": UPLOAD_PRODUCT_LIST_EXCEL_FILE_INSTRUCTIONS,
        "trace_id": session_handle,
    }


@mcp.tool(title="Validate uploaded Product List")
async def validate_upload_product_list_excel_data(
    session_handle: uuid.UUID, 
    request_id: str
) -> Dict[str, Any]:
    f"""
    Validate and extract column information from uploaded Product List Excel file.

    When to call:
        - User ask to validate the uploaded Product List Excel file after uploading.
        - Automatically called when previous tool need to validate the uploaded Product List Excel file.

    When not to call:
        - When can not define the request_id from chat context (Ask user to provide).

    Usage example (One-line):
        - Validate the uploaded file.
        - How is my previous upload progress?
        - Does the upload finished?
        - Are my products/SDSs imported from the Excel file?

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}
    - Must be called after upload_product_list_excel_file tool

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - request_id (str): Upload request identifier from upload_product_list_excel_file

    Important Guidelines:
        - Only call this after user has uploaded Excel file via upload_product_list_excel_file
        - If request not found, ask user to follow upload_product_list_excel_file instructions again
        - Automatically map extracted columns to required fields (product_name, supplier_of_sds, etc.)
        - If unable to auto-map, ask user to manually select matching columns
        - After mapping confirmation, call process_upload_product_list_excel_data

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    session_handle = str(session_handle)
    upload_key = f"upload_product_list:{session_handle}:{request_id}"
    upload_info =  redis_client.get(upload_key)
    if not upload_info:
        return {
            "status": "error",
            "code": "UPLOAD_SESSION_EXPIRED",
            "instruction": [
                "Upload session expired. Please use the upload_product_list_excel_file tool to create a new upload session."
            ],
            "trace_id": session_handle,
        }

    upload_url = f"{DOMAIN}/uploadProductList?session_id={session_handle}&request_id={request_id}"
    upload_status = upload_info.get("status")
    if upload_status == "processing" and upload_info.get("mapped_data"):
        return {
            "status": "success",
            "code": "UPLOAD_PROCESSING",
            "data": {
                "session_handle": session_handle,
                "request_id": request_id,
            },
            "instruction": [
                "Already validated, call process_upload_product_list_excel_data tool with mapped_data as empty",
            ],
            "trace_id": session_handle,
        }
    elif upload_status == "processed":
        return {
            "status": "success",
            "code": "UPLOAD_PROCESSED",
            "data": {
                "session_handle": session_handle,
                "request_id": request_id,
            },
            "instruction": [
                "Already processed, call process_upload_product_list_excel_data tool to continue",
            ],
            "trace_id": session_handle,
        }
    elif upload_status == "extracting":
        product_list_id = upload_info.get("product_list_id")
        if product_list_id:
            return {
                "status": "success",
                "code": "UPLOAD_EXTRACTING",
                "data": {
                    "session_handle": session_handle,
                    "request_id": request_id,
                    "product_list_id": product_list_id,
                },
                "instruction": [
                    "Already extracting, call check_upload_product_list_excel_data_status tool with product_list_id to continue",
                ],
                "trace_id": session_handle,
            }
    elif not upload_status in ["uploaded", "validated"]:
        error = "Upload not completed. Please try again."
        if upload_info.get("status") == "error":
            error = f"Upload error: {upload_info.get('error_message')}. Please try again."

        reset_upload_session(upload_key, session_handle, request_id)
        return {
            "status": "error",
            "code": "UPLOAD_ERROR",
            "data": {
                "error_message": error,
                "upload_url": upload_url,
            },
            "instruction": UPLOAD_PRODUCT_LIST_EXCEL_FILE_INSTRUCTIONS,
            "trace_id": session_handle,
        }

    file_name = upload_info.get("file_name")
    file_path = upload_info.get("file_path")
    if not file_path or not file_name:
        reset_upload_session(upload_key, session_handle, request_id)
        return {
            "status": "error",
            "code": "UPLOAD_ERROR",
            "data": {
                "error_message": "Error when accessing file. Please try again.",
                "upload_url": upload_url,
            },
            "instruction": UPLOAD_PRODUCT_LIST_EXCEL_FILE_INSTRUCTIONS,
            "trace_id": session_handle,
        }

    total_row = upload_info.get("total_row")
    if not total_row:
        reset_upload_session(upload_key, session_handle, request_id)
        return {
            "status": "error",
            "code": "UPLOAD_ERROR",
            "data": {
                "error_message":  "Not found any data from uploaded file. Please try again.",
                "upload_url": upload_url,
            },
            "instruction": UPLOAD_PRODUCT_LIST_EXCEL_FILE_INSTRUCTIONS,
            "trace_id": session_handle,
        }

    extracted_columns = upload_info.get("extracted_columns")
    if not extracted_columns:
        reset_upload_session(upload_key, session_handle, request_id)
        return {
            "status": "error",
            "code": "UPLOAD_ERROR",
            "data": {
                "error_message": "Unable to extract columns from uploaded file. Please try again.",
                "upload_url": upload_url,
            },
            "instruction": UPLOAD_PRODUCT_LIST_EXCEL_FILE_INSTRUCTIONS,
            "trace_id": session_handle,
        }

    redis_client.set(upload_key, {
        **upload_info,
        "status": "validated"
    })

    return {
        "status": "success",
        "code": "OK",
        "data": {
            "session_handle": session_handle,
            "request_id": request_id,
            "extracted_columns": extracted_columns,
        },
        "instruction": [
            "Auto map columns name in extracted_columns to a dictionary. The dictionary must have keys: product_name, supplier_of_sds. The dictionary can optionally have: location, location_id, product_code, cas_no, vendor_email, amount, amount_unit, link_to_sds, sku, external_system_id. Example: {'product_name': 'PRODUCT NAME', 'supplier_of_sds': 'SUPPLIER OF SDS', 'location': 'LOCATION', 'location_id': 'DEPARTMENT ID', 'product_code': 'PRODUCT CODE', 'cas_no': 'CAS NUMBER', 'vendor_email': 'VENDOR EMAIL', 'amount': 'AMOUNT VALUE', 'amount_unit': 'AMOUNT UNIT', 'link_to_sds': 'EXTERNAL SYSTEM URL', 'sku': 'SKU', 'external_system_id': 'EXTERNAL SYSTEM ID'}. If not found required key or exist column name not able to match, ask user to choose key that match with column name in extracted_columns.",
            "Ask user to confirm mapped data whether it is correct.",
            "If user confirmed correct, call and pass the mapped data to process_upload_product_list_excel_data tool",
        ],
        "trace_id": session_handle,
    }


@mcp.tool(title="Process uploaded Product List")
async def process_upload_product_list_excel_data(
    session_handle: uuid.UUID, 
    request_id: str,
    mapped_data: dict, 
    auto_match_product: bool,
) -> Dict[str, Any]:
    f"""
    Process validated Product List Excel data and import products into inventory.

    When to call:
        - Automatically called when previous tool need to process the uploaded Product List Excel data.
        - User confirmed the excel file column mapping from validate step.
        - User ask to process the uploaded Product List Excel data.

    When not to call:
        - When can not define the request_id from chat context (Ask user to provide).
        - When can not define the auto_match_product from chat context (Ask user to provide).

    Usage example (One-line):
        - Process the uploaded Product List Excel data.
        - How is my previous upload progress?
        - Does the upload finished?
        - Are my products/SDSs imported from the Excel file?


    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}
    - Must be called after validate_upload_product_list_excel_data tool

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - request_id (str): Upload request identifier from validate step
        - mapped_data (dict): Column mapping from Excel columns to system fields from validate step.
        - auto_match_product (bool): Whether to automatically match products to SDSs in global database

    Important Guidelines:
        - Only call after validate_upload_product_list_excel_data has confirmed column mapping
        - If request_id or mapped_data missing, restart from upload_product_list_excel_file
        - Always ask user if they want automatic matching enabled
        - After processing, call check_upload_product_list_excel_data_status to monitor progress

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    session_handle = str(session_handle)
    upload_key = f"upload_product_list:{session_handle}:{request_id}"
    upload_info =  redis_client.get(upload_key)
    if not upload_info:
        return {
            "status": "error",
            "code": "UPLOAD_SESSION_EXPIRED",
            "instruction": [
                "Upload session expired. Please use the add_sds_by_uploading_sds_pdf_file or add_sds_by_url tool to create a new upload session."
            ],
            "trace_id": session_handle,
        }
    
    upload_url = f"{DOMAIN}/uploadProductList?session_id={session_handle}&request_id={request_id}"
    file_name = upload_info.get("file_name")
    file_path = upload_info.get("file_path")
    total_row = upload_info.get("total_row")
    if not file_path or not file_name or not total_row:
        return {
            "status": "error",
            "code": "UPLOAD_VALIDATION_ERROR",
            "data": {
                "error_message": "Validation error",
            },
            "instruction": ["Call validate_upload_product_list_excel_data tool again"],
            "trace_id": session_handle,
        }
    
    upload_status = upload_info.get("status")
    converted_data = upload_info.get("extracted_data")
    if not mapped_data:
        mapped_data = upload_info.get("mapped_data")

    if upload_status == "processed" and converted_data:
        pass
    elif upload_status == "extracting":
        product_list_id = upload_info.get("product_list_id")
        if product_list_id:
            return {
                "status": "success",
                "code": "UPLOAD_EXTRACTING",
                "data": {
                    "session_handle": session_handle,
                    "request_id": request_id,
                    "product_list_id": product_list_id,
                },
                "instruction": [
                    "Already extracting, call check_upload_product_list_excel_data_status tool with product_list_id to continue",
                ],
                "trace_id": session_handle,
            }
    elif (
        not upload_status in ["validated", "processing"]
        or not mapped_data
    ):
        return {
            "status": "error",
            "code": "UPLOAD_VALIDATION_ERROR",
            "data": {
                "error_message": "Not validated",
            },
            "instruction": ["Call validate_upload_product_list_excel_data tool again"],
            "trace_id": session_handle,
        }
    else:
        redis_client.set(upload_key, {
            **upload_info,
            "mapped_data": mapped_data,
            "status": "processing"
        })

        column_mapping = {}
        for key, value in mapped_data.items():
            column_mapping[value] = key

        try:
            df = pd.read_excel(file_path)
            data_list = df.to_dict('records')
        
            extracted_count = 0
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
                    extracted_count += 1

            redis_client.set(upload_key, {
                **upload_info,
                "extracted_rows_count": f"{extracted_count}/{total_row - 1}"
            })
        except Exception as e:
            reset_upload_session(upload_key, session_handle, request_id)
            return {
                "status": "error",
                "code": "UPLOAD_PROCESS_ERROR",
                "data": {
                    "error_message":  f"Error when processing file: {str(e)}. Please try again.",
                    "upload_url": upload_url,
                },
                "instruction": UPLOAD_PRODUCT_LIST_EXCEL_FILE_INSTRUCTIONS,
                "trace_id": session_handle,
            }

        try:
            converted_data = json.dumps(extracted_data)
        except Exception as e:
            reset_upload_session(upload_key, session_handle, request_id)
            return {
                "status": "error",
                "code": "UPLOAD_PROCESS_ERROR",
                "data": {
                    "error_message":  f"Error extracting file: {str(e)}. Please try again.",
                    "upload_url": upload_url,
                },
                "instruction": UPLOAD_PRODUCT_LIST_EXCEL_FILE_INSTRUCTIONS,
                "trace_id": session_handle,
            }

        redis_client.set(upload_key, {
            **upload_info,
            "extracted_data": converted_data,
            "status": "processed"
        })

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    try:
        with open(file_path, "rb") as f:
            response = requests.post(
                f"{BACKEND_URL}/substance/uploadProductList/",
                headers=headers,
                data={
                    "extracted": converted_data,
                    "auto_match": str(auto_match_product).lower(),
                },
                files={"file": (file_name, f, "application/pdf")},
                timeout=10,
            )

        if response.status_code == 200:
            os.remove(file_path)
            response_data = response.json()

            redis_client.set(upload_key, {
                **upload_info,
                "uploaded_file_name": response_data.get("file_name"),
                "uploaded_file_path": response_data.get("file_path"),
                "product_list_id": response_data.get("product_list_id"),
                "status": "extracting"
            })

            return {
                "status": "success",
                "code": "OK",
                "data": {
                    "session_handle": session_handle,
                    "request_id": request_id,
                    "product_list_id": response_data.get("product_list_id"),
                },
                "instruction": [
                    "Show information for uploaded data",
                    "Call check_upload_product_list_excel_data_status with product_list_id for checking status of the upload process"
                ],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except Exception as e:
        reset_upload_session(upload_key, session_handle, request_id)
        return {
            "status": "error",
            "code": "UPLOAD_PROCESS_ERROR",
            "data": {
                "error_message": f"Error extracting file: {str(e)}. Please try again.",
                "upload_url": upload_url,
            },
            "instruction": UPLOAD_PRODUCT_LIST_EXCEL_FILE_INSTRUCTIONS,
            "trace_id": session_handle,
        }


@mcp.tool(title="Check upload Product List status")
async def check_upload_product_list_excel_data_status(
    session_handle: uuid.UUID, 
    product_list_id: str
) -> Dict[str, Any]:
    f"""
    Monitor the processing status for imported Product List Excel data.

    When to call:
        - User ask to check the status of their imported file.
        - Automatically called when previous tool need to check the status of uploaded file.

    When not to call:
        - When can not define the product_list_id from chat context (Ask user to provide).

    Usage example (One-line):
        - How is my previous upload progress?
        - Does the upload finished?
        - Are my products/SDSs imported from the Excel file?

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}
    - Must be called after process_upload_product_list_excel_data tool

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - product_list_id (str): Product list identifier from process_upload_product_list_excel_data

    Important Guidelines:
        - Only call after process_upload_product_list_excel_data has started import
        - If product_list_id not found, restart from upload_product_list_excel_file
        - If progress shows completion (N/N products processed), display final results
        - If progress incomplete, show current status and call this tool again after brief wait
        - If unmatched products exist, suggest calling get_sds_request to list them

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    session_handle = str(session_handle)
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    endpoint = f"{BACKEND_URL}/binder/getImportProductListStatus/?id={product_list_id}"

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            progress = data.get("progress")
            return {
                "status": "success",
                "code": "OK",
                "data": {
                    "session_handle": session_handle,
                    "progress": progress,
                    **data,
                },
                "instruction": [
                    "Show information for current progress in data",
                    "If progress is not finished, call check_upload_product_list_excel_data_status tool with product_list_id again.",
                    "If progress is finished and there are unmatched products, suggest user to list them by calling get_sds_request tool with product_list_id from data."
                ],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))
    

@mcp.tool(title="Get list of product lists imported from the Excel files")
async def get_uploaded_product_list(
    session_handle: uuid.UUID,
    search_keyword: str = "",
    page: int = 1, 
    page_size: int = 10,
) -> Dict[str, Any]:
    f"""
    Get the list of all product lists imported from the Excel files.

    When to call:
        - User ask to get the list of all product lists imported from the Excel files.

    Usage example (One-line):
        - Show me all product lists imported.
        - List all excel files uploaded.

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        {PAGINATION_PARAM_DESCRIPTION}
        - search_keyword (str, optional): Search term to filter product lists. Default: "" (all product lists)

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    instruction = [
        "Show list of all product lists imported from the Excel files",
        "Recommend user to manage product lists with these actions: get_product_list_summary, get_sds_request tools",
    ]

    try:
        search_param = f"?page={page}&page_size={page_size}"
        if search_keyword:
            search_param += f"&search={search_keyword}"

        api_url = f"{BACKEND_URL}/binder/importProductList/{search_param}"
        response = requests.get(
            api_url,
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            try:
                res = GetImportProductListResponse(**data)
                return {
                    "status": "success",
                    "code": "OK",
                    "data": {
                        "session_handle": session_handle,
                        "results": [
                            item.model_dump(by_alias=True) 
                            for item in res.results
                        ],
                    },
                    "instruction": instruction,
                    "trace_id": session_handle,
                }
            except ValueError as e:
                return {
                    "status": "success",
                    "code": "OK",
                    "data": {
                        "session_handle": session_handle,
                        "results": data.get("results", []),
                        "count": data.get("count", 0),
                        "next_page": int(page) + 1 if data.get("next") else None,
                        "previous_page": int(page) - 1 if data.get("previous") else None,
                    },
                    "instruction": instruction,
                    "trace_id": session_handle,
                }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Get summary of a product list imported from the Excel file")
async def get_product_list_summary(
    session_handle: uuid.UUID,
    product_list_id: str,
    page: int = 1, 
    page_size: int = 10,
) -> Dict[str, Any]:
    f"""
    Get the summary of a product list imported from the Excel file.

    When to call:
        - User ask to get the summary of a product list imported from the Excel file.

    When not to call:
        - When can not define the product_list_id from chat context (Ask user to provide).

    Usage example (One-line):
        - Show me the summary of the product list <product list name>.
        - Show me information of the uploaded excel file <excel file name>.

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        {PAGINATION_PARAM_DESCRIPTION}
        - product_list_id (str): ID of the product list imported from the Excel file

    Important Guidelines:
        {PRODUCT_LIST_ID_REQUIRED_GUIDELINES}
        {PRODUCT_LIST_NAME_TO_PRODUCT_LIST_ID_GUIDELINES}

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    instruction = [
        "Show summary of the products/requests imported from the Excel file",
        "If have unmatched products/requests, suggest user to match them with the global database by calling match_sds_request with search_sds tool",
        "If have matched products/requests, suggest user to manage them with these actions: show_customer_product_detail, add_sds, move_sds, copy_sds_to_another_location, archive_sds tools",
    ]

    try:
        search_param = f"?wish_list_id={product_list_id}&page={page}&page_size={page_size}"
        api_url = f"{BACKEND_URL}/binder/importProductListSummary/{search_param}"
        response = requests.get(
            api_url,
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            try:
                res = GetProductListSummaryResponse(**data)
                return {
                    "status": "success",
                    "code": "OK",
                    "data": {
                        "session_handle": session_handle,
                        "results": [
                            item.model_dump(by_alias=True) 
                            for item in res.results
                        ],
                    },
                    "instruction": instruction,
                    "trace_id": session_handle,
                }
            except ValueError as e:
                return {
                    "status": "success",
                    "code": "OK",
                    "data": {
                        "session_handle": session_handle,
                        "results": data.get("results", []),
                        "count": data.get("count", 0),
                        "next_page": int(page) + 1 if data.get("next") else None,
                        "previous_page": int(page) - 1 if data.get("previous") else None,
                    },
                    "instruction": instruction,
                    "trace_id": session_handle,
                }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))

    
@mcp.tool(title="Get list of SDS Requests (Unmatched Products)")
async def get_sds_request(
    session_handle: uuid.UUID, 
    search: str = "", 
    product_list_id: str = "",
    page: int = 1, 
    page_size: int = 10
) -> Dict[str, Any]:
    f"""
    Retrieve SDS requests that have not been matched to any SDS in the global database.

    When to call:
        - User ask to list all unmatched products/SDS requests.
        - Automatically called when previous tool need to list all unmatched products/SDS requests.

    Usage example (One-line):
        - Show me all request from the uploaded file.
        - List all unmatched products/SDS requests.
        - Find request <keyword>
        - Show me all products that does not link to any SDS.
        - List all un-linked products/SDS requests.

    Synonyms: 
    {SYNONYMS}
    - Unmatched SDSs, unmatched products, SDS requests, substance requests.

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        {PAGINATION_PARAM_DESCRIPTION}
        - search (str, optional): Search term to filter requests. Default: "" (all requests)
        - product_list_id (str, optional): Filter by specific import job ID. Default: "" (all jobs)

    Important Guidelines:
        - If user wants to match SDS request, call search_sds with keyword:
          "supplier_name + product_name" from the request
        - Display product_name, supplier_name, and other request details clearly
        - Guide user through match_sds_request tool to link found SDSs

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """
        
    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info
    
    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    endpoint = f"{BACKEND_URL}/substance/sdsRequests?page={page}&page_size={page_size}"

    if search:
        endpoint += f"&search={search}"

    if product_list_id:
        endpoint += f"&wish_list_id={product_list_id}"

    recommend_instruction = [
        "Display results in table",
        "If no results are found, suggest user to upload_product_list_excel_file tool for uploading another product list, get_uploaded_product_list or get_product_list_summary tool for getting summary of the product list",
        "If have results, suggest user these next actions: search_sds tool for finding SDS on global database, match_sds_request tool for matching SDS to the product request"
    ]

    try:
        response = requests.get(endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            try:
                res = SdsRequestResponse(**data)
                return {
                    "status": "success",
                    "code": "OK",
                    "data": {
                        "session_handle": session_handle,
                        "results": [
                            item.model_dump(by_alias=True) 
                            for item in res.results
                        ],
                        "count": res.count,
                        "next_page": int(page) + 1 if res.next else None,
                        "previous_page": int(page) - 1 if res.previous else None,
                    },
                    "instruction": recommend_instruction,
                    "trace_id": session_handle,
                }
            except ValueError as e:
                return {
                    "status": "success",
                    "code": "OK",
                    "data": {
                        "session_handle": session_handle,
                        "results": data.get("results", []),
                        "count": data.get("count", 0),
                        "next_page": int(page) + 1 if data.get("next") else None,
                        "previous_page": int(page) - 1 if data.get("previous") else None,
                    },
                    "instruction": recommend_instruction,
                    "trace_id": session_handle,
                }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Match product request to a SDS")
async def match_sds_request(
    session_handle: uuid.UUID, 
    request_id: str, 
    sds_id: str, 
    use_sds_data: bool
) -> Dict[str, Any]:
    f"""
    Link a SDS request (unmatched product) to an SDS from the SDS Managers 16 millions SDS global database.

    When to call:
        - User ask to match/link a SDS request to a global SDS.
        - Automatically called when previous tool need to match/link a SDS request to a global SDS.

    When not to call:
        - When can not define the request_id from chat context (Ask user to provide).
        - When can not define the sds_id from chat context (Ask user to provide).
        - When can not define the use_sds_data from chat context (Ask user to provide).

    Usage example (One-line):
        - Match this request to the SDS <SDS name>.
        - Link this product to the SDS <SDS name> with SDS data.
        - Match this request to the SDS <SDS name> but keep current request data.

    Synonyms: 
    {SYNONYMS}
    - Match unmatched SDS, link product request

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - request_id (str): ID of the unmatched product request
        - sds_id (str): ID of the SDS to match from global database
        - use_sds_data (bool): Whether to use SDS data or keep original request data

    Important Guidelines:
        - If request_id is not available, ask user to provide SDS/product name
          Then call get_sds_request with the name as search keyword
          Always ask user to choose if multiple results are found
        {SDS_ID_REQUIRED_GUIDELINES}
        {SDS_NAME_TO_SDS_ID_GUIDELINES}
        - Show comparison of product name and supplier between request and SDS
        - Ask user whether to use SDS data (more accurate) or keep request data

    Returns:
        {DEFAULT_RETURN_TEMPLATE}
    """

    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    endpoint = f"{BACKEND_URL}/substance/{request_id}/matchSdsRequest/"
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
            return {
                "status": "success",
                "code": "OK",
                "data": {
                    "session_handle": session_handle,
                    **response.json(),
                },
                "instruction": [
                    "Show information",
                    "Recommend these next actions: get_sds_request (For continue matching SDS to the product request), show_customer_product_detail (For showing the product information), copy_sds_to_another_location (For copying the SDS to another location), archive_sds (For archiving the SDS)"
                ],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))


@mcp.tool(title="Update product information")
async def edit_product_data(
    session_handle: uuid.UUID,
    product_id: str,
    sds_pdf_product_name: Optional[str] = None,
    chemical_name_synonyms: Optional[str] = None,
    external_system_id: Optional[str] = None,
) -> Dict[str, Any]:
    f"""
    Edit editable fields of an product (SDS assigned to a location) in the customer's inventory.

    When to call:
        - User ask to update/edit the information of a product/SDS.
        - Automatically called when previous tool need to update the information of a product/SDS.

    When not to call:
        - When can not define the product_id from chat context (Ask user to provide).
        - User does not provide any editable fields: sds_pdf_product_name, chemical_name_synonyms, external_system_id (Ask user to provide).

    Usage example (One-line):
        - Update the product name of this product to <new product name>.
        - Set the external system ID of this product to <new external system ID>.
        - Help me edit synonyms for SDS <SDS name> from location <location name> to <new product name>.

    Synonyms: 
    {SYNONYMS}

    Prerequisites:
    {AUTHORIZED_PREREQUISITES}

    Parameters:
        {SESSION_HANDLE_PARAM_DESCRIPTION}
        - product_id (str): Unique ID of product in customer's inventory
        - sds_pdf_product_name (str, optional): Product name override/custom name
        - chemical_name_synonyms (str, optional): Alternative names/synonyms for the chemical
        - external_system_id (str, optional): External reference/integration identifier

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
        {DEFAULT_RETURN_TEMPLATE}
    """
        
    info, is_expired = validate_session(session_handle)
    if is_expired:
        return info

    headers = {SDS_HEADER_NAME: f"{info.get('api_key')}"}
    endpoint = f"{BACKEND_URL}/substance/{product_id}/updateSDS/"

    is_valid = (
        sds_pdf_product_name is not None or
        chemical_name_synonyms is not None or
        external_system_id is not None
    )
    if not is_valid:
        return {
            "status": "error",
            "code": "MISSING_REQUIRED_PARAMETERS",
            "instruction": [
                "At least one field must be provided for update"
            ],
            "trace_id": session_handle,
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
                "code": "OK",
                "instruction": [
                    "Immediately call tool `show_customer_product_detail` with the same "
                    f"`session_handle={session_handle}` and `product_id={product_id}` to verify the update. "
                    "Compare the returned record against the submitted payload to confirm: "
                    "• `sds_pdf_product_name` matches the new value (and is removed if empty string was sent). "
                    "• `chemical_name_synonyms` matches the new value (and is removed if empty string was sent). "
                    "• `external_system_id` matches the new value (and is removed if empty string was sent). "
                    "If the values match, tell the user: 'Update verified in customer library.' "
                    "If any mismatch is found, report which fields differ and suggest retrying the edit."
                ],
                "trace_id": session_handle,
            }
        else:
            try:
                return handle_api_error(response, session_handle)
            except:
                return server_error_response(
                    session_handle, 
                    response.status_code, 
                    response.text
                )
    except requests.exceptions.RequestException as e:
        return connection_error_response(session_handle, str(e))
