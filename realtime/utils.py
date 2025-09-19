from datetime import datetime, timezone
from dateutil import parser as dtparser
def parse_ts(ts):
    if isinstance(ts,(int,float)) or (isinstance(ts,str) and ts.isdigit()):
        v=float(ts); 
        if v>1e12: v/=1000.0
        return datetime.fromtimestamp(v,tz=timezone.utc)
    return dtparser.parse(str(ts)).astimezone(timezone.utc)
