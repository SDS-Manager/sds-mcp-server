from cache import redis_client
import json
import requests
import logging
from config import BACKEND_URL

logger = logging.getLogger(__name__)

def get_cached_api_key(session_id: str = None) -> str:
    """Retrieve cached API key for the session."""

    data = redis_client.get(session_id)

    if not data:
        raise ValueError("No API key found. Please call set_api_key first.")
    
    return json.loads(data)["token"]

async def make_sds_api_call(endpoint: str, token: str, method: str = "GET", data: dict = None) -> dict:
    """Make authenticated API call to SDS Manager with user's API key."""
            
    headers = {
        "Authorization": f"JWT {token}",
        "Content-Type": "application/json"
    }
    
    url = f"{BACKEND_URL}/{endpoint}"
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=30)
        elif method.upper() == "PATCH":
            response = requests.patch(url, headers=headers, json=data, timeout=30)
        elif method.upper() == "PUT":
            response = requests.put(url, headers=headers, json=data, timeout=30)
        elif method.upper() == "DELETE":
            response = requests.delete(url, headers=headers, timeout=30)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()
        return response.json()
        
    except requests.RequestException as e:
        logger.error(f"SDS API call failed: {e}")
        raise ValueError(f"SDS API call failed: {str(e)}")

