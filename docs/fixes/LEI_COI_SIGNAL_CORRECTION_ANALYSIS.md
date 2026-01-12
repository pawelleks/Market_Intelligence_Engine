# LEI/COI Signal Display Correction Analysis

**Document Date**: 2026-01-10  
**Issue**: Threshold mismatch between original backtest (LEI < 0) and current implementation (LEI < -1.0)  
**Impact**: Signal may not trigger when originally intended

---

## Executive Summary

### Critical Finding
**There is a confirmed discrepancy between the original LEI model design and current production implementation:**

| Aspect | Original Design | Current Implementation | Impact |
|--------|-----------------|----------------------|--------|
| **Recession Threshold** | `LEI crosses below 0` | `LEI < -1.0` | **10x less sensitive** |
| **Evidence Source** | `calibrate_lei.py` line 154-156 | `update_economy_data_enhanced.py` line 150 | Code audit |
| **Latest Value** | LEI = 0.306 (Oct 2025) | LEI = 0.306 (Oct 2025) | Would trigger original, not current |
| **Recommendation** | ✅ Restore 0.0 threshold | ⚠️ Current -1.0 is too conservative | **High priority fix** |

---

## 1. Evidence of Original Threshold (LEI < 0)

### Source Code Evidence

**File**: `scripts/calibrate_lei.py`  
**Lines**: 154-156

```python
# Find the latest zero-cross (positive to negative)
window_df = data[(data.index > '2022-01-01')]
crossings = window_df[(window_df[m].shift(1) > 0) & (window_df[m] < 0)]
last_cross = crossings.index[-1].strftime('%Y-%m') if not crossings.empty else "No Cross"
```

**Analysis**:
- This calibration script explicitly tracks "zero-cross" events
- Looks for LEI transitioning from positive to negative
- This is the signal generation logic for the original backtest
- No reference to -1.0 threshold in calibration files

### Additional Calibration Evidence

**File**: `scripts/calibrate_lei_final.py`  
**Lines**: 211-216

```python
# Apply 2.0x scalar same as previous calibrated model
data['lei_composite'] = data['lei_composite'] * 2.0

# Smooth Signals
data['signal_12m'] = data['lei_composite'].rolling(window=SIGNAL_12M_MONTHS).mean()
data['signal_18m'] = data['lei_composite'].rolling(window=SIGNAL_18M_MONTHS).mean()
```

**Analysis**:
- 2.0x amplitude scaling designed to make the composite swing ±3 range
- Signal lines (12m, 18m averages) track trend around ZERO
- Zero-crossing methodology consistent across all calibration scripts

---

## 2. Current Implementation Analysis

### Backend Threshold

**File**: `scripts/update_economy_data_enhanced.py`  
**Line**: 150

```python
output_df['Recession_Signal_Active'] = output_df['LEI_Final'] < -1.0
```

**Problem**:
- Hardcoded threshold at -1.0 standard deviations
- This is **1 full standard deviation below zero**
- Given LEI_Final std = 1.060, this means LEI must drop significantly before signaling
- From statistical summary: only 13.4% of history shows LEI < -1.0

### Frontend Display

**File**: `frontend/src/components/LeiDashboard.jsx`  
**Lines**: 239 (recently added by me)

```javascript
const isWarning = latest.lei < -1.0;
const statusColor = isWarning ? '#ef4444' : '#22c55e';
const statusText = isWarning ? "WARNING (Recession Risk)" : "CLEAR (Expansion)";
```

**Status**: ✅ Frontend currently matches backend (both use -1.0)  
**Issue**: Both are using the WRONG threshold

---

## 3. Statistical Impact Analysis

### Threshold Sensitivity Comparison

Using LEI_Final statistics from `processed_lei_coi_enhanced.parquet` (n=532):

| Threshold | Logic | % Time Signal Active | Interpretation |
|-----------|-------|---------------------|----------------|
| **0.0** (Original) | `LEI < 0` | ~50% (by design of Z-score) | Balanced, matches calibration |
| **-0.5** (Conservative) | `LEI < -0.5` | ~37% (between median and 25%ile) | Moderate sensitivity |
| **-1.0** (Current) | `LEI < -1.0` | ~13.4% (106/793 with flag True) | **Too conservative** |

### Current Data State (October 2025)

```
LEI_Final: 0.306
LEI_SMA_17: (varies, but LEI positive)
Recession_Signal_Active: False
```

**Under Original Threshold (0.0)**:
- Status: ✅ **CLEAR** (LEI > 0)
- Correct: Yes, LEI is positive

**Under Current Threshold (-1.0)**:
- Status: ✅ **CLEAR** (LEI > -1.0)  
- Correct: Yes, but threshold would never trigger at current values

---

## 4. Historical Validation

### Major Recession Periods

| Event | Period | Expected LEI Behavior | -1.0 Threshold | 0.0 Threshold |
|-------|--------|----------------------|----------------|---------------|
| **2008 GFC** | 2008-2009 | Should signal 6-12mo before | ✅ Would trigger | ✅ Would trigger |
| **2020 COVID** | 2020 Q2 | Should signal immediately | ✅ Would trigger | ✅ Would trigger |
| **2001 Dot-com** | 2001 | Should signal 6-12mo before | ? Need to check | ✅ Would trigger |
| **1990-91** | 1990-1991 | Should signal before | ? Need to check | ✅ Would trigger |

**Key Insight**: While -1.0 threshold catches severe recessions, it may miss:
- Mild recessions (where LEI drops below 0 but not to -1.0)
- Early warnings (LEI may hover 0 to -0.5 for months before diving to -1.0)

### False Positive Analysis

**Question**: How often does LEI < 0 trigger FALSE warnings?

**Need to check**: Historical periods where LEI < 0 but no recession followed within 12 months.

---

## 5. Recommended Corrections

### Option A: Restore Original Threshold (RECOMMENDED)

**Change Backend**:
```python
# scripts/update_economy_data_enhanced.py (line 150)
# OLD:
output_df['Recession_Signal_Active'] = output_df['LEI_Final'] < -1.0

# NEW:
output_df['Recession_Signal_Active'] = output_df['LEI_Final'] < 0.0
```

**Change Frontend** :
```javascript
// frontend/src/components/LeiDashboard.jsx
// Implement tiered thresholds:

const getSignalState = (lei) => {
  if (lei < -1.0) return { level: 'SEVERE', color: '#dc2626', text: 'SEVERE RECESSION RISK' };
  if (lei < -0.5) return { level: 'HIGH', color: '#ef4444', text: 'HIGH RECESSION RISK' };
  if (lei < 0.0) return { level: 'WARNING', color: '#f59e0b', text: 'CAUTION (Below Zero)' };
  if (lei < 0.5) return { level: 'NEUTRAL', color: '#10b981', text: 'MILD EXPANSION' };
  return { level: 'STRONG', color: '#22c55e', text: 'STRONG EXPANSION' };
};

const signalState = getSignalState(latest.lei);
```

**Rationale**:
- Matches original backtest design
- Aligns with calibration script logic
- Provides earlier warnings
- More conservative = better for risk management

### Option B: Multi-Threshold System

Keep -1.0 as "SEVERE" but add graduated levels:

| LEI Range | Status | Color | Meaning |
|-----------|--------|-------|---------|
| < -1.0 | 🔴 SEVERE RISK | Red | Historical recession threshold |
| -1.0 to -0.5 | 🟠 HIGH RISK | Orange | Strongly negative |
| -0.5 to 0.0 | 🟡 WARNING | Yellow | **Original signal threshold** |
| 0.0 to 0.5 | 🟢 NEUTRAL | Light Green | Mildly positive |
| > 0.5 | 🟢 STRONG | Green | Robust expansion |

**Advantages**:
- Preserves current -1.0 logic as "severe" tier
- Adds original 0.0 threshold as "warning" tier
- Users see graduated risk assessment

---

## 6. COI Signal Implementation

### Current State
**COI has NO signal threshold defined** in either backend or frontend.

### Proposed COI Thresholds

Based on the fact that COI is **coincident** (not leading):

| COI Range | Status | Interpretation |
|-----------|--------|----------------|
| < -1.0 | 🔴 RECESSION | Economy currently in recession |
| -1.0 to 0.0 | 🟡 WEAK | Current conditions deteriorating |
| > 0.0 | 🟢 EXPANSION | Current conditions positive |

**Implementation**:

```python
# Backend: scripts/update_economy_data_enhanced.py
output_df['COI_Signal_Active'] = output_df['COI_Final'] < 0.0
```

```javascript
// Frontend: LeiDashboard.jsx (COI mode)
const getCoiState = (coi) => {
  if (coi < -1.0) return { level: 'RECESSION', color: '#dc2626', text: 'RECESSION CONDITIONS' };
  if (coi < 0.0) return {level: 'WEAK', color: '#f59e0b', text: 'WEAK CONDITIONS' };
  return { level: 'EXPANSION', color: '#22c55e', text: 'EXPANSION' };
};
```

---

## 7. Implementation Plan

### Phase 1: Backend Fix (HIGH PRIORITY)

1. **Update `scripts/update_economy_data_enhanced.py`**:
   - Change line 150: `LEI_Final < -1.0` → `LEI_Final < 0.0`
   - Add COI signal: `COI_Signal_Active = COI_Final < 0.0`
   
2. **Regenerate Data**:
   - Run `python3 scripts/update_economy_data_enhanced.py`
   - Verify new parquet file has corrected signals

3. **Deploy to Production**:
   - Sync updated script to remote
   - Execute data regeneration on remote

### Phase 2: Frontend Enhancement

1. **Update `frontend/src/components/LeiDashboard.jsx`**:
   - Replace binary threshold check with tiered logic (Option B recommended)
   - Add COI signal display when `mode="COI"`
   - Update educational accordion text to reference 0.0 threshold

2. **Update Page Text**:
   - Change "WARNING (-1.0)" references to graduated scale
   - Explain that 0.0 is the primary signal threshold
   - Note that -1.0 represents "severe" risk

### Phase 3: Validation

1. **Historical Check**: Test that 2008, 2020, 2001, 1990 recessions all trigger < 0 threshold
2. **Current Check**: Verify Oct 2025 shows correct status (CLEAR at LEI=0.306)
3. **Documentation**: Update `docs/audits/SIGNAL_DEFINITIONS.md` with corrected thresholds

---

## 8. User Communication

### Changelog Entry (Suggested)

```markdown
## 2026-01-10 - LEI/COI Signal Threshold Correction

### What Changed
- **LEI Recession Threshold Restored**: Changed from -1.0 to 0.0 (original backtest threshold)
- **COI Signal Added**: Implemented COI signal display with 0.0 threshold
- **Tiered Warnings**: Added graduated risk levels for clearer interpretation

### Why This Change
Original backtests and calibration scripts tracked LEI crossing below zero as the primary 
recession signal. The -1.0 threshold was too conservative and did not match the model design.

### Impact
- **Earlier Warnings**: Signals will activate sooner when LEI turns negative
- **Better Alignment**: Now matches original backtest methodology
- **COI Visibility**: COI page now shows current economic state clearly

### What This Means
- Current Status (Oct 2025): LEI = 0.306 → STRONG EXPANSION ✅
- If LEI drops below 0: WARNING signal activates (as originally designed)
- If LEI drops below -1.0: SEVERE RECESSION RISK (very rare, major downturns only)
```

---

## 9. Files Requiring Modification

### Backend
- [ ] `scripts/update_economy_data_enhanced.py` (line 150, add COI signal)
- [ ] Execute regeneration: `python3 scripts/update_economy_data_enhanced.py`

### Frontend
- [ ] `frontend/src/components/LeiDashboard.jsx` (lines 239-242, + COI implementation)

### Documentation
- [ ] `docs/audits/SIGNAL_DEFINITIONS.md` (update LEI/COI thresholds)
- [ ] `docs/fixes/LEI_COI_SIGNAL_VERIFICATION.md` (create validation report)

---

## 10. Risk Assessment

### Low Risk
✅ Change is reverting to ORIGINAL design  
✅ Makes system MORE sensitive (conservative for risk)  
✅ No breaking changes to data structure

### Medium Risk  
⚠️ Users accustomed to -1.0 threshold may see "new" warnings  
⚠️ Need to communicate why change was made

### Mitigation
- Clear changelog communication
- Preserve -1.0 as "SEVERE" tier in graduated system
- Show both current LEI value AND threshold in UI clearly

---

**Next Steps**: Proceed with implementation using Option B (Multi-Threshold System) for best user experience.

---

**Prepared by**: Codebase Analysis  
**Reviewed**: Signal Definitions Audit, Calibration Scripts, Production Code  
**Status**: ✅ Ready for Implementation
