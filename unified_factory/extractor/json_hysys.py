
import json
from typing import Dict, Any

def extract_hysys_orv(path: str) -> Dict[str, Any]:
    cfg = json.load(open(path, "r", encoding="utf-8"))
    nodes = []
    # states -> nodes (single or multiple states as nodes)
    for idx, st in enumerate(cfg.get("states", []), 1):
        nodes.append({"id": f"state_{idx}", "type": "state", "attrs": st})
    layer = {
        "name": "hysys_orv",
        "simulator": "hysys_orv",
        "version": "unknown",
        "metadata": {k: v for k, v in cfg.items() if k not in ("states",)},
        "nodes": nodes,
        "lines": [],
        "mechanismRelationships": []
    }
    return layer
