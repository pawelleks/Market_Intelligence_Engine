# MINSKY - Prediction Analysis Report

**Generated**: 2026-02-22 03:02  
**Analysis Period**: 1986-01-01 00:00:00 to 2025-07-01 00:00:00  
**Data Coverage**: 39.5 years

---

## Executive Summary

**Overall Performance Rank**: #8 out of 9 models  
**Overall Score**: 0.0/100

### Key Metrics at a Glance

| Metric | Value | Assessment |
|--------|-------|------------|
| **Hit Rate** | nan% | ❌ Poor |
| **False Positive Rate** | 100.0% | ❌ High |
| **Average Lead Time** | nan months | ❌ Too Early |
| **Avg 12m Return After Signal** | 0.4% | ⚠️ Blow-off Top Pattern |
| **Total Signals Generated** | 1 | - |
| **Recessions Analyzed** | 0 | - |
| **Recessions Caught** | 0 | - |

---

## Recession Prediction Performance

### Summary Statistics

- **Hit Rate**: nan% (0 of 0 recessions predicted)
- **Average Lead Time**: nan months
- **Lead Time Range**: 2 to 12 months

### Recession-by-Recession Analysis

| Recession | Start Date | Signal? | Lead Time | Assessment |
|-----------|------------|---------|-----------|------------|
| 1990-91 | 1990-08 | ❌ No | N/A | Missed |
| 2001 | 2001-04 | ❌ No | N/A | Missed |
| 2008-09 | 2008-01 | ✅ Yes | 12mo | Good timing |
| 2020 | 2020-03 | ✅ Yes | 2mo | Late warning |

### False Positive Analysis

**False Positive Rate**: 100.0% (1 of 1 signals)

**Assessment**: ❌ **High false positive rate** - This model triggers frequently without recessions. Best used as an early warning system, not a definitive signal.

---

## Market Performance After Signals

### Average Returns Post-Signal

| Time Horizon | Average Return | Min | Max |
|--------------|----------------|-----|-----|
| **6 Months** | 25.8% | 25.8% | 25.8% |
| **12 Months** | 0.4% | 0.4% | 0.4% |
| **24 Months** | 13.6% | 13.6% | 13.6% |

### Drawdown Analysis

- **Average Max Drawdown**: -8.5%
- **Worst Drawdown**: -8.5%
- **Average Time to Bottom**: 11.1 months

### Blow-off Top Analysis

**Blow-off Tops Detected**: 1 out of 1 signals (100.0%)

⚠️ **High Blow-off Top Rate**: Markets rallied **37.6% on average** in the **7.8 months** after this model signaled TROUBLE before eventually declining.

**Implication**: Recession signals from this model do NOT mean immediate market crash. Expect a rally first, then gradual decline.

**Trading Strategy**: 
- Don't short immediately when signal triggers
- Consider selling rallies into strength
- Use options strategies (sell calls, buy puts with 6-12mo expiry)
- Reduce equity exposure gradually, not all at once

---

## Signal Characteristics

**Total Observations**: 159  
**TROUBLE Periods**: 155 (97.5% of time)  
**WARNING Periods**: 0  
**CLEAR Periods**: 0

---

## Key Findings & Recommendations

### Recommended Use Cases

- **Supporting Indicator**: Use as part of a broader ensemble
- **Tactical Trading**: Suitable for near-term positioning

### Limitations

- ⚠️ High false positive rate (100%) - many signals don't lead to recessions
- ⚠️ Very high blow-off top rate (100%) - signals don't mean immediate market crashes

---

**Report Generated**: 2026-02-22 03:02:35  
**Data Source**: Path B Prediction Analysis Framework  
**For questions or refinements**: See `docs/analysis/`
