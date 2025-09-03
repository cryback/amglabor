#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

# Build from CSV -> JSON
python3 build_daily_totals.py --input "data/daily_totals.csv" --output "daily_totals.json"

# Open the result for a quick eyeball check
open "daily_totals.json"
echo "Done."
