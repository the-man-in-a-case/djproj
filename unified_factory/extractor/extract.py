
from typing import Dict, Any
from pathlib import Path

from .ini_traffic import extract_traffic_ini
from .ini_gas import extract_gas_ini
from .ned_gas import extract_ned_topology
from .json_hysys import extract_hysys_orv
from .json_tank import extract_hysys_tank
from .dss_power import extract_opendss
from .xml_exchange import extract_exchange_xml

def build_unified(project_name: str, paths: Dict[str, str]) -> Dict[str, Any]:
    layers = []
    # traffic
    layers.append(extract_traffic_ini(paths["traffic_config_ini"]))
    # gas ini and ned topology
    layers.append(extract_gas_ini(paths["gas_omnetpp_ini"]))
    layers.append(extract_ned_topology(paths["gas_topology_ned"]))
    # hysys orv & tank
    layers.append(extract_hysys_orv(paths["hy_config_json"]))
    layers.append(extract_hysys_tank(paths["tank_config_json"]))
    # power (OpenDSS)
    dss_paths = {
        "master": paths["master_dss"],
        "circuit": paths["circuit_dss"],
        "lines": paths["lines_dss"],
        "transformers": paths["transformers_dss"],
        "loads": paths["loads_dss"],
        "capacitors": paths["capacitors_dss"],
    }
    layers.append(extract_opendss(dss_paths))
    # middleware exchange
    layers.append(extract_exchange_xml(paths["exchange_xml"]))

    return {
        "project": {"name": project_name},
        "layers": layers
    }
