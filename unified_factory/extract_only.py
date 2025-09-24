
from extractor.extract import build_unified
from pathlib import Path
import json, sys

def run(out_path: str = "unified.json"):
    paths = dict(
        traffic_config_ini="/mnt/data/traffic_config.ini",
        gas_omnetpp_ini="/mnt/data/gas_omnetpp.ini",
        gas_topology_ned="/mnt/data/gas_topology.ned",
        hy_config_json="/mnt/data/hy_config.json",
        tank_config_json="/mnt/data/tank_config.json",
        exchange_xml="/mnt/data/exchange.xml",
        master_dss="/mnt/data/master.dss",
        circuit_dss="/mnt/data/circuit.dss",
        lines_dss="/mnt/data/lines.dss",
        transformers_dss="/mnt/data/transformers.dss",
        loads_dss="/mnt/data/loads.dss",
        capacitors_dss="/mnt/data/capacitors.dss",
    )
    unified = build_unified("multi-sim-project", paths)
    Path(out_path).write_text(json.dumps(unified, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "unified.json"
    run(out)
