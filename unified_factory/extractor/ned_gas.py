
import re
def extract_ned_topology(path: str):
    SUB = re.compile(r'^(?P<i>[A-Za-z0-9_]+):\s*(?P<t>[A-Za-z0-9_]+)\s*\{')
    CON = re.compile(r'^(?P<a>[^\s]+)\.out\+\+\s*-->\s*GasPipe\s*\{(?P<p>[^}]+)\}\s*-->\s*(?P<b>[^\s]+)\.in\+\+\s*;')
    nodes={}; lines=[]
    with open(path,"r",encoding="utf-8",errors="ignore") as f:
        raw=f.read()
    def parse(ps):
        out={}
        for t in ps.replace("\n"," ").split(";"):
            t=t.strip()
            if not t: continue
            if "=" in t:
                k,v=[x.strip() for x in t.split("=",1)]
                v=v.rstrip("mm").strip()
                try: out[k]=float(v)
                except: out[k]=v
        return out
    in_sub=in_conn=False
    for ln in raw.splitlines():
        s=ln.strip()
        if s.startswith("submodules:"): in_sub=True; in_conn=False; continue
        if s.startswith("connections:"): in_conn=True; in_sub=False; continue
        if in_sub:
            m=SUB.match(s)
            if m: nodes[m.group("i")]={"id":m.group("i"),"type":m.group("t"),"attrs":{}}
        if in_conn:
            m=CON.match(s)
            if m:
                a,b=m.group("a"),m.group("b")
                lines.append({"id":f"{a}__to__{b}","type":"GasPipe","from":a,"to":b,"attrs":parse(m.group("p"))})
    return {"name":"gas_topology","simulator":"omnetpp","version":"unknown","metadata":{},"nodes":list(nodes.values()),"lines":lines,"mechanismRelationships":[]}
