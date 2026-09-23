from functools import lru_cache

from django.conf import settings


@lru_cache(maxsize=1)
def get_redis_client():
    import redis

    return redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
