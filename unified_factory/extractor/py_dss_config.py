
from typing import Dict, Any
SAFE_NAMES = {"__builtins__": {}}
def _safe_exec(path: str) -> Dict[str, Any]:
    env: Dict[str, Any] = {}
    try:
        code = open(path, "r", encoding="utf-8").read()
        compiled = compile(code, path, "exec")
        exec(compiled, SAFE_NAMES, env)
    except Exception:
        env = {}
    return env
def _to_list(x): return x if isinstance(x, list) else [x]
def extract_power_py_config(path: str) -> Dict[str, Any]:
    env = _safe_exec(path)
    BASE_DSS_DIRECTORY = env.get("BASE_DSS_DIRECTORY")
    MASTER_DSS_FILE_NAME = env.get("MASTER_DSS_FILE_NAME")
    GAS_GENERATOR_NAMES = env.get("GAS_GENERATOR_NAMES", [])
    GENERATOR_POWER_PERCENTAGES = env.get("GENERATOR_POWER_PERCENTAGES", {})
    GAS_NODE_TO_GENERATOR_MAP = env.get("GAS_NODE_TO_GENERATOR_MAP", {})
    ALPHA = env.get("ALPHA"); BETA = env.get("BETA"); GAMMA = env.get("GAMMA")
    COMPRESSOR_LOAD_NAMES = env.get("COMPRESSOR_LOAD_NAMES", [])
    SIMULATION_SETTINGS = env.get("SIMULATION_SETTINGS", {})
    OUTPUT_FILES = env.get("OUTPUT_FILES", {})
    INFLUXDB_CONFIG = env.get("INFLUXDB_CONFIG", {})
    gen_nodes=[{"id":f"gen_{n}","type":"generator","attrs":{"name":n,"target_ratio":GENERATOR_POWER_PERCENTAGES.get(n)}} for n in GAS_GENERATOR_NAMES]
    mech=[{"type":"gas_to_power","from":g,"to":_to_list(t),"attrs":{"mapping":"gas_node_to_generator"}} for g,t in GAS_NODE_TO_GENERATOR_MAP.items()]
    meta={"py_config":{"base_dss_directory":BASE_DSS_DIRECTORY,"master_dss_file_name":MASTER_DSS_FILE_NAME,
         "alpha":ALPHA,"beta":BETA,"gamma":GAMMA,"simulation_settings":SIMULATION_SETTINGS,"output_files":OUTPUT_FILES,
         "influxdb":INFLUXDB_CONFIG,"compressor_load_names":COMPRESSOR_LOAD_NAMES,
         "generator_power_percentages":GENERATOR_POWER_PERCENTAGES,"gas_generator_names":GAS_GENERATOR_NAMES,
         "gas_node_to_generator_map":GAS_NODE_TO_GENERATOR_MAP}}
    return {"nodes":gen_nodes,"mechanismRelationships":mech,"metadata":meta}
