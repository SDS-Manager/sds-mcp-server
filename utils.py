from cache import redis_client
from config import BACKEND_URL, SDS_HEADER_NAME
import logging
import requests
import uuid
from typing import Dict, Any, Optional, Tuple


logger = logging.getLogger(__name__)


def bootstrap_session_from_api_key(
    api_key: str,
    session_handle: Optional[uuid.UUID] = None,
) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    """
    Validate an API key against the SDS Manager backend and persist the resulting
    session in Redis. Returns (info, session_handle, error_message).

    If session_handle is provided, that key is used; otherwise a new UUID is
    generated for the headless session.
    """
    if not api_key:
        return None, None, "API key is required"

    if session_handle and session_handle != uuid.UUID(int=0):
        handle = str(session_handle)
    else:
        handle = str(uuid.uuid4())
    session_key = f"sds_mcp:{handle}"

    try:
        response = requests.get(
            f"{BACKEND_URL}/user/",
            headers={SDS_HEADER_NAME: api_key},
            timeout=30,
        )
    except requests.exceptions.RequestException as e:
        logger.error("Backend request failed during API key bootstrap: %s", e)
        return None, handle, f"Failed to reach backend: {e}"

    if response.status_code == 200:
        result = response.json()
        info = {
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
        }
        redis_client.set(session_key, info)
        return info, handle, None

    try:
        error_data = response.json()
        error_message = error_data.get("error_message") or response.text
    except ValueError:
        error_message = response.text

    redis_client.set(session_key, {
        "logged_in": False,
        "login_error": True,
        "error_message": error_message,
    })
    return None, handle, error_message


def validate_session(
    session_handle: Optional[uuid.UUID],
    x_api_key: Optional[str] = None,
) -> Tuple[Dict[str, Any], bool]:
    """
    Resolve a session. Preference order:
      1. session_handle from Redis (if valid and logged in).
      2. x_api_key header — bootstrap a headless session if a valid key is provided.

    Returns (info_or_error_response, is_error).
    """
    if session_handle and session_handle != uuid.UUID(int=0):
        session_key = f"sds_mcp:{session_handle}"
        info = redis_client.get(session_key)
        if (
            info 
            and info.get("logged_in")
            and (
                not x_api_key
                or x_api_key == info.get("api_key")
            )
        ):
            redis_client.set(session_key, info)
            return info, False

    if x_api_key:
        info, handle, error_message = bootstrap_session_from_api_key(
            x_api_key, session_handle
        )
        if info:
            return info, False
        trace_id = handle or session_handle
        return {
            "status": "error",
            "code": "API_KEY_INVALID",
            "data": {
                "error_message": error_message,
            },
            "instruction": [
                "Invalid or expired API key. Verify the x-api-key header or login again using get_login_url."
            ],
            "trace_id": trace_id,
        }, True

    if session_handle and session_handle != uuid.UUID(int=0):
        session_key = f"sds_mcp:{session_handle}"
        info = redis_client.get(session_key)
        if not info:
            return {
                "status": "error",
                "code": "SESSION_EXPIRED",
                "instruction": [
                    "Session expired. Please use the get_login_url tool with new session ID to create a new session."
                ],
                "trace_id": session_handle,
            }, True

        return {
            "status": "error",
            "code": "AUTHENTICATION_ERROR",
            "data": {
                "error_message": info.get("error_message"),
            },
            "instruction": [
                "Authorization error. Please login again using get_login_url tool with new session ID."
            ],
            "trace_id": session_handle,
        }, True

    return {
        "status": "error",
        "code": "NOT_AUTHENTICATED",
        "instruction": [
            "Not authenticated. Provide a valid x-api-key header or use the get_login_url tool to create a new session."
        ],
        "trace_id": None,
    }, True


def api_error_response(
    session_handle: uuid.UUID,
    status_code: int,
    error_message: str
) -> Dict[str, Any]:
    return {
        "status": "error",
        "code": "API_ERROR",
        "data": {
            "status_code": status_code,
            "error_message": error_message,
        },
        "instruction": [
            "Notify user about the error in human-friendly way",
            "Ask user to verify the input and try again."
        ],
        "trace_id": session_handle,
    }


def handle_api_error(response: requests.Response, session_handle: uuid.UUID) -> Dict[str, Any]:
    error_response = response.json()
    error_msg = error_response.get("error_message", None)
    error_code = error_response.get("error_code", None)
    if not error_msg or not error_code:
        return api_error_response(session_handle, response.status_code, response.text)

    if error_code in ["NOT_EXISTED_API_KEY"]:
        info = redis_client.get(f"sds_mcp:{session_handle}")
        if info:
            redis_client.set(f"sds_mcp:{session_handle}", {
                "logged_in": False,
                "login_error": True,
                "error_message": error_msg,
            })

        return {
            "status": "error",
            "code": "API_KEY_INVALID",
            "data": {
                "status_code": response.status_code,
                "error_code": error_code,
                "error_message": error_msg,
            },
            "instruction": [
                "Invalid API key. Please login again using get_login_url tool with new session ID."
            ],
            "trace_id": session_handle,
        }

    if error_code in [
        "AUTHENTICATION_AUTH_IS_NOT_ACTIVE_BAD_REQUEST",
        "API_KEY_NOT_ACTIVE",
        "SUBSCRIPTION_ACCESS_MCP_CHAT_AGENT_NOT_PERMISSION",
        "CUSTOMER_SUBSCRIPTION_DOES_NOT_EXIST",
    ]:
        return {
            "status": "error",
            "code": "AUTHORIZATION_ERROR",
            "data": {
                "status_code": response.status_code,
                "error_code": error_code,
                "error_message": error_msg,
            },
            "instruction": [
                "Notify user about the error in human-friendly way",
                "Ask user to contact organization administrator for support."
            ],
            "trace_id": session_handle,
        }

    return api_error_response(session_handle, response.status_code, error_msg)


def reset_upload_session(
    session_key: str,
    session_handle: uuid.UUID,
    request_id: str,
    location_id: str = None
) -> None:
    session_info = {
        "session_id": session_handle,
        "request_id": request_id,
        "status": "inited",
    }
    if location_id:
        session_info["location_id"] = location_id

    redis_client.set(session_key, session_info)


def connection_error_response(
    session_handle: uuid.UUID,
    error_message: str
) -> Dict[str, Any]:
    return {
        "status": "error",
        "code": "CONNECTION_ERROR",
        "data": {
            "error_message": error_message,
        },
        "instruction": [
            "Failed to connect to service. Retry to call the tool again."
        ],
        "trace_id": session_handle,
    }


def server_error_response(
    session_handle: uuid.UUID,
    status_code: int,
    error_message: str
) -> Dict[str, Any]:
    return {
        "status": "error",
        "code": "SERVER_ERROR",
        "data": {
            "status_code": status_code,
            "error_message": error_message,
        },
        "instruction": [
            "Notify user about the error in human-friendly way",
            "Ask user to contact organization administrator for support."
        ],
        "trace_id": session_handle,
    }
