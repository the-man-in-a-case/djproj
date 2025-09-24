# backend/apps/events/celery_events.py
"""
同时监听：
1) Celery 全局事件（task-received/started/succeeded/failed/...）
2) Redis 发布的项目特定事件（兼容 project:*:worker_events）

在 SUCCESS/FAILED 时：
- 读取 Redis 中 worker 写入的结果（优先 result:<task_id>；也兼容 project:<pid>:results:<run_id>）
- 更新 Action（status/describe）
- 转发为 SSE payload -> 发布到 events:project:<pid> 频道（由 /api/sse/events 取用）

环境变量（可选）：
- WORKER_EVENTS_CHANNEL_PATTERN：Redis 项目事件的订阅通配（默认 "project:*:worker_events"）
- SSE_EVENTS_CHANNEL_FMT：SSE 转发频道格式（默认 "events:project:{pid}"）
"""

import os
import json
import time
import threading
import logging
from typing import Any, Dict, Optional

import redis
from django.conf import settings
from django.db import transaction

from .celery_app import celery_event_app  # Celery(broker=settings.RABBITMQ_URL)
from apps.core.models import Action

logger = logging.getLogger(__name__)

# ---- 配置 ----
WORKER_EVENTS_CHANNEL_PATTERN = os.getenv("WORKER_EVENTS_CHANNEL_PATTERN", "project:*:worker_events")
SSE_EVENTS_CHANNEL_FMT = os.getenv("SSE_EVENTS_CHANNEL_FMT", "events:project:{pid}")

# 过滤掉噪声事件
SUPPRESSED_EVENTS = {"worker-heartbeat"}

_started = False
_lock = threading.Lock()

def ensure_event_listener_started():
    """
    在 Django AppConfig.ready() 中调用，启动后台监听线程（进程内单例）。
    """
    global _started
    with _lock:
        if _started:
            return
        t = threading.Thread(target=_bootstrap, name="events-mux", daemon=True)
        t.start()
        _started = True
        logger.info("[events] Celery+Redis 事件监听已启动")

def _bootstrap():
    """
    启动两个监听线程：Redis 项目事件 & Celery 全局事件。
    线程内部带重连与异常保护。
    """
    threads = [
        threading.Thread(target=_redis_listener_loop, name="redis-listener", daemon=True),
        threading.Thread(target=_celery_listener_loop, name="celery-listener", daemon=True),
    ]
    for th in threads:
        th.start()

    # 常驻
    while True:
        time.sleep(60)


# ======================================================================================
# Redis 侧：订阅项目特定事件（兼容 "project:*:worker_events"），并转发到 SSE 频道
# ======================================================================================

def _redis_listener_loop():
    while True:
        try:
            r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
            ps = r.pubsub(ignore_subscribe_messages=True)
            # 订阅项目事件（如由 worker 发布）：project:<pid>:worker_events
            ps.psubscribe(WORKER_EVENTS_CHANNEL_PATTERN)
            logger.info(f"[events] Redis PSUBSCRIBE {WORKER_EVENTS_CHANNEL_PATTERN}")

            for msg in ps.listen():
                if not msg or msg.get("type") not in {"message", "pmessage"}:
                    continue

                channel = msg.get("channel") or msg.get("pattern") or ""
                if isinstance(channel, bytes):
                    channel = channel.decode("utf-8", "ignore")
                data_str = msg.get("data")
                if isinstance(data_str, bytes):
                    data_str = data_str.decode("utf-8", "ignore")

                try:
                    _handle_redis_project_event(r, channel, data_str)
                except Exception as e:
                    logger.exception(f"[events] 处理 Redis 项目事件异常: {e}")

        except Exception as e:
            logger.error(f"[events] Redis 监听异常，将在5s后重连：{e}")
            time.sleep(5)

def _handle_redis_project_event(r: "redis.Redis", channel: str, data_str: str):
    """
    处理 worker 发布到 Redis 的项目事件：
    - channel 形如 "project:<pid>:worker_events"
    - data_str 是 JSON payload，建议包含 {run_id, status, message, task_id?, task_name?}
    - 我们兼容读取 project:<pid>:results:<run_id> 哈希，拼装结果，并转发 SSE

    同时：如状态为 SUCCESS/FAILED，则尝试更新 Action 状态。
    """
    parts = channel.split(":")
    if len(parts) < 3 or parts[0] != "project" or parts[-1] != "worker_events":
        # 非项目事件频道，忽略
        return
    pid = parts[1]

    try:
        payload = json.loads(data_str or "{}")
    except Exception:
        payload = {"raw": data_str or ""}

    run_id = str(payload.get("run_id", "") or "")
    status_up = str(payload.get("status", "") or "").upper()
    message = payload.get("message", "")
    task_id = str(payload.get("task_id", "") or "")

    # 兼容读取项目结果哈希 project:<pid>:results:<run_id>
    result = _fetch_project_run_result(r, pid, run_id)

    # 若有确定的终态，尝试更新 DB
    if status_up in {"SUCCESS", "FAILED", "ERROR"}:
        # FAILED/ERROR 均视作失败
        final_status = "success" if status_up == "SUCCESS" else "failed"
        # 优先从 result 中推导 project_id/action_id；否则尝试从 payload 中带来的字段
        project_id = result.get("project_id") or payload.get("project_id") or pid
        action_id = result.get("action_id") or payload.get("action_id") or task_id  # task_id 就是 action_id
        describe = result.get("describe") or payload.get("message") or ""
        _update_action_safe(project_id, action_id, final_status, describe)

    # 转发到 SSE 频道（events:project:<pid>），由 /api/sse/events 返回给前端
    sse_chan = SSE_EVENTS_CHANNEL_FMT.format(pid=pid)
    
    # 构建统一的 SSE 数据格式
    project_id = result.get("project_id") or payload.get("project_id") or pid
    action_id = result.get("action_id") or payload.get("action_id") or task_id  # task_id 就是 action_id
    
    # 获取 Action 信息
    action_name = ""
    industry = []
    try:
        if project_id and action_id:
            act = Action.objects.get(project_id=project_id, action_id=action_id)
            action_name = act.action_name
            # 从关联的 Target 中获取 industry 信息
            # Action 和 Target 是一对多关系，通过 act.target_list.all() 获取所有关联的 Target
            # 这里使用 set 去重后转为 list
            industries = set()
            for target in act.target_list.all():
                industries.add(target.industry)
            industry = list(industries)
    except Exception as e:
        logger.warning(f"[events] 获取 Action 信息失败：{e}")
    
    # 构建 event 字符串
    event_status = status_up.lower()
    if event_status == "success":
        event_type = "success"
    elif event_status == "failed" or event_status == "error":
        event_type = "failed"
    elif event_status == "started":
        event_type = "started"
    else:
        event_type = "received"
    
    # 构建 event 消息内容
    event_message = f"{event_type}-{message or describe or ''}"
    
    # 构建统一格式的 SSE 数据
    sse_data = [{
        "action id": action_id,
        "action name": action_name,
        "industry": industry,
        "event": event_message
    }]
    
    r.publish(sse_chan, json.dumps(sse_data))

def _fetch_project_run_result(r: "redis.Redis", pid: str, run_id: str) -> Dict[str, Any]:
    """
    读取 worker 写入的项目结果：
    - 优先读取哈希：project:<pid>:results:<run_id>
      （字段值若为 JSON 字符串则尝试 json.loads）
    """
    if not pid or not run_id:
        return {}
    key = f"project:{pid}:results:{run_id}"
    data = r.hgetall(key) or {}
    out: Dict[str, Any] = {}
    for k, v in data.items():
        try:
            out[k] = json.loads(v)
        except Exception:
            out[k] = v
    return out


# ======================================================================================
# Celery 侧：监听全局事件（*），在 succeeded/failed 时抓取 result:<task_id> 结果并落库 + SSE
# ======================================================================================

def _celery_listener_loop():
    while True:
        try:
            # 开启事件（可能已开启，无需强依赖）
            try:
                with celery_event_app.connection() as conn:
                    conn.ensure_connection(max_retries=3)
                celery_event_app.control.enable_events()
            except Exception:
                logger.debug("[events] enable_events 可能已开启或权限不足，忽略")

            with celery_event_app.connection() as conn:
                recv = celery_event_app.events.Receiver(conn, handlers={"*": _handle_celery_event})
                logger.info("[events] Celery 全局事件监听开始")
                recv.capture(limit=None, timeout=None, wakeup=True)

        except Exception as e:
            logger.error(f"[events] Celery 监听异常，将在5s后重连：{e}")
            time.sleep(5)

def _handle_celery_event(e: Dict[str, Any]):
    """
    处理 Celery 全局事件：
    - 对 task-succeeded / task-failed：读取 result:<task_id>，落库并转发 SSE
    - 对 task-received / task-started：仅记录/可选更新状态（若能解析到 project_id/action_id）
    - 忽略 worker-heartbeat
    """
    typ = e.get("type", "")
    if typ in SUPPRESSED_EVENTS or typ.endswith("worker-heartbeat"):
        return

    task_id = e.get("uuid", "")
    name = e.get("name", "")
    hostname = e.get("hostname", "")

    # 仅当出现成功/失败时读取 worker 结果
    if typ.endswith("task-succeeded") or typ.endswith("task-failed"):
        final_status = "success" if typ.endswith("task-succeeded") else "failed"
        _process_task_terminal_event(task_id, final_status)
        return

    # 可选：对 received/started 做轻量处理（如后续要统计/看板，可在此扩展）
    if typ.endswith("task-received"):
        logger.info(f"[events] received  id={task_id} name={name} host={hostname}")
        # 尝试获取 project_id 并发布 SSE 事件
        try:
            # 从 task_id 对应的 Action 获取 project_id
            # 注意：这里假设 task_id 就是 action_id
            act = Action.objects.get(action_id=task_id)
            project_id = str(act.project_id)
            
            # 构建统一格式的 SSE 数据
            sse_chan = SSE_EVENTS_CHANNEL_FMT.format(pid=project_id)
            r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
            
            # 获取 industry 信息
            industries = set()
            for target in act.target_list.all():
                industries.add(target.industry)
            industry = list(industries)
            
            sse_data = [{
                "action id": task_id,
                "action name": act.action_name,
                "industry": industry,
                "event": "received-任务已接收"
            }]
            
            r.publish(sse_chan, json.dumps(sse_data))
        except Exception as e:
            logger.warning(f"[events] 发布 received 事件失败：{e}")
    elif typ.endswith("task-started"):
        logger.info(f"[events] started   id={task_id} name={name} host={hostname}")
        # 尝试获取 project_id 并发布 SSE 事件
        try:
            # 从 task_id 对应的 Action 获取 project_id
            # 注意：这里假设 task_id 就是 action_id
            act = Action.objects.get(action_id=task_id)
            project_id = str(act.project_id)
            
            # 构建统一格式的 SSE 数据
            sse_chan = SSE_EVENTS_CHANNEL_FMT.format(pid=project_id)
            r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
            
            # 获取 industry 信息
            industries = set()
            for target in act.target_list.all():
                industries.add(target.industry)
            industry = list(industries)
            
            sse_data = [{
                "action id": task_id,
                "action name": act.action_name,
                "industry": industry,
                "event": "started-任务已开始执行"
            }]
            
            r.publish(sse_chan, json.dumps(sse_data))
        except Exception as e:
            logger.warning(f"[events] 发布 started 事件失败：{e}")
    elif typ.endswith("task-revoked"):
        logger.info(f"[events] revoked   id={task_id} name={name} host={hostname}")
    else:
        # 其他事件按需扩展
        logger.debug(f"[events] {typ} id={task_id} name={name} host={hostname}")

def _process_task_terminal_event(task_id: str, final_status: str):
    """
    终态事件处理：
    - 从 Redis 读取 result:<task_id>
    - 解析出 project_id/action_id/describe 等
    - 更新 Action，并转发到 SSE 频道（events:project:<pid>）
    """
    if not task_id:
        return
    r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    result_json = r.get(f"result:{task_id}")

    payload: Dict[str, Any] = {"task_id": task_id, "status": final_status, "source": "celery"}

    if result_json:
        try:
            res = json.loads(result_json)
            payload.update(res)
            project_id = str(res.get("project_id", "")) or ""
            action_id = str(res.get("action_id", "")) or task_id  # task_id 就是 action_id
            describe = res.get("describe", "") or ""
            
            if project_id and action_id:
                _update_action_safe(project_id, action_id, final_status, describe)
                
                # 获取 Action 信息以构建统一格式的 SSE 数据
                try:
                    act = Action.objects.get(project_id=project_id, action_id=action_id)
                    action_name = act.action_name
                    
                    # 获取 industry 信息
                    industries = set()
                    for target in act.target_list.all():
                        industries.add(target.industry)
                    industry = list(industries)
                    
                    # 构建 event 消息内容
                    event_message = f"{final_status}-{describe}"
                    
                    # 构建统一格式的 SSE 数据
                    sse_data = [{
                        "action id": action_id,
                        "action name": action_name,
                        "industry": industry,
                        "event": event_message
                    }]
                    
                    # SSE 转发
                    sse_chan = SSE_EVENTS_CHANNEL_FMT.format(pid=project_id)
                    r.publish(sse_chan, json.dumps(sse_data))
                except Exception as e:
                    logger.warning(f"[events] 构建并发布统一格式 SSE 数据失败：{e}")
            else:
                logger.warning(f"[events] result 无 project_id：task_id={task_id}")
        except Exception as parse_err:
            logger.error(f"[events] 解析 result 失败：{parse_err}")
    else:
        logger.warning(f"[events] 未找到 result:{task_id}，无法落库/转发")


# ======================================================================================
# 共用：更新数据库 Action
# ======================================================================================

def _update_action_safe(project_id: str, action_id: str, status: str, describe: str = ""):
    """
    安全更新 Action（status/describe），错误不抛出，便于后台线程稳定运行。
    """
    if not project_id or not action_id:
        return
    try:
        with transaction.atomic():
            act = Action.objects.select_for_update().get(project_id=project_id, action_id=action_id)
            act.status = status
            if describe:
                act.describe = describe
            act.save()
        logger.info(f"[events] Action 更新成功：{project_id}/{action_id} -> {status}")
    except Action.DoesNotExist:
        logger.warning(f"[events] 找不到 Action 记录：{project_id}/{action_id}")
    except Exception as e:
        logger.error(f"[events] 更新 Action 失败：{project_id}/{action_id} -> {e}")
