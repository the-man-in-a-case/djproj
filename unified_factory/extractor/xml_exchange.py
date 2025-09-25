
import xml.etree.ElementTree as ET
def infer_link(name: str):
    if "To" in name:
        parts=name.split("To")
        if len(parts)==2: return parts[0].lower(), parts[1].lower()
    return None, None
def extract_exchange_xml(path: str):
    tree=ET.parse(path); root=tree.getroot(); mech=[]
    for obj in root.findall(".//objectClass"):
        cls=obj.get("name",""); 
        if "To" in cls:
            src,dst=infer_link(cls); attrs=[a.get("name") for a in obj.findall(".//attribute")]
            mech.append({"type":"object","name":cls,"from":src,"to":dst,"attrs":attrs})
    for inter in root.findall(".//interactionClass"):
        cls=inter.get("name",""); params=[p.get("name") for p in inter.findall(".//parameter")]
        if "To" in cls:
            src,dst=infer_link(cls); mech.append({"type":"interaction","name":cls,"from":src,"to":dst,"attrs":params})
        else:
            mech.append({"type":"interaction","name":cls,"from":None,"to":None,"attrs":params})
    return {"name":"middleware_exchange","simulator":"hla_fom","version":"1.0","metadata":{},"nodes":[], "lines":[], "mechanismRelationships":mech}
