
from extractor.extract import build_unified
from render import render_all
from pathlib import Path
import json
def demo():
    paths = dict(
        traffic_config_ini=r".\des\traffic_config.ini",
        gas_omnetpp_ini=r".\des\gas_omnetpp.ini",
        gas_topology_ned=r".\des\gas_topology.ned",
        hy_config_json=r".\des\hy_config.json",
        tank_config_json=r".\des\tank_config.json",
        exchange_xml=r".\des\exchange.xml",
        master_dss=r".\des\opendss\master.dss",
        circuit_dss=r".\des\opendss\circuit.dss",
        lines_dss=r".\des\opendss\lines.dss",
        transformers_dss=r".\des\opendss\transformers.dss",
        loads_dss=r".\des\opendss\loads.dss",
        capacitors_dss=r".\des\opendss\capacitors.dss",
        config_py=r".\des\opendss\config.py"
    )
    unified = build_unified("multi-sim-project", paths)
    Path("./unified.json").write_text(json.dumps(unified, ensure_ascii=False, indent=2), encoding="utf-8")
    out = render_all(unified, "generated_out", "templates")
    print("Rendered:", out)
if __name__ == "__main__":
    demo()
