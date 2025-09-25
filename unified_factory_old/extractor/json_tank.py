
import json
from typing import Dict, Any

def extract_hysys_tank(path: str) -> Dict[str, Any]:
    cfg = json.load(open(path, "r", encoding="utf-8"))
    nodes = []
    # state array -> multiple nodes
    for idx, st in enumerate(cfg.get("state", []), 1):
        nodes.append({"id": f"tank_state_{idx}", "type": "state", "attrs": st})
    # simulator runtime settings as metadata
    meta = {}
    for k in ("file_paths", "influxdb", "simulator", "runtime"):
        if k in cfg: meta[k] = cfg[k]
    layer = {
        "name": "hysys_tank",
        "simulator": "hysys_tank",
        "version": "unknown",
        "metadata": meta,
        "nodes": nodes,
        "lines": [],
        "mechanismRelationships": []
    }
    return layer
