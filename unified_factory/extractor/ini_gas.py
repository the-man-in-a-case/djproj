
import re
def extract_gas_ini(path: str):
    NODE = re.compile(r'^topology\.(?P<name>[^.]+)\.(?P<attr>[^\s=]+)\s*=\s*(?P<val>.+)$')
    WILD = re.compile(r'^topology\.\*\.(?P<attr>[^\s=]+)\s*=\s*(?P<val>.+)$')
    nodes = {}; globals = {}; others = {}; general = {}
    with open(path,"r",encoding="utf-8",errors="ignore") as f:
        for raw in f:
            s = raw.strip()
            if not s or s.startswith("#"): continue
            if s.startswith("[") and "General" in s: general={"section":"General"}; continue
            m = NODE.match(s)
            if m:
                name, attr, val = m.group("name"), m.group("attr"), m.group("val").split("#",1)[0].strip().strip('"')
                t = "valve" if name.lower().startswith("valve") else ("receiving_station" if "receivingstationinput" in name.lower() else "unknown")
                nodes.setdefault(name, {"id":name,"type":t,"attrs":{}})
                try: nodes[name]["attrs"][attr] = float(val) if "." in val or "e" in val.lower() else int(val)
                except: nodes[name]["attrs"][attr] = val
                continue
            m2 = WILD.match(s)
            if m2:
                attr, val = m2.group("attr"), m2.group("val").split("#",1)[0].strip().strip('"')
                globals[attr] = val; continue
            if "=" in s:
                k,v=[p.strip() for p in s.split("=",1)]; others[k]=v
    return {"name":"gas","simulator":"omnetpp","version":"unknown",
            "metadata":{"general":general,"globals":globals,"others":others},
            "nodes":list(nodes.values()),"lines":[],"mechanismRelationships":[]}
