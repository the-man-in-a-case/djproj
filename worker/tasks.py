import os
import time
import json
import redis
from .worker_app import app

RESULT_REDIS_URL = os.getenv("WORKER_RESULT_REDIS", "redis://redis.djproj.svc.cluster.local:6379/2")

def _emit(pid, event):
    r = redis.from_url(RESULT_REDIS_URL, decode_responses=True)
    r.publish(f"project:{pid}:worker_events", json.dumps(event))

@app.task(name="worker.tasks.handle_target")
def handle_target(project_id: str, run_id: str, target: dict):
    r = redis.from_url(RESULT_REDIS_URL, decode_responses=True)
    try:
        time.sleep(30)
        rk = f"project:{project_id}:results:{run_id}"
        payload = {"run_id": run_id, "project_id": project_id, "target": target, "status": "SUCCESS", "ts": time.time()}
        r.hset(rk, mapping={k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in payload.items()})
        r.incr(f"project:{project_id}:completed_count")
        _emit(project_id, {"run_id": run_id, "status": "SUCCESS", "message": "done"})
        return payload
    except Exception as e:
        r.incr(f"project:{project_id}:errors_count")
        _emit(project_id, {"run_id": run_id, "status": "ERROR", "message": str(e)})
        raise
