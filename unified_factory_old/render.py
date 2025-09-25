
from typing import Dict, Any, Iterable, Optional
from pathlib import Path
from shutil import copyfile
from jinja2 import Environment, FileSystemLoader, StrictUndefined


DES_ROOT = Path(__file__).resolve().parent / "des"
DES_MAPPING = {
    "traffic_config.ini": DES_ROOT / "traffic_config.ini",
    "gas_omnetpp.ini": DES_ROOT / "gas_omnetpp.ini",
    "gas_topology.ned": DES_ROOT / "gas_topology.ned",
    "hy_config.json": DES_ROOT / "hy_config.json",
    "tank_config.json": DES_ROOT / "tank_config.json",
    "exchange.xml": DES_ROOT / "exchange.xml",
    "master.dss": DES_ROOT / "opendss" / "master.dss",
    "circuit.dss": DES_ROOT / "opendss" / "circuit.dss",
    "lines.dss": DES_ROOT / "opendss" / "lines.dss",
    "transformers.dss": DES_ROOT / "opendss" / "transformers.dss",
    "loads.dss": DES_ROOT / "opendss" / "loads.dss",
    "capacitors.dss": DES_ROOT / "opendss" / "capacitors.dss",
}

def build_env(templates_dir: str):
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    return env

def _find_layer(layers, name):
    for L in layers:
        if L.get("name") == name:
            return L
    return None

def render_all(unified: Dict[str, Any], target_dir: str, templates_dir: str, select: Optional[Iterable[str]]=None):
    env = build_env(templates_dir)
    out = Path(target_dir)
    out.mkdir(parents=True, exist_ok=True)

    # map filename -> (template, layer_name)
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
        "capacitors.dss": ("capacitors.dss.j2", "power")
    }

    to_render = mapping.items() if not select else [(k, mapping[k]) for k in select if k in mapping]

    for fname, (tpl, layer_name) in to_render:
        des_path = DES_MAPPING.get(fname)
        if des_path and des_path.exists():
            copyfile(des_path, out / fname)
            continue

        tmpl = env.get_template(tpl)
        layer = _find_layer(unified["layers"], layer_name)
        content = tmpl.render(project=unified["project"], layer=layer, layers=unified["layers"])
        (out / fname).write_text(content, encoding="utf-8")

    return str(out)
