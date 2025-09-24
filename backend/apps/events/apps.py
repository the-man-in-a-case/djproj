import threading, logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)

class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.events"

    def ready(self):
        # 启动 Celery 事件监听后台线程（进程内单例）
        try:
            from .celery_events import ensure_event_listener_started
            ensure_event_listener_started()
            logger.info("[events] Celery 事件监听线程已启动")
        except Exception as e:
            logger.error(f"[events] 启动 Celery 事件监听失败: {e}")
