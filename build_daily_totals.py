#!/usr/bin/env python3
"""
Build daily_totals.json from a CSV you edit in Excel.

Input (default): data/daily_totals.csv
Output (default): daily_totals.json

CSV columns (header row required):
  weekOf, park, dow, hours, cost, pct

Notes:
- "pct" may be plain number (12.72), text ("12.72%"), or an Excel-exported fraction (0.1272).
- Missing Mon–Sun rows are auto-filled with zeros for each park present in the CSV.
- The output uses the "Option 1" JSON shape your app expects:
    { "weekOf": "YYYY-MM-DD", "parks": { "<ParkName>": { "days": [...] } } }
- "totalPct" is not written; the iOS app computes weekly % automatically.
"""

import argparse, csv, json, os, sys
from collections import defaultdict, OrderedDict
from typing import Optional, List, Dict, Any

# Desired day order in output
DOW_ORDER = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]

# Allow flexible inputs like "monday", "tues", "5", etc.
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
    if not s:
        return ""
    key = s.strip().lower()
    # If alias known, use it; else try first 3 letters as Title case
    return DOW_ALIASES.get(key, s.strip()[:3].title())

def parse_float(v):
    """Parse numbers that may include $, commas, %, or be None/blank."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return 0.0
    # Remove common formatting
    s = s.replace("$", "").replace(",", "").replace("%", "")
    try:
        return float(s)
    except ValueError:
        return 0.0

def parse_pct(v):
    """
    Parse percentage values.
    Accepts:
      - 12.72     -> 12.72
      - "12.72%"  -> 12.72
      - 0.1272    -> 12.72  (Excel percent export)
    """
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        val = float(v)
        return val * 100.0 if 0 < val <= 1 else val
    s = str(v).strip()
    if not s:
        return 0.0
    if s.endswith("%"):
        return parse_float(s)  # "12.72%" -> 12.72
    val = parse_float(s)
    return val * 100.0 if 0 < val <= 1 else val

def read_csv(path: str) -> List[Dict[str, Any]]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows: List[Dict[str, Any]] = []
        for r in reader:
            # Normalize keys a bit
            row = { (k.strip() if isinstance(k,str) else k): (v.strip() if isinstance(v,str) else v) for k,v in r.items() }
            rows.append(row)
        return rows

def pick_week_of(rows: List[Dict[str, Any]], cli_week_of: Optional[str]) -> str:
    if cli_week_of:
        return cli_week_of
    # Pick the most-common non-empty value across possible "weekOf" header variants
    candidates = [r.get("weekOf") or r.get("WeekOf") or r.get("week_of") for r in rows]
    candidates = [c for c in candidates if c]
    if not candidates:
        sys.exit("ERROR: No weekOf provided. Add a weekOf column in CSV or use --week-of YYYY-MM-DD.")
    return sorted(candidates, key=lambda x: candidates.count(x), reverse=True)[0]

def main():
    ap = argparse.ArgumentParser(description="Build daily_totals.json from CSV")
    ap.add_argument("--input", "-i", default="data/daily_totals.csv", help="CSV path (default: data/daily_totals.csv)")
    ap.add_argument("--output", "-o", default="daily_totals.json", help="Output JSON path (default: daily_totals.json)")
    ap.add_argument("--week-of", help='Override weekOf (e.g., "2025-09-01" or "09-01-2025")')
    args = ap.parse_args()

    if not os.path.exists(args.input):
        sys.exit(f"CSV not found: {args.input}")

    rows = read_csv(args.input)
    if not rows:
        sys.exit("CSV is empty.")

    week_of = pick_week_of(rows, args.week_of)

    # parks -> dow -> record
    parks: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)

    for r in rows:
        park = r.get("park") or r.get("Park") or r.get("location") or ""
        park = park.strip()
        if not park:
            print("Skipping row with empty park:", r)
            continue

        dow = r.get("dow") or r.get("DOW") or r.get("day") or ""
        dow = norm_dow(dow)
        if dow not in DOW_ORDER:
            print(f"Skipping row with bad dow ({dow}):", r)
            continue

        hours = round(parse_float(r.get("hours")), 2)
        cost  = round(parse_float(r.get("cost")), 2)
        pct   = round(parse_pct(r.get("pct")), 2)

        parks[park][dow] = {
            "dow": dow,
            # "date" intentionally omitted
            "hours": hours,
            "cost": cost,
            "pct": pct
        }

    # Fill missing days with zeros; sort parks alphabetically
    out_parks = OrderedDict()
    for park_name in sorted(parks.keys()):
        day_list = []
        by_dow = parks[park_name]
        for d in DOW_ORDER:
            if d in by_dow:
                day_list.append(by_dow[d])
            else:
                day_list.append({"dow": d, "hours": 0.0, "cost": 0.0, "pct": 0.0})
        out_parks[park_name] = {"days": day_list}
        # No totalPct; app computes weekly % automatically

    result = {"weekOf": week_of, "parks": out_parks}

    # Write pretty JSON
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
        f.write("\n")

    print(f"Wrote {args.output} (weekOf={week_of}, parks={len(out_parks)})")

if __name__ == "__main__":
    main()
