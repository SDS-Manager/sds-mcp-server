from mcp.server.fastmcp import FastMCP
from cache import redis_client
from typing import Dict, List, Any, Optional
from helper import make_sds_api_call
from config import BACKEND_URL
import logging
import requests
import time
import hashlib
import json


logger = logging.getLogger(__name__)


mcp = FastMCP(
    name="SDS Manager Search",
    stateless_http=True,
)

@mcp.tool(description="Search customer SDS by text query. Returns {results: [...]}.")
def search(query: str) -> Dict[str, Any]:
    """
    Arguments:

        A single query string.

        Returns:

        An array of objects with the following properties:

        id - a unique ID for the document or search result item
        product_name - a string product name for the search result item
        producer_name - a string producer name for the search result item
        
    """


    return {
        "results": [
            {
                "id": "1",
                "product_name": "Acetone",
                "producer_name": "Merck"
            },
            {
                "id": "2",
                "product_name": "Mask",
                "producer_name": "3M United"
            },
            {
                "id": "3",
                "product_name": "Diesel",
                "producer_name": "Thermo Fisher"
            }
        ]
    }


@mcp.tool(description="Fetch a customer SDS by ID. Returns the SDS payload.")
async def fetch(id: str) -> Dict[str, Any]:
    """
        Arguments:

        A string which is a unique identifier for the search document.

        Returns:

        A single object with the following properties:

        id - a unique ID for the document or search result item
        product_name - a string product name for the search result item
        producer_name - a string producer name for the search result item
    """

    mock_map ={
        "1": {
            "id": "1",
            "product_name": "Acetone",
            "producer_name": "Merck",
        },
        "2": {
            "id": "2",
            "product_name": "Mask",
            "producer_name": "3M United"
        },
        "3": {
            "id": "3",
            "product_name": "Diesel",
            "producer_name": "Thermo Fisher"
        }
    }

    # Parse the results
    return mock_map[id]
