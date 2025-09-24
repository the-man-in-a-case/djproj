"""
工厂：根据行业/版本渲染 Jinja2 模板，生成：
  - 主业务 Deployment（含 sidecar + 每行业容器）
  - 每容器 ConfigMap
  - KEDA ScaledJob（只扩 Celery worker）
"""
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape, TemplateNotFound
from pathlib import Path
from typing import Dict, List

TPL_DIR = Path(__file__).resolve().parent / "templates"

class FactoryRenderer:
    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(TPL_DIR)),
            autoescape=select_autoescape(enabled_extensions=("j2",)),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def _render_container_snippet(self, ind: str, version: str) -> str:
        # 行业专属模板优先，如不存在则回退 default
        candidates = [f"container_{ind}.j2", "container_default.j2"]
        for name in candidates:
            try:
                tpl = self.env.get_template(name)
                return tpl.render(industry=ind, version=version)
            except TemplateNotFound:
                continue
        # should not reach here
        return f"- name: {ind}\n  image: alpine:3.20\n  command: [\"sh\",\"-c\",\"echo {ind}; sleep 3600\"]\n"

    def render_all(self, project, industries: List[str], version: str, keda_kind: str="ScaledJob") -> Dict[str, str]:
        container_snippets = [ self._render_container_snippet(ind, version) for ind in industries ]

        # 1) Deployment
        deploy_tpl = self.env.get_template("deploy.yaml.j2")
        deployment_yaml = deploy_tpl.render(
            project=project,
            industries=industries,
            version=version,
            container_snippets=container_snippets,
        )

        # 2) Per-container ConfigMap
        cm_tpl = self.env.get_template("configmap.yaml.j2")
        cm_yamls = {}
        for ind in industries:
            cm_yamls[ind] = cm_tpl.render(
                project=project,
                container_name=ind,
                version=version,
                content=f"# config for {ind} v{version}\nkey: value\n",
            )

        # 3) KEDA
        keda_tpl = self.env.get_template("keda_scaledjob.yaml.j2")
        keda_yaml = keda_tpl.render(queue_name="actions")

        result = {
            "k8s/deploy.yaml": deployment_yaml,
            "k8s/keda.yaml": keda_yaml,
        }
        for name, y in cm_yamls.items():
            result[f"k8s/cm.{name}.yaml"] = y
        return result
