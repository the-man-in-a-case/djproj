import json
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.conf import settings
from config.celery_app import app as celery_app
from .models import Project, WorkerRun
from .factory import render_manifests
from .k8s_apply import apply_yaml
def _ctx(p: Project):
    return {"project": {
        "id": str(p.id), "name": p.name, "user": p.user, "industry": p.industry,
        "namespace": p.namespace, "params": p.params, "containers": p.containers,
        "queue_name": p.queue_name, "max_workers": p.max_workers, "scale_threshold": p.scale_threshold,
    }}
@csrf_exempt
def create_project(request: HttpRequest):
    if request.method!="POST": return JsonResponse({"error":"Method not allowed"}, status=405)
    body=json.loads(request.body or "{}")
    name=body.get("name"); user=body.get("user"); industry=body.get("industry", [])
    if not name or not user or not isinstance(industry, list):
        return JsonResponse({"ok":False,"error":"invalid payload, require {name,user,industry[]}."}, status=400)
    containers=body.get("containers", []); params=body.get("params", {})
    namespace=body.get("namespace", settings.K8S_DEFAULT_NAMESPACE)
    queue_name=body.get("queue_name", settings.WORKER_QUEUE_NAME)
    max_workers=int(body.get("max_workers",5)); scale_threshold=int(body.get("scale_threshold",1))
    with transaction.atomic():
        p=Project.objects.create(name=name, user=user, industry=industry, namespace=namespace, containers=containers, params=params, queue_name=queue_name, max_workers=max_workers, scale_threshold=scale_threshold, status="APPLYING")
    yaml_text=render_manifests(_ctx(p)); applied=apply_yaml(yaml_text, namespace=namespace)
    p.status="RUNNING"; p.save(update_fields=["status","updated_at"])
    return JsonResponse({"ok":True,"project_id":str(p.id),"applied":applied,"yaml":yaml_text})
@csrf_exempt
def submit_target(request: HttpRequest):
    if request.method!="POST": return JsonResponse({"error":"Method not allowed"}, status=405)
    body=json.loads(request.body or "{}")
    try:
        pid=body["project_id"]; target=body.get("target", {}); p=Project.objects.get(id=pid)
    except Exception:
        return JsonResponse({"ok":False,"error":"project not found or bad payload"}, status=400)
    with transaction.atomic():
        run=WorkerRun.objects.create(project=p, target=target, status="QUEUED")
        if p.status in ["RUNNING","CREATED"]: p.status="DISPATCHED"; p.save(update_fields=["status","updated_at"])
    task_name=p.params.get("workerTaskName", settings.WORKER_TASK_NAME)
    res=celery_app.send_task(task_name, args=[str(p.id), str(run.id), target], queue=p.queue_name)
    run.celery_task_id=res.id; run.status="STARTED"; run.save(update_fields=["celery_task_id","status","updated_at"])
    return JsonResponse({"ok":True,"run_id":str(run.id),"celery_task_id":res.id})
def project_status(request: HttpRequest, pid):
    try: p=Project.objects.get(id=pid)
    except Project.DoesNotExist: return JsonResponse({"ok":False,"error":"project not found"}, status=404)
    runs=list(p.runs.values("id","status","created_at","updated_at","celery_task_id"))
    summary={"RUNNING":0,"SUCCESS":0,"ERROR":0,"QUEUED":0,"STARTED":0}
    for r in runs: summary[r["status"]]=summary.get(r["status"],0)+1
    info={"id":str(p.id),"name":p.name,"user":p.user,"industry":p.industry,"status":p.status,"runs":runs,"summary":summary}
    try:
        import redis
        r=redis.from_url(settings.WORKER_RESULT_REDIS, decode_responses=True)
        info["counters"]={"targets":int(r.get(f"project:{p.id}:targets_count") or 0),"completed":int(r.get(f"project:{p.id}:completed_count") or 0),"errors":int(r.get(f"project:{p.id}:errors_count") or 0)}
    except Exception: pass
    return JsonResponse({"ok":True,"project":info})
