import redis
from config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, REDIS_TTL
import json


class RedisClient:
    """ """

    def __init__(self):
        """ """
        self._client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
        )

    def get(self, key: str) -> str:
        """ """
        res = self._client.get(key)

        if res:
            return json.loads(res.decode("utf-8"))
        return None

    def set(self, key: str, value: dict):
        """ """
        self._client.set(key, json.dumps(value), ex=REDIS_TTL)

    def setex(self, key: str, time: int, value: str):
        """Set key with expiration time in seconds"""
        self._client.setex(key, time, value)

    def delete(self, key: str):
        """ """
        self._client.delete(key)


redis_client = RedisClient()
