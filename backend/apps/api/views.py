import json, os, uuid, logging
from django.db import transaction
from django.http import JsonResponse, HttpRequest
from rest_framework.decorators import api_view
from rest_framework import status
from django.conf import settings
import redis
from celery import Celery
from apps.core.models import Project, Action, Target
from .serializers import ProjectCreateSerializer, ActionCreateSerializer
from apps.factory.renderer import FactoryRenderer

logger = logging.getLogger(__name__)

# Celery app only for producing tasks & receiving events (producer only here)
celery_app = Celery("producer", broker=settings.RABBITMQ_URL)

@api_view(["POST"])
def create_project(request: HttpRequest):
    """
    接口1：创建 Project 并调用工厂生成/应用 YAML（示例仅返回生成的 YAML 文本，不直接 apply）
    """
    serializer = ProjectCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return JsonResponse({"ok":False,"errors":serializer.errors}, status=400)

    with transaction.atomic():
        proj = serializer.save()

    # 渲染 YAML 产物
    factory = FactoryRenderer()
    rendered = factory.render_and_apply(
        project=proj,
        industries=proj.industry,
        version=proj.industry_version,
        keda_kind="ScaledJob",  # 我们选择 ScaledJob：一条消息 = 一个Pod
    )

    return JsonResponse({
        "ok": True,
        "project_id": str(proj.id),
        "artifacts": rendered,   # 包含 deploy.yaml / cm.<container>.yaml / keda.yaml
    }, status=201)

@api_view(["POST"])
def dispatch_action(request: HttpRequest):
    """
    接口2：下发目标 → 发送到 RabbitMQ Celery 队列，由 KEDA 弹 Worker 处理
    """
    # 使用序列化器处理请求
    ser = ActionCreateSerializer(data=request.data)
    if not ser.is_valid():
        return JsonResponse({"ok":False,"errors":ser.errors}, status=400)

    data = ser.validated_data
    try:
        project = Project.objects.get(id=data["project_id"])
    except Project.DoesNotExist:
        return JsonResponse({"ok":False,"error":"project not found"}, status=404)

    # 生成新的 action_id
    action_id = str(uuid.uuid4())[:8]
    
    with transaction.atomic():
        try:
            action = Action.objects.create(
                        project=project,
                        action_id=action_id,
                        action_name=data['action_name'],
                        status="queued"
                    )
            # 构建 targets 列表用于传递给 Celery 任务
            targets = []
            if "target" in data and data["target"]:
                for target_item in data["target"]:
                    # 修复外键赋值方式
                    target = Target.objects.create(
                        action=action,  # 直接使用action对象，而不是action.id
                        node_id=target_item['id'],
                        node_name=target_item['name'],
                        industry=target_item['industry'],
                        parameter=target_item.get('parameter', {})  # 使用get避免key不存在的错误
                    )
                    targets.append({
                        "node_id": target_item["id"],
                        "industry": target_item["industry"],
                        "parameter": target_item.get('parameter', {})
                    })
        except Exception as e:
            # 捕获所有异常并返回错误信息
            logger.error(f"创建Action或Target失败: {str(e)}")
            return JsonResponse({"ok":False, "error":str(e)}, status=500)

    # 发送为 Celery 任务（队列名 actions）
    # 任务签名：worker_app.tasks.process_action(project_id, action_id, targets)
    task = celery_app.send_task(
        "worker_app.tasks.process_action",
        args=[str(project.id), action_id, targets],
        queue=settings.RABBITMQ_QUEUE
    )

    # 可将 Celery task_id 写入 Redis 以便 SSE 侧反查
    r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
    r.set(f"taskmap:{project.id}:{action_id}", task.id, ex=7*24*3600)

    # 返回生成的 action_id 给前端
    return JsonResponse({"ok":True, "action_id": action_id})
