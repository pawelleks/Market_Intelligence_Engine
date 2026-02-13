# Documentation Structure Analysis

**Audit Date**: February 12, 2026  
**Scope**: Complete inventory and assessment of /docs directory

---

## Directory Inventory

### Root Documentation Files

| File | Size | Purpose | Last Updated | Status |
|------|------|---------|--------------|--------|
| `docs/README.md` | 2.6KB | Documentation hub & quick start | Not specified | ✅ Current |
| `docs/ARCHITECTURE_PRINCIPLES.md` | 5.9KB | Core philosophy & pipeline rules | 2026-01-10 | ⚠️ Outdated |
| `docs/business_confidence_migration_plan.md` | 8.3KB | Specific migration task | Not specified | ❓ Unclear |
| `docs/daily_pipeline_run.md` | 7.1KB | Full daily pipeline breakdown | 2025-12-12 | ⚠️ Needs refresh |
| `docs/data_check.md` | 156B | Stub file | Not specified | ❓ Empty |
| `docs/data_standards.md` | 1.4KB | Data naming/format standards | Not specified | ⚠️ Incomplete |
| `docs/Security.md` | 1.7KB | Security considerations | Not specified | ⚠️ Minimal |
| `docs/testing_access.md` | 994B | Testing procedures | Not specified | ⚠️ Minimal |
| `docs/TESTING_CHECKLIST.md` | 5.3KB | QA checklist | Not specified | ⚠️ Outdated |

### CORE Subdirectory (Architecture)

| File | Size | Purpose | Status |
|------|------|---------|--------|
| `docs/CORE/ARCHITECT_BIBLE.md` | 26.0KB | Master architecture document | ⚠️ Partial coverage |
| `docs/CORE/CLI_REFERENCE.md` | 1.8KB | CLI command reference | ⚠️ Incomplete |
| `docs/CORE/DAILY_PIPELINE.md` | 6.5KB | Daily build schedule | ⚠️ Duplicate of root |
| `docs/CORE/DATA_REFERENCE.md` | 1.9KB | Data dictionary | ⚠️ Minimal |
| `docs/CORE/EXPECTED_MOVES_SPEC.md` | 10.9KB | Expected Moves specification | ⚠️ Spec only, no architecture |
| `docs/CORE/ANALYTICS_REFERENCE.md` | 2.4KB | Analytics engines overview | ⚠️ High-level only |
| `docs/CORE/PIPELINE_ARCHITECTURE.md` | 6.1KB | Dependency graph & CLI | ⚠️ CLI-focused, missing analytics |
| `docs/CORE/SEASONALITY_REFERENCE.md` | 2.0KB | Seasonality engine reference | ⚠️ Minimal |
| `docs/CORE/state_classification.md` | 1.8KB | Regime classification rules | ⚠️ Incomplete |

### Other Subdirectories

| Directory | Files | Purpose | Status |
|-----------|-------|---------|--------|
| `docs/DEVELOPMENT` | 2 files | Setup & contributing guides | ❓ Not reviewed |
| `docs/OPERATIONS` | 1 file | Deployment runbook | ❓ Not reviewed |
| `docs/UI_SYSTEM` | 1 file | React/Vite UI specs | ❓ Not reviewed |
| `docs/analysis` | 0 files | Analysis docs | ❓ Empty |
| `docs/analytics` | 0 files | Analytics breakdown | ❓ Empty |
| `docs/audits` | 0 files | Audit logs | ❓ Empty |
| `docs/fixes` | 0 files | Bug fixes documented | ❓ Empty |

---

## Key Findings

### What's Well Documented
1. ✅ **Core Philosophy** - ARCHITECTURE_PRINCIPLES defines offline-first pattern clearly
2. ✅ **Daily Pipeline Steps** - daily_pipeline_run.md lists all CLI commands and data flow
3. ✅ **Market Prices Ingestion** - Covered in PIPELINE_ARCHITECTURE
4. ✅ **Data Dictionary/Naming** - ARCHITECT_BIBLE Part 10 has comprehensive field definitions
5. ✅ **Testing Protocols** - ARCHITECTURE_PRINCIPLES has testing checklist

### Critical Documentation Gaps

#### Gap #1: Expected Moves Engine (CRITICAL)
- **Files**: `src/mie_lib/analytics/expected_moves/` (3 modules, 3-backend system)
- **Documented**: ❌ Zero architecture documentation
- **Found**: `docs/CORE/EXPECTED_MOVES_SPEC.md` (10.9KB specification only)
- **Missing**: 
  - Module architecture (3 backends)
  - When to use each backend
  - Calculation formulas
  - Theta integration details
  - Reliability tracking mechanism
  - API endpoint reference

#### Gap #2: Split-Source Data Strategy (CRITICAL)
- **Location**: Code comments in `polygon.py`, `massive.py`
- **Documented**: ❌ Zero architectural documentation
- **Requirement**: "OPTION CHAINS: Must come from Massive.com (Flat Files). Do NOT refactor."
- **Impact**: Invisible constraint could be violated during refactoring

#### Gap #3: Theta Data Integration (HIGH)
- **Files**: `src/mie_lib/analytics/expected_moves/theta_expected_moves_engine.py` (16KB)
- **Documented**: ❌ Zero documentation
- **Features**: REST API, index/stock differentiation, bad tick filter
- **Missing**: Setup, usage, architecture

#### Gap #4: GEX Real-Time Capability (MEDIUM)
- **Files**: `src/mie_lib/analytics/gex/api_endpoints.py`
- **Documented**: As batch-only
- **Actual**: Batch with on-demand via `force_refresh=true`
- **Missing**: Parameter documentation, cache strategy, fallback behavior

#### Gap #5: API Endpoint Reference (MEDIUM)
- **Current State**: Scattered across modules
- **Missing**: Centralized reference with:
  - All endpoints listed
  - Real-time vs batch classification
  - Parameter documentation
  - Return types

#### Gap #6: Calculation Formulas (MEDIUM)
- **Missing**: Mathematical definitions of:
  - Straddle EM: `ATM Call Price + ATM Put Price`
  - IV EM: `spot * iv * sqrt(dte/365)`
  - Confidence Score: `f(VIX1D)` (formula unknown)
  - Sigma Factor: `0.85 * Straddle`
  - Black-Scholes: risk-free rate = 4.5% (assumption)

---

## Documentation Quality Assessment

### By Document Type

#### Architecture Documents (Quality: MEDIUM)
- **Strength**: Comprehensive coverage of general principles
- **Weakness**: Missing new modules (Expected Moves, Theta, GEX real-time)
- **Age**: ARCHITECT_BIBLE from 2025-12-12 (2 months old)

#### API Reference (Quality: LOW)
- **Strength**: Individual endpoint docstrings
- **Weakness**: No centralized reference, scattered across modules
- **Coverage**: ~50% of endpoints documented

#### Tutorial/Guides (Quality: MEDIUM)
- **Strength**: Setup and contributing guides exist
- **Weakness**: Missing advanced topics (real-time strategies, Theta usage)

#### Data Reference (Quality: LOW)
- **Strength**: ARCHITECT_BIBLE Part 10 has naming conventions
- **Weakness**: Missing new fields, persistence patterns incomplete

---

## Maintenance Issues

### Duplicate Documentation
1. `daily_pipeline_run.md` (root) ≈ `docs/CORE/DAILY_PIPELINE.md`
2. Both describe same pipeline steps with slight variations
3. **Risk**: Inconsistency if one is updated but not the other

### Stale References
1. ARCHITECT_BIBLE references "V1 system" in places
2. Some timestamps from 2025-12 (2 months old)
3. Documentation says "will be added" for features now implemented

### Orphaned Files
1. `data_check.md` - 156 bytes, appears unfinished
2. Empty subdirectories: `analysis/`, `analytics/`, `audits/`, `fixes/`

---

## File-by-File Assessment

### High Priority (Missing Core Content)

**docs/CORE/ARCHITECT_BIBLE.md**
- Size: 26.0KB (longest document)
- Coverage: Parts 1-10 structure
- ❌ Missing: Expected Moves, Theta integration, real-time strategies
- ⚠️ Warning: "Last Updated 2025-12-12" (outdated)
- Recommendation: Add Part 11-12 for new modules

**docs/CORE/EXPECTED_MOVES_SPEC.md**
- Size: 10.9KB
- Content: Calculation specification only
- ❌ Missing: Architecture, 3-backend system, API details
- Recommendation: Expand to architecture document or link to new guide

### Medium Priority (Incomplete Coverage)

**docs/daily_pipeline_run.md**
- Size: 7.1KB
- Content: CLI commands and dependencies
- ⚠️ Issue: Doesn't explain 3-part EM flow, Theta alternative
- Recommendation: Update with EM backends, real-time options

**docs/ARCHITECTURE_PRINCIPLES.md**
- Size: 5.9KB
- Content: Core philosophy and patterns
- ⚠️ Missing: Split-source constraint, provider hierarchy
- Recommendation: Add "Data Provider Strategy" section

### Low Priority (Stub/Minimal)

**docs/data_standards.md** - 1.4KB
**docs/Security.md** - 1.7KB
**docs/CLI_REFERENCE.md** - 1.8KB

---

## Recommendations for Documentation Improvements

### Tier 1: Critical (Do First)
1. Create `docs/CORE/EXPECTED_MOVES_ARCHITECTURE.md` (3-5 pages)
2. Add "Split-Source Data Strategy" section to ARCHITECTURE_PRINCIPLES
3. Create `docs/CORE/THETA_INTEGRATION.md` (2-3 pages)

### Tier 2: Important (Do Next)
1. Create centralized `docs/API_REFERENCE.md` with all endpoints
2. Add "Real-Time vs Batch" decision flowchart to main README
3. Update PIPELINE_ARCHITECTURE with 3-part EM flow

### Tier 3: Nice to Have
1. Expand DATA_REFERENCE with new fields and persistence patterns
2. Create advanced tutorial: "Implementing Real-Time Analytics"
3. Clean up duplicate files (consolidate daily pipeline docs)

---

## Checklist for Documentation Completeness

- [ ] All modules have architecture documentation
- [ ] Real-time vs batch nature explicitly stated for each module
- [ ] API endpoints documented with parameters and return types
- [ ] Data provider hierarchy and fallback logic explained
- [ ] Calculation formulas documented with mathematical notation
- [ ] Critical constraints documented (not just in code comments)
- [ ] Real-time capabilities explicitly listed (e.g., force_refresh parameter)
- [ ] Setup/integration requirements documented (e.g., Theta Terminal)
- [ ] Caching strategies documented (TTL, invalidation)
- [ ] No duplicate documentation for same feature

---

**Status**: ✅ Inventory complete. Ready for detailed module documentation audit.
