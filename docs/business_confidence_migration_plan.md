# Business Confidence Series Migration Plan

> **Status:** Ready for Implementation Approval  
> **Research Complete:** 2026-01-14  
> **Estimated Implementation Time:** 2-3 hours

---

## Current State (Before Migration)

### Primary Series
| Attribute | Value |
|-----------|-------|
| Series ID | UMCSENT |
| Name | University of Michigan Consumer Sentiment |
| **Problem** | ❌ Measures **consumer** sentiment, not **business** confidence |
| Data Range | 1952-11-01 to 2025-11-01 |
| Frequency | Monthly |
| Unit | Index 1966:Q1=100 |

### Related Metrics
- **None** (empty array in config)

### Configuration Files
- [aggregate_indicators.py](file:///Users/pawelleks/Documents/Python/Projects/Market_Intelligence_Engine/src/mie_lib/analytics/jpm_dashboard/aggregate_indicators.py#L63-68): `'primary': ['UMCSENT']`
- [jpm_dashboard.py](file:///Users/pawelleks/Documents/Python/Projects/Market_Intelligence_Engine/src/mie_lib/api/routers/jpm_dashboard.py#L75): `'business-confidence': 'UMCSENT'`
- [business_confidence_config.json](file:///Users/pawelleks/Documents/Python/Projects/Market_Intelligence_Engine/frontend/src/data/tier2_configs/business_confidence_config.json): Educational content references "consumer sentiment"

### Health Score Calculation
- Function: `calculate_business_confidence_health()`
- Location: [jpm_dashboard.py#L451-482](file:///Users/pawelleks/Documents/Python/Projects/Market_Intelligence_Engine/src/mie_lib/api/routers/jpm_dashboard.py#L451-482)
- Thresholds calibrated for UMCSENT (50-100 scale)

---

## Proposed New State (After Migration)

### Primary Series
| Attribute | Value |
|-----------|-------|
| Series ID | **BSCICP02USM460S** |
| Name | Business Tendency Survey (Manufacturing) |
| **Solution** | ✅ Actual **business** confidence indicator |
| Data Range | 1950-01-01 to 2025-11-01 |
| Frequency | Monthly |
| Unit | Percent (centered around 100) |
| Source | OECD via FRED |

### Related Metrics

| Order | Series ID | Display Name | Category | Unit |
|-------|-----------|--------------|----------|------|
| 1 | CFNAI | Chicago Fed National Activity | activity | Index |
| 2 | GACDISA066MSFRBNY | Empire State Manufacturing | survey | Index |
| 3 | BUSLOANS | Commercial & Industrial Loans | lending | $B |
| 4 | BAMLC0A4CBBB | BBB Corporate Bond Spread | credit | % |

---

## Migration Steps

### Phase 1: Data Preparation

- [ ] **1.1** Add BSCICP02USM460S to `config/macro_series.yml`
- [ ] **1.2** Run FRED data ingestion: `mie fred download`
- [ ] **1.3** Verify data file exists: `data/raw/macro/fred/BSCICP02USM460S.parquet`
- [ ] **1.4** Analyze data distribution for health score calibration

### Phase 2: Backend Updates

- [ ] **2.1** Update [aggregate_indicators.py](file:///Users/pawelleks/Documents/Python/Projects/Market_Intelligence_Engine/src/mie_lib/analytics/jpm_dashboard/aggregate_indicators.py):
  ```diff
  'business_confidence': {
  -    'primary': ['UMCSENT'],
  -    'secondary': ['CSCICP03USM665S', 'CFNAI'],
  -    'components': ['BPMTTL', 'GACDISA066MSFRBNY'],
  +    'primary': ['BSCICP02USM460S'],
  +    'secondary': ['CFNAI', 'GACDISA066MSFRBNY'],
  +    'components': ['BUSLOANS', 'BAMLC0A4CBBB'],
       'freq': 'monthly'
  }
  ```

- [ ] **2.2** Update [jpm_dashboard.py](file:///Users/pawelleks/Documents/Python/Projects/Market_Intelligence_Engine/src/mie_lib/api/routers/jpm_dashboard.py):
  - Update `INDICATOR_PRIMARY_SERIES`
  - Update `SERIES_UNITS`
  - Update `SERIES_DISPLAY_NAMES`
  - Recalibrate `calculate_business_confidence_health()` thresholds

- [ ] **2.3** Update [mie.py](file:///Users/pawelleks/Documents/Python/Projects/Market_Intelligence_Engine/src/mie_lib/cli/mie.py):
  ```diff
  - 'business-confidence': {'file': 'business_confidence.parquet', 'primary_series': 'UMCSENT'},
  + 'business-confidence': {'file': 'business_confidence.parquet', 'primary_series': 'BSCICP02USM460S'},
  ```

- [ ] **2.4** Update [tier2_release_mappings.json](file:///Users/pawelleks/Documents/Python/Projects/Market_Intelligence_Engine/config/tier2_release_mappings.json):
  ```json
  "business_confidence": {
      "display_name": "Business Confidence",
      "primary_series": ["BSCICP02USM460S"],
      "related_series": ["CFNAI", "GACDISA066MSFRBNY", "BUSLOANS", "BAMLC0A4CBBB"]
  }
  ```

### Phase 3: Frontend Updates

- [ ] **3.1** Update [business_confidence_config.json](file:///Users/pawelleks/Documents/Python/Projects/Market_Intelligence_Engine/frontend/src/data/tier2_configs/business_confidence_config.json):
  - Update educational content to reference "business confidence"
  - Add `related_metrics` array with 4 metrics

### Phase 4: Regenerate Data

- [ ] **4.1** Regenerate aggregations: `mie jpm aggregate`
- [ ] **4.2** Verify `data/processed/jpm_dashboard/business_confidence.parquet` contains new series

### Phase 5: Deploy & Verify

- [ ] **5.1** Deploy backend changes
- [ ] **5.2** Deploy frontend changes
- [ ] **5.3** Verify Business Confidence page shows new primary series
- [ ] **5.4** Verify Related Metrics section populated
- [ ] **5.5** Verify health score makes sense with new data

---

## Verification Plan

### Automated Tests
```bash
# Run existing tests
pytest tests/ -v -k "jpm_dashboard or business_confidence"

# Verify data file exists after ingestion
python3 -c "import pandas as pd; df = pd.read_parquet('data/raw/macro/fred/BSCICP02USM460S.parquet'); print(f'Rows: {len(df)}, Latest: {df.date.max()}')"
```

### Manual Verification
1. Navigate to `/economy/business-confidence` page
2. Verify:
   - Primary value displayed is from BSCICP02USM460S (around 100 baseline, not 50-100)
   - Chart title updated
   - Related Metrics section shows 4 metrics with values
   - Health score reasonable (not showing "Critical" incorrectly)

---

## Health Score Calibration Notes

The new series (BSCICP02USM460S) uses a **different scale** than UMCSENT:

| Metric | UMCSENT | BSCICP02USM460S |
|--------|---------|-----------------|
| Baseline | 100 (1966) | 100 (normalized) |
| Typical Range | 50-110 | 98-102 |
| Interpretation | Higher = more confident | Above 100 = positive, Below 100 = negative |

**Recommended threshold mapping:**
```python
def calculate_business_confidence_health(current_value, percentile, yoy_change):
    """
    BSCICP02USM460S: Centered around 100
    >101 = Highly optimistic
    100-101 = Optimistic
    99-100 = Neutral
    98-99 = Cautious
    <98 = Pessimistic
    """
    score = 0
    
    # Percentile component (50% weight)
    score += percentile * 0.5
    
    # Absolute level component (50% weight)
    if current_value >= 101.5:
        score += 50  # Very optimistic
    elif current_value >= 100.5:
        score += 45  # Optimistic
    elif current_value >= 100.0:
        score += 40  # Neutral-positive
    elif current_value >= 99.5:
        score += 30  # Neutral-negative
    elif current_value >= 99.0:
        score += 15  # Cautious
    elif current_value >= 98.0:
        score += 5   # Pessimistic
    else:
        score += 0   # Very pessimistic
    
    return int(max(0, min(100, score)))
```

---

## Rollback Plan

If migration causes issues:

1. **Revert code changes** — Use git to revert commits
2. **Restore UMCSENT as primary** — Update configs back to original values
3. **Regenerate data** — Run `mie jpm aggregate` to restore UMCSENT-based files
4. **Clear any cached data** — If API caching is enabled

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Health score incorrect after migration | Medium | High | Careful threshold calibration, test before deploy |
| Missing data for new series | Low | High | Already verified data exists via FRED API |
| Frontend display issues | Low | Medium | Test in staging environment |
| User confusion about changed values | Low | Low | Values will change but meaning preserved |

---

## What Happens to UMCSENT?

**Decision:** Keep in system but remove from Business Confidence indicator.

**Justification:**
- UMCSENT is still used in LEI calculation (`scripts/calibrate_lei_final.py`)
- Valid for Consumer Spending or Consumer Confidence contexts
- Just incorrectly placed as Business Confidence primary

**Future consideration:** Create separate "Consumer Confidence" indicator page if needed.
