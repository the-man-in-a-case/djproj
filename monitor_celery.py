#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时观察 Celery 任务状态并收集结果到 JSONL 文件。

用法示例：
  export CELERY_BROKER_URL=amqp://user:pass@rabbitmq:5672/
  export CELERY_RESULT_BACKEND=redis://redis:6379/0
  python monitor_celery.py --outfile results.jsonl --summary-every 5
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

from celery import Celery
from celery.result import AsyncResult
from celery.events.state import State
from celery.events import EventReceiver

def now_iso():
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"

class CeleryMonitor:
    def __init__(self,
                 broker_url: str,
                 result_backend: Optional[str],
                 outfile: str,
                 console: bool = True,
                 summary_every: int = 5):
        self.app = Celery("monitor")
        self.app.conf.broker_url = broker_url
        if result_backend:
            self.app.conf.result_backend = result_backend

        self.outfile_path = outfile
        self.console = console
        self.summary_every = max(0, summary_every)
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self.state = State()               # 聚合所有任务状态
        self.counts = {"received": 0, "started": 0, "succeeded": 0, "failed": 0, "retried": 0, "revoked": 0}
        self.last_summary_t = time.time()

        # 打开输出文件（追加）
        self.outfile = open(self.outfile_path, "a", encoding="utf-8")

    # 将对象转为可序列化（防止 result/args 不可 JSON 化）
    @staticmethod
    def _safe(obj):
        try:
            json.dumps(obj)
            return obj
        except Exception:
            return repr(obj)

    def _log_console(self, msg: str):
        if self.console:
            print(msg, flush=True)

    def _write_jsonl(self, record: Dict[str, Any]):
        self.outfile.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.outfile.flush()

    def _collect_result(self, task_id: str):
        """在任务结束(成功/失败/撤销)时，尽量从后端取结果"""
        try:
            ar = AsyncResult(task_id, app=self.app)
            data = {
                "id": task_id,
                "state": ar.state,
                "ready": ar.ready(),
                "successful": None,
                "result": None,
                "traceback": None,
            }
            if ar.ready():
                data["successful"] = ar.successful()
                # 注意：某些 backend 的 result 可能不是 JSON 可序列化
                data["result"] = self._safe(ar.result)
                data["traceback"] = ar.traceback
            return data
        except Exception as e:
            return {"id": task_id, "error": f"result_fetch_failed: {e}"}

    def _on_event(self, e: Dict[str, Any]):
        with self._lock:
            self.state.event(e)
            typ = e.get("type", "")
            tid = e.get("uuid")
            tname = e.get("name")
            hostname = e.get("hostname")
            # 统计
            if typ.endswith("task-received"):
                self.counts["received"] += 1
            elif typ.endswith("task-started"):
                self.counts["started"] += 1
            elif typ.endswith("task-succeeded"):
                self.counts["succeeded"] += 1
            elif typ.endswith("task-failed"):
                self.counts["failed"] += 1
            elif typ.endswith("task-retried"):
                self.counts["retried"] += 1
            elif typ.endswith("task-revoked"):
                self.counts["revoked"] += 1

            # 控制台输出简要行
            if self.console and typ.startswith("task-"):
                ts = datetime.utcnow().strftime("%H:%M:%S")
                extra = []
                if "runtime" in e:
                    extra.append(f"runtime={e['runtime']:.3f}s")
                if "retries" in e:
                    extra.append(f"retries={e['retries']}")
                if typ.endswith(("task-failed",)):
                    extra.append(f"exc={e.get('exception')}")
                print(f"[{ts}] {typ}  id={tid}  name={tname}  host={hostname}  {' '.join(extra)}", flush=True)

            # 在“最终态”落盘一条完整记录
            if typ.endswith(("task-succeeded", "task-failed", "task-revoked")) and tid:
                t = self.state.tasks.get(tid)
                record = {
                    "ts": now_iso(),
                    "event": typ,
                    "id": tid,
                    "name": getattr(t, "name", tname),
                    "hostname": hostname,
                    "args": self._safe(getattr(t, "args", e.get("args"))),
                    "kwargs": self._safe(getattr(t, "kwargs", e.get("kwargs"))),
                    "runtime": getattr(t, "runtime", e.get("runtime")),
                    "retries": getattr(t, "retries", e.get("retries")),
                    "exception": e.get("exception"),
                }
                # 拼接 result 后端数据
                record.update(self._collect_result(tid))
                self._write_jsonl(record)

            # 定期打印汇总
            if self.summary_every > 0:
                now = time.time()
                if now - self.last_summary_t >= self.summary_every:
                    self.last_summary_t = now
                    total = len(self.state.tasks)
                    running = sum(1 for x in self.state.tasks.values() if getattr(x, "state", "") == "STARTED")
                    self._log_console(
                        f"[SUM] total={total} running={running} "
                        f"recv={self.counts['received']} start={self.counts['started']} "
                        f"ok={self.counts['succeeded']} fail={self.counts['failed']} "
                        f"retry={self.counts['retried']} revk={self.counts['revoked']}"
                    )

    def run(self):
        # 确保开启事件
        try:
            self.app.control.enable_events()
        except Exception:
            # 某些场景 worker 已开启或权限不足，这里忽略错误
            pass

        self._log_console(f"[info] broker={self.app.conf.broker_url} backend={self.app.conf.result_backend}")
        self._log_console(f"[info] writing results to {self.outfile_path}")
        # 捕获事件
        with self.app.connection() as conn:
            recv = EventReceiver(conn, handlers={"*": self._on_event})
            # 以较小的 timeout 循环，便于响应 Ctrl+C
            while not self._stop.is_set():
                try:
                    recv.capture(limit=None, timeout=1, wakeup=True)
                except Exception:
                    # 超时等非致命错误，继续拉取
                    pass

    def stop(self):
        self._stop.set()
        try:
            self.outfile.flush()
            self.outfile.close()
        except Exception:
            pass

def main():
    parser = argparse.ArgumentParser(description="Celery 实时监控与结果采集脚本")
    parser.add_argument("--outfile", default="results.jsonl", help="结果输出 JSONL 文件")
    parser.add_argument("--no-console", action="store_true", help="不在控制台打印实时事件")
    parser.add_argument("--summary-every", type=int, default=5, help="汇总打印间隔秒(0=关闭)")
    args = parser.parse_args()

    broker = os.getenv("CELERY_BROKER_URL")
    backend = os.getenv("CELERY_RESULT_BACKEND")
    if not broker:
        print("ERROR: 请设置环境变量 CELERY_BROKER_URL", file=sys.stderr)
        sys.exit(1)

    mon = CeleryMonitor(
        broker_url=broker,
        result_backend=backend,
        outfile=args.outfile,
        console=not args.no_console,
        summary_every=args.summary_every,
    )

    def _sigint(_sig, _frm):
        mon._log_console("[info] stopping...")
        mon.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sigint)
    signal.signal(signal.SIGTERM, _sigint)

    try:
        mon.run()
    finally:
        mon.stop()

if __name__ == "__main__":
    main()
