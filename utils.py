from cache import redis_client
import requests
import uuid
from typing import Dict, Any, Tuple


def validate_session(session_handle: uuid.UUID) -> Tuple[Dict[str, Any], bool, bool]:
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

    if not info.get("logged_in"):
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

    redis_client.set(session_key, info)
    return info, False


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
