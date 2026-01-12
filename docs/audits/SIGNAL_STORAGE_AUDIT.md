# Historical Signal Data Storage Audit

**Scan Date**: 2026-01-10
**Audit Status**: Completed

## Executive Summary
A comprehensive scan of the repository identified **20 primary data files** containing historical economic signals. The storage architecture is robust, utilizing **Parquet** format for all signal time-series, which ensures efficient I/O and type safety.

**Key Strengths:**
- **Deep History**: Core models (LEI/COI, ABCT, Recession Momentum) have signal history extending back over **50 years** (to ~1960-1970).
- **Data Integrity**: Most critical signal columns (`LEI_Final`, `Cycle_Phase`, `Recession_Prob`) are clean with minimal nulls.
- **Unified location**: Primary signals are well-organized in `data/analytics/macro` and `data/processed`.

**Gaps Identified:**
- **Null Values**: `processed_lei_coi_enhanced.parquet` has some nulls in `LEI_Final` (261 rows) likely due to the 120-month rolling window initialization. This is expected but reduces effective analyzeable history.
- **Hamilton Model**: History is short (start date 2005) due to the underlying GDP data or windowing constraints. This limits its use for training on 2000 or 2008 recessions if not extended.

---

## 1. Storage Inventory Statistics
- **Total Signal Files**: 20
- **Total Formats**: 18 Parquet, 1 JSON, 1 Failed (JSON)
- **Longest History**: `panel.parquet` (171 Years) - likely valid data but potentially sparse.
- **Shortest History**: `hamilton_model.parquet` (19.8 Years).

---

## 2. Model Coverage Matrix

| Model | Signal Data File | Start Date | End Date | Years | Status | Priority Gap |
|-------|------------------|------------|----------|-------|--------|--------------|
| **Enhanced LEI/COI** | `processed_lei_coi_enhanced.parquet` | 1960-01-31 | 2026-01-31 | 66.0 | 🟢 Ready | Rolling window nulls |
| **Business Cycle** | `processed_business_cycle.parquet` | 1981-07-31 | 2025-09-30 | 44.2 | 🟢 Ready | None |
| **Minsky Model** | `minsky_model.parquet` | 1986-01-01 | 2025-04-01 | 39.2 | 🟢 Ready | None |
| **ABCT Model** | `abct_model.parquet` | 1959-01-01 | 2025-09-01 | 66.7 | 🟢 Ready | None |
| **Hamilton Switch** | `hamilton_model.parquet` | 2005-04-01 | 2025-01-01 | 19.8 | 🟡 Partial | *Need longer history* |
| **HP Filter** | `hp_model.parquet` | 2005-01-01 | 2025-04-01 | 20.2 | 🟡 Partial | *Need longer history* |
| **Recession Momentum** | `recession_momentum.parquet` | 1971-01-01 | 2025-11-01 | 54.8 | 🟢 Ready | None |
| **LAG Index** | `lag_model.parquet` | 1990-01-01 | 2025-12-01 | 35.9 | 🟢 Ready | None |
| **Fed Trap** | `fed_trap_divergence.parquet` | 1998-08-01 | 2025-08-01 | 27.0 | 🟢 Ready | None |

---

## 3. Detailed File Analysis

### Core Analysis Files (`data/analytics/macro`)

#### **`processed_lei_coi_enhanced.parquet`**
- **Content**: The single source of truth for the LEI/COI dashboard.
- **Signals**: `LEI_Final`, `COI_Final`, `Recession_Signal_Active`.
- **Quality**: `LEI_Final` has **261 Nulls** at the start (1960-1981 period presumably). Effective signal start is likely ~1981.
- **Recommendation**: Check if the large null window can be reduced or if specific series (NFCI?) are limiting the history.

#### **`processed_business_cycle.parquet`**
- **Content**: Merged dataset of LEI, COI, LAG, and S&P 500.
- **Signals**: `Cycle_Phase` (Recovery/Expansion/Slowdown/Recession), `Recession_Prob`.
- **Quality**: Very clean. 44 Years of complete cycle data. Excellent for backtesting.

#### **`recession_flags.parquet`**
- **Content**: A long history file likely containing NBER recession dates or similar.
- **Signals**: `recession_flag`, `phase`.
- **History**: 171 Years. Useful ground truth for training.

### Processed Model Files (`data/processed`)

#### **`minsky_model.parquet`**
- **Signals**: `minsky_instability_gap`, `leverage_ratio`.
- **History**: 39 Years (Starts 1986).
- **Notes**: Captures the GFC (2008) and Covid (2020) but not the 1970s stagflation. This might be limited by `BCNSDODNS` (Corp Debt) or `CPATAX` availability in the specific format used.

#### **`abct_model.parquet`**
- **Signals**: `abct_boom_score`, `malinvestment_ratio`.
- **History**: 66 Years (Starts 1959).
- **Notes**: One of the deepest history files. Excellent for analyzing long-term structural cycles.

#### **`hamilton_model.parquet`** & **`hp_model.parquet`**
- **Signals**: `recession_prob` (Hamilton), `output_gap` (HP).
- **History**: ~20 Years (Starts ~2005).
- **Critical Issue**: This is too short for robust training. It misses the 2000 Dot-com bubble and only barely captures the lead-up to 2008. The underlying input (`GDPC1`?) usually goes back further.
- **Action**: Investigate `hp_model_generator.py` to see why it truncates data (possibly credit series `TOTDTEUSQ163N` start date?).

---

## 4. Recommendations for Next Phase

1.  **Extend Quantitative Models**: The Hamilton and HP Filter models need to be extended back to at least 1980 to be comparable with the Business Cycle and LEI models. Priority: Investigate `TOTDTEUSQ163N` constraint.
2.  **Harmonize Start Dates**: For a unified "Risk Score", we need a common start date. ~1990 is the current LCD (Lowest Common Denominator) due to LAG and Minsky. 1990-2025 is a decent 35-year window covering 3-4 major cycles.
3.  **Null Handling**: Explicitly handle the pre-1980 nulls in `processed_lei_coi_enhanced` so they don't break backtests (e.g. drop rows before valid signals start).
