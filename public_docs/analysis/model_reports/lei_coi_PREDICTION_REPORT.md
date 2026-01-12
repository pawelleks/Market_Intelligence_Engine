# LEI COI - Prediction Analysis Report

**Generated**: 2026-01-11 11:25  
**Analysis Period**: 1960-01-31 00:00:00 to 2026-01-31 00:00:00  
**Data Coverage**: 66.0 years

---

## Executive Summary

**Overall Performance Rank**: #5 out of 9 models  
**Overall Score**: 22.5/100

### Key Metrics at a Glance

| Metric | Value | Assessment |
|--------|-------|------------|
| **Hit Rate** | 33.3% | ❌ Poor |
| **False Positive Rate** | 83.3% | ❌ High |
| **Average Lead Time** | 18.5 months | ⚠️ Acceptable |
| **Avg 12m Return After Signal** | 18.8% | ⚠️ Blow-off Top Pattern |
| **Total Signals Generated** | 6 | - |
| **Recessions Analyzed** | 6 | - |
| **Recessions Caught** | 2 | - |

---

## Recession Prediction Performance

### Summary Statistics

- **Hit Rate**: 33.3% (2 of 6 recessions predicted)
- **Average Lead Time**: 18.5 months
- **Lead Time Range**: 10 to 27 months

### Recession-by-Recession Analysis

| Recession | Start Date | Signal? | Lead Time | Assessment |
|-----------|------------|---------|-----------|------------|
| 1980 | 1980-02 | ❌ No | N/A | Missed |
| 1981-82 | 1981-08 | ❌ No | N/A | Missed |
| 1990-91 | 1990-08 | ❌ No | N/A | Missed |
| 2001 | 2001-04 | ✅ Yes | 27mo | Very early |
| 2008-09 | 2008-01 | ✅ Yes | 10mo | Good timing |
| 2020 | 2020-03 | ❌ No | N/A | Missed |

### False Positive Analysis

**False Positive Rate**: 83.3% (5 of 6 signals)

**Assessment**: ❌ **High false positive rate** - This model triggers frequently without recessions. Best used as an early warning system, not a definitive signal.

---

## Market Performance After Signals

### Average Returns Post-Signal

| Time Horizon | Average Return | Min | Max |
|--------------|----------------|-----|-----|
| **6 Months** | 6.9% | -5.0% | 18.9% |
| **12 Months** | 18.8% | -5.5% | 40.0% |
| **24 Months** | 24.1% | -46.7% | 60.2% |

### Drawdown Analysis

- **Average Max Drawdown**: -11.3%
- **Worst Drawdown**: -49.3%
- **Average Time to Bottom**: 5.6 months

### Blow-off Top Analysis

**Blow-off Tops Detected**: 6 out of 6 signals (100.0%)

⚠️ **High Blow-off Top Rate**: Markets rallied **42.7% on average** in the **17.9 months** after this model signaled TROUBLE before eventually declining.

**Implication**: Recession signals from this model do NOT mean immediate market crash. Expect a rally first, then gradual decline.

**Trading Strategy**: 
- Don't short immediately when signal triggers
- Consider selling rallies into strength
- Use options strategies (sell calls, buy puts with 6-12mo expiry)
- Reduce equity exposure gradually, not all at once

---

## Signal Characteristics

**Total Observations**: 793  
**TROUBLE Periods**: 106 (13.4% of time)  
**WARNING Periods**: 43  
**CLEAR Periods**: 383

---

## Key Findings & Recommendations

### Recommended Use Cases

- **Supporting Indicator**: Use as part of a broader ensemble
- **Strategic Planning**: Good for long-term portfolio allocation

### Limitations

- ⚠️ Misses 67% of recessions - don't rely on this model alone
- ⚠️ High false positive rate (83%) - many signals don't lead to recessions
- ⚠️ Very high blow-off top rate (100%) - signals don't mean immediate market crashes

---

**Report Generated**: 2026-01-11 11:25:27  
**Data Source**: Path B Prediction Analysis Framework  
**For questions or refinements**: See `docs/analysis/`
