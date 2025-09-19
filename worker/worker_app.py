import os
from celery import Celery

# 获取环境变量配置
broker = os.getenv("CELERY_BROKER_URL", "amqp://user:password@rabbitmq.djproj.svc.cluster.local:5672//")
backend = os.getenv("CELERY_RESULT_BACKEND", "redis://redis.djproj.svc.cluster.local:6379/1")

# 创建Celery应用实例
app = Celery("worker", broker=broker, backend=backend)

# 确保任务模块被自动发现
app.autodiscover_tasks(["worker"], force=True)

# 可选：添加配置以提高可靠性
app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
)
