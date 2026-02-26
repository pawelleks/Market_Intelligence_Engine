# HAMILTON - Prediction Analysis Report

**Generated**: 2026-02-26 03:02  
**Analysis Period**: 1970-04-01 00:00:00 to 2025-04-01 00:00:00  
**Data Coverage**: 55.0 years

---

## Executive Summary

**Overall Performance Rank**: #3 out of 9 models  
**Overall Score**: 29.7/100

### Key Metrics at a Glance

| Metric | Value | Assessment |
|--------|-------|------------|
| **Hit Rate** | 50.0% | ⚠️ Good |
| **False Positive Rate** | 50.0% | ✅ Excellent |
| **Average Lead Time** | 9.8 months | ✅ Optimal |
| **Avg 12m Return After Signal** | 2.4% | ⚠️ Blow-off Top Pattern |
| **Total Signals Generated** | 6 | - |
| **Recessions Analyzed** | 8 | - |
| **Recessions Caught** | 4 | - |

---

## Recession Prediction Performance

### Summary Statistics

- **Hit Rate**: 50.0% (4 of 8 recessions predicted)
- **Average Lead Time**: 9.8 months
- **Lead Time Range**: 1 to 19 months

### Recession-by-Recession Analysis

| Recession | Start Date | Signal? | Lead Time | Assessment |
|-----------|------------|---------|-----------|------------|
| 1970 | 1970-01 | ❌ No | N/A | Missed |
| 1973-75 | 1973-12 | ✅ Yes | 14mo | Good timing |
| 1980 | 1980-02 | ✅ Yes | 1mo | Late warning |
| 1981-82 | 1981-08 | ✅ Yes | 19mo | Very early |
| 1990-91 | 1990-08 | ❌ No | N/A | Missed |
| 2001 | 2001-04 | ❌ No | N/A | Missed |
| 2008-09 | 2008-01 | ❌ No | N/A | Missed |
| 2020 | 2020-03 | ✅ Yes | 5mo | Late warning |

### False Positive Analysis

**False Positive Rate**: 50.0% (3 of 6 signals)

**Assessment**: ✅ **Excellent precision** - This model has the lowest false positive rate, making it highly reliable for actionable signals.

---

## Market Performance After Signals

### Average Returns Post-Signal

| Time Horizon | Average Return | Min | Max |
|--------------|----------------|-----|-----|
| **6 Months** | -3.8% | -14.6% | 7.6% |
| **12 Months** | 2.4% | -37.2% | 26.5% |
| **24 Months** | 7.3% | -39.9% | 49.2% |

### Drawdown Analysis

- **Average Max Drawdown**: -25.9%
- **Worst Drawdown**: -49.0%
- **Average Time to Bottom**: 7.9 months

### Blow-off Top Analysis

**Blow-off Tops Detected**: 6 out of 6 signals (100.0%)

⚠️ **High Blow-off Top Rate**: Markets rallied **23.4% on average** in the **13.9 months** after this model signaled TROUBLE before eventually declining.

**Implication**: Recession signals from this model do NOT mean immediate market crash. Expect a rally first, then gradual decline.

**Trading Strategy**: 
- Don't short immediately when signal triggers
- Consider selling rallies into strength
- Use options strategies (sell calls, buy puts with 6-12mo expiry)
- Reduce equity exposure gradually, not all at once

---

## Signal Characteristics

**Total Observations**: 221  
**TROUBLE Periods**: 29 (13.1% of time)  
**WARNING Periods**: 16  
**CLEAR Periods**: 176

---

## Key Findings & Recommendations

### ⭐ Top Performer

This model ranks in the **top 3** of all tested models. 

### Strength: Low False Positive Rate

- ✅ Best used for **high-conviction signals**
- ✅ Suitable for tactical trading and risk reduction
- ✅ When this model signals TROUBLE, take it seriously

### Strength: Actionable Lead Time

- ✅ Short lead time means timely signals
- ✅ Less risk of "too early" positioning
- ✅ Better for tactical trading

### Recommended Use Cases

- **Secondary Confirmation**: Use to confirm signals from other models
- **Tactical Trading**: Suitable for near-term positioning
- **Risk Management**: Trigger defensive actions when signal activates

### Limitations

- ⚠️ Very high blow-off top rate (100%) - signals don't mean immediate market crashes

---

**Report Generated**: 2026-02-26 03:02:36  
**Data Source**: Path B Prediction Analysis Framework  
**For questions or refinements**: See `docs/analysis/`
