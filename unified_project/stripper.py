import json
import re
from pathlib import Path
from configparser import ConfigParser
from xml.etree import ElementTree as ET

BASE_DIR = Path(__file__).resolve().parent

def parse_hysys_orv_json(p: Path):
    raw_text = p.read_text(encoding="utf-8")
    data = json.loads(raw_text)
    nodes = [{"id": "simulation_file", "type": "file", "attrs": {"path": data.get("simulation_file")}}]
    for st in data.get("states", []):
        sid = st.get("state_name", "state")
        nodes.append({"id": f"state:{sid}", "type": "state", "attrs": {k: v for k, v in st.items() if k != "state_name"}})
    if "influxdb" in data:
        nodes.append({"id": "influxdb", "type": "influx", "attrs": data["influxdb"]})
    return {
        "name": "HYSYS_ORV",
        "simulator": "hysys_orv",
        "version": "1.0",
        "metadata": {"raw_text": raw_text},
        "nodes": nodes,
        "edges": [],
        "mechanismRelationships": []
    }

def parse_hysys_tank_json(p: Path):
    raw_text = p.read_text(encoding="utf-8")
    data = json.loads(raw_text)
    nodes = []
    if "file_paths" in data:
        nodes.append({"id": "file_paths", "type": "paths", "attrs": data["file_paths"]})
    if "simulator" in data:
        nodes.append({"id": "simulator", "type": "sim_state", "attrs": data["simulator"]})
    for idx, st in enumerate(data.get("state", [])):
        nodes.append({"id": f"state:{idx}", "type": "state", "attrs": st})
    if "influxdb" in data:
        nodes.append({"id": "influxdb", "type": "influx", "attrs": data["influxdb"]})
    return {
        "name": "HYSYS_TANK",
        "simulator": "hysys_tank",
        "version": "1.0",
        "metadata": {"raw_text": raw_text},
        "nodes": nodes,
        "edges": [],
        "mechanismRelationships": []
    }

def parse_traffic_ini(p: Path):
    raw_text = p.read_text(encoding="utf-8")
    cp = ConfigParser()
    cp.read_string(raw_text)
    defaults = dict(cp.defaults())
    nodes = [{"id": "DEFAULT", "type": "traffic_params", "attrs": defaults}]
    return {
        "name": "TRAFFIC",
        "simulator": "traffic",
        "version": "1.0",
        "metadata": {"raw_text": raw_text},
        "nodes": nodes,
        "edges": [],
        "mechanismRelationships": []
    }

def parse_gas_omnetpp_ini(p: Path):
    raw_text = p.read_text(encoding="utf-8")
    lines = raw_text.splitlines()
    general = {}
    gas_nodes_order = []
    gas_nodes = {}
    receive = {}
    outputs = {}
    valves = {}
    
    section = None
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("[") and s.endswith("]"):
            section = s.strip("[]")
            continue
        if "=" not in s:
            continue
        key, val = map(str.strip, s.split("=", 1))
        val = re.split(r"\s+#", val)[0].rstrip()

        if section == "General":
            general[key] = val
            continue

        if key.startswith("topology."):
            suffix = key[len("topology."):]

            if suffix.startswith("gas_"):
                node_id, attr = suffix.split(".", 1)
                if node_id not in gas_nodes:
                    gas_nodes[node_id] = {}
                    gas_nodes_order.append(node_id)
                gas_nodes[node_id][attr] = val
            elif suffix.startswith("receivingStationInput."):
                attr = suffix.split(".", 1)[1]
                receive[attr] = val
            elif suffix.endswith("outputJsonFile"):
                outputs["outputJsonFile"] = val
            elif suffix.endswith("outputFileName"):
                outputs["outputFileName"] = val
            elif suffix.startswith("valve"):
                m = re.match(r"valve(\d+)\.(R|opening)", suffix)
                if m:
                    vid = f"valve{m.group(1)}"
                    attr = m.group(2)
                    valves.setdefault(vid, {})[attr] = val

    nodes = [{"id": "General", "type": "general", "attrs": general}]
    for nid in gas_nodes_order:
        nodes.append({"id": nid, "type": "gas_node", "attrs": gas_nodes[nid]})
    if receive:
        nodes.append({"id": "receivingStationInput", "type": "io", "attrs": receive})
    if outputs:
        nodes.append({"id": "outputs", "type": "io", "attrs": outputs})
    for vid, attrs in valves.items():
        nodes.append({"id": vid, "type": "valve", "attrs": attrs})

    return {
        "name": "OMNET_GAS",
        "simulator": "omnetpp",
        "version": "1.0",
        "metadata": {"source_file": "gas_omnetpp.ini", "raw_ini_text": raw_text},
        "nodes": nodes,
        "edges": [],
        "mechanismRelationships": []
    }

def parse_gas_topology_ned(p: Path):
    raw_text = p.read_text(encoding="utf-8", errors="ignore")
    no_comments = re.sub(r"//.*", "", raw_text)
    edge_set = []
    for m in re.finditer(r"(gas_\d+_\d+)\s*<[-=]*>\s*(gas_\d+_\d+)", no_comments):
        a, b = m.group(1), m.group(2)
        edge_set.append({"id": f"{a}~{b}", "source": a, "target": b, "type": "bidirectional"})
    for m in re.finditer(r"(gas_\d+_\d+)\s*-->\s*(gas_\d+_\d+)", no_comments):
        a, b = m.group(1), m.group(2)
        edge_set.append({"id": f"{a}->{b}", "source": a, "target": b, "type": "directed"})
    return {"edges": edge_set, "raw_text": raw_text}

def parse_exchange_xml(p: Path):
    raw_text = p.read_text(encoding="utf-8")
    root = ET.fromstring(raw_text)
    rels = []
    for obj in root.findall(".//objectClass"):
        name = obj.attrib.get("name", "")
        m = re.match(r"([A-Za-z]+)To([A-Za-z]+)", name)
        if m:
            frm, to = m.group(1), m.group(2)
            rels.append({
                "id": name,
                "from": frm.upper(),
                "to": to.upper(),
                "mechanism": "HLA_ObjectClass",
                "attrs": {"class": name}
            })
    for inter in root.findall(".//interactionClass"):
        name = inter.attrib.get("name", "")
        m = re.match(r"([A-Za-z]+)To([A-Za-z]+)", name)
        if m:
            frm, to = m.group(1), m.group(2)
            rels.append({
                "id": name,
                "from": frm.upper(),
                "to": to.upper(),
                "mechanism": "HLA_InteractionClass",
                "attrs": {"class": name}
            })
        elif name in ("SimulationControl", "DataTransferComplete", "StepSynchronization", "StopSignalInteraction"):
            rels.append({
                "id": name,
                "from": "ALL",
                "to": "ALL",
                "mechanism": "HLA_InteractionClass",
                "attrs": {"class": name}
            })
    return {"relationships": rels, "raw_text": raw_text}

# --------- Parsing Files ---------
files = {
    "hysys_orv": BASE_DIR / "out" / "hy_config.json",
    "hysys_tank": BASE_DIR / "out" / "tank_config.json",
    "traffic": BASE_DIR / "out" / "traffic_config.ini",
    "omnet_ini": BASE_DIR / "out" / "gas_omnetpp.ini",
    "omnet_ned": BASE_DIR / "out" / "gas_topology.ned",
    "exchange": BASE_DIR / "out" / "exchange.xml"
}

layers = []
exchange_raw_text = None
if files["hysys_orv"].exists():
    layers.append(parse_hysys_orv_json(files["hysys_orv"]))
if files["hysys_tank"].exists():
    layers.append(parse_hysys_tank_json(files["hysys_tank"]))
if files["traffic"].exists():
    layers.append(parse_traffic_ini(files["traffic"]))
if files["omnet_ini"].exists():
    omnet_layer = parse_gas_omnetpp_ini(files["omnet_ini"])
    if files["omnet_ned"].exists():
        topology_info = parse_gas_topology_ned(files["omnet_ned"])
        omnet_layer["edges"] = topology_info["edges"]
        omnet_layer.setdefault("metadata", {})["topology_raw_text"] = topology_info["raw_text"]
    layers.append(omnet_layer)

mechanisms = []
if files["exchange"].exists():
    exchange_info = parse_exchange_xml(files["exchange"])
    mechanisms = exchange_info["relationships"]
    exchange_raw_text = exchange_info["raw_text"]

unified = {
    "project": {"id": "demo-001", "name": "Unified-Multi-Sim"},
    "layers": layers,
    "mechanismRelationships": mechanisms
}

if exchange_raw_text is not None:
    unified["metadata"] = {"exchange_raw_text": exchange_raw_text}

# Write output
output_file = BASE_DIR / "output_unified_layers.json"
output_file.write_text(json.dumps(unified, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Output written to: {output_file}")
