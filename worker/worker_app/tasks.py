import os, time, json
import redis
from celery import shared_task

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

@shared_task(name="worker_app.tasks.process_action", bind=True)
def process_action(self, project_id: str, action_id: str, industry: str, node: str, parameter: dict):
    """
    任务逻辑：睡眠30s → 写入 Redis 结果（供 SSE 读取）
    为确保 “一条消息=一个Pod”，请使用：--concurrency=1 --max-tasks-per-child=1 --pool=solo
    """
    time.sleep(30)

    result = {
        "project_id": project_id,
        "action_id": action_id,
        "industry": industry,
        "node": node,
        "parameter": parameter,
        "status": "success",
        "describe": "mock completed",
        "task_id": self.request.id,
    }
    r = redis.Redis.from_url(REDIS_URL, decode_responses=True)
    # 以 task_id 为主键
    r.setex(f"result:{self.request.id}", 3*24*3600, json.dumps(result))
    # 同时也可用 project_id:action_id 建索引
    r.setex(f"result:{project_id}:{action_id}", 3*24*3600, json.dumps(result))
    return result
