# pip install influxdb-client
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from typing import Optional, Dict, Any, List
import os
import json

# ===== 基础连接参数（也可改为写死在代码里）=====
INFLUX_URL   = os.getenv("INFLUX_URL",   "http://192.168.119.200:8087")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "FZ8H-QX0YSryEwYsqY4GJTDN6AH6vXdazUtpe6F7JZIjK1oSqrFkiHC-U6l_DJwMA9YOPG9D3u_ki1jim8h5cQ==")
INFLUX_ORG   = os.getenv("INFLUX_ORG",   "my-org")
BUCKET       = os.getenv("INFLUX_BUCKET","hysys")

def build_flux_query(
    bucket: str,
    measurement: str,
    task_id: Optional[str] = None,
    node_name: Optional[str] = None,
    step: Optional[str] = None,
    start: str = "-30d",
    stop: Optional[str] = None,
    limit: int = 0,          # 取 N 条（0=不限）
) -> str:
    range_part = f'|> range(start: {start})' if not stop else f'|> range(start: {start}, stop: {stop})'

    filters = [f'r._measurement == "{measurement}"']

    def build_filter(tag: str, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if "*" in value:
            pattern = value.replace("*", ".*")
            return f'r.{tag} =~ /^{pattern}$/'
        else:
            return f'r.{tag} == "{value}"'

    for tag, val in [("task_id", task_id), ("node_name", node_name), ("step", step)]:
        f = build_filter(tag, val)
        if f:
            filters.append(f)

    filter_part = " and ".join(filters)

    # 关键：先按 tag 分组，再 pivot，这样 tag 会以列形式保留
    flux = f'''
from(bucket: "{bucket}")
{range_part}
|> filter(fn: (r) => {filter_part})
|> group(columns: ["_measurement","task_id","node_name","step"])
|> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
'''
    flux += '|> group()\n'
    if limit and limit > 0:
        flux += f'|> sort(columns: ["_time"], desc: true)\n|> limit(n: {limit})\n'
        # 若希望最终升序输出，可再追加：
        # flux += '|> sort(columns: ["_time"])\n'
    else:
        flux += '|> sort(columns: ["_time"])\n'

    return flux

def query_attributes_as_json(
    measurement: str,
    task_id: Optional[str] = None,
    node_name: Optional[str] = None,
    step: Optional[str] = None,
    start: str = "-30d",
    stop: Optional[str] = None,
    bucket: str = BUCKET,
    url: str = INFLUX_URL,
    token: str = INFLUX_TOKEN,
    org: str = INFLUX_ORG,
    limit:int = 0,   # 只返回最有一条
) -> List[Dict[str, Any]]:
    """
    按（task_id/node_name/step）过滤，返回包含“所有字段”的 JSON 列表。
    每个元素代表一个时间点（或多条同一时间多序列被 pivot 合并）。
    """
    flux = build_flux_query(bucket, measurement, task_id, node_name, step, start, stop, limit)

    with InfluxDBClient(url=url, token=token, org=org) as client:
        tables = client.query_api().query(flux)

    # 把每一行转换成“时间+属性们”的 dict
    results: List[Dict[str, Any]] = []
    for table in tables:
        for record in table.records:
            row = dict(record.values)  # 包含 _time、task_id、node_name、step、以及各 fields 列
            # 统一时间键为 "time"
            if "_time" in row:
                row["time"] = row.pop("_time").isoformat()
            # 去除一些不太有用的系统列（可按需保留/删除）
            for k in ["_measurement", "_start", "_stop", "result", "table", "_table"]:
                row.pop(k, None)

            results.append(row)

    return results

if __name__ == "__main__":
    # === 使用示例 ===
    # 1) 只用两个索引（示例：task_id + node_name），查询最近30天
    # 读取2.1工作路径里最新信息
    data_003 = query_attributes_as_json(
        measurement="hysys_test",
        task_id="*",      # 选择id，输入2.*则输出2阶段的所有信息
        node_name="*",       # 选择节点，输入*则输出所有节点信息
        # step="1",     # 选择步序，输入第1步所有信息，不传即忽略
        start="-30d",           # 最近30天
        # stop=None,            #终止时间，不传则到当前
        limit=1,        # 获取数量，输入0获取所有信息，输入X获取最新X条信息，输入1可以获取step步序
    )
    print(json.dumps(data_003, ensure_ascii=False, indent=2))

    # # 读取2.1工作路径里最新信息
    # data_003 = query_attributes_as_json(
    #     measurement="from_gas",   # 选择数据表，根据实际情况修改
    #     task_id="2.1",      # 选择task_id，输入2.*则输出2阶段的所有信息
    #     node_name="*",       # 选择节点，输入*则输出所有节点信息
    #     # step="1",     # 选择步序，输入第1步所有信息，不传即忽略
    #     start="-30d",           # 最近30天
    #     bucket=BUCKET,    # 选择bucket，根据实际情况修改
    #     # stop=None,            #终止时间，不传则到当前
    #     limit=0,        # 获取数量，输入0获取所有信息，输入X获取最新X条信息，输入1可以获取step步序
    # )
    # print(json.dumps(data_003, ensure_ascii=False, indent=2))


    # 2) 全量查询（慎用），把 start 设为很早的时间，但是可以据此获取到所有task_id的数据，如果仿真过去时间太久，建议用 start="1970-01-01T00:00:00Z" 方案查询
    # data_all = query_attributes_as_json(
    #     measurement="your_measurement",
    #     task_id="device-001",
    #     node_name="node_name-A",
    #     start="1970-01-01T00:00:00Z"
    # )
    # print(json.dumps(data_all, ensure_ascii=False, indent=2))

    # 3) 三个索引都指定（task_id + node_name + step）
    # data_3 = query_attributes_as_json(
    #     measurement="your_measurement",
    #     task_id="device-001",
    #     node_name="node_name-A",
    #     step="step-01",
    #     start="-7d"
    # )
    # print(json.dumps(data_3, ensure_ascii=False, indent=2))
