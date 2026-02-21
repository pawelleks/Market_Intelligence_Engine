# LAG - Prediction Analysis Report

**Generated**: 2026-02-21 16:30  
**Analysis Period**: 1960-01-01 00:00:00 to 2026-01-01 00:00:00  
**Data Coverage**: 66.0 years

---

## Executive Summary

**Overall Performance Rank**: #4 out of 9 models  
**Overall Score**: 28.1/100

### Key Metrics at a Glance

| Metric | Value | Assessment |
|--------|-------|------------|
| **Hit Rate** | 62.5% | ✅ Excellent |
| **False Positive Rate** | 55.6% | ⚠️ Acceptable |
| **Average Lead Time** | 15.2 months | ⚠️ Acceptable |
| **Avg 12m Return After Signal** | 3.2% | ⚠️ Blow-off Top Pattern |
| **Total Signals Generated** | 9 | - |
| **Recessions Analyzed** | 8 | - |
| **Recessions Caught** | 5 | - |

---

## Recession Prediction Performance

### Summary Statistics

- **Hit Rate**: 62.5% (5 of 8 recessions predicted)
- **Average Lead Time**: 15.2 months
- **Lead Time Range**: 7 to 27 months

### Recession-by-Recession Analysis

| Recession | Start Date | Signal? | Lead Time | Assessment |
|-----------|------------|---------|-----------|------------|
| 1970 | 1970-01 | ❌ No | N/A | Missed |
| 1973-75 | 1973-12 | ✅ Yes | 7mo | Good timing |
| 1980 | 1980-02 | ✅ Yes | 9mo | Good timing |
| 1981-82 | 1981-08 | ✅ Yes | 27mo | Very early |
| 1990-91 | 1990-08 | ❌ No | N/A | Missed |
| 2001 | 2001-04 | ✅ Yes | 9mo | Good timing |
| 2008-09 | 2008-01 | ✅ Yes | 24mo | Very early |
| 2020 | 2020-03 | ❌ No | N/A | Missed |

### False Positive Analysis

**False Positive Rate**: 55.6% (5 of 9 signals)

**Assessment**: ⚠️ **Acceptable precision** - False positive rate is moderate. Use in combination with other models for confirmation.

---

## Market Performance After Signals

### Average Returns Post-Signal

| Time Horizon | Average Return | Min | Max |
|--------------|----------------|-----|-----|
| **6 Months** | -2.0% | -42.6% | 20.5% |
| **12 Months** | 3.2% | -19.6% | 32.7% |
| **24 Months** | 10.1% | -34.9% | 55.7% |

### Drawdown Analysis

- **Average Max Drawdown**: -16.0%
- **Worst Drawdown**: -47.2%
- **Average Time to Bottom**: 8.1 months

### Blow-off Top Analysis

**Blow-off Tops Detected**: 6 out of 9 signals (66.7%)

⚠️ **Moderate Blow-off Top Risk**: About half of signals were followed by market rallies before eventual declines.

**Implication**: Mixed behavior - some signals led to immediate declines, others had blow-off tops.

**Trading Strategy**: Monitor other models for confirmation before taking action.

---

## Signal Characteristics

**Total Observations**: 793  
**TROUBLE Periods**: 97 (12.2% of time)  
**WARNING Periods**: 130  
**CLEAR Periods**: 560

---

## Key Findings & Recommendations

### Strength: High Hit Rate

- ✅ Captures majority of recessions
- ✅ Reliable for recession forecasting
- ✅ Good for strategic asset allocation

### Recommended Use Cases

- **Secondary Confirmation**: Use to confirm signals from other models
- **Strategic Planning**: Good for long-term portfolio allocation
- **Risk Management**: Trigger defensive actions when signal activates

### Limitations


---

**Report Generated**: 2026-02-21 16:30:46  
**Data Source**: Path B Prediction Analysis Framework  
**For questions or refinements**: See `docs/analysis/`
