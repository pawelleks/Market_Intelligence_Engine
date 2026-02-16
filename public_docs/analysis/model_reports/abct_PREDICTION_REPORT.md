# ABCT - Prediction Analysis Report

**Generated**: 2026-02-16 08:29  
**Analysis Period**: 1970-01-01 00:00:00 to 2025-11-01 00:00:00  
**Data Coverage**: 55.8 years

---

## Executive Summary

**Overall Performance Rank**: #8 out of 9 models  
**Overall Score**: 0.0/100

### Key Metrics at a Glance

| Metric | Value | Assessment |
|--------|-------|------------|
| **Hit Rate** | 0.0% | ❌ Poor |
| **False Positive Rate** | 100.0% | ❌ High |
| **Average Lead Time** | nan months | ❌ Too Early |
| **Avg 12m Return After Signal** | 12.4% | ⚠️ Blow-off Top Pattern |
| **Total Signals Generated** | 2 | - |
| **Recessions Analyzed** | 7 | - |
| **Recessions Caught** | 0 | - |

---

## Recession Prediction Performance

### Summary Statistics

- **Hit Rate**: 0.0% (0 of 7 recessions predicted)
- **Average Lead Time**: nan months
- **Lead Time Range**: nan to nan months

### Recession-by-Recession Analysis

| Recession | Start Date | Signal? | Lead Time | Assessment |
|-----------|------------|---------|-----------|------------|
| 1973-75 | 1973-12 | ❌ No | N/A | Missed |
| 1980 | 1980-02 | ❌ No | N/A | Missed |
| 1981-82 | 1981-08 | ❌ No | N/A | Missed |
| 1990-91 | 1990-08 | ❌ No | N/A | Missed |
| 2001 | 2001-04 | ❌ No | N/A | Missed |
| 2008-09 | 2008-01 | ❌ No | N/A | Missed |
| 2020 | 2020-03 | ❌ No | N/A | Missed |

### False Positive Analysis

**False Positive Rate**: 100.0% (2 of 2 signals)

**Assessment**: ❌ **High false positive rate** - This model triggers frequently without recessions. Best used as an early warning system, not a definitive signal.

---

## Market Performance After Signals

### Average Returns Post-Signal

| Time Horizon | Average Return | Min | Max |
|--------------|----------------|-----|-----|
| **6 Months** | 2.5% | -6.9% | 11.9% |
| **12 Months** | 12.4% | 9.6% | 15.2% |
| **24 Months** | 15.0% | 1.4% | 28.6% |

### Drawdown Analysis

- **Average Max Drawdown**: -16.5%
- **Worst Drawdown**: -23.1%
- **Average Time to Bottom**: 10.2 months

### Blow-off Top Analysis

**Blow-off Tops Detected**: 2 out of 2 signals (100.0%)

⚠️ **High Blow-off Top Rate**: Markets rallied **25.8% on average** in the **16.3 months** after this model signaled TROUBLE before eventually declining.

**Implication**: Recession signals from this model do NOT mean immediate market crash. Expect a rally first, then gradual decline.

**Trading Strategy**: 
- Don't short immediately when signal triggers
- Consider selling rallies into strength
- Use options strategies (sell calls, buy puts with 6-12mo expiry)
- Reduce equity exposure gradually, not all at once

---

## Signal Characteristics

**Total Observations**: 671  
**TROUBLE Periods**: 33 (4.9% of time)  
**WARNING Periods**: 52  
**CLEAR Periods**: 586

---

## Key Findings & Recommendations

### Recommended Use Cases

- **Supporting Indicator**: Use as part of a broader ensemble
- **Tactical Trading**: Suitable for near-term positioning

### Limitations

- ⚠️ Misses 100% of recessions - don't rely on this model alone
- ⚠️ High false positive rate (100%) - many signals don't lead to recessions
- ⚠️ Very high blow-off top rate (100%) - signals don't mean immediate market crashes

---

**Report Generated**: 2026-02-16 08:29:26  
**Data Source**: Path B Prediction Analysis Framework  
**For questions or refinements**: See `docs/analysis/`
