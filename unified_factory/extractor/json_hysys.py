
import json
def extract_hysys_orv(path: str):
    cfg=json.load(open(path,"r",encoding="utf-8"))
    nodes=[{"id":f"state_{i+1}","type":"state","attrs":st} for i,st in enumerate(cfg.get("states",[]))]
    meta={k:v for k,v in cfg.items() if k not in ("states",)}
    return {"name":"hysys_orv","simulator":"hysys_orv","version":"unknown","metadata":meta,"nodes":nodes,"lines":[],"mechanismRelationships":[]}
