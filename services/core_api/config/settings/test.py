from .base import *  # noqa: F401,F403

DEBUG = False

DATABASES["default"] = env.db(  # noqa: F405
    "DATABASE_URL", default="postgres://orbit:orbit@localhost:5432/orbit_test"
)

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

KAFKA_PRODUCER_ENABLED = False

# Tests must not require a live Redis instance.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
