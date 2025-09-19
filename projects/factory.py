from jinja2 import Environment, FileSystemLoader, StrictUndefined
from pathlib import Path
import yaml

def render_manifests(ctx):
    project = ctx["project"]
    
    # 确保containers是列表
    if not isinstance(project.get("containers"), list):
        project["containers"] = []
    
    TPL_ROOT = Path(__file__).resolve().parent/'templates'/'k8s'
    env = Environment(loader=FileSystemLoader(str(TPL_ROOT)), 
                     undefined=StrictUndefined, 
                     trim_blocks=True, 
                     lstrip_blocks=True)
    
    cm_tpl = env.get_template("configmap.yaml.j2")
    dep_tpl = env.get_template("deployment_worker.yaml.j2")
    so_tpl = env.get_template("scaledobject.yaml.j2")
    
    docs = []
    
    # 渲染ConfigMap
    for c in project["containers"]:
        if c.get("configmap_data") and isinstance(c["configmap_data"], dict):
            try:
                cm_content = cm_tpl.render(project=project, container=c)
                # 验证YAML格式
                yaml.safe_load(cm_content)
                docs.append(cm_content)
            except Exception as e:
                print(f"Error rendering ConfigMap: {e}")
    
    # 渲染Deployment
    try:
        dep_content = dep_tpl.render(project=project)
        yaml.safe_load(dep_content)
        docs.append(dep_content)
    except Exception as e:
        print(f"Error rendering Deployment: {e}")
    
    # 渲染ScaledObject
    try:
        so_content = so_tpl.render(project=project)
        yaml.safe_load(so_content)
        docs.append(so_content)
    except Exception as e:
        print(f"Error rendering ScaledObject: {e}")
    
    return "\n---\n".join(docs)
