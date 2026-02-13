# Real-Time vs Offline/Batch Implementation Analysis

**Audit Date**: February 12, 2026  
**Scope**: Detailed examination of each module's data flow pattern

---

## 1. Market Prices Module

### Implementation Details

**Files**:
- `src/mie_lib/data_ingest/yfinance_loader.py` (16.8KB)

**Data Sources**:
1. **Primary**: Polygon API (if `POLYGON_AVAILABLE=True`)
2. **Fallback**: yfinance library

**Data Flow**:
```
External API (Polygon/yfinance)
         ↓
fetch_full_history() OR update_ticker_incremental()
         ↓
DataFrame (OHLCV standardization)
         ↓
_write_outputs()
         ↓
data/raw/{TICKER}.parquet + data/raw/{TICKER}.csv
         ↓
Registry entry in data/meta/dataset_registry.json
```

### Key Characteristics

**Pattern**: ✅ **BATCH ONLY**

**Ingestion Schedule**:
- Full history: One-time fetch of "max" period (e.g., 20+ years)
- Incremental: Daily updates via CLI orchestrator.sh

**Update Logic**:
```python
def update_ticker_incremental(ticker: str):
    # 1. Load existing parquet
    existing = pd.read_parquet(RAW_DIR / f"{ticker}.parquet")
    last_date = existing["date"].max().date()
    
    # 2. Calculate fetch start
    start_fetch = last_date + timedelta(days=1)
    
    # 3. Check if update needed
    if start_fetch > datetime.now().date():
        return {"status": "no_new"}  # Already up-to-date
    
    # 4. Fetch only new rows
    new_df = fetch_polygon_history(ticker, start_date=start_fetch.isoformat())
    
    # 5. Gap detection (missing weekdays between last_date and first new date)
    missing_weekdays = _detect_missing_weekdays(last_date, new_dates_list)
    if missing_weekdays:
        return {"status": "gap_detected", "gap_info": ...}
    
    # 6. Append & deduplicate
    combined = pd.concat([existing, new_df])
    combined = combined.drop_duplicates(subset=["date"]).sort_values("date")
    
    # 7. Write back
    combined.to_parquet(RAW_DIR / f"{ticker}.parquet")
```

**Intraday Safety**:
```python
def _filter_intraday_rows(df):
    # Remove rows where date >= today (before market close)
    # EXCEPTION: Allow "today" after 22:00 (10 PM) for post-market close processing
    if now.hour >= 22:
        cutoff_date = datetime.now().date() + timedelta(days=1)
    else:
        cutoff_date = datetime.now().date()
    
    f = df[df["date"].dt.date < cutoff_date]
    return f, skipped_count
```

### Documentation Status

**Documented**: ✅ Correctly as batch  
**Missing**: Gap detection algorithm details

---

## 2. Options Data (Flat Files + API Fallback)

### Implementation Details

**Files**:
- `src/mie_lib/data_ingest/providers/polygon.py` (9.9KB)
- `src/mie_lib/data_ingest/providers/massive.py` (9.5KB)
- `src/mie_lib/data_ingest/providers/massive_api.py` (exists)

### Two-Part Strategy

#### Part A: Flat Files (Batch, Primary)
**Source**: Massive.com daily CSV files

**Pattern**: ✅ **BATCH**

**Data Flow**:
```
Massive.com (Daily CSV snapshot)
         ↓
data/raw/massive/options/options_YYYY-MM-DD.csv (~1-2GB)
         ↓
MassiveOptionsLoader.load_day_aggregates()
         ↓
Filter by ticker + expiration
         ↓
DataFrame with: strike, type (call/put), close, iv, gamma, delta, oi
```

**Schedule**:
- One file per trading day
- Downloaded overnight via `fetch-options-snapshot` CLI command
- Persisted for historical use

#### Part B: API (Fallback, Real-Time)
**Source**: Polygon.io REST API

**Pattern**: ⚠️ **REAL-TIME (Fallback Only)**

**Key Functions**:
```python
def fetch_options_snapshot(ticker: str, api_key: str) -> pd.DataFrame:
    """Fetch full options chain snapshot for a ticker from Polygon.io
    Returns DataFrame with: day, underlying_ticker, option_ticker, open_interest, 
    implied_volatility, gamma, delta
    """
    # Pagination-based fetch
    url = f"https://api.polygon.io/v3/snapshot/options/{api_ticker}"
    # Loop through pages, rate limiting 0.1s between requests
    # Returns all contracts for the day
```

### Critical Architectural Constraint (Code-Only)

**Constraint**: "Split-Source" Strategy

```python
# From polygon.py header
"""⛔ CRITICAL ARCHITECTURE CONSTRAINT (READ BEFORE MODIFYING):
-----------------------------------------------------------
This module adheres to the strict "Split-Source" Data Strategy defined in agent_rules.md

OPTION CHAINS: Must come from Massive.com (Flat Files). Do NOT refactor to use APIs.
ENRICHMENT: yfinance is allowed ONLY for underlying price/metadata.
Any attempt to replace the flat-file ingest with an API call is a violation of project constraints.
"""
```

**Documentation Status**: ❌ **NOT in architecture docs**

### Documentation Status

**Documented**: Partially (flat file mentioned, API fallback not explained)  
**Missing**:
- Split-source constraint not in ARCHITECT_BIBLE
- When API is used vs not used unclear
- Fallback logic undocumented

---

## 3. Expected Moves Engine (CRITICAL GAP)

### Implementation Details

**Files**:
- `src/mie_lib/analytics/expected_moves/engine.py` (29.9KB)
- `src/mie_lib/analytics/expected_moves/theta_expected_moves_engine.py` (16.3KB)
- `src/mie_lib/analytics/expected_moves/api_endpoints.py` (7.4KB)

**Total**: 53.6KB of complex code with ZERO architecture documentation

### 3-Backend Architecture

#### Backend 1: Massive Flat File (Batch, Primary for Historical)

**Data Flow**:
```
Massive CSV (data/raw/massive/options/options_YYYY-MM-DD.csv)
         ↓
run_daily_em_build(as_of = historical_date)
         ↓
MassiveOptionsLoader.load_day_aggregates(as_of_str, tickers=None)
         ↓
Full DataFrame in memory (all tickers, all expirations)
         ↓
_filter_chain(df_all, ticker, expiry_date)
         ↓
Filter by: underlying_ticker + expiration date
         ↓
Rename columns to standard: strike, option_type, prev_close_mid, iv
         ↓
enrich_with_yf_data() - Add missing OI/IV from yfinance
         ↓
_process_ticker() - For each expiry (ODTE, WEEKLY, MONTHLY):
  - Find ATM strike
  - Get call/put prices
  - Calculate EM = call_mid + put_mid
  - Calculate IV-based EM
  - Calculate confidence score (from VIX1D)
         ↓
Save to: data/analytics/expected_moves/{TICKER}_expected_moves.parquet
Save to: data/analytics/expected_moves/pending/pending_YYYY-MM-DD.parquet
```

**Trigger**: `python -m mie_lib.cli.mie update-expected-moves --as-of YYYY-MM-DD`

**Pattern**: ✅ **BATCH (Historical)**

#### Backend 2: Polygon API (Real-time, For Today)

**Data Flow**:
```
run_daily_em_build(as_of = today OR future)
         ↓
is_historical = False  (as_of >= date.today())
         ↓
For each ticker and expiration:
  fetch_option_chain_snapshot(ticker, spot_price, expiration_date)
         ↓
Polygon API: /v3/snapshot/options/{ticker}?expiration_date=YYYY-MM-DD
         ↓
Pagination-based fetch (limit=250 per page)
         ↓
Parse into: strike, option_type, prev_close_mid, iv
         ↓
enrich_with_yf_data() - Add missing OI/IV
         ↓
_process_ticker() - Same calculation as Backend 1
         ↓
Save to parquet + pending
```

**Trigger**: Automatic when `as_of >= date.today()` in orchestrator

**Pattern**: ⚠️ **REAL-TIME (For Today Only)**

**When Used**:
- Nightly orchestrator runs with `as_of = date.today()`
- Flat file not yet generated for the day
- Polygon API used as gap-filler until flat file available

#### Backend 3: Theta Data REST (Independent Real-Time)

**Data Flow**:
```
User calls: GET /api/v1/expected_moves/theta/latest/{ticker}
         ↓
ThetaExpectedMovesEngine.run(ticker)
         ↓
get_spot_price() → Theta REST /v2/hist/stock/eod or /v2/hist/index/eod
         ↓
get_last_trading_day() → Determine previous complete trading session
         ↓
get_expirations(as_of) → Resolve 0DTE, WEEKLY, MONTHLY expirations
         ↓
For each expiration:
  get_atm_straddle(option_root, exp_date, spot_price)
         ↓
  Theta API: /v2/bulk_snapshot/option/quote?root=SPXW&exp=YYYYMMDD
         ↓
  Parse straddle price = call_price + put_price
         ↓
  Apply bad tick filter (near-zero detection + estimation)
         ↓
  Calculate EM = straddle_price * SIGMA_FACTOR (0.85)
         ↓
Save to: data/expected_moves_v2/{ticker}_expected_moves_v2.parquet
         ↓
Return JSON response with: high, low, plus_minus, debug info
```

**Pattern**: ⚠️ **REAL-TIME (On-Demand)**

**Independent System**:
- Not part of main pipeline orchestrator
- Separate data directory
- Separate parquet files
- Direct REST API calls only
- Accessible via dedicated endpoint

### Data Persistence (3-Layer System)

**Layer 1: Main History (Parquet)**
```
data/analytics/expected_moves/{TICKER}_expected_moves.parquet
Columns: date, expiry_type, expiry_date, spot_price, expected_move, 
         upper_range, lower_range, vix1d, confidence_score, timestamp
```

**Layer 2: Latest (JSON)**
```
data/analytics/options/latest.json
{
  "as_of": "2026-02-12",
  "source": "MassiveFlatFile",
  "vix1d": 15.4,
  "confidence_score": 75,
  "tickers": {
    "SPY": {
      "spot_price": 450.12,
      "expirations": {
        "ODTE": {...},
        "WEEKLY": {...},
        "MONTHLY": {...}
      }
    }
  }
}

Merge Logic: If existing JSON has newer as_of, preserve it + merge new tickers
```

**Layer 3: Pending (Parquet)**
```
data/analytics/expected_moves/pending/pending_YYYY-MM-DD.parquet
Columns: ticker, expiry_type, expiry_date, underlying_price, 
         expected_move_dollars, upper_range, lower_range, vix1d_value, 
         confidence_score_percent, timestamp

Purpose: Separate queue for reliability/backtest processor
Used to track EM accuracy post-expiration
```

### Calculation Methods (Undocumented)

**Method 1: Straddle EM**
```python
def calculate_straddle_em(call_mid: float, put_mid: float) -> float:
    """Expected Move = ATM Call Price + ATM Put Price"""
    return call_mid + put_mid
```

**Method 2: IV-Based EM**
```python
def calculate_iv_em(spot_price: float, iv_val: float, days_to_expiry: int) -> float:
    """EM = Spot * IV * sqrt(DTE / 365)"""
    # Formula not shown in code, but typical Black-Scholes sigma interpretation
    # Approximates 1-standard-deviation move
    return spot_price * iv_val * (days_to_expiry / 365) ** 0.5
```

**Method 3: Confidence Score**
```python
def calculate_confidence_score(vix1d_val: float) -> int:
    """Confidence based on VIX1D level"""
    # Formula not documented in code
    # Presumably: higher VIX → lower confidence
    # Returns: 0-100 integer
```

**Method 4: Black-Scholes Fallback**
```python
# When price missing, estimate using Black-Scholes
from mie_lib.analytics.gex.gex_engine import BlackScholes
T = max(days_to_expiry, 0.001) / 365.0
r = 0.045  # HARDCODED: Risk-free rate = 4.5% (assumption not documented)
if otype == "C":
    val = BlackScholes.call_price(spot_price, strike, T, r, iv_val)
else:
    val = BlackScholes.put_price(spot_price, strike, T, r, iv_val)
```

### API Endpoints

**Endpoint 1: Latest Batch Data**
```
GET /api/v1/expected_moves/latest
GET /api/v1/expected_moves/massive/latest

Returns: data/analytics/options/latest.json
Mode: Pure batch (serves pre-computed)
```

**Endpoint 2: Reliability Statistics**
```
GET /api/v1/expected_moves/reliability/summary
GET /api/v1/expected_moves/reliability/history?ticker=SPY&expiry_type=WEEKLY

Returns: Aggregated statistics from parquet files
Mode: Pure batch (aggregates historical data)
```

**Endpoint 3: Theta Real-Time**
```
GET /api/v1/expected_moves/theta/latest/{ticker}

Returns: Live calculation via Theta API
Mode: Real-time on-demand
Payload: Same format as batch but calculated fresh
```

**Endpoint 4: Static Pre-Computed**
```
GET /api/v1/expected_moves/static/latest

Returns: data/public/data/expected_moves_static.json
Mode: Pure batch (static file, instant)
```

### Documentation Status

**Documented**: ❌ **ZERO**

**Missing**:
- Module architecture (3 backends)
- 3-backend decision logic
- Calculation formulas
- Confidence scoring
- Data persistence layers
- API endpoint reference
- When Theta backend is appropriate
- Black-Scholes assumptions
- Reliability tracking workflow
- Date precedence logic in JSON merge

---

## 4. GEX Engine (Batch-First with Real-Time Option)

### Implementation Details

**Files**:
- `src/mie_lib/analytics/gex/api_endpoints.py` (6.5KB)
- `src/mie_lib/analytics/gex/gex_engine.py` (referenced)

### Data Flow (3-Layer Preference)

```
User Request: GET /api/v1/gex/latest/{ticker}
         ↓
1. Try In-Memory Cache (Fastest)
   └─ If hit AND age < 15 minutes → Return cached data
         ↓
2. Try Disk Storage (Batch)
   └─ Load from: data/analytics/gex/{TICKER}/profile_{DATE}.json
   └─ If valid → Return + update cache
         ↓
3. Calculate On-Demand (Real-Time Fallback)
   └─ Only if missing OR force_refresh=true
   └─ GEXEngine.fetch_and_calculate_gex(ticker)
   └─ Return + update cache
   └─ Save to cache (in-memory only, not to disk)
         ↓
Return response
```

### Cache Strategy (Undocumented)

**In-Memory Cache**:
```python
_GEX_CACHE: Dict[str, Dict] = {}  # {ticker: {"timestamp": datetime, "data": dict}}
CACHE_TTL_MINUTES = 15
```

**TTL Logic**:
```python
if ticker in _GEX_CACHE:
    entry = _GEX_CACHE[ticker]
    age = datetime.now() - entry["timestamp"]
    if age < timedelta(minutes=CACHE_TTL_MINUTES):  # 15 minutes
        return entry["data"]  # Serve from cache
```

### Real-Time Capability (Hidden Feature)

**Parameter**: `force_refresh: bool = False`

```python
@router.get("/latest/{ticker}")
def get_latest_gex(ticker: str, force_refresh: bool = False):
    """
    Returns the latest Gamma Exposure (GEX) profile for a ticker.
    STRICTLY prefers persistent storage (Daily Build).
    Only calculates on-demand if:
    1. Data is completely missing from disk.
    2. force_refresh=True is passed.
    """
```

**Undocumented Usage**:
```
GET /api/v1/gex/latest/SPY?force_refresh=true  → Forces live calculation
GET /api/v1/gex/latest/SPY                      → Prefers cached/batch
```

### Pattern

**Documented**: ✅ As batch only  
**Actual**: ⚠️ **BATCH-FIRST WITH REAL-TIME OPTION**

### Documentation Status

**Missing**:
- `force_refresh` parameter not documented
- Cache TTL not documented
- Fallback behavior not explained
- When on-demand calculation is triggered
- Data quality differences (batch vs on-demand)

---

## 5. Macro/FRED Data (Correctly Documented as Batch)

### Implementation Details

**Files**:
- `src/mie_lib/data_ingest/macro/providers/fred.py` (8.5KB)

### Data Flow

```
FRED API (Federal Reserve Economic Data)
         ↓
FredProvider.fetch_series(series_id, start_date="1970-01-01")
         ↓
Load existing parquet (if any)
         ↓
fetch_series_incremental() - Only fetch new observations
         ↓
If no existing: Fetch full from 1970-01-01
If existing: Fetch from (last_date + 1 day) to today
         ↓
Rate limiting: 0.5-1.0 second delay between API calls
         ↓
Clean & validate: Remove NaNs (FRED uses '.' for missing)
         ↓
Apply transformations (e.g., ICSA inversion for unemployment claims)
         ↓
Dedup on 'date', sort, reset index
         ↓
Save to: data/raw/macro/fred/{SERIES_ID}.parquet
```

### Incremental Update Logic

```python
def fetch_series_incremental(series_id: str, min_start_date: str = "1960-01-01"):
    # 1. Get last date from existing parquet
    last_date = self.get_last_date(series_id)
    
    # 2. If not exists, fetch full history from 1960
    if last_date is None:
        return self.fetch_series(series_id, start_date=min_start_date)
    
    # 3. If up-to-date, skip
    next_date = (last_date + timedelta(days=1)).strftime('%Y-%m-%d')
    today = datetime.now().strftime('%Y-%m-%d')
    if next_date >= today:
        return existing_data
    
    # 4. Fetch only new observations
    new_data = self.fetch_series(series_id, start_date=next_date)
    
    # 5. Merge & deduplicate
    combined = pd.concat([existing, new_data])
    combined = combined.drop_duplicates(subset=['date'], keep='last').sort_values('date')
    
    return combined
```

### Pattern

**Pattern**: ✅ **BATCH ONLY**

**Schedule**:
- Daily via orchestrator
- Incremental updates only
- Rate-limited API calls
- Self-healing (downloads missing files on demand)

### Documentation Status

**Documented**: ✅ Correctly as batch  
**Coverage**: Good in ARCHITECT_BIBLE

---

## 6. HMM Engine (Batch Only)

### Implementation Details

**Files**:
- `src/mie_lib/analytics/hmm/api_endpoints.py` (2.0KB)

### Data Flow

```
Daily Pipeline (Not on API request)
         ↓
build-hmm-daily --tickers @config
         ↓
Calculate HMM regimes on feature data
         ↓
Save to: data/analytics/hmm/
         ↓
API Request: GET /backtest/{ticker}
         ↓
Load: data/analytics/hmm/backtest_results_{ticker}.json
         ↓
Return pre-computed results
```

### Pattern

**Pattern**: ✅ **BATCH ONLY (No Real-Time)**

**API Behavior**:
- Pure file loading
- No calculations on request
- Returns 404 if data missing (run pipeline first)

### Documentation Status

**Documented**: ✅ Correctly as batch  
**Coverage**: Good in daily_pipeline_run.md

---

## Summary Table

| Module | Data Source | Pattern | Documented | Status |
|--------|-------------|---------|-----------|---------|
| Market Prices | YFinance/Polygon | Batch | ✅ | Correct |
| Options (Flat File) | Massive CSV | Batch | ✅ | Correct |
| Options (API) | Polygon API | Real-time fallback | ⚠️ | Undocumented fallback |
| Expected Moves | 3 backends | Hybrid | ❌ | **MISSING** |
| GEX | Batch/On-demand | Batch-first | ⚠️ | Hidden real-time feature |
| FRED | FRED API | Batch | ✅ | Correct |
| HMM | Pre-computed | Batch | ✅ | Correct |

---

**Status**: ✅ Analysis complete. Ready for documentation improvements.
