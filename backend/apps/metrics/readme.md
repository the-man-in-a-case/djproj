- 连接路径：/ws/metrics/<project_id>/<action_id>/  
- 分组：group = f"metrics:{project_id}:{action_id}"  
- 首帧或后续消息传入： 

```

{
  "percentage": 50.0,              // 必填：0~100
  "measurement": "*",              // 选填：容器名/measurement；"*" 表示查询该 task 的所有 measurement
  "window": 0,                     // 选填：以 percentage 对应 step 为中心，左右各取 window 个 step（默认 0，即只取一个 step）
  "start": "-30d"                  // 选填：Flux range 起点，默认 "-30d"
}
```
-  “task_id” = f"{project_id}.{action_id}"（与 Influx 中的 tag 对齐）  
-  基于该 task 的所有 step，按 percentage 定位目标 step，并按 window 取一个 step 范围；
-  对每个 measurement，按 step 范围查询数据，并返回。
-  measurement="*" 时，会对该 task 的每个 measurement 都执行一次查询并合并返回。  
- 返回（示例结构）：  
```
{
  "project_id": "...",
  "action_id": "...",
  "task_id": "...",
  "percentage": 50.0,
  "selected_steps": ["12","13"],
  "measurements": {
    "opendss": [ { "time":"...","step":"12","node_name":"...","voltage":..., ... }, ... ],
    "omnet":   [ ... ],
    "hysys":   [ ... ]
  }
}
```

使用方式（前端）

连接：ws://<host>/ws/metrics/<project_id>/<action_id>/

发送示例：
```
{"percentage": 65, "measurement": "*", "window": 1, "start": "-30d"}

```
返回：见文首 JSON 结构示例。