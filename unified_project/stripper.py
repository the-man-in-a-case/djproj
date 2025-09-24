import json
import re
import shlex
from collections import OrderedDict
from pathlib import Path
from configparser import ConfigParser
from xml.etree import ElementTree as ET

BASE_DIR = Path(__file__).resolve().parent


def capture_text_metadata(text: str):
    lines = text.splitlines()
    entries = [{"number": idx, "text": line} for idx, line in enumerate(lines, 1)]
    return {"lines": entries, "endswith_newline": text.endswith("\n")}

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
        "metadata": {"raw_text": capture_text_metadata(raw_text)},
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
        "metadata": {"raw_text": capture_text_metadata(raw_text)},
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
        "metadata": {"raw_text": capture_text_metadata(raw_text)},
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
        "metadata": {"source_file": "gas_omnetpp.ini", "raw_ini_text": capture_text_metadata(raw_text)},
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
    return {"edges": edge_set, "raw_text": capture_text_metadata(raw_text)}


def parse_dss_params(tokens):
    params = OrderedDict()
    for token in tokens:
        if "=" in token:
            key, val = token.split("=", 1)
            params[key] = val
        else:
            params[token] = None
    return params


def normalize_value(val):
    if val is None:
        return None
    val = val.strip()
    if not val:
        return ""
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        parts = [part.strip() for part in inner.split(",")]
        return [normalize_value(part) for part in parts if part]
    if re.fullmatch(r"[-+]?\d+", val):
        try:
            return int(val)
        except ValueError:
            return val
    if re.fullmatch(r"[-+]?\d*\.\d+(?:[eE][-+]?\d+)?", val):
        try:
            num = float(val)
            return int(num) if num.is_integer() else num
        except ValueError:
            return val
    return val


def ensure_bus_node(node_map, bus_name):
    bus_id = f"bus:{bus_name}"
    if bus_id not in node_map:
        node_map[bus_id] = {"id": bus_id, "type": "dss_bus", "attrs": {"name": bus_name}}
    return node_map[bus_id]


def add_or_update_node(node_map, node_id, node_type, attrs):
    if node_id in node_map:
        node_map[node_id]["attrs"].update(attrs)
    else:
        node_map[node_id] = {"id": node_id, "type": node_type, "attrs": attrs}


def parse_opendss_directory(dir_path: Path):
    if not dir_path.exists():
        return None

    file_order = [
        "master.dss",
        "circuit.dss",
        "lines.dss",
        "transformers.dss",
        "loads.dss",
        "capacitors.dss"
    ]

    files_meta = OrderedDict()
    node_map = OrderedDict()
    edges = []
    edge_ids = set()

    type_map = {
        "circuit": "dss_circuit",
        "line": "dss_line",
        "transformer": "dss_transformer",
        "load": "dss_load",
        "capacitor": "dss_capacitor",
        "vsource": "dss_vsource",
        "buscoords": "dss_bus"
    }

    for file_name in file_order:
        file_path = dir_path / file_name
        if not file_path.exists():
            continue

        text = file_path.read_text(encoding="utf-8")
        text_meta = capture_text_metadata(text)
        commands = []

        for line in text.splitlines():
            stripped = line.strip()
            if not stripped:
                commands.append({"type": "blank"})
                continue
            if stripped.startswith("!"):
                commands.append({"type": "comment", "text": stripped})
                continue

            tokens = shlex.split(stripped, comments="!")
            if not tokens:
                continue
            action = tokens[0].lower()

            if action == "new" and len(tokens) >= 2:
                element = tokens[1]
                params = parse_dss_params(tokens[2:])
                command_entry = {
                    "type": "new",
                    "element": element,
                    "params": [{"key": key, "value": params[key]} for key in params]
                }
                commands.append(command_entry)

                etype, _, ename = element.partition('.')
                etype_lower = etype.lower()
                node_type = type_map.get(etype_lower, "dss_element")
                if etype_lower == "buscoords":
                    node_id = f"bus:{ename}"
                else:
                    node_id = f"{etype_lower}:{ename}" if ename else etype_lower

                attrs = {key: normalize_value(value) for key, value in params.items() if value is not None}

                if etype_lower == "buscoords":
                    bus_node = ensure_bus_node(node_map, ename)
                    bus_node["attrs"].update({k: normalize_value(v) for k, v in params.items() if v is not None})
                else:
                    if etype_lower in {"line", "transformer", "load", "capacitor", "vsource"}:
                        add_or_update_node(node_map, node_id, node_type, attrs)
                    elif etype_lower == "circuit":
                        add_or_update_node(node_map, node_id, node_type, attrs)
                    else:
                        add_or_update_node(node_map, node_id, node_type, attrs)

                if etype_lower == "line":
                    bus1 = params.get("bus1")
                    bus2 = params.get("bus2")
                    if bus1 and bus2:
                        ensure_bus_node(node_map, bus1)
                        ensure_bus_node(node_map, bus2)
                        edge_id = f"line:{ename}"
                        if edge_id not in edge_ids:
                            edges.append({
                                "id": edge_id,
                                "source": f"bus:{bus1}",
                                "target": f"bus:{bus2}",
                                "type": "dss_line",
                                "attrs": {"line": f"line:{ename}"}
                            })
                            edge_ids.add(edge_id)
                elif etype_lower == "transformer":
                    buses_val = params.get("buses")
                    if buses_val:
                        bus_list = [b.strip() for b in buses_val.strip("[]").split(",") if b.strip()]
                        if len(bus_list) >= 2:
                            ensure_bus_node(node_map, bus_list[0])
                            ensure_bus_node(node_map, bus_list[1])
                            edge_id = f"transformer:{ename}"
                            if edge_id not in edge_ids:
                                edges.append({
                                    "id": edge_id,
                                    "source": f"bus:{bus_list[0]}",
                                    "target": f"bus:{bus_list[1]}",
                                    "type": "dss_transformer",
                                    "attrs": {"transformer": f"transformer:{ename}"}
                                })
                                edge_ids.add(edge_id)
                elif etype_lower in {"load", "capacitor", "vsource"}:
                    bus_name = params.get("bus1")
                    if bus_name:
                        ensure_bus_node(node_map, bus_name)
                        edge_id = f"{etype_lower}:{ename}"
                        if edge_id not in edge_ids:
                            edges.append({
                                "id": edge_id,
                                "source": f"bus:{bus_name}",
                                "target": node_id,
                                "type": f"dss_{etype_lower}",
                                "attrs": {"element": node_id}
                            })
                            edge_ids.add(edge_id)
            elif action == "redirect" and len(tokens) >= 2:
                commands.append({"type": "redirect", "target": tokens[1]})
            elif action == "solve":
                params = parse_dss_params(tokens[1:])
                commands.append({"type": "solve", "params": [{"key": key, "value": params[key]} for key in params]})
            elif action == "clear":
                commands.append({"type": "clear"})
            elif action == "set":
                params = parse_dss_params(tokens[1:])
                commands.append({"type": "set", "params": [{"key": key, "value": params[key]} for key in params]})
            else:
                commands.append({"type": "command", "tokens": tokens})

        files_meta[file_name] = {
            "lines": text_meta["lines"],
            "endswith_newline": text_meta["endswith_newline"],
            "commands": commands
        }

    if not files_meta:
        return None

    metadata = {
        "directory": "opendss",
        "opendss_files": {
            "order": [name for name in file_order if name in files_meta],
            "files": files_meta
        }
    }

    layer = {
        "name": "OPEN_DSS",
        "simulator": "opendss",
        "version": "1.0",
        "metadata": metadata,
        "nodes": list(node_map.values()),
        "edges": edges,
        "mechanismRelationships": []
    }

    return layer

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
    return {"relationships": rels, "raw_text": capture_text_metadata(raw_text)}

# --------- Parsing Files ---------
files = {
    "hysys_orv": BASE_DIR / "out" / "hy_config.json",
    "hysys_tank": BASE_DIR / "out" / "tank_config.json",
    "traffic": BASE_DIR / "out" / "traffic_config.ini",
    "omnet_ini": BASE_DIR / "out" / "gas_omnetpp.ini",
    "omnet_ned": BASE_DIR / "out" / "gas_topology.ned",
    "exchange": BASE_DIR / "out" / "exchange.xml",
    "opendss_dir": BASE_DIR / "out" / "opendss"
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

opendss_layer = parse_opendss_directory(files["opendss_dir"])
if opendss_layer is not None:
    layers.append(opendss_layer)

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
