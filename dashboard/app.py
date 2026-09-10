#!/usr/bin/env python3
"""Read-only FCN300 operator dashboard and bounded reporting API."""
from __future__ import annotations

import json, math, os, socket, statistics, subprocess, time, urllib.request
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
PERSISTENCE_CADENCE_SECONDS = 5
GAP_SECONDS = 20
HISTORY_FIELDS = {
    "voltage_l1": ("Voltage A", "V"), "voltage_l2": ("Voltage B", "V"), "voltage_l3": ("Voltage C", "V"),
    "current_a": ("Current A", "A"), "current_b": ("Current B", "A"), "current_c": ("Current C", "A"),
    "active_power_kw": ("Active power", "kW"), "reactive_power_kvar": ("Reactive power", "kvar"),
    "apparent_power_kva": ("Apparent power", "kVA"), "power_factor": ("Power factor", ""),
    "frequency": ("Frequency", "Hz"), "energy_kwh": ("Active import energy", "kWh"),
}
RANGES = {"live": (timedelta(minutes=15), 5), "1h": (timedelta(hours=1), 10),
          "24h": (timedelta(hours=24), 60), "7d": (timedelta(days=7), 300),
          "30d": (timedelta(days=30), 900)}

def get_json(url, timeout=3.0):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode())

def iso(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

def latest_stored_row():
    query=urlencode({"select":"created_at","order":"created_at.desc","limit":"1"})
    rows=get_json(POSTGREST+"?"+query,2.5); stamp=iso(rows[0]["created_at"]) if rows else None
    return {"status":"HEALTHY" if stamp else "UNKNOWN","last_row_timestamp":stamp.isoformat() if stamp else None,
            "last_row_age_seconds":round(max(0,(datetime.now(timezone.utc)-stamp).total_seconds()),2) if stamp else None,
            "cadence_seconds":PERSISTENCE_CADENCE_SECONDS,"gap_rule_seconds":GAP_SECONDS,"error":None}

def recorder_health():
    hit=_cache.get("latest-row")
    if hit and time.monotonic()-hit[0]<4: return hit[1]
    try: result=latest_stored_row()
    except Exception as exc:
        result={"status":"ERROR","last_row_timestamp":None,"last_row_age_seconds":None,
                "cadence_seconds":PERSISTENCE_CADENCE_SECONDS,"gap_rule_seconds":GAP_SECONDS,
                "error":f"{type(exc).__name__}: {exc}"}
    _cache["latest-row"]=(time.monotonic(),result); return result

def live():
    now = datetime.now(timezone.utc)
    try:
        root=get_json(PROD_ROOT)
    except Exception as exc:
        return {"state":"OFFLINE","timestamp":None,"age_seconds":None,"serial_ok":False,"persistence":{},
                "recorder":recorder_health(),"values":{},"diag":{},"diag_error":None,
                "error":f"{type(exc).__name__}: {exc}"}
    try: stamp=iso(root.get("timestamp","")); age=max(0.0,(now-stamp).total_seconds())
    except (TypeError,ValueError): stamp,age=None,None
    serial=root.get("serial_ok")
    state="ERROR" if serial is False else ("UNKNOWN" if serial is not True or stamp is None else ("LIVE" if age<=5 else "STALE"))
    try: diag,diag_error=get_json(PROD_DIAG),None
    except Exception as exc: diag,diag_error={},f"{type(exc).__name__}: {exc}"
    return {"state":state,"timestamp":root.get("timestamp"),"age_seconds":round(age,2) if age is not None else None,
            "serial_ok":serial,"persistence":root.get("persistence",{}),"recorder":recorder_health(),
            "values":root,"diag":diag,"diag_error":diag_error,"error":None}

def date_range(params, max_days=366):
    if "start" in params and "end" in params:
        start=iso(params["start"][0]); end=iso(params["end"][0]); days=(end-start).total_seconds()/86400
        if days<=0 or days>max_days: raise ValueError(f"range must be positive and no more than {max_days} days")
        return start.astimezone(LOCAL_TZ).date().isoformat(),end.astimezone(LOCAL_TZ).date().isoformat(),start,end
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
    threshold=max(float(GAP_SECONDS),sample_cadence*3); gaps=[]; cursor=start
    for stamp,*_ in points:
        if (stamp-cursor).total_seconds()>threshold: gaps.append((cursor,stamp))
        cursor=stamp
    if (effective_end-cursor).total_seconds()>threshold: gaps.append((cursor,effective_end))
    return {"coverage":round(coverage,1),"expected_cadence_seconds":sample_cadence,"gap_count":len(gaps),
            "longest_gap_seconds":round(max(((b-a).total_seconds() for a,b in gaps),default=0)),
            "last_gap":None if not gaps else {"start":gaps[-1][0].isoformat(),"end":gaps[-1][1].isoformat(),"seconds":round((gaps[-1][1]-gaps[-1][0]).total_seconds())},
            "current_gap":bool(gaps and gaps[-1][1]==effective_end),
            "gap_rule_seconds":threshold,
            "gaps":[{"start":a.isoformat(),"end":b.isoformat(),"category":"COMMUNICATION"} for a,b in gaps[-50:]]}

def history_range(params):
    name=params.get("range",["24h"])[0]; now=datetime.now(timezone.utc)
    if name in RANGES:
        delta,bucket_seconds=RANGES[name]; return name,now-delta,now,bucket_seconds
    if name!="custom": raise ValueError("range must be live, 1h, 24h, 7d, 30d, or custom")
    start=iso(params.get("from",[""])[0]); end=iso(params.get("to",[""])[0]); seconds=(end-start).total_seconds()
    if seconds<=0 or seconds>366*86400: raise ValueError("custom range must be between 1 second and 366 days")
    return name,start,end,max(5,math.ceil(seconds/1500))

def telemetry_history(params):
    range_name,start,end,bucket_seconds=history_range(params)
    requested=params.get("metrics",["active_power_kw"])[0].split(",")
    metrics=list(dict.fromkeys(metric for metric in requested if metric in HISTORY_FIELDS))
    if not metrics or len(metrics)>10: raise ValueError("request 1-10 supported metrics")
    rows,truncated=fetch_rows("created_at,"+",".join(metrics),start,end)
    samples=[]; grouped=defaultdict(lambda:defaultdict(list))
    for row in rows:
        try: stamp=iso(row["created_at"])
        except (KeyError,TypeError,ValueError): continue
        samples.append((stamp,)); bucket=math.floor(stamp.timestamp()/bucket_seconds)*bucket_seconds
        for metric in metrics:
            try:
                value=float(row[metric])
                if math.isfinite(value): grouped[bucket][metric].append(value)
            except (KeyError,TypeError,ValueError): pass
    first=math.floor(start.timestamp()/bucket_seconds)*bucket_seconds
    last=math.floor(min(end,datetime.now(timezone.utc)).timestamp()/bucket_seconds)*bucket_seconds
    timestamps=[]; series={metric:[] for metric in metrics}; cursor=first
    while cursor<=last:
        timestamps.append(cursor)
        for metric in metrics:
            values=grouped[cursor].get(metric,[]); series[metric].append(round(statistics.fmean(values),4) if values else None)
        cursor+=bucket_seconds
    summaries={}
    for metric in metrics:
        values=[(timestamps[i],value) for i,value in enumerate(series[metric]) if value is not None]
        summaries[metric]=None if not values else {"min":min(v for _,v in values),"max":max(v for _,v in values),
            "average":round(statistics.fmean(v for _,v in values),4),
            "peak_timestamp":datetime.fromtimestamp(max(values,key=lambda item:item[1])[0],timezone.utc).isoformat()}
    sample_cadence=cadence(samples)
    return {"range":range_name,"from":start.isoformat(),"to":end.isoformat(),"bucket_seconds":bucket_seconds,
            "rows":len(samples),"truncated":truncated,"timestamps":timestamps,"series":series,
            "meta":{metric:{"label":HISTORY_FIELDS[metric][0],"unit":HISTORY_FIELDS[metric][1]} for metric in metrics},
            "summary":summaries,"quality":availability(samples,start,end,sample_cadence),"error":None}

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

def fixed_command(args):
    try:
        result=subprocess.run(args,capture_output=True,text=True,timeout=2,check=False)
        return result.stdout.strip() if result.returncode==0 else "UNAVAILABLE"
    except (OSError,subprocess.TimeoutExpired): return "UNAVAILABLE"

def tcp_state(port):
    try:
        with socket.create_connection(("127.0.0.1",port),timeout=1): return "HEALTHY"
    except OSError: return "UNAVAILABLE"

def diagnostics():
    services={service:fixed_command(["systemctl","--user","is-active",service]).upper()
              for service in ("ais-energy.service","fcn300-dashboard.service")}
    owner=fixed_command(["fuser","/dev/ttyUSB0"])
    return {"services":services,"postgres":tcp_state(5432),"postgrest":tcp_state(3000),
            "serial_owner_pids":owner or "UNAVAILABLE","dashboard":"HEALTHY","error":None}

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
            if path=="/api/history": self.send(200,json.dumps(telemetry_history(parse_qs(parsed.query)))); return
            if path=="/api/energy": self.send(200,json.dumps(energy_history(parse_qs(parsed.query)))); return
            if path=="/api/electrical-history": self.send(200,json.dumps(electrical_history())); return
            if path=="/api/diagnostics": self.send(200,json.dumps(diagnostics())); return
            if path=="/healthz": self.send(200,'{"status":"ok","app":"fcn300-dashboard"}'); return
            if path.startswith("/static/"):
                file=(HERE/"static"/path[8:]).resolve()
                if HERE/"static" not in file.parents or not file.is_file(): self.send(404,b"not found","text/plain"); return
                types={".css":"text/css; charset=utf-8",".js":"application/javascript; charset=utf-8",".txt":"text/plain; charset=utf-8"}
                self.send(200,file.read_bytes(),types.get(file.suffix,"application/octet-stream")); return
            self.send(404,b"not found","text/plain")
        except ValueError as exc: self.send(400,json.dumps({"error":str(exc)}))
        except Exception as exc: self.send(502,json.dumps({"error":f"{type(exc).__name__}: {exc}"}))

if __name__=="__main__": ThreadingHTTPServer(("0.0.0.0",PORT),Handler).serve_forever()
