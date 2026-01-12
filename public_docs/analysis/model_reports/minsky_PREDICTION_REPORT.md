# MINSKY - Prediction Analysis Report

**Generated**: 2026-01-11 11:25  
**Analysis Period**: 1986-01-01 00:00:00 to 2025-04-01 00:00:00  
**Data Coverage**: 39.2 years

---

## Executive Summary

**Overall Performance Rank**: #4 out of 9 models  
**Overall Score**: 25.1/100

### Key Metrics at a Glance

| Metric | Value | Assessment |
|--------|-------|------------|
| **Hit Rate** | 50.0% | ⚠️ Good |
| **False Positive Rate** | 62.5% | ⚠️ Acceptable |
| **Average Lead Time** | 7.0 months | ⚠️ Acceptable |
| **Avg 12m Return After Signal** | 11.1% | ⚠️ Blow-off Top Pattern |
| **Total Signals Generated** | 8 | - |
| **Recessions Analyzed** | 4 | - |
| **Recessions Caught** | 2 | - |

---

## Recession Prediction Performance

### Summary Statistics

- **Hit Rate**: 50.0% (2 of 4 recessions predicted)
- **Average Lead Time**: 7.0 months
- **Lead Time Range**: 2 to 12 months

### Recession-by-Recession Analysis

| Recession | Start Date | Signal? | Lead Time | Assessment |
|-----------|------------|---------|-----------|------------|
| 1990-91 | 1990-08 | ❌ No | N/A | Missed |
| 2001 | 2001-04 | ❌ No | N/A | Missed |
| 2008-09 | 2008-01 | ✅ Yes | 12mo | Good timing |
| 2020 | 2020-03 | ✅ Yes | 2mo | Late warning |

### False Positive Analysis

**False Positive Rate**: 62.5% (5 of 8 signals)

**Assessment**: ⚠️ **Acceptable precision** - False positive rate is moderate. Use in combination with other models for confirmation.

---

## Market Performance After Signals

### Average Returns Post-Signal

| Time Horizon | Average Return | Min | Max |
|--------------|----------------|-----|-----|
| **6 Months** | 6.9% | -6.3% | 25.8% |
| **12 Months** | 11.1% | -0.3% | 29.9% |
| **24 Months** | 12.4% | -39.1% | 47.7% |

### Drawdown Analysis

- **Average Max Drawdown**: -14.7%
- **Worst Drawdown**: -47.3%
- **Average Time to Bottom**: 6.6 months

### Blow-off Top Analysis

**Blow-off Tops Detected**: 8 out of 8 signals (100.0%)

⚠️ **High Blow-off Top Rate**: Markets rallied **28.9% on average** in the **17.2 months** after this model signaled TROUBLE before eventually declining.

**Implication**: Recession signals from this model do NOT mean immediate market crash. Expect a rally first, then gradual decline.

**Trading Strategy**: 
- Don't short immediately when signal triggers
- Consider selling rallies into strength
- Use options strategies (sell calls, buy puts with 6-12mo expiry)
- Reduce equity exposure gradually, not all at once

---

## Signal Characteristics

**Total Observations**: 158  
**TROUBLE Periods**: 99 (62.7% of time)  
**WARNING Periods**: 30  
**CLEAR Periods**: 25

---

## Key Findings & Recommendations

### Strength: Actionable Lead Time

- ✅ Short lead time means timely signals
- ✅ Less risk of "too early" positioning
- ✅ Better for tactical trading

### Recommended Use Cases

- **Secondary Confirmation**: Use to confirm signals from other models
- **Tactical Trading**: Suitable for near-term positioning

### Limitations

- ⚠️ Very high blow-off top rate (100%) - signals don't mean immediate market crashes

---

**Report Generated**: 2026-01-11 11:25:27  
**Data Source**: Path B Prediction Analysis Framework  
**For questions or refinements**: See `docs/analysis/`
