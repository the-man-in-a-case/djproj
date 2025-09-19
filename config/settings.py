import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY","dev-secret")
DEBUG = os.getenv("DEBUG","1") == "1"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS","*").split(",")
INSTALLED_APPS=[
 "django.contrib.admin","django.contrib.auth","django.contrib.contenttypes",
 "django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles",
 "rest_framework","channels","projects","realtime",
]
MIDDLEWARE=[
 "django.middleware.security.SecurityMiddleware",
 "django.contrib.sessions.middleware.SessionMiddleware",
 "django.middleware.common.CommonMiddleware",
 "django.middleware.csrf.CsrfViewMiddleware",
 "django.contrib.auth.middleware.AuthenticationMiddleware",
 "django.contrib.messages.middleware.MessageMiddleware",
 "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF="config.urls"
TEMPLATES=[{"BACKEND":"django.template.backends.django.DjangoTemplates","DIRS":[BASE_DIR/'templates'],"APP_DIRS":True,"OPTIONS":{"context_processors":[
 "django.template.context_processors.debug","django.template.context_processors.request","django.contrib.auth.context_processors.auth","django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION="config.wsgi.application"
ASGI_APPLICATION="config.asgi.application"
DATABASES={"default":{"ENGINE":os.getenv("DB_ENGINE","django.db.backends.sqlite3"),"NAME":os.getenv("DB_NAME",str(BASE_DIR/'db.sqlite3')),"USER":os.getenv("DB_USER",""),"PASSWORD":os.getenv("DB_PASSWORD",""),"HOST":os.getenv("DB_HOST",""),"PORT":os.getenv("DB_PORT","")}}
AUTH_PASSWORD_VALIDATORS=[
 {"NAME":"django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
 {"NAME":"django.contrib.auth.password_validation.MinimumLengthValidator"},
 {"NAME":"django.contrib.auth.password_validation.CommonPasswordValidator"},
 {"NAME":"django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE="zh-hans"; TIME_ZONE="Asia/Shanghai"; USE_I18N=True; USE_TZ=True
STATIC_URL="static/"; DEFAULT_AUTO_FIELD="django.db.models.BigAutoField"
CHANNEL_LAYERS={"default":{"BACKEND":"channels_redis.core.RedisChannelLayer","CONFIG":{"hosts":[os.getenv("CHANNEL_REDIS_URL","redis://redis.djproj.svc.cluster.local:6379/0")]}}}
CELERY_BROKER_URL=os.getenv("CELERY_BROKER_URL","amqp://user:password@rabbitmq.djproj.svc.cluster.local:5672//")
CELERY_RESULT_BACKEND=os.getenv("CELERY_RESULT_BACKEND","redis://redis.djproj.svc.cluster.local:6379/1")
WORKER_TASK_NAME=os.getenv("WORKER_TASK_NAME","worker.tasks.handle_target")
WORKER_QUEUE_NAME=os.getenv("WORKER_QUEUE_NAME","celery")
WORKER_RESULT_REDIS=os.getenv("WORKER_RESULT_REDIS","redis://redis.djproj.svc.cluster.local:6379/2")
INFLUX_URL=os.getenv("INFLUX_URL","http://influxdb.djproj.svc.cluster.local:8086")
INFLUX_TOKEN=os.getenv("INFLUX_TOKEN","dev-token")
INFLUX_ORG=os.getenv("INFLUX_ORG","dev-org")
INFLUX_BUCKET=os.getenv("INFLUX_BUCKET","dev-bucket")
K8S_INCLUSTER=os.getenv("K8S_INCLUSTER","0")=="1"
K8S_CONTEXT=os.getenv("K8S_CONTEXT")
K8S_DEFAULT_NAMESPACE=os.getenv("K8S_DEFAULT_NAMESPACE","default")
DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE', 'django.db.backends.sqlite3'),
        'NAME': os.getenv('DB_NAME', str(BASE_DIR / 'data' / 'db.sqlite3')),  # 将数据库文件放在data目录
        'USER': os.getenv('DB_USER', ''),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', ''),
        'PORT': os.getenv('DB_PORT', ''),
        # SQLite特定配置
        'OPTIONS': {
            'timeout': 30,  # 增加超时时间防止锁问题
        }
    }
}