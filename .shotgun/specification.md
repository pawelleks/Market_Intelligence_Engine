# Specification: Documentation Audit for Market Intelligence Engine

## TLDR

**Key Points:**
- Comprehensive audit of /docs directory reveals critical gaps between codebase implementation and documentation, particularly in real-time vs batch data transitions and newer analytics modules
- 5 critical modules lack architecture documentation: Expected Moves (3-backend system), Theta integration, Split-Source constraints, GEX real-time capability, and API endpoint reference

**Major Features:**
- Systematic documentation gap inventory across all modules and components
- Real-time vs batch classification audit for all 10+ API endpoints
- Provider hierarchy and data flow analysis (Polygon, Massive, FRED, Theta)
- Discrepancy severity assessment and prioritized remediation plan

**Key Concerns:**
- Expected Moves module (53.6KB code) completely undocumented despite complex 3-backend architecture
- Split-Source Data Strategy (critical architectural constraint) only in code comments, not in ARCHITECTURE_PRINCIPLES
- Multiple API endpoints with real-time capability hidden from users (Theta endpoint, GEX force_refresh parameter)
- Calculation formulas for Expected Moves (Straddle EM, IV EM, confidence scoring, Black-Scholes) nowhere in documentation

---

## Executive Summary

This specification defines the scope, methodology, and deliverables for a comprehensive documentation audit of the Market Intelligence Engine. The audit has identified significant discrepancies between implementation and documentation, with **6 critical gaps** requiring immediate remediation.

### Key Findings

**Critical Issues (Severity: CRITICAL)**
1. **Expected Moves Engine**: 53.6KB of complex code, 3-backend architecture (Massive/Polygon/Theta), completely undocumented
2. **Split-Source Data Strategy**: Architectural constraint visible only in code comments, not in ARCHITECTURE_PRINCIPLES
3. **Theta Integration**: 16.3KB module with full REST API integration, zero documentation

**High-Priority Issues (Severity: HIGH)**
4. Data provider hierarchy incomplete or inaccurate across all modules
5. API endpoint reference missing (5+ Expected Moves endpoints undocumented)
6. Real-time capabilities hidden (Theta endpoint, GEX force_refresh parameter not in docs)

**Medium-Priority Issues (Severity: MEDIUM)**
7. GEX real-time capability documented as batch-only; actual code supports on-demand calculation
8. Calculation formulas undocumented (Straddle EM, IV EM, confidence score, Black-Scholes)
9. Fallback and error recovery logic not explained in architecture docs

---

## Audit Scope and Methodology

### Components Audited

**Data Ingestion Modules:**
- Market Prices (YFinance/Polygon)
- Options Data (Massive CSV + Polygon API)
- Macro/FRED Data
- Spot Price enrichment

**Analytics Engines:**
- Expected Moves (3 backends: Massive, Polygon, Theta)
- GEX (Gamma Exposure)
- HMM (Hidden Markov Model)
- LEI/Business Cycle indicators

**API Endpoints:**
- All /api/v1/* endpoints
- Expected Moves endpoints (5+)
- GEX endpoints (2)
- HMM endpoints (2)
- Macro endpoints (2)

**Documentation Assets:**
- ARCHITECT_BIBLE.md (26KB)
- ARCHITECTURE_PRINCIPLES.md
- PIPELINE_ARCHITECTURE.md
- EXPECTED_MOVES_SPEC.md
- All supporting guides and references

### Audit Criteria

**Documentation completeness assessed on:**
1. **Architecture**: Module structure, dependencies, design patterns
2. **Data flow**: Input sources, processing steps, output locations
3. **Real-time vs batch**: Explicit classification of each component's mode
4. **API contracts**: Parameters, return types, error codes
5. **Calculation methods**: Formulas, algorithms, assumptions
6. **Provider hierarchy**: Fallback logic, data source priority
7. **Constraints**: Architectural rules, forbidden patterns
8. **Setup/integration**: External dependencies, environment configuration
9. **Caching strategies**: TTL, invalidation, storage patterns
10. **Testing protocols**: Validation procedures, acceptance criteria

---

## Discrepancy Inventory by Severity

### CRITICAL: Expected Moves Engine

**What's Missing:**
- Zero documentation for 53.6KB module with complex 3-backend architecture
- 3-backend system (Massive/Polygon/Theta) not mentioned in any doc
- Calculation formulas (Straddle EM, IV EM, Sigma factor) undocumented
- Confidence scoring methodology unknown
- Theta integration (16.3KB module) completely undocumented
- Data persistence layers (3-layer system) not explained
- JSON merge logic for latest.json invisible
- Pending queue mechanism undocumented
- Black-Scholes fallback assumptions (4.5% risk-free rate) hardcoded, not explained

**Impact:**
- New developers can't understand module design
- Can't validate calculation correctness
- Theta backend invisible to users
- Can't troubleshoot EM inaccuracies
- Risk of violation during refactoring

**Files Affected:**
- `docs/CORE/ARCHITECT_BIBLE.md` (missing entire section)
- `docs/CORE/EXPECTED_MOVES_SPEC.md` (has spec, not architecture)
- No `EXPECTED_MOVES_ARCHITECTURE.md`
- No `THETA_INTEGRATION.md`

---

### CRITICAL: Split-Source Data Strategy

**What's Missing:**
- Architectural constraint not in ARCHITECTURE_PRINCIPLES
- "Do NOT refactor options chains to APIs" rule only in code comments
- Rationale (cost, compliance, determinism) not documented
- Split-source enforcement mechanism invisible
- Constraint applies only to options chains, not to other modules

**Impact:**
- New developers might violate constraint during refactoring
- Architectural decision invisible to stakeholders
- Code review could miss violations
- Maintenance risk high

**Files Affected:**
- `docs/CORE/ARCHITECTURE_PRINCIPLES.md` (missing "Data Provider Strategy" section)
- `docs/CORE/DATA_REFERENCE.md` (incomplete)
- No `DATA_PROVIDER_STRATEGY.md`

---

### CRITICAL: Theta Expected Moves Integration

**What's Missing:**
- Module completely undocumented (16.3KB code, 0 docs)
- REST API endpoint `/api/v1/expected_moves/theta/latest/{ticker}` not in reference
- Theta Terminal setup requirements not mentioned
- Bad tick filter logic undocumented
- Estimation logic for missing data not explained
- Option root mapping (SPX → SPXW) not explained
- When to use Theta vs batch endpoint not clarified
- Sigma factor (0.85) not explained

**Impact:**
- Theta capability invisible to API users
- Setup requirements unknown
- Users can't decide which endpoint to use
- Alternative EM calculation not discoverable

**Files Affected:**
- No `THETA_INTEGRATION.md` document
- API reference missing endpoint
- Integration requirements undocumented

---

### HIGH: API Endpoint Reference Missing

**What's Missing:**
- No centralized API reference document
- 5+ Expected Moves endpoints not documented:
  - GET /api/v1/expected_moves/latest
  - GET /api/v1/expected_moves/massive/latest
  - GET /api/v1/expected_moves/reliability/summary
  - GET /api/v1/expected_moves/reliability/history
  - GET /api/v1/expected_moves/theta/latest/{ticker}
  - GET /api/v1/expected_moves/static/latest
- 2+ GEX endpoints partially documented:
  - GET /api/v1/gex/latest/{ticker} (missing force_refresh parameter)
  - GET /api/v1/gex/history/heatmap/{ticker}
- Real-time vs batch classification absent for all endpoints
- Data freshness indicators missing (batch date, Theta timestamp)

**Impact:**
- Users don't know all endpoints exist
- Parameters undocumented (force_refresh hidden)
- Can't choose appropriate endpoint
- API surface unknown to new developers

**Files Affected:**
- No `docs/API_REFERENCE.md` or `API_ENDPOINTS.md`
- Endpoints documented only in code docstrings
- No centralized reference

---

### HIGH: Data Provider Hierarchy Incomplete

**What's Missing:**
- Market Prices: Polygon as primary not clearly stated (docs mention Yahoo Finance)
- Options chains: 3-tier hierarchy (Massive/Polygon/fallback) not fully documented
- Fallback logic undocumented for all modules
- Rate limiting strategy not explained (API calls have delays)
- Fallback conditions not specified (when does it trigger?)
- Provider switching logic (Massive → Polygon) not explained

**Impact:**
- Architecture not accurately represented
- New providers might be added incorrectly
- Fallback behavior unpredictable
- Developers assume wrong data source is primary

**Files Affected:**
- `docs/CORE/ARCHITECTURE_PRINCIPLES.md`
- `docs/CORE/ARCHITECT_BIBLE.md`
- No `DATA_PROVIDER_STRATEGY.md`

---

### HIGH: GEX Real-Time Capability Hidden

**What's Missing:**
- Documented as batch-only, actual code supports on-demand
- force_refresh parameter not documented anywhere
- Cache strategy undocumented (15-min TTL unknown)
- Fallback order not explained (cache → disk → calculation)
- When on-demand calculation triggers not explained
- Data quality differences (batch vs on-demand) not mentioned
- Cache invalidation logic invisible

**Impact:**
- Users can't trigger live calculation
- Cache behavior unpredictable
- Can't tune TTL if needed
- Data freshness ambiguous

**Files Affected:**
- `docs/CORE/ARCHITECT_BIBLE.md`
- `docs/CORE/ANALYTICS_REFERENCE.md`
- API documentation (missing force_refresh)

---

### MEDIUM: Calculation Formulas Undocumented

**What's Missing:**
- Straddle EM: `ATM Call Price + ATM Put Price` (formula not in docs)
- IV-based EM: `spot_price * iv_val * sqrt(dte/365)` (formula not shown)
- Confidence Score: `f(VIX1D)` (formula unknown, VIX1D mapping not documented)
- Sigma Factor: `0.85 * Straddle` (0.85 constant not explained, origin unknown)
- Black-Scholes: risk-free rate = 4.5% (hardcoded assumption not documented)

**Impact:**
- Can't validate calculation correctness
- Users can't understand EM values
- Can't explain results to stakeholders
- Risk of calculation misunderstanding

**Files Affected:**
- `docs/CORE/EXPECTED_MOVES_SPEC.md`
- `docs/CORE/ARCHITECT_BIBLE.md`
- No separate calculation reference

---

### MEDIUM: Data Persistence Patterns Incomplete

**What's Missing:**
- Expected Moves 3-layer persistence not explained:
  - Layer 1: Main history (parquet)
  - Layer 2: Latest (JSON with merge logic)
  - Layer 3: Pending (parquet, separate queue)
- JSON merge logic invisible (prevents overwrite with older data)
- Pending queue purpose unclear (reliability/backtest validation)
- Directory structure incomplete
- Partitioning strategy not documented
- Data retention policies not specified

**Impact:**
- Can't understand data flow
- Merge conflicts possible
- Data loss risk during migrations
- Unclear which file is source of truth

**Files Affected:**
- `docs/CORE/DATA_REFERENCE.md`
- `docs/data_standards.md`
- Missing data persistence guide

---

### MEDIUM: Fallback and Error Recovery Undocumented

**What's Missing:**
- Market Prices: When Polygon falls back to yfinance not explained
- Options: When Polygon API used instead of Massive not clear
- Expected Moves: Fallback from Massive to Polygon not explained
- GEX: Fallback to on-demand calculation not documented
- FRED: Fallback to cache when API fails not explained
- Error handling strategies invisible
- Retry logic undocumented
- Data quality degradation not mentioned

**Impact:**
- Can't troubleshoot failures
- User expectations unclear
- Data quality ambiguous
- System behavior unpredictable

**Files Affected:**
- All architecture documents missing error handling sections
- No error recovery guide

---

## Discrepancy Summary Table

| Issue | Component | Severity | Status | Impact |
|-------|-----------|----------|--------|--------|
| Module architecture missing | Expected Moves | CRITICAL | 0% doc | High: 53.6KB undocumented |
| 3-backend system not mentioned | Expected Moves | CRITICAL | 0% doc | Users don't know backends exist |
| Theta integration undocumented | Expected Moves | CRITICAL | 0% doc | Feature invisible |
| Split-source constraint invisible | Data Strategy | CRITICAL | Code only | Risk of architectural violation |
| Calculation formulas missing | Expected Moves | MEDIUM | 0% doc | Can't validate correctness |
| Confidence scoring undefined | Expected Moves | MEDIUM | 0% doc | Results unexplainable |
| API endpoint reference missing | All endpoints | HIGH | 0% doc | Surface area unknown |
| Provider hierarchy incomplete | Data flow | HIGH | Partial | Architecture inaccurate |
| GEX real-time hidden | GEX | HIGH | Not in spec | Feature undiscoverable |
| force_refresh parameter | GEX API | HIGH | Not in docs | Can't trigger live calc |
| Data persistence patterns | Storage | MEDIUM | Partial | Data flow unclear |
| Fallback logic | Error handling | MEDIUM | Not documented | Troubleshooting difficult |
| Error recovery | All modules | MEDIUM | Not documented | Behavior unpredictable |
| Cache strategy | GEX | MEDIUM | Not documented | TTL/invalidation unclear |

---

## Documentation Requirements by Severity

### Critical (Must Create/Update Immediately)

**1. Expected Moves Architecture Document** (3-5 pages)
- Module overview: 3-backend system
- Backend 1: Massive flat file (batch, historical)
- Backend 2: Polygon API (real-time, live today)
- Backend 3: Theta Data REST (independent, on-demand)
- Data persistence: 3-layer system (parquet, JSON, pending)
- Decision logic: when to use each backend
- Calculation methods: Straddle EM, IV EM, confidence scoring
- Black-Scholes fallback: assumptions and limitations
- API endpoints: all 5+ endpoints documented

**2. Split-Source Data Strategy Update to ARCHITECTURE_PRINCIPLES** (1-2 pages)
- Constraint definition: options chains must use Massive CSV
- Rationale: cost optimization, compliance, determinism, consistency
- Enforcement mechanisms: conditional logic, code comments, agent rules
- Provider hierarchy by component
- Fallback logic and conditions

**3. Theta Integration Documentation** (2-3 pages)
- Module overview: independent real-time backend
- REST API: endpoints and payloads
- Setup requirements: Theta Terminal configuration
- Bad tick filter: definition and logic
- Option root mapping: stock vs index mapping
- When to use: vs batch endpoint comparison
- Data flow: spot price → expirations → straddle → EM

**4. Centralized API Reference** (2-3 pages)
- All endpoints listed with paths
- Real-time vs batch classification
- Parameters (including hidden ones like force_refresh)
- Return types and response formats
- Data freshness indicators
- Error codes and handling

### High Priority (Create/Update Next)

**5. Data Provider Strategy** (2-3 pages)
- Provider hierarchy by component
- Market Prices: Polygon primary, yfinance fallback
- Options: Massive primary, Polygon fallback, forbidden API refactor
- FRED: FRED API primary, local cache fallback
- Fallback conditions and triggers
- Rate limiting strategy

**6. GEX Real-Time Capability Documentation** (1-2 pages)
- force_refresh parameter: purpose and usage
- Cache strategy: 15-min TTL, in-memory storage
- Fallback order: cache → disk → on-demand calculation
- When live calculation triggers
- Data quality differences
- Cache invalidation rules

**7. Calculation Formulas Reference** (1-2 pages)
- Straddle EM formula and definition
- IV-based EM formula and derivation
- Confidence score methodology (VIX1D mapping)
- Sigma factor (0.85) origin and justification
- Black-Scholes parameters and assumptions
- Fallback conditions and logic

### Medium Priority (Create/Update After)

**8. Data Persistence Patterns Guide** (1-2 pages)
- Expected Moves 3-layer persistence
- JSON merge logic and date precedence
- Pending queue purpose and workflow
- Directory structure and partitioning
- Data retention policies
- Reliability tracking mechanism

**9. Fallback and Error Recovery Guide** (1-2 pages)
- Fallback triggers by component
- Error handling strategies
- Retry logic and backoff
- Data quality degradation indicators
- Troubleshooting fallback scenarios

**10. Update ARCHITECT_BIBLE** (2-3 page additions)
- Add Part 11: Expected Moves architecture
- Add Part 12: Real-time vs batch classification
- Update Part 10 with new provider hierarchy
- Add section: critical architectural constraints

---

## Documentation Quality Standards

### Required for Every Module Documentation

**Architecture Section:**
- Clear description of module purpose and scope
- Data sources (external APIs, files, caches)
- Processing steps in sequence
- Output locations and formats
- Dependencies on other modules
- Configuration requirements

**Real-Time vs Batch Classification:**
- Explicit statement: "This module is BATCH/REAL-TIME/HYBRID"
- When data is available (scheduled batch, on-demand, streaming)
- Data freshness (daily update, hours, minutes, seconds)
- Recalculation frequency if applicable

**Data Flow Diagram:**
- Visual representation of data sources → processing → outputs
- Fallback paths clearly shown
- External dependencies marked
- Decision points (when fallback triggers)

**API Contract Documentation:**
- All endpoints listed with full paths
- HTTP method and request body
- Query parameters with types and defaults
- Response schema with all fields
- Error responses and status codes
- Hidden/undocumented parameters noted

**Calculation Reference:**
- Mathematical formulas with notation
- Variable definitions and units
- Assumptions and limitations
- Fallback logic when data missing
- Example calculations with real values

**Configuration Guide:**
- Environment variables required
- API keys and authentication
- External service setup steps
- Performance tuning parameters
- Troubleshooting common issues

### Acceptance Criteria

Each documentation artifact will be accepted only if:
1. ✅ All formulas mathematically correct and tested
2. ✅ All endpoints covered (no hidden parameters)
3. ✅ All data flows include fallback paths
4. ✅ Real-time vs batch explicitly stated
5. ✅ All external dependencies listed
6. ✅ All configuration requirements documented
7. ✅ Code examples match actual implementation
8. ✅ Diagrams validate (mermaid syntax correct)
9. ✅ No references to undocumented modules
10. ✅ Consistent terminology across all docs

---

## Verification and Validation

### Phase 1: Documentation Completion (Deliverable)
- All 10 documentation artifacts created/updated
- Cross-references validated (no broken links)
- Code examples verified against actual implementation
- Diagrams rendered correctly

### Phase 2: Gap Closure Validation
For each critical/high issue:
1. Identify which documentation addresses it
2. Verify documentation is discoverable
3. Confirm comprehensiveness (no gaps remain)
4. Validate against actual code implementation

### Phase 3: Consistency Review
- Terminology consistent across docs
- Real-time vs batch consistently labeled
- Formula notation uniform
- Provider hierarchies match across docs
- No contradictions or conflicts

---

## Related Artifacts

**Research Files:**
- `research.md` - Executive summary of audit findings
- `research/documentation-structure.md` - Complete directory inventory
- `research/real-time-vs-batch-analysis.md` - Detailed module analysis
- `research/data-provider-strategy.md` - Provider hierarchy and constraints
- `research/api-endpoint-analysis.md` - API endpoint classification

**Codebase References:**
- `src/mie_lib/analytics/expected_moves/` - Expected Moves module (53.6KB)
- `src/mie_lib/analytics/expected_moves/theta_expected_moves_engine.py` - Theta integration
- `src/mie_lib/analytics/gex/api_endpoints.py` - GEX real-time capability
- `src/mie_lib/data_ingest/providers/polygon.py` - Split-Source constraints
- `docs/CORE/ARCHITECT_BIBLE.md` - Master architecture (26KB)
- `docs/CORE/ARCHITECTURE_PRINCIPLES.md` - Core philosophy

---

## Success Criteria

This audit specification will be considered successful when:

1. **Completeness**: All 10 documentation artifacts are created/updated and reviewed
2. **Discrepancy Closure**: All 13 identified discrepancies have corresponding documentation
3. **Discoverability**: New developers can find answers to:
   - "What are the 3 Expected Moves backends?"
   - "When should I use Theta vs batch endpoint?"
   - "Why can't options be refactored to use APIs?"
   - "What does force_refresh do?"
   - "How do the calculation formulas work?"
4. **Accuracy**: All documentation matches actual code implementation
5. **Maintainability**: Documentation is structured for easy updates as code evolves
6. **Stakeholder Alignment**: Architecture decisions are visible and explained (not code-only)

