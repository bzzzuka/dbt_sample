import os

from cachelib.redis import RedisCache

SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "change_me_to_a_random_string")

RESULTS_BACKEND = RedisCache(
    host=os.environ.get("REDIS_HOST", "redis"),
    port=int(os.environ.get("REDIS_PORT", "6379")),
    db=int(os.environ.get("REDIS_RESULTS_DB", "4")),
    key_prefix="superset_results_",
)
