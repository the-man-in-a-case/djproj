
from typing import Dict, Any, List
import xml.etree.ElementTree as ET

def infer_link(name: str):
    # crude inference by class name e.g. PowerToPipeData1 -> power -> pipe
    lower = name.lower()
    if "to" in name:
        parts = name.split("To")
        if len(parts) == 2:
            return parts[0].lower(), parts[1].lower()
    return None, None

def extract_exchange_xml(path: str) -> Dict[str, Any]:
    tree = ET.parse(path)
    root = tree.getroot()
    mech = []

    # objects
    for obj in root.findall(".//objectClass"):
        cls_name = obj.get("name","")
        if "To" in cls_name:
            src, dst = infer_link(cls_name)
            attrs = [a.get("name") for a in obj.findall(".//attribute")]
            mech.append({"type": "object", "name": cls_name, "from": src, "to": dst, "attrs": attrs})

    # interactions
    for inter in root.findall(".//interactionClass"):
        cls_name = inter.get("name","")
        if "To" in cls_name:
            src, dst = infer_link(cls_name)
            params = [p.get("name") for p in inter.findall(".//parameter")]
            mech.append({"type": "interaction", "name": cls_name, "from": src, "to": dst, "attrs": params})
        else:
            # treat control interactions as middleware relationships without endpoints
            params = [p.get("name") for p in inter.findall(".//parameter")]
            mech.append({"type": "interaction", "name": cls_name, "from": None, "to": None, "attrs": params})

    layer = {
        "name": "middleware_exchange",
        "simulator": "hla_fom",
        "version": "1.0",
        "metadata": {},
        "nodes": [],
        "lines": [],
        "mechanismRelationships": mech
    }
    return layer
