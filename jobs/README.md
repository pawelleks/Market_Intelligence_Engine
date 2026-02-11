# Jobs Directory

This directory contains scheduled job scripts that run as part of the Daily Pipeline.

## Jobs

### fetch_market_eod_chains.py
Fetches End-of-Day (EOD) full option chains for multiple symbols from ThetaData.

**Schedule:** Daily at 22:30 UTC (after market close)

**Symbols:** `SPX`, `SPY`, `NDX`, `QQQ`, 'IWM'

**Output:** `data/raw/chain_[SYMBOL]_[YYYY-MM-DD].parquet`

**Features:**
- **Bulk Fetching:** Uses ThetaData's `/v2/bulk_snapshot/option/quote` endpoint for sub-10 second execution.
- Multi-symbol support with per-symbol error handling
- Symbol-specific root matching (e.g., SPX + SPXW weeklies)
- Automatic date selection (today if after close, yesterday if before)
- Skips if output file already exists

**Usage:**
```bash
python jobs/fetch_market_eod_chains.py
```

---

### process_implied_probabilities.py
Processes raw option chains into implied probability distributions for multiple symbols.

**Schedule:** Daily at 22:35 UTC (5 mins after chain fetch)

**Inputs:** `data/raw/chain_[SYMBOL]_*.parquet` (today's files)

**Outputs:**
- `frontend/public/data/probability_surface_[SYMBOL].json` — Density surfaces (PDF bell curves)
- `frontend/public/data/forward_cone_[SYMBOL].json` — Forward projections (p05-p95 quantiles)

**Per-Symbol ERP (Drift Adjustment):**
| Symbol | ERP   | Description         |
|--------|-------|---------------------|
| SPX    | 4.0%  | S&P 500 baseline    |
| SPY    | 4.0%  | S&P 500 ETF         |
| NDX    | 5.0%  | Nasdaq 100          |
| QQQ    | 5.0%  | Nasdaq 100 ETF      |
| IWM    | 6.0%  | Russell 2000 (high beta) |

**Features:**
- Multi-symbol processing with per-symbol error handling
- Continues to next symbol if one fails
- Automatic chain file discovery
- Breeden-Litzenberger PDF extraction
- Forward price via Put-Call Parity
- 8 nearest expirations for density surfaces
- 45-day forward quantile projection
- Pipeline audit integration

**Usage:**
```bash
python jobs/process_implied_probabilities.py
```
