# Business Confidence Series Research Report

> **Run Date:** 2026-01-14  
> **Task:** Research FRED series for Business Confidence migration  
> **Status:** ✅ Research Complete - Ready for Implementation Approval

---

## Executive Summary

### The Problem
The Business Confidence indicator page currently uses **UMCSENT** (University of Michigan Consumer Sentiment) as its primary series. This is a **mislabeling issue** — UMCSENT measures *consumer* sentiment, not *business* confidence.

### Recommended Solution

| Current | Proposed |
|---------|----------|
| **Primary:** UMCSENT (Consumer Sentiment) | **Primary:** BSCICP02USM460S (Business Tendency Survey) |
| **Related:** None | **Related:** CFNAI, GACDISA066MSFRBNY, BUSLOANS, BAMLC0A4CBBB |

### Key Findings
1. ✅ **BSCICP02USM460S** is the best primary candidate — current, 75+ years of data, zero missing values
2. ⚠️ **BSCICP03USM665S** (originally proposed) is **stale** — last data from Jan 2024 (744 days old)
3. ❌ **ISM Manufacturing PMI** (NAPM) is **not available on FRED** — ISM publishes proprietary data
4. ✅ Four supporting series verified and available

---

## Detailed Research Results

### Series Verification Summary

| Series ID | Description | Status | Data Freshness | Data Range | Missing Values |
|-----------|-------------|--------|----------------|------------|----------------|
| **UMCSENT** | UMich Consumer Sentiment | ✅ Available | Current | 1952-2025 | 210 |
| **BSCICP03USM665S** | OECD Business Confidence Composite | ⚠️ Stale | 744 days old | 1950-2024 | 0 |
| **BSCICP02USM460S** | Business Tendency Survey (Mfg) | ✅ Current | 74 days old | 1950-2025 | 0 |
| **NAPM** | ISM Manufacturing PMI | ❌ Not Found | — | — | — |
| **BAMLC0A4CBBB** | BBB Corporate Bond Spread | ✅ Current | 2 days old | 1996-2026 | 62 |
| **BUSLOANS** | C&I Loans | ✅ Current | 44 days old | 1947-2025 | 0 |
| **CFNAI** | Chicago Fed National Activity | ✅ Available | 135 days old | 1967-2025 | 0 |
| **GACDISA066MSFRBNY** | Empire State Manufacturing | ✅ Current | 44 days old | 2001-2025 | 0 |

### Detailed Series Analysis

#### Recommended Primary: BSCICP02USM460S
```
Title: Business Tendency Surveys (Manufacturing): Confidence Indicators: 
       Composite Indicators: National Indicator for United States
Frequency: Monthly
Units: Percent
Data Range: 1950-01-01 to 2025-11-01
Data Points: 911
Missing Values: 0
Last Updated: 2025-12-15
```

**Why this is the best choice:**
- ✅ Actually measures **business** confidence (manufacturing sector)
- ✅ Current data (updated within 90 days)
- ✅ 75+ years of history for robust percentile calculations
- ✅ Zero missing values — clean data
- ✅ OECD standardized methodology — comparable across countries

#### Why NOT BSCICP03USM665S (Originally Proposed)
Despite being named "Business Confidence", this series:
- ⚠️ Last data point: January 2024 (744 days stale)
- ⚠️ Appears to be discontinued or delayed
- ⚠️ Cannot provide current economic readings

#### Why NOT ISM Manufacturing PMI
- ❌ **Not available on FRED** — ISM publishes proprietary data
- ❌ Alternative series codes (NAPM, NAPMPMI, USPMIBMI) don't exist
- ❌ Would require separate data source integration

---

## Proposed Configuration

### New Primary + Related Metrics

```yaml
business_confidence:
  primary:
    - series_id: BSCICP02USM460S
      name: Business Confidence (Manufacturing)
      description: OECD Business Tendency Survey - Manufacturing sector confidence
      frequency: M
      unit: Percent

  secondary:
    - series_id: CFNAI
      name: Chicago Fed National Activity Index
      description: Weighted average of 85 monthly indicators
      frequency: M
      unit: Index
      
    - series_id: GACDISA066MSFRBNY
      name: Empire State Manufacturing Survey
      description: NY Fed manufacturing conditions index
      frequency: M
      unit: Index
      
    - series_id: BUSLOANS
      name: Commercial & Industrial Loans
      description: Business borrowing at commercial banks
      frequency: M
      unit: Billions of Dollars
      
    - series_id: BAMLC0A4CBBB
      name: BBB Corporate Bond Spread
      description: Investment-grade credit spread
      frequency: D
      unit: Percent
```

### What Happens to UMCSENT?

**Recommendation:** Keep in `macro_series.yml` but remove from business_confidence primary series.

**Justification:**
- UMCSENT is valuable for other purposes (consumer spending, LEI calculation)
- Currently used in LEI model (`scripts/calibrate_lei_final.py`)
- Should NOT be the primary indicator for "Business Confidence" page

---

## Migration Impact Assessment

### Files Requiring Changes

| File | Changes Needed |
|------|----------------|
| [aggregate_indicators.py](file:///Users/pawelleks/Documents/Python/Projects/Market_Intelligence_Engine/src/mie_lib/analytics/jpm_dashboard/aggregate_indicators.py) | Update `INDICATOR_SERIES['business_confidence']['primary']` |
| [jpm_dashboard.py](file:///Users/pawelleks/Documents/Python/Projects/Market_Intelligence_Engine/src/mie_lib/api/routers/jpm_dashboard.py) | Update `INDICATOR_PRIMARY_SERIES`, `SERIES_UNITS`, `SERIES_DISPLAY_NAMES`, health score function |
| [mie.py](file:///Users/pawelleks/Documents/Python/Projects/Market_Intelligence_Engine/src/mie_lib/cli/mie.py) | Update `primary_series` mapping |
| [tier2_release_mappings.json](file:///Users/pawelleks/Documents/Python/Projects/Market_Intelligence_Engine/config/tier2_release_mappings.json) | Update `primary_series` and `related_series` |
| [business_confidence_config.json](file:///Users/pawelleks/Documents/Python/Projects/Market_Intelligence_Engine/frontend/src/data/tier2_configs/business_confidence_config.json) | Update educational content and add `related_metrics` |
| [macro_series.yml](file:///Users/pawelleks/Documents/Python/Projects/Market_Intelligence_Engine/config/macro_series.yml) | Add BSCICP02USM460S entry |

### Health Score Recalculation Required

The current `calculate_business_confidence_health()` function uses thresholds calibrated for UMCSENT (50-100 range):

```python
# Current thresholds (UMCSENT)
if current_value >= 90: score += 50  # Exceptional
elif current_value >= 80: score += 45  # Strong
elif current_value >= 70: score += 40  # Moderate
# ...
```

BSCICP02USM460S uses a **different scale** (centered around 100, deviations in percentage points).

**Required:** New thresholds must be calibrated for BSCICP02USM460S data range.

### AI Prompt Status

The [economic_analyst.txt](file:///Users/pawelleks/Documents/Python/Projects/Market_Intelligence_Engine/prompts/economic_analyst.txt) prompt contains:
> "Business Confidence: Above 80 = optimistic, below 60 = pessimistic"

This will need updating if the new series uses different thresholds.

---

## Implementation Readiness Checklist

### Data Availability ✅
- [x] Primary series (BSCICP02USM460S) exists on FRED
- [x] Primary series has sufficient history (75+ years)
- [x] Primary series is currently updated (within 90 days)
- [x] At least 2 related metrics available and verified (4 total)
- [x] All series accessible via FRED API
- [ ] ❌ ISM PMI not available (excluded from plan)

### Documentation Complete ✅
- [x] Research findings documented
- [x] Series comparison table completed
- [x] Files requiring changes identified
- [x] Health score impact documented

### Decision Points Resolved
- [x] **Primary series:** BSCICP02USM460S (Business Tendency Survey)
- [ ] **Health score thresholds:** Need calibration during implementation
- [x] **UMCSENT disposition:** Keep for other uses, remove from business_confidence
- [x] **Related metrics:** CFNAI, GACDISA066MSFRBNY, BUSLOANS, BAMLC0A4CBBB

---

## Next Steps

1. **Approve this research** — Confirm recommendations are acceptable
2. **Fetch new series data** — Add BSCICP02USM460S to `macro_series.yml` and run data ingestion
3. **Calibrate health score** — Analyze BSCICP02USM460S distribution and set appropriate thresholds
4. **Update backend code** — Modify aggregation and API files
5. **Update frontend config** — Add related metrics to tier2 config
6. **Update AI prompt** — Adjust thresholds if needed
7. **Test and deploy** — Verify dashboard shows correct data
