
import re
def extract_opendss(paths):
    RE_LINE=re.compile(r'(?i)New\s+Line\.(?P<id>\S+)\s+.*?bus1=(?P<bus1>\S+)\s+bus2=(?P<bus2>\S+)(?P<rest>.*)')
    RE_TRANS=re.compile(r'(?i)New\s+Transformer\.(?P<id>\S+).*?buses=\[(?P<buses>[^\]]+)\](?P<rest>.*)')
    RE_LOAD=re.compile(r'(?i)New\s+Load\.(?P<id>\S+)\s+.*?bus1=(?P<bus1>\S+)(?P<rest>.*)')
    RE_CAP=re.compile(r'(?i)New\s+Capacitor\.(?P<id>\S+)\s+.*?bus1=(?P<bus1>\S+)(?P<rest>.*)')
    RE_BUSCOORD=re.compile(r'(?i)New\s+BusCoords\.(?P<bus>\S+)\s+x=(?P<x>[-0-9.]+)\s+y=(?P<y>[-0-9.]+)')
    def parse_attrs(rest):
        attrs={}
        for tok in rest.strip().split():
            if "=" in tok:
                k,v=tok.split("=",1); v=v.strip("[]").strip(",")
                try: attrs[k]=float(v) if "." in v else int(v)
                except: attrs[k]=v
        return attrs
    nodes={}; lines=[]
    try:
        with open(paths.get("circuit",""),"r",encoding="utf-8",errors="ignore") as f:
            for line in f:
                m=RE_BUSCOORD.search(line)
                if m:
                    bus=m.group("bus"); nodes.setdefault(bus,{"id":bus,"type":"bus","attrs":{}})
                    nodes[bus]["attrs"].update({"x":float(m.group("x")),"y":float(m.group("y"))})
    except: pass
    with open(paths.get("lines",""),"r",encoding="utf-8",errors="ignore") as f:
        for raw in f:
            m=RE_LINE.search(raw)
            if m:
                lid=m.group("id"); b1=m.group("bus1"); b2=m.group("bus2"); attrs=parse_attrs(m.group("rest"))
                lines.append({"id":lid,"type":"line","from":b1,"to":b2,"attrs":attrs})
                for b in (b1,b2): nodes.setdefault(b,{"id":b,"type":"bus","attrs":{}})
    with open(paths.get("transformers",""),"r",encoding="utf-8",errors="ignore") as f:
        for raw in f:
            m=RE_TRANS.search(raw)
            if m:
                tid=m.group("id"); buses=[b.strip() for b in m.group("buses").split(",")]; attrs=parse_attrs(m.group("rest"))
                if len(buses)>=2: lines.append({"id":tid,"type":"transformer","from":buses[0],"to":buses[1],"attrs":attrs})
                for b in buses: nodes.setdefault(b,{"id":b,"type":"bus","attrs":{}})
    with open(paths.get("loads",""),"r",encoding="utf-8",errors="ignore") as f:
        for raw in f:
            m=RE_LOAD.search(raw)
            if m:
                ld=m.group("id"); b=m.group("bus1"); attrs=parse_attrs(m.group("rest"))
                nodes.setdefault(b,{"id":b,"type":"bus","attrs":{}})
                nodes[f"load_{ld}"]={"id":f"load_{ld}","type":"load","attrs":{"bus":b,**attrs}}
    with open(paths.get("capacitors",""),"r",encoding="utf-8",errors="ignore") as f:
        for raw in f:
            m=RE_CAP.search(raw)
            if m:
                cid=m.group("id"); b=m.group("bus1"); attrs=parse_attrs(m.group("rest"))
                nodes.setdefault(b,{"id":b,"type":"bus","attrs":{}})
                nodes[f"cap_{cid}"]={"id":f"cap_{cid}","type":"capacitor","attrs":{"bus":b,**attrs}}
    return {"name":"power","simulator":"opendss","version":"unknown","metadata":{"files":paths},
            "nodes":list(nodes.values()),"lines":lines,"mechanismRelationships":[]}
