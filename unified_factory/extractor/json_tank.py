
import json
def extract_hysys_tank(path: str):
    cfg=json.load(open(path,"r",encoding="utf-8"))
    nodes=[{"id":f"tank_state_{i+1}","type":"state","attrs":st} for i,st in enumerate(cfg.get("state",[]))]
    meta={}
    for k in ("file_paths","influxdb","simulator","runtime"):
        if k in cfg: meta[k]=cfg[k]
    return {"name":"hysys_tank","simulator":"hysys_tank","version":"unknown","metadata":meta,"nodes":nodes,"lines":[],"mechanismRelationships":[]}
