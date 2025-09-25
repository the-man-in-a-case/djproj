
from typing import Dict, Any
import re

def condense(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())

def parse_float(v: str):
    try:
        return float(v)
    except Exception:
        return v

def parse_int(v: str):
    try:
        return int(v)
    except Exception:
        return v

def kv_list(d: Dict[str, Any]):
    return [{"key": k, "value": v} for k, v in d.items()]
