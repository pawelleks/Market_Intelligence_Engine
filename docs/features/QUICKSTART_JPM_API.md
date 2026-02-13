# Quick Start: JPM Dashboard API Testing

## Prerequisites

Ensure FRED data has been downloaded and aggregated:
```bash
cd /Users/pawelleks/Documents/Python/Projects/Market_Intelligence_Engine

# Download FRED data (should have 98 series)
python -m mie_lib.cli.mie build-macro-data

# Run aggregation
python -m mie_lib.cli.mie aggregate-jpm-dashboard

# Verify output files exist
ls -lh data/processed/jpm_dashboard/
# Should show 10 parquet files (gdp.parquet, labor_market.parquet, etc.)

# Validate data quality
python -m mie_lib.analytics.jpm_dashboard.validate
# Should show PASS or WARN (not FAIL)
```

## Starting the API Server

```bash
# Start the FastAPI server
python run_api.py

# Server will start on http://localhost:8000
# API documentation available at: http://localhost:8000/docs
```

## Testing the API

### Option A: Bash Script (Recommended for Mac/Linux)
```bash
./scripts/test_jpm_api.sh
```

### Option B: Python Script
```bash
python tests/test_jpm_api.py
```

### Option C: Manual curl Commands
```bash
# Health check
curl http://localhost:8000/api/v1/jpm-dashboard/health | python -m json.tool

# Overview (all 10 indicators with sparklines)
curl http://localhost:8000/api/v1/jpm-dashboard/overview | python -m json.tool

# Specific indicator (labor market)
curl http://localhost:8000/api/v1/jpm-dashboard/indicators/labor-market | python -m json.tool

# Single series (unemployment rate)
curl http://localhost:8000/api/v1/jpm-dashboard/series/UNRATE | python -m json.tool

# Date range query
curl "http://localhost:8000/api/v1/jpm-dashboard/indicators/inflation?start_date=2023-01-01&end_date=2024-01-01" | python -m json.tool
```

## Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/jpm-dashboard/health` | GET | Data freshness status for all indicators |
| `/api/v1/jpm-dashboard/overview` | GET | Latest values + 12-month sparklines (all 10 indicators) |
| `/api/v1/jpm-dashboard/indicators/{category}` | GET | Full historical data for specific indicator |
| `/api/v1/jpm-dashboard/series/{series_id}` | GET | Single FRED series with all calculated metrics |

## Available Categories

- `gdp` - GDP & Economic Output
- `consumer-spending` - Consumer Expenditure
- `labor-market` - Employment & Unemployment
- `interest-rates` - Federal Funds & Treasury Yields
- `inflation` - CPI & Price Indices
- `business-confidence` - Surveys & Sentiment
- `stock-market` - S&P 500 & VIX
- `trade-balance` - Imports, Exports, Deficit
- `housing` - Housing Starts & Permits
- `policy` - Federal Reserve Balance Sheet

## Expected Results

**All endpoints should return:**
- HTTP 200 status code
- Valid JSON response
- No error messages

**Health endpoint should show:**
- `status`: "ok" or "stale" for each indicator
- `indicators`: array of 10 objects with freshness data

**Overview endpoint should return:**
- 10 indicator objects
- Each with `current_value`, `current_date`, `sparkline` (12 points)

## Troubleshooting

### Issue: API returns 404
**Cause:** Aggregated data files don't exist

**Solution:**
```bash
python -m mie_lib.cli.mie aggregate-jpm-dashboard
```

### Issue: API returns 503 (Service Unavailable)
**Cause:** Data is too stale (> threshold days old)

**Solution:**
```bash
# Re-download FRED data
python -m mie_lib.cli.mie build-macro-data

# Re-run aggregation
python -m mie_lib.cli.mie aggregate-jpm-dashboard
```

### Issue: Some categories return empty data
**Cause:** FRED series failed to download

**Solution:**
```bash
# Check which series failed
cat data/pipeline_status/economic_pipeline.json | grep "errors"

# Check validation output
python -m mie_lib.analytics.jpm_dashboard.validate
```

### Issue: Module import errors
**Cause:** Missing dependencies

**Solution:**
```bash
pip install -r requirements.txt
```

## Testing on Remote Server

```bash
# SSH to remote
ssh deploy@digitalocean

# Run tests against production API
cd ~/market_intelligence_engine
API_BASE_URL=http://localhost:8000 python tests/test_jpm_api.py
```
