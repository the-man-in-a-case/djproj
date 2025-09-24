import math
from dateutil import parser as dtparser
from datetime import datetime, timezone

def parse_ts(ts):
    if isinstance(ts,(int,float)) or (isinstance(ts,str) and ts.isdigit()):
        v=float(ts)
        if v>1e12: v/=1000.0
        return datetime.fromtimestamp(v,tz=timezone.utc)
    return dtparser.parse(str(ts)).astimezone(timezone.utc)

def lerp_ts(start_dt, end_dt, percent):
    p=max(0.0,min(100.0,float(percent)))
    return start_dt + (end_dt-start_dt)*(p/100.0)
