# Data Provider Strategy Analysis

**Audit Date**: February 12, 2026  
**Scope**: Provider hierarchy, fallback logic, and Split-Source constraints

---

## Part 1: Current Provider Hierarchy (Code vs Documentation)

### Market Prices (Stocks/Indices)

**Documented** (ARCHITECTURE_PRINCIPLES.md):
> "External source (Yahoo Finance, FRED API, etc.)"

**Actual** (yfinance_loader.py):
```
Primary:   Polygon API (if POLYGON_AVAILABLE=True)
Fallback:  yfinance library
```

**Code**:
```python
# Try Polygon First (Primary)
if POLYGON_AVAILABLE:
    try:
        df = fetch_polygon_history(ticker)
        if not df.empty:
            source = "polygon"
    except Exception as e:
        LOG.warning(f"Polygon fetch failed: {e}")

# Fallback to YFinance
if df.empty:
    df = _df_from_yfinance(ticker)
    if not df.empty:
        source = "yfinance"
```

**Discrepancy**: 
- Docs mention Yahoo Finance as primary
- Code shows Polygon as primary (when available)
- Fallback chain not documented

**Impact**: MEDIUM
- New developers might assume yfinance is primary
- Polygon dependency not explicit in architecture docs

---

### Options Data (3-Tier Hierarchy)

#### Tier 1: Massive Flat Files (Primary, Batch)
**Purpose**: Batch processing, cost-effective, historical compliance  
**Source**: Massive.com daily CSV snapshots  
**Location**: `data/raw/massive/options/options_YYYY-MM-DD.csv` (~1-2GB)  
**Provider**: MassiveOptionsLoader (flat-file ingest)  

**When Used**:
- Historical dates (`as_of < date.today()`)
- Processing day where flat file already downloaded
- Reliability backtest validation

**Format**:
```csv
day,underlying_ticker,option_ticker,strike,type,expiration,close,iv,gamma,delta,oi
2026-02-12,SPY,SPY250219C450,450.0,call,2026-02-19,2.45,0.18,0.045,0.62,154200
```

#### Tier 2: Polygon API (Fallback, Real-Time)
**Purpose**: Gap-filler when flat file not ready, live snapshot  
**Source**: Polygon.io REST API `/v3/snapshot/options/`  
**Provider**: polygon.fetch_options_snapshot()  

**When Used**:
- Today's processing when flat file not available
- Expected Moves calculation for current day
- Real-time enrichment

**Implementation**:
```python
def fetch_options_snapshot(ticker: str, api_key: str) -> pd.DataFrame:
    """Fetch full options chain snapshot from Polygon.io"""
    url = f"https://api.polygon.io/v3/snapshot/options/{api_ticker}"
    
    # Pagination loop with rate limiting
    all_results = []
    page_count = 0
    while url:
        resp = requests.get(url, timeout=30)
        results = resp.json().get("results", [])
        all_results.extend(results)
        
        # Rate limit: 0.1s between pages
        time.sleep(0.1)
        
        # Parse next page URL
        url = resp.json().get("next_url")
        if url:
            url = f"{url}&apiKey={api_key}"
    
    # Format to Massive schema
    return pd.DataFrame(formatted)
```

#### Tier 3: Forbidden (Constraint)
**Restriction**: Do NOT refactor options chains to use APIs as primary  

**Code Comments**:
```python
"""⛔ CRITICAL ARCHITECTURE CONSTRAINT (READ BEFORE MODIFYING):
This module adheres to the strict "Split-Source" Data Strategy

OPTION CHAINS: Must come from Massive.com (Flat Files). Do NOT refactor to use APIs.
ENRICHMENT: yfinance is allowed ONLY for underlying price/metadata.
Any attempt to replace the flat-file ingest with an API call is a violation of project constraints.
"""
```

**Rationale** (inferred from constraints):
- Cost optimization (flat files cheaper than API calls)
- Compliance/auditability (CSV trail for backtest validation)
- Deterministic processing (avoid API latency/failures)
- Consistency (same data for backtest and live)

**Documentation Status**: ❌ **NOT IN ARCHITECT_BIBLE**

---

### Economic Data (FRED)

**Documented** (ARCHITECTURE_PRINCIPLES.md):
> "External source (Yahoo Finance, FRED API, etc.)"

**Actual** (fred.py):
```
Primary:   FRED API (Federal Reserve Economic Data)
Fallback:  Local parquet cache
```

**Provider**:
```python
class FredProvider:
    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"
    
    def fetch_series(series_id: str, start_date: Optional[str] = "1970-01-01"):
        """Fetch from FRED API with rate limiting"""
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json"
        }
        
        response = httpx.get(self.BASE_URL, params=params, timeout=10.0)
        # Parse observations, clean NaNs (FRED uses '.' for missing)
        # Apply transformations (e.g., ICSA inversion)
        # Rate limit: 0.5s delay between calls
```

**Incremental Strategy**:
```python
def fetch_series_incremental(series_id: str):
    last_date = self.get_last_date(series_id)
    
    if last_date is None:
        # Full history from 1960
        return fetch_series(series_id, start_date="1960-01-01")
    
    if (last_date + 1 day) >= today:
        # Already up-to-date
        return existing_data
    
    # Fetch only new observations
    new_data = fetch_series(series_id, start_date=next_date)
    
    # Merge with existing
    return combined
```

**Documentation Status**: ✅ **Correctly described**

---

### Expected Moves (3-Backend Strategy)

#### Backend 1: Massive Flat File (Primary, Historical)
- **Source**: Bulk CSV from Massive.com
- **When**: `as_of < date.today()`
- **Constraint**: "Strict Flat File usage" - no API fallback if missing
- **Purpose**: Historical backtest validation, cost optimization

#### Backend 2: Polygon API (Live Gap-Filler)
- **Source**: Polygon.io REST API
- **When**: `as_of >= date.today()` and flat file not ready
- **Purpose**: Real-time calculation until flat file available
- **Rate Limiting**: 0.1s between pagination requests

#### Backend 3: Theta Data (Independent)
- **Source**: Theta Terminal REST API (port 25510)
- **When**: User requests `/api/v1/expected_moves/theta/latest/{ticker}`
- **Purpose**: Alternative real-time calculation
- **Independence**: Separate parquet storage, not integrated into main pipeline

**Documentation Status**: ❌ **NOT IN ARCHITECT_BIBLE**

---

## Part 2: Split-Source Data Strategy (Critical Constraint)

### Constraint Definition

**Location**: Code comments in:
- `src/mie_lib/data_ingest/providers/polygon.py`
- `src/mie_lib/data_ingest/providers/massive.py`
- `src/mie_lib/analytics/expected_moves/engine.py`

**Constraint Text**:
```
"OPTION CHAINS: Must come from Massive.com (Flat Files). 
 Do NOT refactor to use APIs.
 ENRICHMENT: yfinance is allowed ONLY for underlying price/metadata.
 Any attempt to replace the flat-file ingest with an API call 
 is a violation of project constraints."
```

### Why This Constraint Exists (Inferred)

#### 1. Cost Optimization
- Massive flat files: Lower cost per record
- API calls: Higher cost at scale (100M+ option records/day)
- Flat files allow bulk processing at fixed cost

#### 2. Compliance & Auditability
- CSV files create immutable audit trail
- Flat files can be archived for regulatory compliance
- Deterministic: Same data in backtest and live
- APIs are ephemeral (no historical snapshot for backtest)

#### 3. Deterministic Processing
- Flat files available at known time
- No API latency/failures during processing
- Consistent results across runs (reproducibility)
- API failures could cause data gaps

#### 4. Consistency Principle
- Backtest must use exact same data as live
- Historical flat files ensure consistency
- APIs would give different data (updated OI, IV, etc.) if re-fetched

### How Constraint is Enforced

#### Enforcement Mechanism 1: Conditional Logic
```python
# In expected_moves/engine.py
if is_historical:
    # Use flat file (mandatory)
    loader.download_day_snapshot(as_of_str)
    df_all = loader.load_day_aggregates(as_of_str, tickers=None)
else:
    # Live mode: Use API as gap-filler
    # But NEVER as replacement for flat file for historical dates
```

#### Enforcement Mechanism 2: Code Comments
```python
# ⛔ WARNING - Developers educated not to change
"Do NOT refactor to use APIs" (explicit instruction in comments)
```

#### Enforcement Mechanism 3: Agent Rules
**File**: `agent_rules.md` (referenced in code)
- Specifies "Split-Source Data Strategy"
- Forbids API refactoring for options chains
- Creates cultural/procedural enforcement

### Violation Prevention

**Question**: What happens if someone tries to use Polygon API for options chains as primary?

**Answer**: Code design prevents easy violation:
```python
# Massive-first design in Expected Moves:
if is_historical:
    # MUST load flat file
    df_all = loader.load_day_aggregates(as_of_str)
    
    # NEVER tries API if flat file missing
    # Returns empty DataFrame instead
    if df_all.empty:
        LOG.warning("No flat file for historical date")
        return {}  # No fallback to API

# Only live mode gets API fallback
```

### Documentation Status

**Current**: ❌ **NOT DOCUMENTED**

**Found In**: Code comments only (not discoverable)

**Impact**: HIGH
- New developers might not understand constraint
- Could refactor against project rules
- Architectural decision invisible

**Recommendation**: Add to ARCHITECTURE_PRINCIPLES.md:
```markdown
## Data Provider Hierarchy (Split-Source Strategy)

### Option Chains
1. Primary: Massive.com flat files (CSV, daily batch)
2. Enrichment: yfinance (for missing OI/IV only)
3. Fallback: Polygon API (live mode only, never for historical)
4. FORBIDDEN: Do NOT refactor to use APIs as primary source

Rationale:
- Cost optimization
- Compliance/auditability
- Deterministic processing
- Consistency (backtest uses exact same data as live)

### Spot Prices & Metadata
1. Primary: yfinance
2. Fallback: Polygon API
3. Real-time: Theta Data REST API (indices)

### Economic Data (FRED)
1. Primary: FRED API with incremental updates
2. Fallback: Local parquet cache
```

---

## Part 3: Provider Integration Matrix

| Component | Primary | Secondary | Fallback | Purpose |
|-----------|---------|-----------|----------|---------|
| **Market Prices** | Polygon API | yfinance | None | Historical prices (daily append) |
| **Options (Batch)** | Massive CSV | - | None | Daily flat file snapshot |
| **Options (Live)** | Massive CSV | Polygon API | None | Today's data if flat file late |
| **Expected Moves** | Massive (hist) | Polygon (live) | Theta (alt) | EM calculation by backend |
| **FRED Data** | FRED API | Local cache | None | Economic indicators |
| **Spot Price** | yfinance | Polygon API | Theta REST | Underlying price for EM |
| **VIX** | Polygon API | - | None | Confidence score input |

---

## Part 4: Real-World Data Flow Examples

### Scenario 1: Historical Backtest (2 Months Ago)

```
User Request: Calculate EM for 2025-12-15
         ↓
as_of = 2025-12-15 (historical, < today)
         ↓
run_daily_em_build(as_of=2025-12-15)
         ↓
is_historical = True
         ↓
MassiveOptionsLoader.download_day_snapshot("2025-12-15")
         ↓
Massive.com provides: options_2025-12-15.csv
         ↓
loader.load_day_aggregates("2025-12-15")
         ↓
DataFrame loaded (millions of option records)
         ↓
Filter by ticker + expiry
         ↓
Enrich with yfinance OI/IV (if missing)
         ↓
Calculate EM for each expiration
         ↓
Save to parquet (for reliability backtest)
```

**Constraints Enforced**:
- ✅ Massive CSV used (primary)
- ✅ yfinance for enrichment only
- ✅ No Polygon API calls for option chains
- ✅ Data immutable (flat file saved as-is)

---

### Scenario 2: Today's Real-Time EM

```
Nightly orchestrator runs at 20:00 UTC (post-market in US)
         ↓
run_daily_em_build(as_of=date.today())
         ↓
as_of >= date.today() → is_historical = False
         ↓
Flat file for today not ready yet (Massive publishes after EOD)
         ↓
For each ticker + expiration:
  fetch_option_chain_snapshot(ticker, spot_price, exp_date)
         ↓
  Call Polygon API: /v3/snapshot/options/{ticker}?expiration_date=YYYY-MM-DD
         ↓
  Polygon API (real-time fallback)
         ↓
  Rate limit: 0.1s between pagination
         ↓
Enrich with yfinance OI/IV
         ↓
Calculate EM (Polygon chain + spot price)
         ↓
Save to parquet + latest.json
         ↓
Later: Massive flat file arrives
         ↓
Tomorrow morning: Re-run with flat file for accuracy
```

**Constraints Enforced**:
- ✅ Polygon used as fallback (not primary)
- ✅ Flat file preferred when available
- ✅ yfinance for enrichment
- ✅ Re-run with flat file for accuracy

---

### Scenario 3: Theta Real-Time Alternative

```
User calls: GET /api/v1/expected_moves/theta/latest/SPY
         ↓
Independent from main pipeline
         ↓
ThetaExpectedMovesEngine.run("SPY")
         ↓
Not constrained by Split-Source rule
         ↓
get_spot_price(): Theta REST API
         ↓
get_expirations(): Calculate from date
         ↓
For each expiration:
  get_atm_straddle(): Theta REST /v2/bulk_snapshot/option/quote
         ↓
  Parse: call_price + put_price
         ↓
  Bad tick filter + estimation
         ↓
  EM = straddle × 0.85
         ↓
Save to separate parquet (data/expected_moves_v2/)
         ↓
Return JSON (independent from batch pipeline)
```

**Constraints Enforced**:
- ✅ Theta backend separate (not affecting main pipeline)
- ✅ No Split-Source rule applies
- ✅ Real-time calculation on-demand
- ✅ Separate data storage (independent)

---

## Part 5: Discrepancy Summary

### Documented vs Actual

| Aspect | Documented | Actual | Severity |
|--------|-----------|--------|----------|
| Market Prices Primary | Yahoo Finance | Polygon API | MEDIUM |
| Options Primary | Not clear | Massive CSV | HIGH |
| Options Fallback | Not documented | Polygon API | HIGH |
| Split-Source Rule | Not in docs | Code constraint | CRITICAL |
| Expected Moves Backends | Not mentioned | 3 backends | CRITICAL |
| Theta Integration | Not mentioned | Full system | HIGH |
| FRED Strategy | Documented | FRED API | LOW |

---

## Part 6: Recommendations

### Critical (Do First)
1. **Document Split-Source Constraint**
   - Add section to ARCHITECTURE_PRINCIPLES
   - Explain cost/compliance/determinism rationale
   - Make constraint discoverable (not just code comments)

2. **Document Expected Moves 3-Backend Architecture**
   - Create new doc: `EXPECTED_MOVES_ARCHITECTURE.md`
   - Explain when each backend is used
   - Document fallback order and rationale

3. **Document Provider Hierarchy**
   - Create data provider strategy section
   - Show fallback chains (market prices, options, EM)
   - Explain why fallbacks exist

### High Priority (Do Soon)
1. Update PIPELINE_ARCHITECTURE with 3-part EM flow
2. Document Theta integration separately
3. Create API reference with real-time/batch classification

### Medium Priority
1. Document calculation formulas (EM, IV EM, confidence)
2. Create decision flowchart (which provider for what)
3. Document rate limiting strategy (API calls)

---

**Status**: ✅ Analysis complete. Ready for documentation specifications.
