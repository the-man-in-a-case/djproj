
from extractor.extract import build_unified
from pathlib import Path
import json, sys


def _resolve_des_path(*parts: str) -> str:
    base_dir = Path(__file__).resolve().parent
    return str(base_dir.joinpath("des", *parts))


def run(out_path: str = "unified.json") -> None:
    paths = dict(
        traffic_config_ini=_resolve_des_path("traffic_config.ini"),
        gas_omnetpp_ini=_resolve_des_path("gas_omnetpp.ini"),
        gas_topology_ned=_resolve_des_path("gas_topology.ned"),
        hy_config_json=_resolve_des_path("hy_config.json"),
        tank_config_json=_resolve_des_path("tank_config.json"),
        exchange_xml=_resolve_des_path("exchange.xml"),
        master_dss=_resolve_des_path("opendss", "master.dss"),
        circuit_dss=_resolve_des_path("opendss", "circuit.dss"),
        lines_dss=_resolve_des_path("opendss", "lines.dss"),
        transformers_dss=_resolve_des_path("opendss", "transformers.dss"),
        loads_dss=_resolve_des_path("opendss", "loads.dss"),
        capacitors_dss=_resolve_des_path("opendss", "capacitors.dss"),
        config_py=_resolve_des_path("opendss", "config.py"),
    )
    unified = build_unified("multi-sim-project", paths)
    Path(out_path).write_text(json.dumps(unified, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Wrote", out_path)


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "unified.json")
