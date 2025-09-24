
import configparser
from typing import Dict, Any
from .utils import parse_float

def extract_traffic_ini(path: str) -> Dict[str, Any]:
    cfg = configparser.ConfigParser()
    cfg.read(path, encoding="utf-8")
    data = {s: {k: parse_float(v) for k, v in cfg[s].items()} for s in cfg.sections() or ["DEFAULT"]}
    if "DEFAULT" in cfg:
        data["DEFAULT"] = {k: parse_float(v) for k, v in cfg["DEFAULT"].items()}
    else:
        # fallback if only defaults present
        data = {"DEFAULT": {k: parse_float(v) for k, v in cfg.defaults().items()}}
    layer = {
        "name": "traffic",
        "simulator": "traffic",
        "version": "unknown",
        "metadata": {},
        "nodes": [{"id": "traffic-sim", "type": "traffic_engine", "attrs": data.get("DEFAULT", {})}],
        "lines": [],
        "mechanismRelationships": []
    }
    return layer
