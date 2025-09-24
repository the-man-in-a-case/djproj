import json, threading, logging, time
import redis
from django.conf import settings
from django.db import transaction
from .celery_app import celery_event_app
from apps.core.models import Action

logger = logging.getLogger(__name__)
_started = False
_lock = threading.Lock()

def ensure_event_listener_started():
    global _started
    with _lock:
        if _started: return
        t = threading.Thread(target=_run, name="celery-events-listener", daemon=True)
        t.start()
        _started = True

def _run():
    """
    订阅 Celery 事件：task-succeeded & task-failed
    收到后：从 Redis 读取 Worker 写入的结果，落库并通过 Redis pubsub 推给 SSE 视图。
    """
    r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        with celery_event_app.connection() as conn:
            recv = celery_event_app.events.Receiver(conn, handlers={
                'task-succeeded': lambda e: _on_task_event(e, r, "success"),
                'task-failed':    lambda e: _on_task_event(e, r, "failed"),
            })
            logger.info("[events] 开始监听 Celery 事件")
            recv.capture(limit=None, timeout=None, wakeup=True)
    except Exception as e:
        logger.error(f"[events] Celery 事件监听异常: {e}")
        # 退避重试
        time.sleep(5)
        _run()

def _on_task_event(e, r, status: str):
    task_id = e.get('uuid')
    logger.info(f"[events] 捕获任务事件: {status} task_id={task_id}")
    # Worker 会写两类键：结果、以及 project_id+action_id mapping
    result_json = r.get(f"result:{task_id}")
    payload = {"task_id": task_id, "status": status, "describe": ""}
    if result_json:
        try:
            res = json.loads(result_json)
            payload.update(res)
            # 写库（更新 Action 状态与描述）
            try:
                with transaction.atomic():
                    act = Action.objects.select_for_update().get(
                        project_id=res.get("project_id"),
                        action_id=res.get("action_id"),
                    )
                    act.status = status
                    act.describe = res.get("describe","")
                    act.save()
            except Exception as db_err:
                logger.error(f"[events] 更新数据库失败: {db_err}")
        except Exception as parse_err:
            logger.error(f"[events] 解析 Redis 结果失败: {parse_err}")

    # 发布给 SSE 订阅者（频道按项目分）
    chan = f"events:project:{payload.get('project_id','unknown')}"
    r.publish(chan, json.dumps(payload))
