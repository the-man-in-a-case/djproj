
from typing import Dict, Any, Iterable, Optional
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, StrictUndefined
def build_env(templates_dir: str):
    return Environment(loader=FileSystemLoader(templates_dir), undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True)
def _find_layer(layers, name):
    for L in layers:
        if L.get("name") == name:
            return L
    return None
def render_all(unified: Dict[str, Any], target_dir: str, templates_dir: str, select: Optional[Iterable[str]]=None):
    env = build_env(templates_dir)
    out = Path(target_dir); out.mkdir(parents=True, exist_ok=True)
    mapping = {
        "traffic_config.ini": ("traffic_config.ini.j2", "traffic"),
        "gas_omnetpp.ini": ("gas_omnetpp.ini.j2", "gas"),
        "gas_topology.ned": ("gas_topology.ned.j2", "gas_topology"),
        "hy_config.json": ("hy_config.json.j2", "hysys_orv"),
        "tank_config.json": ("tank_config.json.j2", "hysys_tank"),
        "exchange.xml": ("exchange.xml.j2", "middleware_exchange"),
        "master.dss": ("master.dss.j2", "power"),
        "circuit.dss": ("circuit.dss.j2", "power"),
        "lines.dss": ("lines.dss.j2", "power"),
        "transformers.dss": ("transformers.dss.j2", "power"),
        "loads.dss": ("loads.dss.j2", "power"),
        "capacitors.dss": ("capacitors.dss.j2", "power"),
        "config.py": ("config.py.j2", "power")
    }
    items = [(k,mapping[k]) for k in select] if select else list(mapping.items())
    for fname, (tpl, layer_name) in items:
        tmpl = env.get_template(tpl)
        layer = _find_layer(unified["layers"], layer_name)
        content = tmpl.render(project=unified["project"], layer=layer, layers=unified["layers"])
        (out / fname).write_text(content, encoding="utf-8")
    return str(out)
