import os
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")
REDIS_TTL = int(os.getenv("REDIS_TTL", "3600"))

PORT = int(os.getenv("PORT", 10000))

SECRET_KEY = os.getenv("SECRET_KEY")

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000/mcp")
SDS_HEADER_NAME = os.getenv("SDS_HEADER_NAME", "X-MCP-API-KEY")
