import redis
from config import REDIS_HOST, REDIS_PORT, REDIS_DB, REDIS_PASSWORD, REDIS_TTL


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
        return self._client.get(key)
    
    def set(self, key: str, value: str):
        """ """
        self._client.set(key, value, ex=REDIS_TTL)
    
    def delete(self, key: str):
        """ """
        self._client.delete(key)


redis_client = RedisClient()