import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret")
DEBUG = os.environ.get("DEBUG","1") == "1"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "corsheaders",
    "channels",
    "server.app"
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "server.urls"
ASGI_APPLICATION = "server.asgi.application"

STATIC_URL = "/static/"
STATIC_ROOT = str(BASE_DIR / "static")
CORS_ALLOW_ALL_ORIGINS = True

# Channels Layer (Redis)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get("CHANNELS_REDIS_URL", "redis://redis:6379/0")]
        }
    }
}

# Influx v2
INFLUX_URL    = os.environ.get("INFLUX_URL","http://influxdb:8086")
INFLUX_TOKEN  = os.environ.get("INFLUX_TOKEN","dev-token")
INFLUX_ORG    = os.environ.get("INFLUX_ORG","dev-org")
INFLUX_BUCKET = os.environ.get("INFLUX_BUCKET","dev-bucket")
MEASUREMENT   = os.environ.get("MEASUREMENT","metrics")

DATA_START_TS = os.environ.get("DATA_START_TS","2024-08-01T00:00:00Z")
DATA_END_TS   = os.environ.get("DATA_END_TS","2024-08-01T01:00:00Z")
DEFAULT_WINDOW_SEC = int(os.environ.get("DEFAULT_WINDOW_SEC","10"))
