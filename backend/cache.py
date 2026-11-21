from flask_caching import Cache
from flask import current_app
from redis.exceptions import RedisError

cache = Cache()

def cached_data(key, loader):
    try:
        value = cache.get(key)
        if value is not None:
            return value
    except RedisError:
        current_app.logger.warning('Redis unavailable; serving database data')
    value = loader()
    try:
        cache.set(key, value, timeout=120)
    except RedisError:
        pass
    return value

def invalidate():
    try:
        cache.delete_many('examinations', 'schedules', 'rubrics')
    except RedisError:
        current_app.logger.warning('Redis unavailable during cache invalidation')
