# ARCHITECTURE PRINCIPLES (Core Rules)

**Status**: Authoritative - ALL development must follow  
**Last Updated**: 2026-01-10  
**Token Count**: ~600 (cheap to include in every prompt)

---

## 🎯 Core Philosophy

**Offline-First Data Layer**: Heavy compute happens in pipelines, not on user request.  
**Service Isolation**: Frontend, Backend, Data Pipelines are separate.  
**Deterministic**: Same inputs = same outputs (reproducible).  
**Test Before Deploy**: Every component tested individually before marking "complete".

---

## 📦 Universal Data Pipeline Pattern

**ALL data processing (Market AND Economic) MUST follow this exact pattern:**

```
1. FETCH/DOWNLOAD
   ↓ External source (Yahoo Finance, FRED API, etc.)
   ↓
2. SAVE RAW (Immutable)
   ↓ data/raw/{source}/{series}.parquet
   ↓ NEVER modify raw data once saved
   ↓
3. CALCULATE (Local Only)
   ↓ Read from raw parquet files
   ↓ NO external API calls during calculation
   ↓ Process deterministically
   ↓
4. SAVE PROCESSED
   ↓ data/processed/{model}.parquet
   ↓
5. API ENDPOINT (FastAPI)
   ↓ Read processed parquet
   ↓ Return JSON to frontend
   ↓
6. FRONTEND DISPLAY
   ↓ Fetch from API
   ↓ Render charts/tables
```

**Reference Implementation**: `scripts/market_data/` - Market Data Pipeline follows this exactly.

---

## 📁 Directory Structure

```
project_root/
├── data/
│   ├── raw/                    # Immutable source data
│   │   ├── market/             # Market prices (Yahoo)
│   │   └── fred/               # Economic series (FRED)
│   ├── processed/              # Calculated indicators
│   │   ├── features/           # Market features
│   │   └── *.parquet           # Economic models
│   ├── analytics/              # Analysis outputs
│   │   ├── macro/              # LEI, COI, etc.
│   │   └── dashboard/          # Dashboard data
│   └── outcomes/               # Prediction analysis outcomes
├── scripts/                    # Data pipeline scripts
│   ├── market_data/            # Market pipeline
│   └── *.py                    # Economic model scripts
├── frontend/
│   └── src/
│       ├── components/         # React components
│       └── pages/              # Page components
└── backend/
    └── routers/                # FastAPI routes
```

---

## 🔧 Technology Stack

**Backend**: Python, FastAPI, pandas  
**Data Format**: Parquet (NOT CSV for large datasets)  
**Frontend**: React (Vite), Recharts, Tailwind  
**Deployment**: Docker Compose (production)

---

## ✅ Testing Protocol (MANDATORY)

**Before marking ANY task "complete", self-check:**

- [ ] Does this follow the 6-step pipeline pattern?
- [ ] Is raw data in `data/raw/`? (NOT mixed with processed)
- [ ] Is processed data in `data/processed/`?
- [ ] Have I tested the script individually?
- [ ] Does the API endpoint return correct data?
- [ ] Does the frontend display correctly?
- [ ] Are there any hardcoded values (0.000)?
- [ ] Have I documented what changed?

**DO NOT proceed to next task until ALL boxes checked.**

---

## 🚫 Common Mistakes to AVOID

❌ Fetching from external APIs during calculations  
❌ Using CSV for large datasets (use Parquet)  
❌ Hardcoding values in frontend (fetch from API)  
❌ Mixing raw and processed data in same directory  
❌ Not testing scripts individually  
❌ Marking "complete" without validation  
❌ Creating new patterns instead of copying existing ones  

---

## 📚 Reference Implementations

**When creating new features, copy these patterns:**

### Market Data Pipeline
- **Location**: `scripts/market_data/`
- **Pattern**: Fetch → Cache → Calculate → Serve
- **Copy this for**: Any market price analysis

### Economic Model Pipeline
- **Location**: `scripts/calculate_*.py`
- **Pattern**: Load from raw/fred → Calculate → Save to processed
- **Copy this for**: Any economic indicator

### FastAPI Endpoint
- **Location**: `backend/routers/macro.py`
- **Pattern**: Load parquet → Filter → Return JSON
- **Copy this for**: Any new API endpoint

### React Page
- **Location**: `frontend/src/pages/LeiIndex.tsx` (or similar)
- **Pattern**: Fetch from API → Display with charts
- **Copy this for**: Any new analysis page

---

## 🎓 Development Workflow

### For New Economic Model:

1. **Check**: Does similar model already exist? Copy its pattern.
2. **Add series**: Update `data/fred_series.yaml` with required FRED series
3. **Create script**: `scripts/calculate_{model_name}.py`
   - Load from `data/raw/fred/`
   - Calculate indicator
   - Save to `data/processed/`
4. **Test script**: Run individually, verify output file exists
5. **Add API endpoint**: Follow existing pattern in `backend/routers/macro.py`
6. **Test API**: `curl http://localhost:8000/api/macro/{model}` - verify JSON
7. **Create frontend page**: Copy structure from existing model page
8. **Test frontend**: Verify display, charts, no hardcoded values
9. **Only then**: Mark complete

### For Bug Fixes:

1. **Don't rewrite everything** - debug only the failing block
2. **Explain fix** before applying
3. **Test the fix** individually
4. **Verify** it doesn't break other components

---

## 🔗 Related Documents

**Detailed architecture**: `docs/ARCHITECT_BIBLE.md` (full system design)  
**Data dictionary**: `docs/ARCHITECT_BIBLE.md` (Part 9)  
**Testing templates**: `docs/TESTING_CHECKLIST.md`  
**Model templates**: `docs/templates/NEW_MODEL_TEMPLATE.md`

---

## 💬 Prompt Usage

**Include in every major task:**

```
Follow architecture principles: docs/ARCHITECTURE_PRINCIPLES.md
Reference implementation: [point to relevant existing code]
Complete testing checklist before marking done.
```

---

**Last Sync with ARCHITECT_BIBLE**: 2026-01-10  
**Maintained By**: System Architecture
