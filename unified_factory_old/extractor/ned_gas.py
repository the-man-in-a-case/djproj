
import re
from typing import Dict, Any, List

SUBMODULE_PAT = re.compile(r'^(?P<id>[A-Za-z0-9_]+):\s*(?P<type>[A-Za-z0-9_]+)\s*\{')
CONN_PAT = re.compile(r'^(?P<from>[^\s]+)\s*\.out\+\+\s*-->\s*GasPipe\s*\{(?P<params>[^}]+)\}\s*-->\s*(?P<to>[^\s]+)\s*\.in\+\+\s*;')

def parse_params(param_str: str) -> Dict[str, Any]:
    attrs = {}
    for token in param_str.replace("\n"," ").split(";"):
        token = token.strip()
        if not token:
            continue
        if "=" in token:
            k, v = [p.strip() for p in token.split("=",1)]
            v = v.rstrip("mm").strip()
            try:
                attrs[k] = float(v)
            except Exception:
                attrs[k] = v
    return attrs

def extract_ned_topology(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        raw = f.read()

    # submodules section
    nodes: Dict[str, Dict[str, Any]] = {}
    lines: List[Dict[str, Any]] = []

    in_sub = False
    in_conn = False

    for line in raw.splitlines():
        s = line.strip()
        if s.startswith("submodules:"):
            in_sub = True; in_conn = False; continue
        if s.startswith("connections:"):
            in_conn = True; in_sub = False; continue
        if in_sub:
            m = SUBMODULE_PAT.match(s)
            if m:
                nid = m.group("id"); ntype = m.group("type")
                nodes[nid] = {"id": nid, "type": ntype, "attrs": {}}
        if in_conn:
            m2 = CONN_PAT.match(s)
            if m2:
                src = m2.group("from"); dst = m2.group("to")
                params = parse_params(m2.group("params"))
                eid = f"{src}__to__{dst}"
                lines.append({"id": eid, "type": "GasPipe", "from": src, "to": dst, "attrs": params})

    layer = {
        "name": "gas_topology",
        "simulator": "omnetpp",
        "version": "unknown",
        "metadata": {},
        "nodes": list(nodes.values()),
        "lines": lines,
        "mechanismRelationships": []
    }
    return layer
