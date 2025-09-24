# backend/apps/metrics/influx_queries.py
from __future__ import annotations
from typing import List, Dict, Any, Optional, Sequence, Tuple
import re
import math
from django.conf import settings

try:
    from influxdb_client import InfluxDBClient
except Exception:  # 库缺失时允许上层 fallback
    InfluxDBClient = None

# ===== 基础工具 =====

def _open_client() -> Optional[InfluxDBClient]:
    if InfluxDBClient is None:
        return None
    return InfluxDBClient(
        url=settings.INFLUX_URL,
        token=settings.INFLUX_TOKEN,
        org=settings.INFLUX_ORG
    )

def _exec_query(flux: str) -> List[Dict[str, Any]]:
    """
    执行 flux 并把每条记录转为 dict（保留 tags/fields；将 _time 标为 time）
    """
    client = _open_client()
    if client is None:
        return []

    try:
        tables = client.query_api().query(flux)
        out: List[Dict[str, Any]] = []
        for table in tables:
            for rec in table.records:
                row = dict(rec.values)
                if "_time" in row:
                    row["time"] = row.pop("_time").isoformat()
                for k in ["_measurement","_start","_stop","result","table","_table","_field","_value"]:
                    row.pop(k, None)
                out.append(row)
        return out
    finally:
        try:
            client.close()
        except Exception:
            pass

# ===== 业务查询 =====

def list_measurements_for_task(bucket: str, task_id: str, start: str = "-90d") -> List[str]:
    """
    列出指定 task_id 的所有 measurement（容器名）
    """
    flux = f'''
from(bucket: "{bucket}")
  |> range(start: {start})
  |> filter(fn: (r) => r.task_id == "{task_id}")
  |> keep(columns: ["_measurement"])
  |> group()
  |> distinct(column: "_measurement")
'''
    rows = _exec_query(flux)
    mset = set()
    for r in rows:
        # distinct(column:"_measurement") 的值通常在 _value 或 _measurement 字段
        m = r.get("_measurement") or r.get("_value")
        if m:
            mset.add(str(m))
    return sorted(mset)

def list_steps_for_task_measurement(bucket: str, task_id: str, measurement: str, start: str = "-90d") -> List[str]:
    """
    列出某个 task+measurement 的所有 step（字符串，按数值优先排序）
    """
    flux = f'''
from(bucket: "{bucket}")
  |> range(start: {start})
  |> filter(fn: (r) => r._measurement == "{measurement}" and r.task_id == "{task_id}")
  |> keep(columns: ["step"])
  |> group()
  |> distinct(column: "step")
'''
    rows = _exec_query(flux)
    steps: List[str] = []
    for r in rows:
        val = r.get("step") or r.get("_value")
        if val is not None:
            steps.append(str(val))

    # 尝试按数值排序（非数字则按字符串）
    def _key(s: str):
        try:
            return (0, float(s))
        except Exception:
            return (1, s)
    steps.sort(key=_key)
    return steps

def choose_steps_by_percentage(steps: Sequence[str], percentage: float, window: int = 0) -> List[str]:
    """
    根据 0~100% 在 steps 上定位一个 index，并在其左右各取 window 个 step。
    """
    if not steps:
        return []
    pct = max(0.0, min(100.0, float(percentage)))
    n = len(steps)
    idx = int(round(pct / 100.0 * (n - 1)))
    lo = max(0, idx - int(window))
    hi = min(n - 1, idx + int(window))
    return steps[lo:hi+1]

def query_task_measurement_steps(
    bucket: str,
    task_id: str,
    measurement: str,
    steps: Sequence[str],
    start: str = "-90d",
    limit: int = 0,
) -> List[Dict[str, Any]]:
    """
    查询 task+measurement 下给定 steps 的所有点，按 _time 升序。
    注意：这里做 pivot，将所有 fields 摊平为列，同时保留 tags。
    """
    if not steps:
        return []
    # 构造 steps 的正则：^(s1|s2|...)$
    pattern = "|".join(re.escape(str(s)) for s in steps)
    flux = f'''
from(bucket: "{bucket}")
  |> range(start: {start})
  |> filter(fn: (r) => r._measurement == "{measurement}" and r.task_id == "{task_id}" and r.step =~ /^({pattern})$/)
  |> group(columns: ["_measurement","task_id","node_name","step"])
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> group()
  |> sort(columns: ["_time"])
'''
    if limit and limit > 0:
        flux += f'  |> limit(n: {limit})\n'

    return _exec_query(flux)

def query_all_measurements_for_task_by_percentage(
    bucket: str,
    task_id: str,
    measurement: Optional[str],
    percentage: float,
    window: int = 0,
    start: str = "-90d",
    limit: int = 0,
) -> Tuple[List[str], Dict[str, List[Dict[str, Any]]]]:
    """
    以 percentage 在 steps 上选定一个或一段 step，查询：
    - 若 measurement="*" 或 None：对该 task 的每个 measurement 查询并合并
    - 否则仅查询该 measurement
    返回：(selected_steps, {measurement -> rows})
    """
    measurements: List[str]
    if not measurement or measurement == "*":
        measurements = list_measurements_for_task(bucket, task_id, start=start)
    else:
        measurements = [measurement]

    # 先用第一个 measurement 获取 step 列表（也可按需改为每个 measurement 单独取 steps）
    steps_all = list_steps_for_task_measurement(bucket, task_id, measurements[0], start=start) if measurements else []
    selected_steps = choose_steps_by_percentage(steps_all, percentage, window=window)

    out: Dict[str, List[Dict[str, Any]]] = {}
    for m in measurements:
        rows = query_task_measurement_steps(bucket, task_id, m, selected_steps, start=start, limit=limit)
        out[m] = rows
    return selected_steps, out
