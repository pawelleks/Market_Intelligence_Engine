# Market Intelligence Engine - Documentation Audit Research

**Date:** February 12, 2026  
**Task:** Comprehensive documentation audit identifying discrepancies between codebase implementation and /docs documentation  
**Focus:** Real-time vs offline/batch transitions, data providers, API endpoints

---

## Research Summary

### 1. Documentation Structure Overview
**Key Finding**: Documentation is well-organized but contains significant gaps in newer modules and undocumented constraints.

- ✅ Core documentation exists: `ARCHITECT_BIBLE.md` (26KB), `ARCHITECTURE_PRINCIPLES.md`, `PIPELINE_ARCHITECTURE.md`
- ❌ **Critical Gap**: Expected Moves Engine (complex 3-backend module) has **zero documentation**
- ❌ **Critical Gap**: Split-Source Data Strategy (main architectural constraint) only in code comments
- ⚠️ **Partial Gap**: GEX Engine, Theta Integration, API endpoints scattered across modules

**Details**: See `research/documentation-structure.md`

---

### 2. Real-Time vs Offline/Batch Implementation - Key Findings

#### Market Prices (Correctly Documented as Batch)
- ✅ YFinance/Polygon: Batch only, no real-time streaming
- ✅ Daily incremental updates with gap detection
- ✅ Data persisted to `data/raw/{TICKER}.parquet`

#### Options Data (Hybrid - Documentation Incomplete)
- ⚠️ **Split-Source Strategy**: Massive flat files (batch) + Polygon API (real-time fallback)
- ⚠️ Code comments explicitly forbid refactoring to APIs: "Do NOT refactor to use APIs"
- ⚠️ This critical constraint NOT in architecture documentation
- Location: `src/mie_lib/data_ingest/providers/polygon.py`, `massive.py`

#### Expected Moves Engine (Completely Undocumented - CRITICAL)
- ❌ **3-Backend Architecture**:
  1. Massive flat file (batch, historical)
  2. Polygon API (real-time, live mode)
  3. Theta Data REST (independent, real-time)
- ❌ **Calculation Logic**: Straddle EM, IV EM, confidence scoring - all undocumented
- ❌ **Data Persistence**: Parquet + JSON + Pending files with merge logic
- ❌ **Reliability Tracking**: Separate pending queue for backtest validation
- Location: `src/mie_lib/analytics/expected_moves/` (3 files)

#### GEX Engine (Batch-First with Hidden Real-Time Capability)
- ⚠️ Documented as: "Daily batch calculation only"
- ⚠️ **Actual**: Batch-preferred but supports on-demand via `force_refresh=true` parameter
- ⚠️ Cache layer (15-min TTL) not documented
- ⚠️ Fallback behavior when calculation fails not explained
- Location: `src/mie_lib/analytics/gex/api_endpoints.py`

#### Macro/FRED Data (Correctly Documented as Batch)
- ✅ Batch-only with incremental updates
- ✅ Rate-limited API calls with retry logic
- ✅ Data to `data/raw/macro/fred/{SERIES_ID}.parquet`

**Details**: See `research/real-time-vs-batch-analysis.md`

---

### 3. Data Provider Analysis

#### Provider Hierarchy (Code vs Docs)

**Documented** (ARCHITECTURE_PRINCIPLES.md):
> "External source (Yahoo Finance, FRED API, etc.)"

**Actual** (code):
```
Market Prices:
  1. Polygon API (if POLYGON_AVAILABLE)
  2. YFinance (fallback)

Options Chains:
  1. Massive flat files (CSV) - PRIMARY
  2. Polygon API (enrichment/fallback)
  3. yfinance (OI/IV enrichment only)
  FORBIDDEN: Direct API refactoring

Expected Moves:
  1. Massive flat file (historical)
  2. Polygon API (live mode)
  3. Theta REST (independent)

FRED:
  1. FRED API (batch with rate limiting)
  2. Local parquet cache
```

**Discrepancy Impact**:
- Polygon as primary for prices NOT documented
- Split-source constraint (options chains) invisible to developers
- Multiple fallback paths create confusion about which is "primary"

**Details**: See `research/data-provider-strategy.md`

---

### 4. API Endpoints - Batch vs Real-Time Classification

**Finding**: Most endpoints serve batch data, but several have undocumented real-time capability.

| Endpoint | Module | Mode | Status |
|----------|--------|------|--------|
| `/api/v1/expected_moves/latest` | Expected Moves | Batch | ❌ Module undocumented |
| `/api/v1/expected_moves/theta/latest/{ticker}` | Expected Moves | Real-time | ❌ Endpoint undocumented |
| `/api/v1/gex/latest/{ticker}` | GEX | Batch-first | ⚠️ Force-refresh hidden |
| `/api/v1/gex/latest/{ticker}?force_refresh=true` | GEX | Real-time | ❌ Not in docs |
| `/api/v1/gex/history/heatmap/{ticker}` | GEX | Batch | ❌ Undocumented |
| `/api/v1/hmm/backtest/{ticker}` | HMM | Batch | ✅ Documented |
| `/api/v1/lei_index` | LEI | Batch | ⚠️ Partial |

**Details**: See `research/api-endpoint-analysis.md`

---

### 5. Critical Code-Only Constraints

### Constraint #1: Split-Source Data Strategy
**Location**: Code comments in `polygon.py`, `massive.py`, `expected_moves/engine.py`

```python
"OPTION CHAINS: Must come from Massive.com (Flat Files). Do NOT refactor to use APIs.
 ENRICHMENT: yfinance is allowed ONLY for underlying price/metadata.
 Any attempt to replace the flat-file ingest with an API call is a violation of project constraints."
```

**Status**: NOT in ARCHITECT_BIBLE or ARCHITECTURE_PRINCIPLES  
**Impact**: New developers might violate this constraint; invisible architectural decision

---

### Constraint #2: Expected Moves Calculation Methods
**Location**: `expected_moves/engine.py` and `theta_expected_moves_engine.py`

- **Straddle EM**: ATM Call Price + ATM Put Price
- **IV EM**: `spot_price * iv_val * sqrt(days_to_expiry / 365)`
- **Sigma Factor**: 0.85 × Straddle (conservative estimate used by Theta backend)
- **Confidence Score**: Tied to VIX1D level (formula undocumented)
- **Black-Scholes Fallback**: Used when price missing, risk-free rate = 4.5% (hardcoded assumption)

**Status**: All formulas in code, NONE in documentation  
**Impact**: Can't validate calculation correctness or explain results to users

---

### Constraint #3: Theta Data Integration
**Location**: `src/mie_lib/analytics/expected_moves/theta_expected_moves_engine.py`

- Independent from main pipeline
- Uses Theta Terminal REST API (port 25510)
- Index/Stock endpoint differentiation
- Option root mapping (SPX → SPXW)
- Bad tick filter + estimation logic

**Status**: Completely undocumented (entire backend invisible)  
**Impact**: Users don't know alternative EM calculation exists

---

## Key Discrepancies Summary

| Issue | Component | Documented | Actual | Severity |
|-------|-----------|------------|--------|----------|
| Expected Moves | Module architecture | 0% | Complex 3-backend system | **CRITICAL** |
| Split-Source Strategy | Data provider rules | 0% (code only) | Strict constraints in code | **HIGH** |
| GEX Real-time | Capability | Batch only | Batch + on-demand | **MEDIUM** |
| Theta Backend | Integration | None | Complete system | **HIGH** |
| Calculation Formulas | EM logic | None | Straddle/IV/Sigma/BS | **MEDIUM** |
| API Endpoints | Reference | Scattered | No central docs | **MEDIUM** |
| Fallback Logic | Provider hierarchy | Incomplete | Multi-level fallbacks | **LOW-MEDIUM** |
| Data Persistence | Storage patterns | Partial | Multiple output dirs | **LOW** |

---

## Research Files Generated

1. **`research/documentation-structure.md`** - Complete directory inventory and file analysis
2. **`research/real-time-vs-batch-analysis.md`** - Detailed implementation analysis by module
3. **`research/data-provider-strategy.md`** - Provider hierarchy and split-source constraints
4. **`research/api-endpoint-analysis.md`** - All endpoints classified by mode and documentation status
5. **`research/calculation-formulas.md`** - Expected Moves calculation methods and Black-Scholes usage
6. **`research/undocumented-modules.md`** - Detailed breakdown of completely missing documentation

---

## Recommended Next Steps

**High Priority** (Critical for usability):
1. Create comprehensive Expected Moves documentation (3-5 pages)
2. Document Split-Source Data Strategy in ARCHITECTURE_PRINCIPLES
3. Create Theta Integration guide with setup instructions

**Medium Priority** (Important for maintainability):
1. Create centralized API Reference with batch/real-time classification
2. Document all calculation formulas (EM, IV EM, confidence scoring, Black-Scholes)
3. Create Decision Flowchart: when to use real-time vs batch

**Low Priority** (Nice to have):
1. Update PIPELINE_ARCHITECTURE with 3-part EM flow
2. Document caching strategy (GEX 15-min TTL)
3. Create data persistence patterns reference

---

**Status**: ✅ Research complete. Ready for specification and plan phases.
