import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("SECRET_KEY", "dev-key")
DEBUG = bool(int(os.getenv("DEBUG", "1")))
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "channels",
    "apps.core",
    "apps.api",
    "apps.factory",
    "apps.events",
    "apps.metrics",
    'corsheaders',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "project.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "static"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "project.wsgi.application"  # not used, but fine
ASGI_APPLICATION = "project.asgi.application"

# Channels / Redis
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB   = int(os.getenv("REDIS_DB", "0"))
REDIS_URL  = os.getenv("REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}")

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [REDIS_URL]},
    },
}

# DB (SQLite for demo)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Static
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Broker / Influx
RABBITMQ_HOST=os.getenv("RABBITMQ_HOST","rabbitmq")
RABBITMQ_PORT=int(os.getenv("RABBITMQ_PORT","5672"))
RABBITMQ_USER=os.getenv("RABBITMQ_USER","admin")
RABBITMQ_PASSWORD=os.getenv("RABBITMQ_PASSWORD","password")
RABBITMQ_VHOST=os.getenv("RABBITMQ_VHOST","/")
RABBITMQ_URL=os.getenv("RABBITMQ_URL", f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}{RABBITMQ_VHOST}")
RABBITMQ_QUEUE=os.getenv("RABBITMQ_QUEUE","actions")

INFLUX_URL=os.getenv("INFLUX_URL","http://influxdb:8086")
INFLUX_TOKEN=os.getenv("INFLUX_TOKEN","dev-token")
INFLUX_ORG=os.getenv("INFLUX_ORG","demo-org")
INFLUX_BUCKET=os.getenv("INFLUX_BUCKET","demo-bucket")

CORS_ALLOW_ALL_ORIGINS = True  # 开发环境，生产环境应限制
