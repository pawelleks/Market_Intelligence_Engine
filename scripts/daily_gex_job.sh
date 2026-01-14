#!/bin/bash
# archival job for GEX Profile
# Should be run after market close (e.g., 5:00 PM ET)

cd /app/ || exit
python3 scripts/archive_daily_gex.py
