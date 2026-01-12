#!/usr/bin/env python3
"""
Audit Signal Storage Script

Scans specific data directories for parquet files, loads them, and produces a summary of:
- File Metadata (Path, Size, Modified)
- Content Stats (Rows, Columns, Date Range)
- Signal Columns (Identification based on keywords)
- Quality (Null counts in signal columns)

Output is printed to stdout in Markdown format for easy copy-pasting into the report.
"""

import os
import sys
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime
import warnings

# Suppress warnings
warnings.filterwarnings("ignore")

# Setup paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Directories to scan
SCAN_DIRS = [
    DATA_DIR / "analytics" / "macro",
    DATA_DIR / "processed",
]

def format_size(size_bytes):
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

def is_signal_column(col_name):
    keywords = [
        'signal', 'prob', 'state', 'phase', 'cycle', 'gap', 'score', 'ratio', 
        'index', 'impulse', 'trend', 'regime', 'warning', 'alert', 'lei', 'coi', 'lag'
    ]
    return any(k in col_name.lower() for k in keywords)

def analyze_file(file_path):
    try:
        stats = {
            'path': str(file_path.relative_to(BASE_DIR)),
            'size': format_size(file_path.stat().st_size),
            'modified': datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%Y-%m-%d'),
            'error': None
        }

        if file_path.suffix == '.parquet':
            df = pd.read_parquet(file_path)
        elif file_path.suffix == '.csv':
            df = pd.read_csv(file_path)
        elif file_path.suffix == '.json':
            # Try reading json, might fail if structure is complex
            try:
                df = pd.read_json(file_path)
            except:
                with open(file_path, 'r') as f:
                    stats['error'] = "JSON structure too complex or not tabular"
                return stats
        else:
            return None # Skip unknown

        if df.empty:
            stats['rows'] = 0
            return stats

        stats['rows'] = len(df)
        stats['cols'] = list(df.columns)
        
        # Date Handling
        date_col = None
        for col in df.columns:
            if 'date' in col.lower() or 'timestamp' in col.lower() or df.index.name == col:
                date_col = col
                break
        
        if date_col and date_col in df.columns:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            valid_dates = df[date_col].dropna()
            if not valid_dates.empty:
                stats['start_date'] = valid_dates.min().strftime('%Y-%m-%d')
                stats['end_date'] = valid_dates.max().strftime('%Y-%m-%d')
                stats['duration_years'] = round((valid_dates.max() - valid_dates.min()).days / 365.25, 1)
        elif isinstance(df.index, pd.DatetimeIndex):
            stats['start_date'] = df.index.min().strftime('%Y-%m-%d')
            stats['end_date'] = df.index.max().strftime('%Y-%m-%d')
            stats['duration_years'] = round((df.index.max() - df.index.min()).days / 365.25, 1)
        else:
            stats['start_date'] = "Unknown"
            stats['end_date'] = "Unknown"

        # Signal Analysis
        signals = [c for c in df.columns if is_signal_column(c)]
        stats['signals'] = signals
        
        # Quality Check (Nulls in signals)
        if signals:
            null_counts = df[signals].isnull().sum()
            stats['nulls'] = {k: v for k, v in null_counts.items() if v > 0}
        
        return stats

    except Exception as e:
        stats['error'] = str(e)
        return stats

def main():
    print("# Signal Data Usage Audit Results\n")
    print(f"**Scan Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    
    files_found = []
    
    for d in SCAN_DIRS:
        if not d.exists():
            continue
        for f in d.rglob("*"):
            if f.is_file() and f.suffix in ['.parquet', '.csv', '.json']:
                files_found.append(f)

    results = []
    for f in files_found:
        res = analyze_file(f)
        if res:
            results.append(res)
            
    # Summary Table
    print("## File Inventory\n")
    print("| File Path | Rows | Start | End | Years | Signals Count |")
    print("|-----------|------|-------|-----|-------|---------------|")
    for r in results:
        if r.get('error'):
            print(f"| {r['path']} | ERROR | - | - | - | - |")
        else:
            sig_count = len(r.get('signals', []))
            print(f"| {r['path']} | {r.get('rows', 0)} | {r.get('start_date', '-')} | {r.get('end_date', '-')} | {r.get('duration_years', '-')} | {sig_count} |")

    # Detailed Breakdown
    print("\n## Detailed Analysis\n")
    for r in results:
        if r.get('error'):
             continue
             
        print(f"### `{r['path']}`")
        print(f"- **Size**: {r['size']}")
        print(f"- **Columns**: `{', '.join(r['cols'][:10])}`" + ("..." if len(r['cols']) > 10 else ""))
        
        if r.get('signals'):
            print("- **Detected Signals**:")
            for s in r['signals']:
                nulls = r.get('nulls', {}).get(s, 0)
                quality = "✅ Clean" if nulls == 0 else f"⚠️ {nulls} Nulls"
                print(f"    - `{s}`: {quality}")
        else:
            print("- **No obvious signal columns detected.**")
            
        print("\n")

if __name__ == "__main__":
    main()
