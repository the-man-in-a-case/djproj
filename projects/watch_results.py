
import argparse
import json
import os
import signal
import sys
import time
from datetime import datetime
from typing import Dict, Any, Optional
import threading
import logging

# 配置日志，禁用kombu.mixins的INFO级别日志
def configure_logging():
    # 设置根日志级别
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    # 禁用kombu.mixins的INFO级别日志
    logging.getLogger('kombu.mixins').setLevel(logging.WARNING)
    # 禁用其他可能产生过多日志的模块
    logging.getLogger('celery').setLevel(logging.WARNING)
    return logging.getLogger('watch_results')

logger = configure_logging()

# 尝试导入必要的库
try:
    import redis  # type: ignore
except Exception as e:
    print("This script requires the 'redis' package. pip install redis")
    raise

try:
    from celery import Celery
    from celery.events.state import State
    from celery.events import EventReceiver
except Exception as e:
    print("This script requires the 'celery' package. pip install celery")
    raise

# 从环境变量获取默认连接信息，提供合理的默认值
DEFAULT_REDIS_URL = os.getenv("WORKER_RESULT_REDIS", "redis://localhost:6379/2")
DEFAULT_CELERY_BROKER = os.getenv("CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//")

# ANSI 颜色代码定义
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
PURPLE = "\033[95m"

# 任务状态颜色映射
task_state_colors = {
    'RECEIVED': BLUE,
    'STARTED': YELLOW,
    'SUCCESS': GREEN,
    'ERROR': RED,
    'FAILED': RED,
    'REVOKED': YELLOW
}

# Celery 事件类型颜色映射
celery_event_colors = {
    'task-received': BLUE,
    'task-started': YELLOW,
    'task-succeeded': GREEN,
    'task-failed': RED,
    'task-revoked': YELLOW,
    'worker-online': CYAN,
    'worker-offline': RED,
    'worker-heartbeat': PURPLE  # 虽然定义了颜色，但不会打印该类型事件
}

# 不需要打印的 Celery 事件类型
suppressed_events = {'worker-heartbeat'}

def ts() -> str:
    """返回当前时间的格式化字符串（时分秒）"""
    return datetime.now().strftime("%H:%M:%S")

def short(s: str, n: int = 8) -> str:
    """将字符串截断到指定长度，保持简洁显示"""
    return s if len(s) <= n else s[:n]

def int_or_zero(v: Any) -> int:
    """将输入转换为整数，如果转换失败则返回0"""
    try:
        return int(v)
    except Exception:
        return 0

def progress_bar(total: int, done: int, errs: int, width: int = 40) -> str:
    """生成进度条字符串，使用指定格式显示"""
    comp = done + errs
    if total <= 0:
        pct = 0.0
    else:
        pct = max(0.0, min(1.0, comp / float(total)))
    filled = int(round(width * pct))
    bar = "·" * filled + "·" * (width - filled)  # 使用点号填充
    color = GREEN if errs == 0 else RED
    return f"{color}[{bar}] {comp:>3}/{total:<3} ({'{:5.1f}'.format(pct*100)}%) ok={done} err={errs}{RESET}"

def fetch_counts(r: "redis.Redis", pid: str) -> tuple[int, int, int]:
    """从 Redis 获取项目的目标总数、已完成数和错误数"""
    total = int_or_zero(r.get(f"project:{pid}:targets_count"))
    done = int_or_zero(r.get(f"project:{pid}:completed_count"))
    errs = int_or_zero(r.get(f"project:{pid}:errors_count"))
    return total, done, errs

def fetch_result(r: "redis.Redis", pid: str, run_id: str) -> Dict[str, Any]:
    """从 Redis 获取特定运行 ID 的结果"""
    key = f"project:{pid}:results:{run_id}"
    data = r.hgetall(key) or {}
    # 尝试对值进行 JSON 解码
    out: Dict[str, Any] = {}
    for k, v in data.items():
        try:
            out[k] = json.loads(v)
        except Exception:
            out[k] = v
    return out

class Watcher:
    """监控器类，用于监控 Redis 和 Celery 事件"""
    def __init__(self, redis_url: str, celery_broker: str, project_id: str = "", exit_when_done: bool = False):
        """
        初始化监控器
        
        参数:
            redis_url: Redis 服务器连接 URL
            celery_broker: Celery 消息代理 URL
            project_id: 要监控的特定项目 ID，空字符串表示监控所有项目
            exit_when_done: 当特定项目完成时是否退出
        """
        self.redis_url = redis_url
        self.celery_broker = celery_broker
        self.project_id = project_id
        self.exit_when_done = exit_when_done
        
        # Redis 相关初始化
        self.r = redis.from_url(redis_url, decode_responses=True)
        self.ps = self.r.pubsub(ignore_subscribe_messages=True)
        
        # Celery 相关初始化
        self.app = Celery("watcher")
        self.app.conf.broker_url = celery_broker
        self.celery_state = State()
        
        # 跟踪状态
        self.stop_event = threading.Event()
        self.task_status_tracker: Dict[str, Dict[str, Any]] = {}
        self.project_stats: Dict[str, Dict[str, int]] = {}
        self.global_stats = {"received": 0, "started": 0, "succeeded": 0, "failed": 0}
        
        # Celery 统计计数
        self.celery_counts = {"received": 0, "started": 0, "succeeded": 0, "failed": 0, "retried": 0, "revoked": 0}
        
        # 项目ID到项目名称的映射（用于更友好的显示）
        self.project_names: Dict[str, str] = {}
        
        # 连接到 Redis 频道
        self._subscribe_redis_channels()
        
        print(f"{CYAN}{ts()}  ▶ Connecting to Celery broker: {celery_broker}{RESET}")
        
        # 显示初始全局进度
        self._display_global_progress()
    
    def _subscribe_redis_channels(self):
        """订阅适当的 Redis 频道"""
        if self.project_id:
            channel = f"project:{self.project_id}:worker_events"
            self.ps.subscribe(channel)
            print(f"{CYAN}{ts()}  ▶ Subscribed Redis channel: {channel} @ {self.redis_url}{RESET}")
        else:
            channel = "project:*:worker_events"
            self.ps.psubscribe(channel)
            print(f"{CYAN}{ts()}  ▶ PSubscribed Redis channel pattern: {channel} @ {self.redis_url}{RESET}")
    
    def _display_global_progress(self):
        """显示全局任务进度概览"""
        received = self.global_stats["received"]
        started = self.global_stats["started"]
        succeeded = self.global_stats["succeeded"]
        failed = self.global_stats["failed"]
        
        # 计算正在运行的任务数（已开始但未完成），确保不出现负数
        running = max(0, started - succeeded - failed)
        
        # 确保统计数据的一致性
        succeeded = min(succeeded, received)
        failed = min(failed, received - succeeded)
        running = max(0, started - succeeded - failed)
        
        print(f"{DIM}{ts()}  ⏱ Global Progress: recv={received} running={running} ok={succeeded} fail={failed}{RESET}")

    def _update_global_stats(self, action: str):
        """更新全局统计信息并显示进度"""
        if action in self.global_stats:
            self.global_stats[action] += 1
            # 实时显示全局进度
            self._display_global_progress()

    def _handle_redis_event(self, ch: str, data_str: str):
        """处理从 Redis 接收到的事件"""
        # channel: "project:<pid>:worker_events"
        parts = ch.split(":")
        if len(parts) < 3 or parts[0] != "project" or parts[-1] != "worker_events":
            print(f"{YELLOW}{ts()}  ⚠ ignoring Redis channel: {ch}{RESET}")
            return
        pid = parts[1]

        try:
            payload = json.loads(data_str)
        except Exception:
            payload = {"raw": data_str}

        run_id = payload.get("run_id", "")
        status = payload.get("status", "").upper()
        message = payload.get("message", "")
        task_id = payload.get("task_id", run_id)
        task_name = payload.get("task_name", "unknown")

        # 初始化项目统计信息
        if pid not in self.project_stats:
            self.project_stats[pid] = {"received": 0, "started": 0, "succeeded": 0, "failed": 0}

        # 跟踪任务状态，避免重复计数
        task_key = f"{pid}:{task_id}"
        if task_key not in self.task_status_tracker:
            self.task_status_tracker[task_key] = {"pid": pid, "task_id": task_id, "task_name": task_name, "received_recorded": False, "started_recorded": False, "completed_recorded": False, "final_status": None}
        
        # 标记Redis事件已接收
        self.task_status_tracker[task_key]["has_redis_event"] = True

        # 获取项目计数
        total, done, errs = fetch_counts(self.r, pid)

        # 根据状态更新统计信息和打印输出
        # 为避免重复计数，我们为不同来源的事件设置不同的处理标记
        should_update_global = False
        
        if status == "RECEIVED" and not self.task_status_tracker[task_key]["received_recorded"]:
            self.project_stats[pid]["received"] += 1
            self.task_status_tracker[task_key]["received_recorded"] = True
            should_update_global = True
            print(f"{ts()}  {BLUE}➤ REDIS TASK RECEIVED{RESET}  pid={short(pid)}  task={task_name}  id={short(task_id)}")
            self.task_status_tracker[task_key]["received_at"] = ts()
        elif status == "STARTED" and not self.task_status_tracker[task_key]["started_recorded"]:
            self.project_stats[pid]["started"] += 1
            self.task_status_tracker[task_key]["started_recorded"] = True
            should_update_global = True
            print(f"{ts()}  {YELLOW}▶ REDIS TASK STARTED{RESET}   pid={short(pid)}  task={task_name}  id={short(task_id)}")
            self.task_status_tracker[task_key]["started_at"] = ts()
        elif status == "SUCCESS" and not self.task_status_tracker[task_key]["completed_recorded"]:
            # 只有在任务未被标记为完成时才更新统计
            self.project_stats[pid]["succeeded"] += 1
            self.task_status_tracker[task_key]["completed_recorded"] = True
            self.task_status_tracker[task_key]["final_status"] = "SUCCESS"
            should_update_global = True
            # 使用指定格式显示进度
            print(f"{ts()}  pid={short(pid)}  run={short(run_id)}  status=SUCCESS  msg={message}")
            # 获取并显示结果
            if run_id:
                result = fetch_result(self.r, pid, run_id)
                result_str = json.dumps(result, ensure_ascii=False, default=str)[:100]
                if len(result_str) >= 100:
                    result_str += "..."
                print(f"     {CYAN}Result:{RESET} {result_str}")
            self.task_status_tracker[task_key]["succeeded_at"] = ts()
        elif status in ["ERROR", "FAILED"] and not self.task_status_tracker[task_key]["completed_recorded"]:
            # 只有在任务未被标记为完成时才更新统计
            self.project_stats[pid]["failed"] += 1
            self.task_status_tracker[task_key]["completed_recorded"] = True
            self.task_status_tracker[task_key]["final_status"] = "FAILED"
            should_update_global = True
            error_msg = payload.get("error", message)
            # 使用指定格式显示进度
            print(f"{ts()}  pid={short(pid)}  run={short(run_id)}  status={status}  msg={error_msg}")
            self.task_status_tracker[task_key]["failed_at"] = ts()
        elif status == "REVOKED" and not self.task_status_tracker[task_key]["completed_recorded"]:
            # 使用指定格式显示进度
            print(f"{ts()}  pid={short(pid)}  run={short(run_id)}  status=REVOKED  msg={message}")
            self.task_status_tracker[task_key]["completed_recorded"] = True
            self.task_status_tracker[task_key]["final_status"] = "REVOKED"
            self.task_status_tracker[task_key]["revoked_at"] = ts()
        else:
            # 打印其他状态的消息
            status_color = task_state_colors.get(status, RESET)
            print(f"{ts()}  pid={short(pid)}  run={short(run_id)}  status={status_color}{status}{RESET}  msg={message}")

        # 如果需要更新全局统计
        if should_update_global:
            action_map = {"RECEIVED": "received", "STARTED": "started", "SUCCESS": "succeeded", "ERROR": "failed", "FAILED": "failed"}
            self._update_global_stats(action_map.get(status, ""))

        # 打印进度条
        if total > 0:
            print(f"     {progress_bar(total, done, errs)}")

        # 确保项目统计数据的一致性
        self._ensure_project_stats_consistency(pid)

        # 如果监控单个项目且已完成，可选择退出
        if self.exit_when_done and self.project_id and total > 0 and (done == total or errs > 0):
            final = "SUCCEEDED" if errs == 0 else "FAILED"
            print(f"{BOLD}{ts()}  ✔ Project {pid} {final}{RESET}")
            self.stop_event.set()

    def _ensure_project_stats_consistency(self, pid: str):
        """确保项目统计数据的一致性"""
        if pid in self.project_stats:
            stats = self.project_stats[pid]
            # 确保成功任务数不大于接收任务数
            stats["succeeded"] = min(stats["succeeded"], stats["received"])
            # 确保失败任务数不大于接收任务数减去成功任务数
            stats["failed"] = min(stats["failed"], stats["received"] - stats["succeeded"])
            # 确保开始任务数至少等于成功任务数加失败任务数
            stats["started"] = max(stats["started"], stats["succeeded"] + stats["failed"])

    def _handle_celery_event(self, e: Dict[str, Any]):
        """处理从 Celery 接收到的事件，过滤掉心跳事件"""
        typ = e.get("type", "")
        
        # 跳过心跳检测事件
        if typ in suppressed_events or typ.endswith('worker-heartbeat'):
            return
        
        self.celery_state.event(e)
        tid = e.get("uuid", "")
        tname = e.get("name", "unknown")
        hostname = e.get("hostname", "unknown")
        
        # 从任务ID中提取可能的项目ID（如果任务ID包含项目信息）
        task_project_id = None
        if ':' in tid:
            task_project_id = tid.split(':')[0]
        
        # 统计
        action = None
        should_update_global = False
        
        # 尝试关联到现有的任务
        matched_task = None
        # 精确匹配：同时匹配项目ID和任务ID
        if task_project_id:
            potential_task_key = f"{task_project_id}:{tid}"
            if potential_task_key in self.task_status_tracker:
                matched_task = potential_task_key
            else:
                # 如果没有精确匹配，尝试查找同一项目的未完成任务
                for task_key, task_info in self.task_status_tracker.items():
                    if task_info["pid"] == task_project_id and not task_info["completed_recorded"]:
                        matched_task = task_key
                        break
        
        # 记录Celery事件计数（仅供参考，不影响全局统计）
        if typ.endswith("task-received"):
            self.celery_counts["received"] += 1
        elif typ.endswith("task-started"):
            self.celery_counts["started"] += 1
        elif typ.endswith("task-succeeded"):
            self.celery_counts["succeeded"] += 1
        elif typ.endswith("task-failed"):
            self.celery_counts["failed"] += 1
        elif typ.endswith("task-retried"):
            self.celery_counts["retried"] += 1
        elif typ.endswith("task-revoked"):
            self.celery_counts["revoked"] += 1
        
        # 只有当没有匹配到Redis任务时，才从Celery事件更新全局统计
        # 这样可以避免重复计数
        if not matched_task:
            if typ.endswith("task-received"):
                action = "received"
                should_update_global = True
                # 如果没有项目ID，初始化一个匿名项目
                if task_project_id and task_project_id not in self.project_stats:
                    self.project_stats[task_project_id] = {"received": 1, "started": 0, "succeeded": 0, "failed": 0}
                elif task_project_id:
                    self.project_stats[task_project_id]["received"] += 1
            elif typ.endswith("task-started"):
                action = "started"
                should_update_global = True
                if task_project_id:
                    self.project_stats[task_project_id]["started"] += 1
            elif typ.endswith("task-succeeded"):
                action = "succeeded"
                should_update_global = True
                if task_project_id:
                    self.project_stats[task_project_id]["succeeded"] += 1
            elif typ.endswith("task-failed"):
                action = "failed"
                should_update_global = True
                if task_project_id:
                    self.project_stats[task_project_id]["failed"] += 1
        
        # 更新全局统计并显示进度
        if should_update_global:
            self._update_global_stats(action)
        
        # 确保项目统计数据的一致性
        if task_project_id in self.project_stats:
            self._ensure_project_stats_consistency(task_project_id)
        
        # 确定事件颜色
        color = celery_event_colors.get(typ, RESET)
        
        # 控制台输出简要行
        extra = []
        if "runtime" in e:
            extra.append(f"runtime={e['runtime']:.3f}s")
        if "retries" in e:
            extra.append(f"retries={e['retries']}")
        if typ.endswith("task-failed"):
            extra.append(f"exc={e.get('exception', 'unknown')}")
            
        # 突出显示 Celery 事件
        print(f"{ts()}  {color}CELERY EVENT:{RESET} {typ}  id={short(tid)}  name={tname}  host={hostname}  {' '.join(extra)}")
        
    def _redis_listener(self):
        """Redis 事件监听器线程函数"""
        while not self.stop_event.is_set():
            try:
                msg = self.ps.get_message(timeout=1.0)
                if not msg:
                    time.sleep(0.05)
                    continue

                # {type: 'message' or 'pmessage', 'channel': '...', 'pattern': '...', 'data': '...'}
                mtype = msg.get("type")
                data_str = msg.get("data")
                ch = msg.get("channel") or msg.get("pattern") or ""

                # For psubscribe, redis-py gives 'pmessage' with 'channel' = actual channel, 'pattern' = subscribed pattern
                if mtype == "pmessage":
                    ch = msg.get("channel") or ch  # real channel
                elif mtype != "message":
                    continue

                if isinstance(data_str, bytes):
                    data_str = data_str.decode("utf-8", "ignore")
                if isinstance(ch, bytes):
                    ch = ch.decode("utf-8", "ignore")

                self._handle_redis_event(ch, data_str)
            except Exception as e:
                print(f"{YELLOW}{ts()}  ⚠ Redis listener error: {e}{RESET}")
                logger.error(f"Redis listener error: {e}")
                time.sleep(1)  # 出错时暂停一下
        
    def _celery_listener(self):
        """Celery 事件监听器线程函数"""
        # 确保开启事件
        try:
            self.app.control.enable_events()
        except Exception:
            # 某些场景 worker 已开启或权限不足，这里忽略错误
            print(f"{YELLOW}{ts()}  ⚠ Failed to enable Celery events (may already be enabled){RESET}")
            logger.warning("Failed to enable Celery events (may already be enabled)")
            
        # 捕获事件
        try:
            with self.app.connection() as conn:
                recv = EventReceiver(conn, handlers={"*": self._handle_celery_event})
                # 以较小的 timeout 循环，便于响应 Ctrl+C
                while not self.stop_event.is_set():
                    try:
                        recv.capture(limit=None, timeout=1, wakeup=True)
                    except Exception:
                        # 超时等非致命错误，继续拉取
                        pass
        except Exception as e:
            print(f"{YELLOW}{ts()}  ⚠ Celery listener error: {e}{RESET}")
            logger.error(f"Celery listener error: {e}")
    
    def run(self):
        """运行监控器主函数"""
        # 创建两个线程分别监听 Redis 和 Celery 事件
        redis_thread = threading.Thread(target=self._redis_listener, daemon=True, name="redis-listener")
        celery_thread = threading.Thread(target=self._celery_listener, daemon=True, name="celery-listener")
        
        # 启动线程
        redis_thread.start()
        celery_thread.start()
        
        # 主线程等待停止信号
        try:
            while not self.stop_event.is_set():
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop_event.set()
            print(f"\n{YELLOW}{ts()}  ← Interrupted, stopping...{RESET}")
        
        # 清理资源
        try:
            self.ps.close()
        except Exception:
            pass
        
        # 等待线程结束
        redis_thread.join(timeout=2)
        celery_thread.join(timeout=2)
        
        print(f"{BOLD}{ts()}  ✔ Watcher stopped{RESET}")
        
        # 打印最终统计信息
        print(f"{BOLD}\nFinal Statistics:{RESET}")
        print(f"Celery events summary: received={self.celery_counts['received']} started={self.celery_counts['started']} succeeded={self.celery_counts['succeeded']} failed={self.celery_counts['failed']} retried={self.celery_counts['retried']} revoked={self.celery_counts['revoked']}")
        
        # 计算并显示全局任务统计
        total_received = self.global_stats["received"]
        total_started = self.global_stats["started"]
        total_succeeded = self.global_stats["succeeded"]
        total_failed = self.global_stats["failed"]
        
        # 确保最终统计数据的一致性
        total_succeeded = min(total_succeeded, total_received)
        total_failed = min(total_failed, total_received - total_succeeded)
        total_started = max(total_started, total_succeeded + total_failed)
        
        print(f"Global task statistics: received={total_received} started={total_started} succeeded={total_succeeded} failed={total_failed}")
        
        # 显示每个项目的统计信息
        for pid, stats in sorted(self.project_stats.items()):
            # 确保项目统计数据的一致性
            stats["succeeded"] = min(stats["succeeded"], stats["received"])
            stats["failed"] = min(stats["failed"], stats["received"] - stats["succeeded"])
            stats["started"] = max(stats["started"], stats["succeeded"] + stats["failed"])
            
            # 计算完成率
            completion_rate = 0.0
            if stats["received"] > 0:
                completion_rate = (stats["succeeded"] + stats["failed"]) / stats["received"] * 100
            
            project_name = self.project_names.get(pid, "")
            name_suffix = f" ({project_name})" if project_name else ""
            print(f"Project {short(pid)}{name_suffix}: received={stats['received']} started={stats['started']} succeeded={stats['succeeded']} failed={stats['failed']} ({completion_rate:.1f}% complete)")

        # 显示未匹配到项目的 Celery 事件统计
        unmatched_received = max(0, self.celery_counts["received"] - total_received)
        unmatched_started = max(0, self.celery_counts["started"] - total_started)
        unmatched_succeeded = max(0, self.celery_counts["succeeded"] - total_succeeded)
        unmatched_failed = max(0, self.celery_counts["failed"] - total_failed)
        
        if any([unmatched_received, unmatched_started, unmatched_succeeded, unmatched_failed]):
            print(f"Unmatched events: received={unmatched_received} started={unmatched_started} succeeded={unmatched_succeeded} failed={unmatched_failed}")

def main():
    """主函数，处理命令行参数并启动监控器"""
    p = argparse.ArgumentParser(description="Watch task status via Redis pub/sub and Celery events.")
    p.add_argument("--redis-url", default=os.getenv("WORKER_RESULT_REDIS", "redis://localhost:6379/2"), help="Redis URL for worker results (default: %(default)s)")
    p.add_argument("--celery-broker", default=os.getenv("CELERY_BROKER_URL", "amqp://guest:guest@localhost:5672//"), help="Celery broker URL (default: %(default)s)")
    p.add_argument("--project-id", default="", help="Watch a specific project id; empty means watch all.")
    p.add_argument("--exit-when-done", action="store_true", help="Exit after the specific project reaches a terminal state.")
    args = p.parse_args()

    print(f"{BOLD}Redis:{RESET} {args.redis_url}  {BOLD}Project:{RESET} {args.project_id or '(all)'}")
    print(f"{BOLD}Celery Broker:{RESET} {args.celery_broker}")
    print(f"{BOLD}Mode:{RESET} Console output only (file output disabled)")
    
    watcher = Watcher(
        redis_url=args.redis_url,
        celery_broker=args.celery_broker,
        project_id=args.project_id,
        exit_when_done=args.exit_when_done
    )
    
    # 处理信号
    def on_sigint(sig, frame):
        watcher.stop_event.set()
        print(f"\n{YELLOW}{ts()}  ← Interrupted, stopping...{RESET}")

    signal.signal(signal.SIGINT, on_sigint)
    signal.signal(signal.SIGTERM, on_sigint)
    
    # 运行监控器
    watcher.run()

if __name__ == "__main__":
    main()
