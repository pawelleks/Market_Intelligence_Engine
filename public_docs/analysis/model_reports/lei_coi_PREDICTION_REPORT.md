# LEI COI - Prediction Analysis Report

**Generated**: 2026-02-18 03:02  
**Analysis Period**: 1960-01-31 00:00:00 to 2026-02-28 00:00:00  
**Data Coverage**: 66.1 years

---

## Executive Summary

**Overall Performance Rank**: #2 out of 9 models  
**Overall Score**: 30.9/100

### Key Metrics at a Glance

| Metric | Value | Assessment |
|--------|-------|------------|
| **Hit Rate** | 66.7% | ✅ Excellent |
| **False Positive Rate** | 62.5% | ⚠️ Acceptable |
| **Average Lead Time** | 13.5 months | ✅ Optimal |
| **Avg 12m Return After Signal** | 18.6% | ⚠️ Blow-off Top Pattern |
| **Total Signals Generated** | 8 | - |
| **Recessions Analyzed** | 6 | - |
| **Recessions Caught** | 4 | - |

---

## Recession Prediction Performance

### Summary Statistics

- **Hit Rate**: 66.7% (4 of 6 recessions predicted)
- **Average Lead Time**: 13.5 months
- **Lead Time Range**: 4 to 30 months

### Recession-by-Recession Analysis

| Recession | Start Date | Signal? | Lead Time | Assessment |
|-----------|------------|---------|-----------|------------|
| 1980 | 1980-02 | ❌ No | N/A | Missed |
| 1981-82 | 1981-08 | ❌ No | N/A | Missed |
| 1990-91 | 1990-08 | ✅ Yes | 4mo | Late warning |
| 2001 | 2001-04 | ✅ Yes | 30mo | Very early |
| 2008-09 | 2008-01 | ✅ Yes | 14mo | Good timing |
| 2020 | 2020-03 | ✅ Yes | 6mo | Good timing |

### False Positive Analysis

**False Positive Rate**: 62.5% (5 of 8 signals)

**Assessment**: ⚠️ **Acceptable precision** - False positive rate is moderate. Use in combination with other models for confirmation.

---

## Market Performance After Signals

### Average Returns Post-Signal

| Time Horizon | Average Return | Min | Max |
|--------------|----------------|-----|-----|
| **6 Months** | 8.0% | -9.8% | 25.4% |
| **12 Months** | 18.6% | 9.5% | 45.4% |
| **24 Months** | 34.3% | -32.3% | 66.8% |

### Drawdown Analysis

- **Average Max Drawdown**: -13.4%
- **Worst Drawdown**: -38.9%
- **Average Time to Bottom**: 6.2 months

### Blow-off Top Analysis

**Blow-off Tops Detected**: 8 out of 8 signals (100.0%)

⚠️ **High Blow-off Top Rate**: Markets rallied **46.0% on average** in the **20.7 months** after this model signaled TROUBLE before eventually declining.

**Implication**: Recession signals from this model do NOT mean immediate market crash. Expect a rally first, then gradual decline.

**Trading Strategy**: 
- Don't short immediately when signal triggers
- Consider selling rallies into strength
- Use options strategies (sell calls, buy puts with 6-12mo expiry)
- Reduce equity exposure gradually, not all at once

---

## Signal Characteristics

**Total Observations**: 794  
**TROUBLE Periods**: 172 (21.7% of time)  
**WARNING Periods**: 197  
**CLEAR Periods**: 163

---

## Key Findings & Recommendations

### ⭐ Top Performer

This model ranks in the **top 3** of all tested models. 

### Strength: High Hit Rate

- ✅ Captures majority of recessions
- ✅ Reliable for recession forecasting
- ✅ Good for strategic asset allocation

### Recommended Use Cases

- **Secondary Confirmation**: Use to confirm signals from other models
- **Tactical Trading**: Suitable for near-term positioning

### Limitations

- ⚠️ Very high blow-off top rate (100%) - signals don't mean immediate market crashes

---

**Report Generated**: 2026-02-18 03:02:59  
**Data Source**: Path B Prediction Analysis Framework  
**For questions or refinements**: See `docs/analysis/`
