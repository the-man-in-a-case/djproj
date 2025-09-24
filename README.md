# Django + Channels + Celery (KEDA ScaledJob) + RabbitMQ + Redis + InfluxDB

本仓库包含：
- **backend/**：Django API（DRF）、WebSocket（Channels）、SSE 事件推送、工厂模板生成 YAML
- **worker/**：独立 Celery Worker（只消费任务、写 Redis，不依赖 Django 代码）
- **deploy/**：Dockerfile、`docker-compose.yml`（本地跑 MQ/Redis/Influx）、K8s KEDA 示例、Nginx 反代示例

## 一、快速开始（本地）
1. 准备 Python 3.10+ 并创建虚拟环境，安装依赖：
   ```bash
   pip install -r deploy/docker/requirements.app.txt
   ```

2. 启动依赖服务（RabbitMQ、Redis、InfluxDB，可选 Grafana）：
   ```bash
   docker compose -f deploy/docker/docker-compose.yml up -d
   ```

3. 复制并编辑环境变量：
   ```bash
   cp .env.example .env
   ```

4. 初始化 Django：
   ```bash
   cd backend
   python manage.py migrate
   python manage.py runserver 0.0.0.0:8000
   ```

5. 另起终端，启动 **单次任务型 Celery Worker**（本地演示，不通过 KEDA）：
   ```bash
   cd worker
   # 建议 virtualenv 或直接用系统 Python
   pip install -r worker_app/requirements.txt
   celery -A worker_app.celery_app worker -Q actions -l INFO --concurrency=1 --max-tasks-per-child=1 --pool=solo
   ```

6. 测试接口：
   - **创建项目**（接口1）
     ```bash
     curl -X POST http://127.0.0.1:8000/api/projects/            -H "Content-Type: application/json"            -d '{"name":"demo","industry":["power","telecom"],"industry_version":"v1","describe":"demo proj"}'
     ```
   - **下发目标**（接口2）
     ```bash
     curl -X POST http://127.0.0.1:8000/api/actions/            -H "Content-Type: application/json"            -d '{"project_id":"<返回的project_id>","action_id":"act-001","industry":"power","node":"n1","parameter":{"k":1}}'
     ```
   - **SSE 监听**（接口4）
     ```bash
     curl -N "http://127.0.0.1:8000/api/sse/events?project_id=<project_id>"
     ```
   - **WebSocket 指标**（接口3，浏览器打开）
     打开 `frontend/index.html`（或 http://127.0.0.1:8000/static/index.html ）

## 二、K8s / KEDA（ScaledJob）最小示例
1. 确保集群已安装 KEDA：
   ```bash
   helm repo add kedacore https://kedacore.github.io/charts
   helm install keda kedacore/keda
   ```
2. 应用示例清单：
   ```bash
   kubectl apply -f deploy/k8s/example/worker-config.yaml
   kubectl apply -f deploy/k8s/example/scaledjob-worker.yaml
   ```
   在集群中，向 RabbitMQ 的 `actions` 队列发送消息，即可看到触发 **ScaledJob** 按消息数创建 Job/Pod，
   每个 Pod 运行一个 Celery worker，仅消费一条消息，完成后退出。

## 三、接口说明（摘要）
见 `apps/api/` `apps/events/` `apps/metrics/`。完整实现附在源码内，代码注释全面。

## 四、目录结构（摘）
```
backend/
  manage.py
  project/
    settings.py, asgi.py, urls.py, routing.py
  apps/
    core/ (models, migrations)
    api/ (serializers, views, urls)
    factory/ (renderer + Jinja2 模板)
    events/ (SSE + Celery 事件监听)
    metrics/ (WebSocket + Influx 查询)
worker/
  worker_app/ (celery_app.py, tasks.py, requirements.txt)
deploy/
  docker/ (Dockerfile, docker-compose.yml, requirements.*)
  k8s/example/ (ScaledJob 等)
  nginx/sse_ws.conf
frontend/index.html
```

## 五、注意
- **解耦**：Django 不执行任务，只负责发消息；Worker 独立镜像，仅消费。通信通过 RabbitMQ（任务）和 Redis（结果）。
- **一条消息 = 一个Pod**：用 **KEDA ScaledJob** + Celery 参数 `--concurrency=1 --max-tasks-per-child=1` 实现。
- **Influx 不可用时**自动回退为 Mock 数据，不影响其它功能演示。
