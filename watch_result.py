#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
watch_results.py

修复点（已实现）：
1) 任务状态机改为“按阶段标志位”：seen_received/seen_started/seen_succeeded/seen_failed/seen_revoked
   - 解决 started/complete 不增长的问题
2) Redis 与 Celery 事件统一入口 _record_transition()，一次且仅一次计数
3) 禁止从 Celery uuid “瞎猜”项目ID；仅当 uuid 已由 Redis 建立映射后，Celery 才合并到同一任务
4) 进度条 OK/ERR 优先取 Redis 计数，缺失时回退本地 project_stats，确保与 Final Statistics 一致
5) Global 与 Project 统计严格对齐，不再出现 OK 数据异常与 clobal successded（typo）冲高

事件来源：
- Redis PubSub：消息中需包含 pid、task_id、task_name、status、run_id（可选）、message（可选）
  status ∈ {RECEIVED, STARTED, SUCCESS, FAILED, ERROR, REVOKED, ...}
- Celery 事件：通过 --celery-broker 指定（可选）。只有在 task_id 已被 Redis 事件“登记”过后，Celery 才参与合并统计算数，避免双计数
"""

import os
import sys
import json
import time
import signal
import argparse
import threading
from datetime import datetime
from typing import Dict, Any, Optional

try:
    import redis
except Exception as e:
    redis = None

# Celery 依赖可选
try:
    from celery import Celery
    from celery.events import EventReceiver
    from celery.events.state import State
except Exception:
    Celery = None
    EventReceiver = None
    State = None

# ====== 颜色与小工具 ======
RESET  = "\033[0m"
BOLD   = "\033[1m"
RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
BLUE   = "\033[34m"
CYAN   = "\033[36m"
GRAY   = "\033[90m"

def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def short(s: Optional[str], n: int = 8) -> str:
    if not s:
        return "-"
    s = str(s)
    return s if len(s) <= n else s[:n]

def progress_bar(total: int, done: int, errs: int, width: int = 40) -> str:
    comp = max(0, min(total, done + errs)) if total > 0 else done + errs
    pct  = 0.0 if total <= 0 else max(0.0, min(1.0, comp / float(total)))
    filled = int(round(width * pct))
    ok_segment = int(round(width * (0 if total <= 0 else done / float(total))))
    bar = "█" * ok_segment + "!" * max(0, filled - ok_segment) + "·" * (width - filled)
    color = GREEN if errs == 0 else RED
    return f"{color}[{bar}] {comp:>3}/{total:<3} ({pct*100:5.1f}%) ok={done} err={errs}{RESET}"

def safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default

# ====== Redis 取数工具（按需调整你的 key 命名）======
def fetch_counts(r: "redis.Redis", pid: str) -> (int, int, int):
    """
    返回 (targets_count, completed_count, errors_count)。
    若没有这些键，返回 0。
    """
    try:
        pipe = r.pipeline()
        pipe.get(f"project:{pid}:targets_count")
        pipe.get(f"project:{pid}:completed_count")
        pipe.get(f"project:{pid}:errors_count")
        res = pipe.execute()
        total = safe_int(res[0], 0)
        done  = safe_int(res[1], 0)
        errs  = safe_int(res[2], 0)
        return total, done, errs
    except Exception:
        return 0, 0, 0

def fetch_result(r: "redis.Redis", pid: str, run_id: str) -> Any:
    """
    示例：尝试读取某个结果 key，可按你的系统自定义。
    """
    if not r:
        return None
    key = f"project:{pid}:result:{run_id}"
    try:
        val = r.get(key)
        if val is None:
            return None
        try:
            return json.loads(val)
        except Exception:
            return val.decode("utf-8", errors="ignore") if isinstance(val, (bytes, bytearray)) else val
    except Exception:
        return None

# ====== 主监控类 ======
class Watcher:
    def __init__(self,
                 redis_url: str,
                 redis_channel: str,
                 celery_broker: Optional[str] = None,
                 suppress_celery_heartbeats: bool = True):
        self.redis_url = redis_url
        self.redis_channel = redis_channel
        self.celery_broker = celery_broker
        self.suppress_celery_heartbeats = suppress_celery_heartbeats

        # Redis
        self.r: Optional["redis.Redis"] = None
        self.pubsub = None

        # 运行标志
        self._stop = threading.Event()

        # Celery 监控
        self.celery_app: Optional["Celery"] = None
        self.celery_state: Optional["State"] = State() if State else None

        # 统计：全局 & 项目
        self.global_stats: Dict[str, int] = {
            "received": 0,
            "started": 0,
            "succeeded": 0,
            "failed": 0,
        }
        self.project_stats: Dict[str, Dict[str, int]] = {}
        # 已知任务（用于去重与 Celery 合并）：key = f"{pid}:{task_id}"
        self.task_status_tracker: Dict[str, Dict[str, Any]] = {}

        # 统计 Celery 事件（仅作观测，不参与总口径）
        self.celery_counts: Dict[str, int] = {
            "received": 0, "started": 0, "succeeded": 0, "failed": 0,
            "retried": 0, "revoked": 0
        }

        # 线程
        self._threads = []

    # ---------- 初始化 ----------
    def init_redis(self):
        if not redis:
            print(f"{RED}[ERR]{RESET} 未安装 redis-py，请先 pip install redis")
            sys.exit(2)
        self.r = redis.from_url(self.redis_url, decode_responses=False)
        self.pubsub = self.r.pubsub(ignore_subscribe_messages=True)
        self.pubsub.subscribe(self.redis_channel)
        print(f"{ts()} {GREEN}[OK]{RESET} 连接 Redis: {self.redis_url}，订阅频道: {self.redis_channel}")

    def init_celery(self):
        if not self.celery_broker:
            return
        if not Celery:
            print(f"{YELLOW}[WARN]{RESET} 未安装 celery（或 celery.events），跳过 Celery 事件监听")
            return
        self.celery_app = Celery(broker=self.celery_broker)
        print(f"{ts()} {GREEN}[OK]{RESET} 连接 Celery Broker: {self.celery_broker}")

    # ---------- 统计与去重 ----------
    def _ensure_project(self, pid: str):
        if pid and pid not in self.project_stats:
            self.project_stats[pid] = {"received": 0, "started": 0, "succeeded": 0, "failed": 0}

    def _ensure_task(self, pid: str, task_id: str, task_name: str = "unknown") -> str:
        task_key = f"{pid}:{task_id}"
        if task_key not in self.task_status_tracker:
            self.task_status_tracker[task_key] = {
                "pid": pid,
                "task_id": task_id,
                "task_name": task_name,
                "seen_received": False,
                "seen_started": False,
                "seen_succeeded": False,
                "seen_failed": False,
                "seen_revoked": False,
                "has_redis_event": False,
                "has_celery_event": False,
            }
        return task_key

    def _record_transition(self, pid: Optional[str], task_id: str, phase: str) -> bool:
        """
        记录任务状态迁移，返回是否“首次”记录（首次才+1）
        phase ∈ {'RECEIVED','STARTED','SUCCESS','FAILED','ERROR','REVOKED'}
        无 pid 的事件不会更新 project/global（避免与 Redis 事件重复计数）
        """
        if not pid:
            return False

        self._ensure_project(pid)
        task_key = self._ensure_task(pid, task_id)
        t = self.task_status_tracker[task_key]

        mapped = {
            "RECEIVED": "seen_received",
            "STARTED": "seen_started",
            "SUCCESS":  "seen_succeeded",
            "FAILED":   "seen_failed",
            "ERROR":    "seen_failed",   # 归并到 failed
            "REVOKED":  "seen_revoked",
        }
        if phase not in mapped:
            return False

        flag = mapped[phase]
        if t.get(flag):
            return False  # 已统计过

        # 首次计数
        t[flag] = True

        # 项目/全局更新
        if phase == "RECEIVED":
            self.project_stats[pid]["received"] += 1
            self.global_stats["received"] += 1
        elif phase == "STARTED":
            self.project_stats[pid]["started"] += 1
            self.global_stats["started"] += 1
        elif phase == "SUCCESS":
            self.project_stats[pid]["succeeded"] += 1
            self.global_stats["succeeded"] += 1
        elif phase in ("FAILED", "ERROR"):
            self.project_stats[pid]["failed"] += 1
            self.global_stats["failed"] += 1
        elif phase == "REVOKED":
            # 如需计入单独统计可扩展
            pass

        self._display_global_progress()
        return True

    def _display_global_progress(self):
        rcv = self.global_stats["received"]
        std = self.global_stats["started"]
        scc = self.global_stats["succeeded"]
        fld = self.global_stats["failed"]
        print(f"{GRAY}{ts()}  Global task summary: received={rcv} started={std} succeeded={scc} failed={fld}{RESET}")

    # ---------- 事件处理：Redis ----------
    def _handle_redis_event(self, data: Dict[str, Any]):
        """
        期望 data 包含：
        pid, task_id, task_name, status, run_id(可选), message(可选)
        """
        pid       = data.get("pid")
        task_id   = data.get("task_id")
        task_name = data.get("task_name", "unknown")
        status    = data.get("status", "").upper().strip()
        run_id    = data.get("run_id")
        message   = data.get("message", "")

        if not pid or not task_id or not status:
            print(f"{YELLOW}[WARN]{RESET} Redis 事件缺少必要字段，已忽略: {data}")
            return

        # 初始化并打标
        self._ensure_project(pid)
        task_key = self._ensure_task(pid, task_id, task_name)
        self.task_status_tracker[task_key]["has_redis_event"] = True

        # 状态迁移（首次计数）
        if status == "RECEIVED":
            if self._record_transition(pid, task_id, "RECEIVED"):
                print(f"{ts()}  {BLUE}➤ REDIS TASK RECEIVED{RESET}  pid={short(pid)}  task={task_name}  id={short(task_id)}")
        elif status == "STARTED":
            if self._record_transition(pid, task_id, "STARTED"):
                print(f"{ts()}  {YELLOW}▶ REDIS TASK STARTED{RESET}   pid={short(pid)}  task={task_name}  id={short(task_id)}")
        elif status == "SUCCESS":
            if self._record_transition(pid, task_id, "SUCCESS"):
                print(f"{ts()}  pid={short(pid)}  run={short(run_id)}  status=SUCCESS  msg={message}")
                if run_id and self.r:
                    result = fetch_result(self.r, pid, run_id)
                    result_str = ""
                    try:
                        result_str = json.dumps(result, ensure_ascii=False, default=str)
                    except Exception:
                        result_str = str(result)
                    if result_str and len(result_str) > 160:
                        result_str = result_str[:160] + "..."
                    print(f"     {CYAN}Result:{RESET} {result_str}")
        elif status in ["ERROR", "FAILED"]:
            if self._record_transition(pid, task_id, status):
                error_msg = data.get("error", message)
                print(f"{ts()}  pid={short(pid)}  run={short(run_id)}  status={status}  msg={error_msg}")
        elif status == "REVOKED":
            if self._record_transition(pid, task_id, "REVOKED"):
                print(f"{ts()}  pid={short(pid)}  run={short(run_id)}  status=REVOKED  msg={message}")
        else:
            print(f"{ts()}  pid={short(pid)}  run={short(run_id)}  status={status}  msg={message}")

        # —— 进度条：优先 Redis 计数，回退本地 —— 
        if self.r and pid:
            total, done_redis, errs_redis = fetch_counts(self.r, pid)
            done_local = self.project_stats[pid]["succeeded"]
            errs_local = self.project_stats[pid]["failed"]
            done = done_redis if done_redis else done_local
            errs = errs_redis if errs_redis else errs_local
            if total > 0:
                print(f"     {progress_bar(total, done, errs)}")

    def _redis_loop(self):
        while not self._stop.is_set():
            try:
                msg = self.pubsub.get_message(timeout=1.0)
                if not msg:
                    continue
                if msg["type"] != "message":
                    continue
                raw = msg["data"]
                if isinstance(raw, (bytes, bytearray)):
                    raw = raw.decode("utf-8", errors="ignore")
                try:
                    data = json.loads(raw)
                except Exception:
                    print(f"{YELLOW}[WARN]{RESET} Redis 消息不是 JSON：{raw}")
                    continue
                self._handle_redis_event(data)
            except Exception as e:
                print(f"{RED}[ERR]{RESET} Redis 监听异常：{e}")
                time.sleep(1.0)

    # ---------- 事件处理：Celery ----------
    def _handle_celery_event(self, e: Dict[str, Any]):
        """
        仅当该 task_id 已被 Redis 事件登记过（即我们知道 pid）时，才纳入 project/global 统计；
        否则只做观测，不更新统计（避免与 Redis 双计数）。
        """
        typ = e.get("type", "")
        if self.suppress_celery_heartbeats and typ.endswith("worker-heartbeat"):
            return

        if self.celery_state:
            self.celery_state.event(e)

        tid = e.get("uuid", "")
        tname = e.get("name", "unknown")
        hostname = e.get("hostname", "unknown")

        # 查找是否已匹配到已知任务（通过 Redis 先登记）
        pid = None
        for task_key, task_info in self.task_status_tracker.items():
            if task_info.get("task_id") == tid:
                pid = task_info.get("pid")
                break

        # 事件类型归并
        if typ.endswith("task-received"):
            self.celery_counts["received"] += 1
            if pid:
                self._record_transition(pid, tid, "RECEIVED")
        elif typ.endswith("task-started"):
            self.celery_counts["started"] += 1
            if pid:
                self._record_transition(pid, tid, "STARTED")
        elif typ.endswith("task-succeeded"):
            self.celery_counts["succeeded"] += 1
            if pid:
                self._record_transition(pid, tid, "SUCCESS")
        elif typ.endswith("task-failed"):
            self.celery_counts["failed"] += 1
            if pid:
                self._record_transition(pid, tid, "FAILED")
        elif typ.endswith("task-revoked"):
            self.celery_counts["revoked"] += 1
            if pid:
                self._record_transition(pid, tid, "REVOKED")
        elif typ.endswith("task-retried"):
            self.celery_counts["retried"] += 1

        # 输出一行日志
        extra = []
        if "runtime" in e:
            try:
                extra.append(f"runtime={float(e['runtime']):.3f}s")
            except Exception:
                pass
        if "retries" in e:
            extra.append(f"retries={e.get('retries')}")
        if typ.endswith("task-failed") and "exception" in e:
            extra.append(f"exc={e.get('exception', 'unknown')}")

        print(f"{ts()}  {CYAN}CELERY EVENT:{RESET} {typ}  id={short(tid)}  name={tname}  host={hostname}  {' '.join(extra)}")

    def _celery_loop(self):
        if not self.celery_app:
            return
        try:
            with self.celery_app.connection() as conn:
                recv = EventReceiver(conn, handlers={"*": self._handle_celery_event})
                print(f"{ts()} {GREEN}[OK]{RESET} 开始接收 Celery 事件...")
                recv.capture(limit=None, timeout=None, wakeup=True)
        except Exception as e:
            if not self._stop.is_set():
                print(f"{RED}[ERR]{RESET} Celery 事件监听异常：{e}")
            time.sleep(1.0)

    # ---------- 控制 ----------
    def start(self):
        self.init_redis()
        if self.celery_broker:
            self.init_celery()

        t1 = threading.Thread(target=self._redis_loop, name="redis-loop", daemon=True)
        self._threads.append(t1)
        t1.start()

        if self.celery_app:
            t2 = threading.Thread(target=self._celery_loop, name="celery-loop", daemon=True)
            self._threads.append(t2)
            t2.start()

        print(f"{ts()} {GREEN}[RUN]{RESET} 监控已启动。按 Ctrl+C 退出。")

        # 主线程阻塞直到退出
        try:
            while not self._stop.is_set():
                time.sleep(0.3)
        except KeyboardInterrupt:
            print()
            self.stop()

    def stop(self):
        if self._stop.is_set():
            return
        print(f"{ts()} {YELLOW}[STOP]{RESET} 停止中...")
        self._stop.set()
        try:
            if self.pubsub:
                self.pubsub.close()
        except Exception:
            pass
        # 等线程收尾
        for t in self._threads:
            if t.is_alive():
                t.join(timeout=1.0)
        self._print_final_statistics()

    # ---------- 终端汇总 ----------
    def _print_final_statistics(self):
        print("\n" + BOLD + "=" * 60 + RESET)
        print(BOLD + "Final Statistics" + RESET)
        print("-" * 60)
        print(f"Global: received={self.global_stats['received']}  started={self.global_stats['started']}  "
              f"succeeded={self.global_stats['succeeded']}  failed={self.global_stats['failed']}")
        print("-" * 60)
        if not self.project_stats:
            print("(no project stats)")
        else:
            for pid, st in self.project_stats.items():
                print(f"Project {pid}: received={st['received']}  started={st['started']}  "
                      f"succeeded={st['succeeded']}  failed={st['failed']}")
        print("=" * 60 + "\n")

# ====== CLI ======
def parse_args():
    p = argparse.ArgumentParser(description="Watch task results from Redis and Celery with de-dup & aligned stats.")
    p.add_argument("--redis-url", default=os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
                   help="Redis connection URL")
    p.add_argument("--redis-channel", default=os.environ.get("REDIS_CHANNEL", "task_events"),
                   help="Redis PubSub channel name")
    p.add_argument("--celery-broker", default=os.environ.get("CELERY_BROKER_URL", ""),
                   help="Celery broker URL (optional). Example: amqp://guest:guest@127.0.0.1:5672//")
    p.add_argument("--no-suppress-heartbeat", action="store_true",
                   help="Do not suppress Celery worker-heartbeat events")
    return p.parse_args()

def main():
    args = parse_args()
    watcher = Watcher(
        redis_url=args.redis_url,
        redis_channel=args.redis_channel,
        celery_broker=(args.celery_broker or None),
        suppress_celery_heartbeats=(not args.no_suppress_heartbeat),
    )

    # 优雅退出
    def _sigterm(sig, frame):
        watcher.stop()
    signal.signal(signal.SIGTERM, _sigterm)
    signal.signal(signal.SIGINT,  _sigterm)

    watcher.start()

if __name__ == "__main__":
    main()
