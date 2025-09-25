
from typing import Dict, Any
from .ini_traffic import extract_traffic_ini
from .ini_gas import extract_gas_ini
from .ned_gas import extract_ned_topology
from .json_hysys import extract_hysys_orv
from .json_tank import extract_hysys_tank
from .dss_power import extract_opendss
from .py_dss_config import extract_power_py_config
from .xml_exchange import extract_exchange_xml
def build_unified(project_name: str, paths: Dict[str, str]) -> Dict[str, Any]:
    layers = []
    layers.append(extract_traffic_ini(paths["traffic_config_ini"]))
    layers.append(extract_gas_ini(paths["gas_omnetpp_ini"]))
    layers.append(extract_ned_topology(paths["gas_topology_ned"]))
    layers.append(extract_hysys_orv(paths["hy_config_json"]))
    layers.append(extract_hysys_tank(paths["tank_config_json"]))
    dss_paths = {"master": paths["master_dss"], "circuit": paths["circuit_dss"], "lines": paths["lines_dss"],
                 "transformers": paths["transformers_dss"], "loads": paths["loads_dss"], "capacitors": paths["capacitors_dss"]}
    power_layer = extract_opendss(dss_paths)
    try:
        cfg = extract_power_py_config(paths["config_py"])
        power_layer["metadata"] = {**power_layer.get("metadata", {}), **cfg.get("metadata", {})}
        power_layer["nodes"].extend(cfg.get("nodes", []))
        power_layer["mechanismRelationships"].extend(cfg.get("mechanismRelationships", []))
    except Exception:
        pass
    layers.append(power_layer)
    layers.append(extract_exchange_xml(paths["exchange_xml"]))
    return {"project":{"name":project_name}, "layers":layers}
