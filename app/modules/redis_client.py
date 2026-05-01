from redis.asyncio import Redis

from app.core.setting import setting


def get_redis_client() -> Redis:
    return Redis.from_url(setting.REDIS_URI, decode_responses=True)
