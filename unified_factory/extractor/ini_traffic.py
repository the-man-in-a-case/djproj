
import configparser
def extract_traffic_ini(path: str):
    cfg = configparser.ConfigParser(); cfg.read(path, encoding="utf-8")
    def norm(section):
        return {k: (float(v) if v.replace('.','',1).isdigit() else v) for k, v in section.items()}
    defaults = norm(cfg["DEFAULT"]) if "DEFAULT" in cfg else {k:v for k,v in cfg.defaults().items()}
    return {"name":"traffic","simulator":"traffic","version":"unknown","metadata":{},
            "nodes":[{"id":"traffic-sim","type":"traffic_engine","attrs":defaults}], "lines":[], "mechanismRelationships":[]}
