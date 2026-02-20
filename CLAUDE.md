# CLAUDE.md - Architectural Standards for AI Agents

**Last Updated**: 2026-02-12  
**Authority**: Repository Audit via Shotgun (`.shotgun/specification.md`)

---

## Purpose

This document defines **mandatory architectural constraints** and **documentation standards** for all AI agents working on the Market Intelligence Engine codebase. These rules are **non-negotiable** and must be followed without exception.

---

## Critical Architectural Constraints

### 1. Split-Source Data Strategy (CRITICAL)

**Rule**: Options chain data MUST use Massive CSV files. Do NOT refactor to use API calls.

**Rationale**:
- **Cost Optimization**: Massive flat files are included in the data subscription; API calls are metered and expensive
- **Determinism**: CSV snapshots are reproducible; API responses vary by timing
- **Compliance**: Bulk data licensing terms differ from API terms
- **Consistency**: Historical backtesting requires fixed snapshots

**Enforcement**:
- Options chains MUST be loaded from `data/raw/massive/options/options_{DATE}.csv`
- Polygon API is for **spot prices only**, not full option chains
- ThetaData REST API is the **only exception** for real-time Expected Moves calculation

**Code Locations**:
- `src/mie_lib/data_ingest/providers/polygon.py`
- `src/mie_lib/data_ingest/providers/massive.py`
- `src/mie_lib/analytics/expected_moves/theta_expected_moves_engine.py` (exception)

**Violation Detection**:
- Any code that calls Polygon/Theta API for full option chains (except `theta_expected_moves_engine.py`)
- Any refactoring that removes Massive CSV loading logic

---

### 2. Real-Time vs Batch Classification (CRITICAL)

**Rule**: Every module and API endpoint MUST be explicitly classified as BATCH, REAL-TIME, or HYBRID.

**Documentation Requirements**:
- Module docstrings MUST include: `Mode: BATCH | REAL-TIME | HYBRID`
- API endpoint docstrings MUST include: `Data Source:` and `Response Time:`
- README and ARCHITECTURE.md MUST maintain endpoint classification tables

**Examples**:
```python
# GOOD
@router.get("/api/v1/expected_moves/theta/latest/{ticker}")
async def get_theta_expected_moves(ticker: str):
    """
    Mode: REAL-TIME
    Data Source: ThetaData REST API (port 25510)
    Response Time: 2-5 seconds
    """
    ...

# BAD (missing classification)
@router.get("/api/v1/gex/latest/{ticker}")
def get_latest_gex(ticker: str):
    """Returns latest GEX data"""
    ...
```

---

### 3. Expected Moves 3-Backend System (CRITICAL)

**Rule**: Expected Moves has THREE independent calculation backends. Do NOT consolidate or remove any backend without explicit approval.

**Backend 1: Massive/Polygon (Batch)**
- **When**: Daily pipeline, post-market
- **Source**: Massive CSV option chains + Polygon spot prices
- **Formula**: `EM = ATM_Call_Mid + ATM_Put_Mid` (straddle price)
- **Output**: `data/analytics/options/latest.json`

**Backend 2: Static Pre-Computed (Batch)**
- **When**: Cron job (`jobs/process_expected_moves_static.py`)
- **Source**: ThetaData REST API for spot + options
- **Formula**: `EM = Straddle_Price * 0.85` (sigma factor)
- **Output**: `public/data/expected_moves_static.json`

**Backend 3: Theta Live (Real-Time)**
- **When**: On-demand per API request
- **Source**: ThetaData REST API (port 25510)
- **Flow**: Fetch spot → Determine expirations → Fetch ATM straddle → Bad tick filter → `EM = Straddle * 0.85`
- **Module**: `src/mie_lib/analytics/expected_moves/theta_expected_moves_engine.py`

**Rationale**: Each backend serves different use cases (historical consistency, fast serving, real-time accuracy).

---

### 4. Hidden API Parameters Must Be Documented (HIGH)

**Rule**: All API parameters, including optional/hidden ones, MUST be documented in both code and centralized API reference.

**Known Hidden Parameters**:
- `GET /api/v1/gex/latest/{ticker}?force_refresh=true` - Bypasses cache, triggers live calculation
- Any future optional parameters must be documented before merging

**Documentation Locations**:
- Endpoint docstring
- `ARCHITECTURE.md` endpoint table
- Centralized API reference (when created)

---

### 5. Calculation Formulas Must Be Documented (MEDIUM)

**Rule**: All mathematical formulas used in analytics MUST be documented with notation, assumptions, and limitations.

**Required Documentation**:
- **Straddle EM**: `EM = ATM_Call_Mid + ATM_Put_Mid`
- **IV-based EM**: `EM = spot_price * iv_val * sqrt(dte/365)`
- **Sigma Factor**: `0.85` multiplier (converts 1-sigma straddle to ~68% confidence range)
- **Confidence Score**: Function of VIX1D (formula must be documented)
- **Black-Scholes Fallback**: Risk-free rate = 4.5% (hardcoded assumption)

**Location**: `ARCHITECTURE.md` or dedicated calculation reference document

### 6. Resource Isolation & Concurrency (CRITICAL)

**Rule**: BATCH processes and REAL-TIME requests MUST NOT compete for the same file handles or blocking network sockets.

**Enforcement**:
- **Read-Only Live Access**: REAL-TIME endpoints/modules MUST open data files (Parquet/CSV) in **read-only mode**. They are FORBIDDEN from writing to `data/` directories.
- **ThetaData Multiplexing**: All REAL-TIME requests to ThetaData (Port 25510) MUST use an `AsyncClient` with a connection pool. Do NOT open/close new sockets per request.
- **The "Safety Valve"**: If a BATCH job is writing to a specific `{ticker}.parquet` file, the REAL-TIME API must serve the *previous* cached version or a 202 Accepted + "Processing" status rather than waiting for the file lock to release.
- **Process Decoupling**: STREAMING data MUST be piped through a dedicated `Queue` or `Redis` pub/sub. Do NOT allow a streaming React page to trigger a direct Python subprocess that writes to disk.

**Violation Detection**:
- Use of `open(file, 'w')` or `df.to_parquet()` inside a `REAL-TIME` classified module.
- Synchronous `time.sleep()` in any FastAPI endpoint (use `await asyncio.sleep()`).
- Direct file manipulation in any module using `theta_expected_moves_engine.py`.

**Rationale**: This prevents "Pipeline Deadlock" where a heavy daily calculation freezes the live UI or causes streaming connections to drop.

---

## Documentation Standards

### 1. Definition of Done

A task is **NOT COMPLETE** until:
- [ ] Unit tests are written/updated and passing
- [ ] Docstrings match the new implementation
- [ ] `ARCHITECTURE.md` is updated if architecture changed
- [ ] API endpoint tables are updated if endpoints changed
- [ ] Types are strict (no `any` in TypeScript, proper type hints in Python)
- [ ] Dead code is removed

### 2. Module Documentation Requirements

Every module MUST have:
- **Purpose**: Clear description of what the module does
- **Mode**: BATCH | REAL-TIME | HYBRID
- **Data Sources**: External APIs, files, caches
- **Processing Steps**: Sequence of operations
- **Output Locations**: Where results are stored
- **Dependencies**: Other modules required
- **Configuration**: Environment variables, setup requirements

### 3. API Endpoint Documentation Requirements

Every endpoint MUST document:
- **HTTP Method and Path**: `GET /api/v1/...`
- **Mode**: BATCH | REAL-TIME | HYBRID
- **Data Source**: Where data comes from
- **Response Time**: Expected latency
- **Parameters**: All query/path parameters with types and defaults
- **Response Schema**: All fields with types
- **Error Responses**: Status codes and error messages

### 4. Centralized Documentation Locations

**Primary References**:
- `README.md` - Quick start, feature overview, deployment
- `ARCHITECTURE.md` - System architecture, data flow, API endpoints
- `docs/CORE/ARCHITECT_BIBLE.md` - Detailed architecture reference
- `docs/CORE/ARCHITECTURE_PRINCIPLES.md` - Design principles
- `docs/archive/legacy_batch/` - Deprecated batch-only documentation

**Specialized Guides**:
- `docs/features/` - Feature-specific documentation
- `docs/research/` - Research and audit reports
- `docs/architecture/` - Architecture deep-dives

---

## Forbidden Patterns

### ❌ DO NOT:
1. **Refactor options chains to use API calls** (violates Split-Source constraint)
2. **Remove or consolidate Expected Moves backends** without explicit approval
3. **Add API endpoints without documenting mode and parameters**
4. **Hardcode assumptions without documenting them** (e.g., risk-free rate)
5. **Create duplicate documentation** (check existing docs first)
6. **Ignore real-time capabilities** (document force_refresh, cache TTL, etc.)
7. **Leave calculation formulas undocumented**
8. **Skip updating ARCHITECTURE.md** when adding/changing endpoints

### ✅ DO:
1. **Check `.shotgun/specification.md`** for audit findings before making changes
2. **Update both code and documentation** in the same PR/commit
3. **Document all API parameters** including optional ones
4. **Classify every module** as BATCH, REAL-TIME, or HYBRID
5. **Reference Shotgun research** in `.shotgun/research/` for context
6. **Add deprecation notices** when moving documentation to archive
7. **Test all internal links** after moving documentation files

---

## Shotgun Audit Reference

This document is based on the comprehensive repository audit performed via Shotgun. For detailed findings:

- **Master Specification**: `.shotgun/specification.md`
- **API Endpoint Analysis**: `.shotgun/research/api-endpoint-analysis.md`
- **Documentation Structure**: `.shotgun/research/documentation-structure.md`
- **Data Provider Strategy**: `.shotgun/research/data-provider-strategy.md`
- **Real-Time vs Batch Analysis**: `.shotgun/research/real-time-vs-batch-analysis.md`

**Key Findings**:
- 6 critical documentation gaps identified
- 5+ undocumented API endpoints
- Split-Source constraint only in code comments (now documented here)
- Expected Moves 3-backend system completely undocumented (now documented here)

---

## Enforcement

**For AI Agents**:
- This document takes precedence over general coding practices
- Violations of CRITICAL constraints will result in rejected changes
- All changes must reference this document when touching constrained areas

**For Human Developers**:
- Code reviews must verify compliance with this document
- PRs touching options data, Expected Moves, or API endpoints require extra scrutiny
- Documentation updates are mandatory, not optional

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-02-12 | Initial creation based on Shotgun audit |

---

**Questions?** Refer to `.shotgun/specification.md` for the full audit report and rationale.

### 6. Pipeline Execution
- **Entry Point**: `run_pipeline.py` is the main entry point for the daily batch pipeline.
- **Usage**: `python run_pipeline.py --run-type MANUAL --stages ...`
- **Do Not Modify**: Never add stages directly to `orchestrator.sh` or `mie.py` `main()`. Always add them to `pipeline/stages.yml`.
- **Orchestrator**: `orchestrator.sh` is now a thin wrapper around `run_pipeline.py` for legacy cron compatibility.
