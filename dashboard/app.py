#!/usr/bin/env python3
"""Read-only FCN300 operator dashboard and bounded reporting API."""
from __future__ import annotations

import json, math, os, statistics, time, urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
LOCAL_TZ = ZoneInfo(os.environ.get("WORKSHOP_TZ", "Asia/Jakarta"))
PROD_ROOT = os.environ.get("PROD_ROOT_URL", "http://127.0.0.1:8080/")
PROD_DIAG = os.environ.get("PROD_DIAG_URL", "http://127.0.0.1:8080/diag/raw")
POSTGREST = os.environ.get("POSTGREST_URL", "http://127.0.0.1:3000/water_monitoring")
PORT = int(os.environ.get("DIAG_PORT", "8090"))
MAX_REPORT_ROWS = 60_000  # ponytail: bounded raw source; add a DB aggregate view when history outgrows this.
_cache = {}

def get_json(url, timeout=3.0):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode())

def iso(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

def live():
    now = datetime.now(timezone.utc)
    try:
        root, diag = get_json(PROD_ROOT), get_json(PROD_DIAG)
        stamp = iso(root.get("timestamp", "")); age = max(0.0, (now-stamp).total_seconds())
        serial = bool(root.get("serial_ok")); state = "LIVE" if serial and age <= 5 else ("STALE" if serial else "OFFLINE")
        return {"state":state,"timestamp":root.get("timestamp"),"age_seconds":round(age,2),"serial_ok":serial,
                "persistence":root.get("persistence",{}),"values":root,"diag":diag,"error":None}
    except Exception as exc:
        return {"state":"OFFLINE","timestamp":None,"age_seconds":None,"serial_ok":False,"persistence":{},
                "values":{},"diag":{},"error":f"{type(exc).__name__}: {exc}"}

def date_range(params, max_days=366):
    today = datetime.now(LOCAL_TZ).date()
    start_date = datetime.fromisoformat(params.get("from",[today.isoformat()])[0]).date()
    end_date = datetime.fromisoformat(params.get("to",[(today+timedelta(days=1)).isoformat()])[0]).date()
    if end_date <= start_date or (end_date-start_date).days > max_days: raise ValueError(f"range must be 1-{max_days} days")
    start = datetime.combine(start_date,datetime.min.time(),LOCAL_TZ).astimezone(timezone.utc)
    end = datetime.combine(end_date,datetime.min.time(),LOCAL_TZ).astimezone(timezone.utc)
    return start_date.isoformat(),end_date.isoformat(),start,end

def fetch_rows(fields,start,end,max_rows=MAX_REPORT_ROWS):
    key=f"{fields}|{start.isoformat()}|{end.isoformat()}|{max_rows}"; hit=_cache.get(key)
    if hit and time.monotonic()-hit[0] < 30: return hit[1]
    rows=[]; page=1000
    while len(rows)<max_rows:
        query=urlencode({"select":fields,"created_at":f"gte.{start.isoformat()}","order":"created_at.asc","limit":str(page),"offset":str(len(rows))})
        query += "&"+urlencode({"created_at":f"lt.{end.isoformat()}"})
        batch=get_json(POSTGREST+"?"+query,6.0); rows.extend(batch)
        if len(batch)<page: break
    result=(rows[:max_rows],len(rows)>=max_rows); _cache[key]=(time.monotonic(),result); return result

def cadence(points):
    gaps=[(b[0]-a[0]).total_seconds() for a,b in zip(points,points[1:])]
    normal=[gap for gap in gaps if 1<=gap<=60]
    return round(statistics.median(normal),1) if normal else 5

def availability(points,start,end,sample_cadence):
    effective_end=min(end,datetime.now(timezone.utc)); duration=max(1.0,(effective_end-start).total_seconds())
    expected=max(1,round(duration/sample_cadence)); coverage=min(100.0,len(points)/expected*100)
    threshold=max(30.0,sample_cadence*3); gaps=[]; cursor=start
    for stamp,*_ in points:
        if (stamp-cursor).total_seconds()>threshold: gaps.append((cursor,stamp))
        cursor=stamp
    if (effective_end-cursor).total_seconds()>threshold: gaps.append((cursor,effective_end))
    return {"coverage":round(coverage,1),"expected_cadence_seconds":sample_cadence,"gap_count":len(gaps),
            "longest_gap_seconds":round(max(((b-a).total_seconds() for a,b in gaps),default=0)),
            "last_gap":None if not gaps else {"start":gaps[-1][0].isoformat(),"end":gaps[-1][1].isoformat(),"seconds":round((gaps[-1][1]-gaps[-1][0]).total_seconds())},
            "current_gap":bool(gaps and gaps[-1][1]==effective_end),
            "gaps":[{"start":a.isoformat(),"end":b.isoformat()} for a,b in gaps[-20:]]}

def energy_history(params):
    start_label,end_label,start,end=date_range(params); rows,truncated=fetch_rows("created_at,energy_kwh",start,end)
    points=[]; broken=False
    for row in rows:
        try:
            point=(iso(row["created_at"]),float(row["energy_kwh"]))
            if math.isfinite(point[1]): broken |= bool(points and point[1]<points[-1][1]); points.append(point)
        except (KeyError,TypeError,ValueError): pass
    sample_cadence=cadence(points); quality=availability(points,start,end,sample_cadence)
    span_days=(end-start).total_seconds()/86400; bucket_seconds=3600 if span_days<=2 else (86400 if span_days<=62 else 604800)
    grouped=defaultdict(list)
    for point in points:
        local=point[0].astimezone(LOCAL_TZ)
        if bucket_seconds==3600: bucket=local.replace(minute=0,second=0,microsecond=0)
        elif bucket_seconds==86400: bucket=local.replace(hour=0,minute=0,second=0,microsecond=0)
        else: bucket=(local-timedelta(days=local.weekday())).replace(hour=0,minute=0,second=0,microsecond=0)
        grouped[bucket].append(point)
    buckets=[]
    for bucket,values in sorted(grouped.items()):
        first_t,first_e=values[0]; last_t,last_e=values[-1]; elapsed=(last_t-first_t).total_seconds()/3600; used=last_e-first_e
        bucket_end=min(end,datetime.now(timezone.utc),bucket.astimezone(timezone.utc)+timedelta(seconds=bucket_seconds))
        expected=max(1,round(max(0,(bucket_end-bucket.astimezone(timezone.utc)).total_seconds())/sample_cadence))
        bucket_coverage=min(100.0,len(values)/expected*100); valid=used>=0 and elapsed>0
        buckets.append({"start":bucket.isoformat(),"label":bucket.strftime("%H:%M" if bucket_seconds==3600 else "%d %b"),
                        "first":first_e,"last":last_e,"energy_kwh":round(used,3) if valid else None,
                        "average_demand_kw":round(used/elapsed,2) if valid and bucket_coverage>=60 else None,
                        "coverage":round(bucket_coverage,1),"partial":bucket_coverage<80,"samples":len(values)})
    elapsed=(points[-1][0]-points[0][0]).total_seconds()/3600 if len(points)>1 else 0
    observed_expected=max(1,round(elapsed*3600/sample_cadence)) if elapsed else 1
    observed_coverage=min(100.0,len(points)/observed_expected*100)
    total=points[-1][1]-points[0][1] if len(points)>1 and not broken else None
    eligible=[b for b in buckets if b["energy_kwh"] is not None and not b["partial"]]; peak=max(eligible,key=lambda b:b["energy_kwh"],default=None)
    return {"from":start_label,"to":end_label,"rows":len(points),"truncated":truncated,"first":points[0][1] if points else None,
            "last":points[-1][1] if points else None,"first_timestamp":points[0][0].isoformat() if points else None,
            "last_timestamp":points[-1][0].isoformat() if points else None,"total_kwh":round(total,3) if total is not None else None,
            "average_demand_kw":round(total/elapsed,2) if total is not None and elapsed>0 and observed_coverage>=80 else None,
            "average_demand_basis":"monitored interval","observed_coverage":round(observed_coverage,1),
            "broken":broken,"aggregation":"hour" if bucket_seconds==3600 else ("day" if bucket_seconds==86400 else "week"),
            "buckets":buckets,"peak":peak,"quality":quality,"error":None}

def imbalance(values):
    mean=statistics.fmean(values); return (max(values)-min(values))/mean*100 if mean else None

def electrical_history():
    now=datetime.now(timezone.utc); local_now=now.astimezone(LOCAL_TZ)
    start=local_now.replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)
    rows,truncated=fetch_rows("created_at,voltage_l1,voltage_l2,voltage_l3,current_a,current_b,current_c",start,now,25_000)
    points=[]
    for row in rows:
        try:
            values=[float(row[k]) for k in ("voltage_l1","voltage_l2","voltage_l3","current_a","current_b","current_c")]
            if all(math.isfinite(v) for v in values): points.append((iso(row["created_at"]),*values))
        except (KeyError,TypeError,ValueError): pass
    sample_cadence=cadence(points); quality=availability(points,start,now,sample_cadence); recent=[p for p in points if p[0]>=now-timedelta(minutes=60)]
    groups=defaultdict(list)
    for point in recent: groups[point[0].astimezone(LOCAL_TZ).replace(second=0,microsecond=0)].append(point)
    buckets=[]
    for key,values in sorted(groups.items()):
        columns=list(zip(*[v[1:] for v in values])); means=[statistics.fmean(c) for c in columns]
        buckets.append({"t":key.isoformat(),"v":[round(v,2) for v in means[:3]],"i":[round(v,2) for v in means[3:]],
                        "v_imbalance":round(imbalance(means[:3]),2),"i_imbalance":round(imbalance(means[3:]),2),"samples":len(values)})
    def summary(source):
        if not source: return None
        volts=[v for p in source for v in p[1:4]]; currents=[v for p in source for v in p[4:7]]
        peak_current=max((v,"ABC"[i],p[0]) for p in source for i,v in enumerate(p[4:7]))
        v_imb=[(imbalance(p[1:4]),p[0]) for p in source]; i_imb=[(imbalance(p[4:7]),p[0]) for p in source]
        return {"voltage":{"min":round(min(volts),2),"max":round(max(volts),2),"average":round(statistics.fmean(volts),2)},
                "current":{"min":round(min(currents),2),"max":round(max(currents),2),"average":round(statistics.fmean(currents),2)},
                "peak_current":{"value":round(peak_current[0],2),"phase":peak_current[1],"time":peak_current[2].isoformat()},
                "voltage_imbalance":{"average":round(statistics.fmean(v for v,_ in v_imb),2),"median":round(statistics.median(v for v,_ in v_imb),2),"peak":round(max(v_imb)[0],2),"time":max(v_imb)[1].isoformat()},
                "current_imbalance":{"average":round(statistics.fmean(v for v,_ in i_imb),2),"median":round(statistics.median(v for v,_ in i_imb),2),"peak":round(max(i_imb)[0],2),"time":max(i_imb)[1].isoformat()}}
    dominance=None
    if recent:
        counts={phase:0 for phase in "ABC"}
        for point in recent: counts["ABC"[max(range(3),key=lambda i:point[4+i])]]+=1
        phase=max(counts,key=counts.get); dominance={"phase":phase,"percent":round(counts[phase]/len(recent)*100,1)}
    return {"range":"today","buckets":buckets,"last_hour":summary(recent),"today":summary(points),
            "phase_dominance_60m":dominance,"quality":quality,"rows":len(points),"truncated":truncated,"error":None}

class Handler(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args): pass
    def send(self,status,body,ctype="application/json"):
        data=body if isinstance(body,bytes) else body.encode(); self.send_response(status); self.send_header("Content-Type",ctype)
        self.send_header("Content-Length",str(len(data))); self.send_header("Cache-Control","no-store"); self.send_header("X-Content-Type-Options","nosniff"); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        parsed=urlparse(self.path); path=parsed.path
        try:
            if path in ("/","/index.html"): self.send(200,(HERE/"static"/"index.html").read_bytes(),"text/html; charset=utf-8"); return
            if path=="/api/live": self.send(200,json.dumps(live())); return
            if path=="/api/energy": self.send(200,json.dumps(energy_history(parse_qs(parsed.query)))); return
            if path=="/api/electrical-history": self.send(200,json.dumps(electrical_history())); return
            if path=="/healthz": self.send(200,'{"status":"ok","app":"fcn300-dashboard"}'); return
            if path.startswith("/static/"):
                file=(HERE/"static"/path[8:]).resolve()
                if HERE/"static" not in file.parents or not file.is_file(): self.send(404,b"not found","text/plain"); return
                self.send(200,file.read_bytes(),"text/css; charset=utf-8" if file.suffix==".css" else "application/javascript; charset=utf-8"); return
            self.send(404,b"not found","text/plain")
        except ValueError as exc: self.send(400,json.dumps({"error":str(exc)}))
        except Exception as exc: self.send(502,json.dumps({"error":f"{type(exc).__name__}: {exc}"}))

if __name__=="__main__": ThreadingHTTPServer(("0.0.0.0",PORT),Handler).serve_forever()
