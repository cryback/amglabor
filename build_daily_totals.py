#!/usr/bin/env python3
"""
Build daily_totals.json from a CSV you edit in Excel.

Input (default): data/daily_totals.csv
Output (default): daily_totals.json

CSV columns (header row required):
  weekOf, park, dow, hours, cost, revenue, pct
  - cost and pct may be blank; they'll be computed if possible.

Auto-compute rules:
  cost    := hours * hourly_rate_from_rates_json   (if cost is blank/0)
  pct     := (cost / revenue) * 100                (if pct is blank/0 and revenue>0)
  pct accepts 12.5, "12.5%" or 0.125 (Excel percent)
  hours/cost/revenue accept $ and commas in input; we sanitize.

JSON output (what your iOS app reads):
  { "weekOf": "...", "parks": { "<Park>": { "days": [ {dow,hours,cost,revenue,pct}, ... ] } } }
"""

import argparse, csv, json, os, sys
from collections import defaultdict, OrderedDict
from typing import Optional, List, Dict, Any

DOW_ORDER = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
DOW_ALIASES = {
    "monday":"Mon","mon":"Mon","1":"Mon",
    "tuesday":"Tue","tue":"Tue","tues":"Tue","2":"Tue",
    "wednesday":"Wed","wed":"Wed","3":"Wed",
    "thursday":"Thu","thu":"Thu","thur":"Thu","thurs":"Thu","4":"Thu",
    "friday":"Fri","fri":"Fri","5":"Fri",
    "saturday":"Sat","sat":"Sat","6":"Sat",
    "sunday":"Sun","sun":"Sun","7":"Sun",
}

def norm_dow(s: str) -> str:
    if not s: return ""
    key = s.strip().lower()
    return DOW_ALIASES.get(key, s.strip()[:3].title())

def parse_float(v):
    if v is None: return 0.0
    if isinstance(v,(int,float)): return float(v)
    s = str(v).strip()
    if not s: return 0.0
    s = s.replace("$","").replace(",","").replace("%","")
    try: return float(s)
    except ValueError: return 0.0

def parse_pct(v):
    # 12.72, "12.72%", or 0.1272 (Excel percent)
    if v is None: return 0.0
    if isinstance(v,(int,float)):
        val = float(v)
        return val*100.0 if 0 < val <= 1 else val
    s = str(v).strip()
    if not s: return 0.0
    if s.endswith("%"): return parse_float(s)  # "12.72%" -> 12.72
    val = parse_float(s)
    return val*100.0 if 0 < val <= 1 else val

def read_csv(path: str) -> List[Dict[str, Any]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows: List[Dict[str, Any]] = []
        for r in reader:
            row = { (k.strip() if isinstance(k,str) else k): (v.strip() if isinstance(v,str) else v) for k,v in r.items() }
            rows.append(row)
        return rows

def read_rates_json(path: str) -> Dict[str, float]:
    """
    Supports either:
      {"parks":[{"name":"Appleton","rate":17.22}, ...], ...}
    or:
      {"Appleton":17.22, "Austell":16.43, ...}
    """
    if not os.path.exists(path):
        print(f"WARNING: rates.json not found at {path}; won't auto-compute cost from rate.")
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"WARNING: could not parse {path}: {e}")
        return {}
    rates: Dict[str, float] = {}

    if isinstance(data, dict) and "parks" in data and isinstance(data["parks"], list):
        for row in data["parks"]:
            if isinstance(row, dict) and "name" in row:
                name = str(row["name"]).strip()
                rate = parse_float(row.get("rate") or row.get("value"))
                if name:
                    rates[name] = rate
    elif isinstance(data, dict):
        # Assume simple map, skip known meta keys
        for k, v in data.items():
            if k in ("target_percentage","last_updated","thresholds"): 
                continue
            rates[str(k)] = parse_float(v)
    else:
        print("WARNING: Unexpected rates.json shape; skipping rates.")
    return rates

def pick_week_of(rows: List[Dict[str, Any]], cli_week_of: Optional[str]) -> str:
    if cli_week_of: return cli_week_of
    candidates = [r.get("weekOf") or r.get("WeekOf") or r.get("week_of") for r in rows]
    candidates = [c for c in candidates if c]
    if not candidates:
        sys.exit("ERROR: No weekOf provided. Add a weekOf column in CSV or use --week-of YYYY-MM-DD.")
    # take the most common
    return sorted(candidates, key=lambda x: candidates.count(x), reverse=True)[0]

def main():
    ap = argparse.ArgumentParser(description="Build daily_totals.json from CSV")
    ap.add_argument("--input", "-i", default="data/daily_totals.csv", help="CSV path")
    ap.add_argument("--output", "-o", default="daily_totals.json", help="Output JSON path")
    ap.add_argument("--week-of", help='Override weekOf (e.g., "2025-09-01" or "09-01-2025")')
    ap.add_argument("--rates", default="rates.json", help="Path to rates.json for hourly rates (default: rates.json)")
    args = ap.parse_args()

    if not os.path.exists(args.input):
        sys.exit(f"CSV not found: {args.input}")
    rows = read_csv(args.input)
    if not rows:
        sys.exit("CSV is empty.")

    week_of = pick_week_of(rows, args.week_of)
    rates = read_rates_json(args.rates)

    # parks -> dow -> record
    parks: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)

    for r in rows:
        park = (r.get("park") or r.get("Park") or r.get("location") or "").strip()
        if not park:
            print("Skipping row with empty park:", r); continue

        dow = norm_dow(r.get("dow") or r.get("DOW") or r.get("day") or "")
        if dow not in DOW_ORDER:
            print(f"Skipping row with bad dow ({dow}):", r); continue

        hours   = round(parse_float(r.get("hours")), 2)
        revenue = round(parse_float(r.get("revenue") or r.get("sales")), 2)
        cost    = round(parse_float(r.get("cost")), 2)
        pct     = round(parse_pct(r.get("pct")), 2)

        # Auto-compute cost from hours * rate if cost missing/zero
        if (cost == 0.0 or not r.get("cost")) and hours > 0:
            rate = rates.get(park, 0.0)
            if rate > 0:
                cost = round(hours * rate, 2)

        # Auto-compute pct from cost and revenue if missing/zero
        if (pct == 0.0 or not r.get("pct")) and cost > 0 and revenue > 0:
            pct = round((cost / revenue) * 100.0, 2)

        parks[park][dow] = {
            "dow": dow,
            "hours": hours,
            "cost": cost,
            "revenue": revenue,     # <—— include revenue in JSON
            "pct": pct
        }

    # Fill missing days with zeros; sort parks alphabetically
    out_parks = OrderedDict()
    for park_name in sorted(parks.keys()):
        by_dow = parks[park_name]
        day_list = []
        for d in DOW_ORDER:
            if d in by_dow:
                day_list.append(by_dow[d])
            else:
                day_list.append({"dow": d, "hours": 0.0, "cost": 0.0, "revenue": 0.0, "pct": 0.0})
        out_parks[park_name] = {"days": day_list}

    result = {"weekOf": week_of, "parks": out_parks}

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        f.write("\n")

    print(f"Wrote {args.output} (weekOf={week_of}, parks={len(out_parks)})")

if __name__ == "__main__":
    main()
