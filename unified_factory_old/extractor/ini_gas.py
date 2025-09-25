
import configparser, re
from typing import Dict, Any, List
from .utils import parse_float

NODE_PAT = re.compile(r'^topology\.(?P<name>[^.]+)\.(?P<attr>[^\s=]+)\s*=\s*(?P<val>.+)$')
WILDCARD_PAT = re.compile(r'^topology\.\*\.(?P<attr>[^\s=]+)\s*=\s*(?P<val>.+)$')

def extract_gas_ini(path: str) -> Dict[str, Any]:
    nodes: Dict[str, Dict[str, Any]] = {}
    globals: Dict[str, Any] = {}
    others: Dict[str, Any] = {}
    general: Dict[str, Any] = {}

    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("["):
                if line.startswith("[") and "General" in line:
                    general = {"section": "General"}
                continue
            m = NODE_PAT.match(line)
            if m:
                name = m.group("name").strip()
                attr = m.group("attr").strip()
                val = m.group("val").split("#",1)[0].strip().strip('"')
                if name not in nodes:
                    # guess type by name
                    ntype = "valve" if name.lower().startswith("valve") else ("receiving_station" if "receivingstationinput" in name.lower() else ("gas_station" if name.startswith("gas_") else "unknown"))
                    nodes[name] = {"id": name, "type": ntype, "attrs": {}}
                # numeric conversion when possible
                try:
                    if "." in val or "e" in val.lower(): nodes[name]["attrs"][attr] = float(val)
                    else: nodes[name]["attrs"][attr] = int(val)
                except Exception:
                    nodes[name]["attrs"][attr] = val
                continue
            m2 = WILDCARD_PAT.match(line)
            if m2:
                attr = m2.group("attr"); val = m2.group("val").split("#",1)[0].strip().strip('"')
                globals[attr] = val
                continue
            # fallback key=value
            if "=" in line:
                k, v = [p.strip() for p in line.split("=",1)]
                others[k] = v

    layer = {
        "name": "gas",
        "simulator": "omnetpp",
        "version": "unknown",
        "metadata": {"general": general, "globals": globals, "others": others},
        "nodes": list(nodes.values()),
        "lines": [],
        "mechanismRelationships": []
    }
    return layer
