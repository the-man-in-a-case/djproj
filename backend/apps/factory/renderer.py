# backend/apps/factory/renderer.py
"""
工厂：渲染 + （可选）自动 apply
- 生成：
  - 主业务 Deployment（含 sidecar + 行业容器片段）
  - 每容器 ConfigMap（1 容器 1 份）
  - KEDA（ScaledJob/ScaledObject）
- 应用（可选）：
  - 先应用所有 ConfigMap
  - 再应用 Deployment
  - 最后应用 KEDA（以便队列触发扩缩容）
"""
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape, TemplateNotFound
from pathlib import Path
from typing import Dict, List, Tuple
import os

# 兼容导入：你已有的 k8s apply 工具
try:
    # 推荐：把 k8s_apply.py 放到 apps/factory/ 下，这样可以用相对导入
    from .k8s_apply import apply_yaml
except Exception:
    # 若路径不在包内，也允许从 PYTHONPATH 直接导入
    from k8s_apply import apply_yaml  # type: ignore

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

    # ===== 行业容器片段（支持 per-industry 模板）=====
    def _render_container_snippet(self, ind: str, version: str) -> str:
        for name in (f"container_{ind}.j2", "container_default.j2"):
            try:
                tpl = self.env.get_template(name)
                return tpl.render(industry=ind, version=version)
            except TemplateNotFound:
                continue
        # fallback
        return (
            f"- name: {ind}\n"
            f"  image: alpine:3.20\n"
            f"  command: [\"sh\",\"-c\",\"echo {ind} v{version}; sleep 3600\"]\n"
            f"  volumeMounts:\n"
            f"    - name: cm-{ind}\n"
            f"      mountPath: /etc/{ind}\n"
        )

    # ===== 仅渲染，不 apply =====
    def render_all(
        self,
        project,
        industries: List[str],
        version: str,
        keda_kind: str = "ScaledJob",   # or "ScaledObject"
        queue_name: str = "actions",
    ) -> Dict[str, str]:
        """
        返回 { "k8s/deploy.yaml": "...", "k8s/cm.<ind>.yaml": "...", "k8s/keda.yaml": "..." }
        """
        container_snippets = [self._render_container_snippet(ind, version) for ind in industries]

        # Deployment
        deploy_tpl = self.env.get_template("deploy.yaml.j2")
        deployment_yaml = deploy_tpl.render(
            project=project,
            industries=industries,
            version=version,
            container_snippets=container_snippets,
        )

        # ConfigMap (per container)
        cm_tpl = self.env.get_template("configmap.yaml.j2")
        cm_yamls = {
            ind: cm_tpl.render(
                project=project,
                container_name=ind,
                version=version,
                content=f"# config for {ind} v{version}\nkey: value\n",
            )
            for ind in industries
        }

        # KEDA（支持 ScaledJob/ScaledObject，两套模板任选其一；默认 ScaledJob）
        if keda_kind == "ScaledObject":
            keda_tpl_name = "keda_scaledobject.yaml.j2"
        else:
            keda_tpl_name = "keda_scaledjob.yaml.j2"

        keda_tpl = self.env.get_template(keda_tpl_name)
        keda_yaml = keda_tpl.render(queue_name=queue_name)

        out = {"k8s/deploy.yaml": deployment_yaml, "k8s/keda.yaml": keda_yaml}
        for name, y in cm_yamls.items():
            out[f"k8s/cm.{name}.yaml"] = y
        return out

    # ===== 渲染并按顺序 apply（CM -> Deployment -> KEDA）=====
    def render_and_apply(
        self,
        project,
        industries: List[str],
        version: str,
        keda_kind: str = "ScaledJob",
        queue_name: str = "actions",
        namespace: str = None,
    ) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
        """
        返回 (artifacts, applied_summary)
        - artifacts: 同 render_all 的 YAML 文本产物
        - applied_summary: {"configmaps": [...], "deployment": [...], "keda": [...]}
        """
        artifacts = self.render_all(project, industries, version, keda_kind, queue_name)

        # 分组：先 CM，再 Deployment，最后 KEDA
        cm_docs = []
        for ind in industries:
            cm_docs.append(artifacts[f"k8s/cm.{ind}.yaml"])
        deploy_docs = [artifacts["k8s/deploy.yaml"]]
        keda_docs = [artifacts["k8s/keda.yaml"]]

        applied = {"configmaps": [], "deployment": [], "keda": []}

        # 1) ConfigMaps
        if cm_docs:
            cm_multidoc = _join_multidoc(cm_docs)
            applied["configmaps"] = apply_yaml(cm_multidoc, namespace=namespace)  # ← 复用你的 apply
        # 2) Deployment
        applied["deployment"] = apply_yaml(_join_multidoc(deploy_docs), namespace=namespace)
        # 3) KEDA
        applied["keda"] = apply_yaml(_join_multidoc(keda_docs), namespace=namespace)

        return artifacts, applied


def _join_multidoc(docs: List[str]) -> str:
    """把多段 YAML 合并为 multi-doc 文本，适配 utils.create_from_dict 的逐文档应用。"""
    # 规范化分隔：确保文档之间有 '---'
    cleaned = []
    for d in docs:
        d = d.strip()
        if not d:
            continue
        if not d.startswith("---"):
            cleaned.append("---\n" + d)
        else:
            cleaned.append(d)
    # 第一个文档可以不带分隔
    if cleaned and cleaned[0].startswith("---"):
        cleaned[0] = cleaned[0].split("---", 1)[-1].lstrip("\n")
    return "\n".join(cleaned)
