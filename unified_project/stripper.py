import json
import re
from pathlib import Path
from configparser import ConfigParser
from xml.etree import ElementTree as ET

def parse_hysys_orv_json(p: Path):
    data = json.loads(p.read_text(encoding="utf-8"))
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
        "metadata": {},
        "nodes": nodes,
        "edges": [],
        "mechanismRelationships": []
    }

def parse_hysys_tank_json(p: Path):
    data = json.loads(p.read_text(encoding="utf-8"))
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
        "metadata": {},
        "nodes": nodes,
        "edges": [],
        "mechanismRelationships": []
    }

def parse_traffic_ini(p: Path):
    cp = ConfigParser()
    cp.read(p, encoding="utf-8")
    defaults = dict(cp.defaults())
    nodes = [{"id": "DEFAULT", "type": "traffic_params", "attrs": defaults}]
    return {
        "name": "TRAFFIC",
        "simulator": "traffic",
        "version": "1.0",
        "metadata": {},
        "nodes": nodes,
        "edges": [],
        "mechanismRelationships": []
    }

def parse_gas_omnetpp_ini(p: Path):
    lines = p.read_text(encoding="utf-8").splitlines()
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
        "metadata": {"source_file": "gas_omnetpp.ini"},
        "nodes": nodes,
        "edges": [],
        "mechanismRelationships": []
    }

def parse_gas_topology_ned(p: Path):
    text = p.read_text(encoding="utf-8", errors="ignore")
    no_comments = re.sub(r"//.*", "", text)
    edge_set = []
    for m in re.finditer(r"(gas_\d+_\d+)\s*<[-=]*>\s*(gas_\d+_\d+)", no_comments):
        a, b = m.group(1), m.group(2)
        edge_set.append({"id": f"{a}~{b}", "source": a, "target": b, "type": "bidirectional"})
    for m in re.finditer(r"(gas_\d+_\d+)\s*-->\s*(gas_\d+_\d+)", no_comments):
        a, b = m.group(1), m.group(2)
        edge_set.append({"id": f"{a}->{b}", "source": a, "target": b, "type": "directed"})
    return edge_set

def parse_exchange_xml(p: Path):
    xml = ET.parse(p)
    root = xml.getroot()
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
    return rels

# --------- Parsing Files ---------
files = {
    "hysys_orv": Path("out/hy_config.json"),
    "hysys_tank": Path("out/tank_config.json"),
    "traffic": Path("out/traffic_config.ini"),
    "omnet_ini": Path("out/gas_omnetpp.ini"),
    "omnet_ned": Path("out/gas_topology.ned"),
    "exchange": Path("out/exchange.xml")
}

layers = []
if files["hysys_orv"].exists():
    layers.append(parse_hysys_orv_json(files["hysys_orv"]))
if files["hysys_tank"].exists():
    layers.append(parse_hysys_tank_json(files["hysys_tank"]))
if files["traffic"].exists():
    layers.append(parse_traffic_ini(files["traffic"]))
if files["omnet_ini"].exists():
    omnet_layer = parse_gas_omnetpp_ini(files["omnet_ini"])
    if files["omnet_ned"].exists():
        edges = parse_gas_topology_ned(files["omnet_ned"])
        omnet_layer["edges"] = edges
    layers.append(omnet_layer)

mechanisms = []
if files["exchange"].exists():
    mechanisms = parse_exchange_xml(files["exchange"])

unified = {
    "project": {"id": "demo-001", "name": "Unified-Multi-Sim"},
    "layers": layers,
    "mechanismRelationships": mechanisms
}

# Write output
output_file = Path("output_unified_layers.json")
output_file.write_text(json.dumps(unified, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Output written to: {output_file}")
