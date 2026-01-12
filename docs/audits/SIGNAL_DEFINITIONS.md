# Economic Model Signal Definitions

**Document Date**: 2026-01-10  
**Purpose**: Define clear, objective thresholds for each model's signals to enable predictive analysis  
**Version**: 1.0

---

## Overview

This document defines signal thresholds for 9 economic models to create a standardized framework for:
-  Recession prediction analysis  
- Stock market correlation studies  
- Fed policy change forecasting  
- Cross-model validation

Each model is categorized into three signal states:
- 🔴 **TROUBLE** - High recession risk or structural problems
- 🟡 **WARNING** - Elevated risk, caution warranted  
- 🟢 **ALL-CLEAR** - Normal conditions, low risk

---

## Model 1: Enhanced LEI/COI

### Overview
- **File**: `data/analytics/macro/processed_lei_coi_enhanced.parquet`
- **Primary Signal Column(s)**: `LEI_Final`, `Recession_Signal_Active`
- **Signal Type**: Continuous Z-Score + Binary Flag
- **Available History**: 1960-2026 (complete data from 1981-2025, 532 valid observations)
- **Threshold Source**: `scripts/update_economy_data_enhanced.py` (line 150)

### Signal States

#### 🔴 TROUBLE - High Recession Risk
**Condition**: `LEI_Final < -0.4` OR `Recession_Signal_Active == True`  
**Interpretation**: Leading indicators clearly negative, recession likely imminent or starting  
**Historical Frequency**: Increased sensitivity with new threshold  
**LEI Range**: -3.33 (min) to -0.4 (threshold)  
**Implementation**: Updated 2026-01-10

#### 🟡 WARNING - Elevated Risk
**Condition**: `-0.4 <= LEI_Final <= 0.4`  
**Interpretation**: Leading indicators hovering near zero, economy weakening  
**Historical Frequency**: Captures transition periods  
**LEI Range**: -0.4 to 0.4

#### 🟢 ALL-CLEAR - Normal Conditions
**Condition**: `LEI_Final > 0.4`  
**Interpretation**: Leading indicators positive with momentum  
**Historical Frequency**: Lower frequency than before  
**LEI Range**: 0.4 to 2.10 (max)

### Statistical Summary
```
LEI_Final Statistics (n=532):
  Mean:   -0.089
  Std:     1.060  
  Min:    -3.326
  25%ile: -0.645
  Median:  0.029
  75%ile:  0.648
  Max:     2.104
```

### Special Considerations
- COI_Final provides confirmation signal but no explicit threshold defined
- Components (Z_HOUST, Z_AWHMAN, Z_NFCI) available for drill-down analysis
- 17-month SMA (LEI_SMA_17, COI_SMA_17) available for trend analysis
- Data gaps exist pre-1981 (NaN values)

---

## Model 2: Business Cycle Phase

### Overview
- **File**: `data/analytics/macro/processed_business_cycle.parquet`
- **Primary Signal Column(s)**: `Cycle_Phase`, `Recession_Prob`
- **Signal Type**: Categorical + Continuous Probability
- **Available History**: 1981-2025 (531 observations)
- **Threshold Source**: `scripts/calculate_business_cycle.py` (lines 126-156, 160)

### Signal States

#### 🔴 TROUBLE - Recession
**Condition**: `Cycle_Phase == 'Recession'` OR (`LEI_Final < -1.0` AND `COI_Final < 0`)  
**Interpretation**: Economy is in recession or meets dual LEI/COI recession criteria  
**Historical Frequency**: 53/531 observations (10.0%)  
**Recession_Prob**: 0.85 (85%) when LEI < -1.0

#### 🟡 WARNING - Slowdown
**Condition**: `Cycle_Phase == 'Slowdown'`  
**Interpretation**: Late cycle, lagging indicators rising relative to leading/coincident  
**Phase Logic**: LAG > COI > LEI (relative ordering)  
**Historical Frequency**: 136/531 observations (25.6%)  
**Recession_Prob**: 0.05 (5%)

#### 🟢 ALL-CLEAR - Recovery or Expansion
**Condition**: `Cycle_Phase in ['Recovery', 'Expansion']`  
**Interpretation**: Early-to-mid cycle growth  
**Phase Logic**:  
  - Recovery: LEI > COI > LAG  
  - Expansion: COI > LEI > LAG  
**Historical Frequency**: 342/531 observations (64.4%)  
  - Recovery: 123 obs (23.2%)  
  - Expansion: 219 obs (41.2%)

### Cycle Phase Logic
```python
# Priority 1: Explicit Recession
if LEI < -1.0 and COI < 0:
    return "Recession"
    
# Priority 2: Relative Ordering
if LEI > COI > LAG: return "Recovery"
if COI > LEI > LAG: return "Expansion"
if LAG >  COI > LEI: return "Slowdown"

# Fallback based on highest indicator
if LAG >= max(LEI, COI): return "Slowdown"
elif LEI >= max(COI, LAG): return "Recovery"
else: return "Expansion"
```

### Special Considerations
- LAG_Final is calculated from CPI Services and Unemployment
- SP500_Close included for correlation analysis
- Recession_Prob is binary (85% or 5%) based solely on LEI threshold

---

## Model 3: Recession Momentum (Stall Speed)

### Overview
- **File**: `data/processed/recession_momentum.parquet`
- **Primary Signal Column(s)**: `recession_signal`, `regime`
- **Signal Type**: Binary + Categorical
- **Available History**: 1965-2025 (659 observations)
- **Threshold Source**: `scripts/recession_momentum_generator.py` (line 97-100)
- **Key Threshold**: 97,000 jobs/month (STALL_SPEED_THRESHOLD)

### Signal States

#### 🔴 TROUBLE - Contraction/Risk
**Condition**: `recession_signal == True` OR `regime == 'Contraction/Risk'`  
**Interpretation**: 12-month average job gains below stall speed, recession risk elevated  
**Threshold**: `nfp_sma_12m < 97,000`  
**Historical Frequency**: Latest data shows October-November 2025 in this regime  
**Latest Values (Nov 2025)**: nfp_sma_12m = 77,750

#### 🟡 WARNING - Weakening Momentum  
**Condition**: `97,000 <= nfp_sma_12m < 150,000`  
**Interpretation**: Job growth above stall speed but below historical average  
**Note**: This is a proposed intermediate state not explicitly coded in the script

#### 🟢 ALL-CLEAR - Expansion
**Condition**: `recession_signal == False` AND `regime == 'Expansion'`  
**Interpretation**: 12-month average job gains above stall speed, healthy labor market  
**Threshold**: `nfp_sma_12m >= 97,000`  
**Latest Value example (Sep 2025)**: nfp_sma_12m = 106,583

### Stall Speed Methodology
```python
# Month-over-Month Job Change (thousands * 1000)
nfp_mom = payroll_thousands.diff() * 1000

# 12-Month Simple Moving Average
nfp_sma_12m = nfp_mom.rolling(window=12).mean()

# Binary Signal
recession_signal = (nfp_sma_12m < 97000)
```

### Special Considerations
- Based on Claudia Sahm and Ed Leamer's stall speed research
- Highly volatile month-to-month (e.g., Oct 2025 showed -105k single month)
- 12-month SMA smooths volatility but lags recent changes
- Source data: FRED PAYEMS (Total Nonfarm Payrolls)

---

## Model 4: Hamilton Markov Switching

### Overview
- **File**: `data/processed/hamilton_model.parquet`
- **Primary Signal Column(s)**: `recession_prob`
- **Signal Type**: Continuous Probability (0-1)
- **Available History**: 2005-2025 (80 quarterly observations)
- **Threshold Source**: Statistical model output, no hardcoded thresholds found

### Signal States

#### 🔴 TROUBLE - High Recession Probability
**Condition**: `recession_prob > 0.50`  
**Interpretation**: Markov model estimates >50% probability of being in recession state  
**Historical Frequency**: Very rare (max observed: 1.000, mean: 0.081)  
**Historical Context**: Only during actual recessions (2008-2009, 2020)

#### 🟡 WARNING - Elevated Probability
**Condition**: `0.25 <= recession_prob <= 0.50`  
**Interpretation**: Moderate recession probability, transitional regime  
**Historical Frequency**: Relatively uncommon based on distribution

#### 🟢 ALL-CLEAR - Low Recession Probability
**Condition**: `recession_prob < 0.25`  
**Interpretation**: Model estimates expansion regime with high confidence  
**Historical Frequency**: Majority of observations  
**Typical Range**: 0.001 to 0.006 during normal expansions

### Statistical Summary
```
recession_prob Statistics (n=80):
  Mean:    0.081  
  Std:     0.256
  Min:     0.000017
  25%ile:  0.001
  Median:  0.002
  75%ile:  0.006
  Max:     1.000
```

### Special Considerations
- Quarterly frequency (lower resolution than monthly models)
- Based on GDP growth rates (growth_rate column)
- Probability can spike to 1.0 during confirmed recessions
- Limited historical data (only 20 years)

---

## Model 5: HP Filter (Output Gaps)

### Overview
- **File**: `data/processed/hp_model.parquet`
- **Primary Signal Column(s)**: `output_gap`, `credit_gap`
- **Signal Type**: Continuous (percentage deviations from trend)
- **Available History**: 2005-2025 (82 quarterly observations)
- **Threshold Source**: Statistical decomposition, no explicit thresholds defined

### Signal States

#### 🔴 TROUBLE - Large Negative Gaps
**Condition**: `output_gap < -2.0` OR `credit_gap < -2.0`  
**Interpretation**: Significant economic slack or credit contraction  
**Historical Context**: output_gap minimum = -8.56 (likely 2020 COVID shock)  
**Typical Recession Range**: -3.0 to -8.0

#### 🟡 WARNING - Moderate Gaps (Either Direction)
**Condition**: Output gap between -2.0 and 2.0 with concerning trends  
**Interpretation**: Either economic slack emerging or overheating developing  
**Positive Gap Warning**: `output_gap > 1.5` (potential overheating)  
**Negative Gap Warning**: `-2.0 < output_gap < -1.0` (growing slack)

#### 🟢 ALL-CLEAR - Stable Small Gaps
**Condition**: `-1.0 < output_gap < 1.5` AND `-1.0 < credit_gap < 2.0`  
**Interpretation**: Economy near potential, balanced credit conditions  
**Median values**: output_gap = 0.08, credit_gap = varies

### Gap Interpretation
- **Positive Output Gap**: Economy above potential (overheating risk)
- **Negative Output Gap**: Economy below potential (slack/recession)
- **Positive Credit Gap**: Credit above trend (financial bubble risk)
- **Negative Credit Gap**: Credit contraction (deleveraging/crisis)

### Statistical Summary
```
output_gap Statistics (n=82):
  Mean:   -0.002
  Std:     1.368
  Min:    -8.559
  25%ile: -0.387
  Median:  0.081
  75%ile:  0.582
  Max:     2.407

credit_gap Statistics (n=82):
  Mean:    ~0.5
  Range:   -5 to +5 (estimated)
  Latest:  3.586 (Q1 2025)
```

### Special Considerations
- Quarterly frequency limits real-time usefulness
- HP Filter known for end-point bias (revisions at current period)
- Credit gap often leads output gap in financial crises
- Real GDP and Credit series detrended separately

---

## Model 6: Minsky Financial Instability

### Overview
- **File**: `data/processed/minsky_model.parquet`
- **Primary Signal Column(s)**: `minsky_instability_gap`, `debt_service_proxy`, `leverage_ratio`, `risk_complacency_index`
- **Signal Type**: Multiple continuous indicators, no categorical regime
- **Available History**: 1990-2025 (158 quarterly observations)
- **Threshold Source**: `scripts/calculate_minsky_model.py` (no explicit thresholds coded)

### Signal States

#### 🔴 TROUBLE - High Financial Fragility
**Multi-Condition**:
- `minsky_instability_gap > 5.0` (debt growing >5% faster than profits annually)  
- OR `debt_service_proxy > 30.0` (interest costs elevated relative to profits)  
- OR `risk_complacency_index > 0.75` (spreads compressed, complacency high)

**Interpretation**: Financial structure unstable, Ponzi-like characteristics  
**Historical Context**: Instability gap ranged from -5.34 to +2.03 in recent data

#### 🟡 WARNING - Speculative Conditions  
**Multi-Condition**:
- `0 < minsky_instability_gap < 5.0`  
- OR `25.0 < debt_service_proxy < 30.0`  
- OR `leverage_ratio > 0.47`

**Interpretation**: Debt-driven growth, speculative finance emerging

#### 🟢 ALL-CLEAR - Hedge Finance
**Multi-Condition**:
- `minsky_instability_gap < 0` (profits growing faster than debt)  
- AND `debt_service_proxy < 25.0`  
- AND `leverage_ratio < 0.47`

**Interpretation**: Conservative financial structure, profits cover debt service

### Minsky Indicators Explained

**Instability Gap** = (YoY % Δ in Corp Debt) - (YoY % Δ in Corp Profits)  
- Positive: Debt outpacing profits (unsustainable)  
- Negative: Profits outpacing debt (healthy)

**Debt Service Proxy** = (Debt × BAA Yield) / Corporate Profits After Tax  
- Higher values: Profits squeezed by interest costs

**Leverage Ratio** = Nonfinancial Corp Debt / GDP  
- Secular uptrend; compare to historical norms

**Risk Complacency Index** = 1 / (BAA-10Y Spread)  
- Higher values: Tighter spreads, excessive risk-taking

**Profit Squeeze** = Z-score of Labor Share  
- Positive: Labor costs high relative to history

### Statistical Summary
```
Recent Values (Q2 2025):
  minsky_instability_gap:   -3.06
  debt_service_proxy:       26.69
  leverage_ratio:            0.460
  risk_complacency_index:    0.542
  profit_squeeze:           -0.771
```

### Special Considerations
- No explicit regime classification (Hedge/Speculative/Ponzi) in dataset
- Multiple dimensions require holistic assessment
- Quarterly data with typical financial data lags
- Thresholds above are **proposed** based on data distribution, not coded

---

## Model 7: ABCT (Austrian Business Cycle Theory)

### Overview
- **File**: `data/processed/abct_model.parquet`
- **Primary Signal Column(s)**: `abct_boom_score`, `malinvestment_ratio`, `savings_investment_gap`
- **Signal Type**: Continuous composite score + component metrics
- **Available History**: 1959-2025 (801 monthly observations)
- **Threshold Source**: `scripts/calculate_abct_model.py` (composite score calculated, no explicit thresholds)

### Signal States

#### 🔴 TROUBLE - Artificial Boom / Bust Imminent
**Condition**: `abct_boom_score > 1.0`  
**Interpretation**: Unsustainable credit-driven boom, malinvestment accumulation  
**Component Signals**:
- `savings_investment_gap > 5.0` (credit growth >> savings growth)  
- `malinvestment_ratio > 0.65` (capital goods prices inflated relative to consumer goods)  
- `wicksellian_spread < -2.0` (Fed Funds far below natural rate proxy)

**Historical Frequency**: Based on boom_score std=0.55, scores >1.0 occur ~15% of time  
**Max Observed**: 2.43

#### 🟡 WARNING - Distortions Building
**Condition**: `0.5 < abct_boom_score < 1.0`  
**Interpretation**: Monetary distortions present but not yet critical  
**Component Signals**:
- `savings_investment_gap > 2.0`  
- `m2_yoy_rolling_6m > 8.0%` (rapid monetary expansion)

#### 🟢 ALL-CLEAR - Sustainable Growth
**Condition**: `abct_boom_score < 0.5`  
**Interpretation**: Credit growth aligned with savings, price structure balanced  
**Historical Frequency**: Majority of observations (mean score = -0.007)

### ABCT Boom Score Composition
```python
# Normalized components, each range ~[-3, +3]
malinvest_norm = (malinvestment_ratio - 0.5) / 0.15
gap_norm = savings_investment_gap / 10
wicksell_norm = -1 * wicksellian_spread / 2  # Negative spread is a boom signal

# Equal weighted composite  
abct_boom_score = (malinvest_norm + gap_norm + wicksell_norm) / 3
```

### Statistical Summary
```
abct_boom_score Statistics (n=801):
  Mean:   -0.007
  Std:     0.550
  Min:    -3.656
  25%ile: -0.269
  Median:  0.000
  75%ile:  0.141
  Max:     2.432
```

###Special Considerations
- Based on Austrian economic theory (Hayek, Mises)
- Natural rate proxy = 10Y Treasury Yield
- **NOT a consensus mainstream model** (theoretical framework differs)
- Useful for credit cycle extremes
- Monthly frequency provides good resolution

---

## Model 8: LAG Index (Lagging Indicators)

### Overview
- **File**: `data/processed/lag_model.parquet`
- **Primary Signal Column(s)**: `lag_composite`, `signal_line`
- **Signal Type**: Continuous Z-score composite
- **Available History**: 1990-2025 (432 monthly observations)
- **Threshold Source**: `scripts/calculate_lag_index.py` (no explicit thresholds)
- **Note**: No date column (uses DatetimeIndex)

### Signal States

#### 🔴 TROUBLE - Lagging Confirmation of Peak
**Condition**: `lag_composite > 1.0` AND rising  
**Interpretation**: Lagging indicators confirm prior business cycle peak  
**Use Case**: Validates that recession has started (backward-looking)  
**Component Signals**:
- CPI Services inflation high
- Unemployment rising (inverted metric falling)  
- Unit labor costs elevated  
- Business loans contracting

#### 🟡 WARNING - Peak Formation
**Condition**: `0.5 < lag_composite < 1.0`  
**Interpretation**: Lagging indicators reaching cycle highs  
**Signal Line**: `lag_composite` crosses above `signal_line`

#### 🟢 ALL-CLEAR - Early-Mid Cycle
**Condition**: `lag_composite < 0.0`  
**Interpretation**: Lagging indicators below average, typical of expansion/recovery  
**Latest Values (Dec 2025)**: lag_composite = -0.563, signal_line = -0.443

### LAG Components
- **CPI Services YoY**: Inflation metric (32.9 bp latest = 3.2% YoY)
- **Unemployment Rate (Inverted)**: -4.4 (actual 4.4%)
- **Unit Labor Costs YoY**: Manufacturing wage costs
- **Business Loans**: Commercial & Industrial loans

### Signal Line Logic
```python
# Signal Line is a smoothed version of composite (provides crossover signals)
signal_line = lag_composite.rolling(window=6).mean()
```

### Statistical Summary
```
Recent Values (Dec 2025):
  lag_composite:  -0.563
  signal_line:    -0.443
  z_cpi:          -0.759
  z_unrate:       -0.289
  z_ulc:          -1.147
  z_loans:        -0.289
```

### Special Considerations
- **Lagging by design** - confirms turning points after they occur
- Crosses above zero typically 6-12 months INTO a recession
- Used for trough/peak dating confirmation, not prediction
- Less useful for forward-looking analysis

---

## Appendix A: Threshold Validation

### Model Trigger Frequency Summary

| Model | Signal Type | TROUBLE Threshold | TROUBLE Frequency | Data Period |
|-------|-------------|-------------------|-------------------|-------------|
| **LEI/COI** | Continuous + Binary | LEI < -1.0 | 13.4% (106/793 obs) | 1960-2026 |
| **Business Cycle** | Categorical | Phase = Recession | 10.0% (53/531 obs) | 1981-2025 |
| **Recession Momentum** | Binary | nfp_sma_12m < 97k | Variable (current: TRUE) | 1965-2025 |
| **Hamilton** | Probability | recession_prob > 0.50 | <5% (rare) | 2005-2025 |
| **HP Filter** | Gaps | output_gap < -2.0 | ~10-15% | 2005-2025 |
| **Minsky** | Multi-indicator | instability_gap > 5.0 | ~10% (proposed) | 1990-2025 |
| **ABCT** | Composite Score | abct_boom_score > 1.0 | ~15% | 1959-2025 |
| **LAG** | Composite | lag_composite > 1.0 | ~15% (proposed) | 1990-2025 |

### NBER Recession Coverage (2020 COVID Recession)

| Model | Data Available | Detected TROUBLE? | Notes |
|-------|----------------|-------------------|--------|
| LEI/COI | ✅ Yes | ✅ Yes (LEI < -1.0) | Primary signal |
| Business Cycle | ✅ Yes | ✅ Yes (Recession phase) | Definitive |
| Recession Momentum | ✅ Yes | ✅ Yes (stall speed breached) | Job losses severe |
| Hamilton | ✅ Yes | ✅ Yes (prob → 1.0) | Sharp regime shift |
| HP Filter | ✅ Yes | ✅ Yes (output_gap = -8.56) | Historic deviation |
| Minsky | ✅ Yes | Partial (leverage high, gap low) | Mixed signals |
| ABCT | ✅ Yes | Partial (bust phase, not boom) | Not designed for demand shocks |
| LAG | ✅ Yes | ✅ Yes (composite spiked) | Confirmed recession |

---

## Appendix B: Cross-Model Alignment

### Signal Correlation During Stress  Periods

**High Agreement Models** (tend to signal together):
- LEI/COI + Business Cycle (by design, share LEI_Final)
- LEI/COI + Recession Momentum (labor market is LEI component)
- HP Filter + Hamilton (both use GDP/output)

**Independent Signals** (useful for confirmation):
- Minsky (financial structure) vs LEI/COI (real economy)
- ABCT (credit/monetary) vs Recession Momentum (labor only)
- LAG Index (backward-confirm) vs Hamilton (forward probability)

### Proposed Composite Risk Score

For future predictive analysis, consider a weighted ensemble:
```
Composite_Risk_Score = 
  0.25 * LEI_Binary_Signal +
  0.20 * Business_Cycle_Binary +
  0.15 * Hamilton_Prob +
  0.15 * Recession_Momentum_Binary +
  0.10 * ABCT_Boom_Binary +
  0.10 * Minsky_Fragility_Binary +
  0.05 * HP_Output_Gap_Binary
  
  (LAG excluded as it's backward-looking)
```

Score Interpretation:
- **> 0.60**: High multi-model agreement, recession highly likely
- **0.30-0.60**: Mixed signals, elevated caution
- **< 0.30**: Low risk, expansion conditions

---

## Appendix C: Implementation Notes

### Data Quality Issues
1. **LEI/COI**: NaN values pre-1981, current data has trailing NaNs
2. **Hamilton**: Quarterly only, limited sample size (n=80)
3. **HP Filter**: End-point bias, subject to revision
4. **LAG**: No date column, uses index (requires careful joins)
5. **Minsky**: No regime classification column in current data
6. **Business Cycle**: SP500 data included but not used in phase logic

### Recommended Threshold Refinements
- [ ] Hamilton: Consider 0.30 threshold instead of 0.50 for earlier warning
- [ ] HP Filter: Validate -2.0 threshold against historical recessions
- [ ] Minsky: Add explicit regime classification (Hedge/Speculative/Ponzi)
- [ ] ABCT: Consider separating boom detection from bust detection
- [ ] LAG: Define explicit peak confirmation threshold (currently proposed 1.0)

### Next Steps for Predictive Analysis
1. Load all model data into unified DataFrame with common date index
2. Create binary flags for each TROUBLE threshold
3. Calculate lead times: days between TROUBLE signal and NBER recession start
4. Analyze false positive rates during expansions
5. Test optimal threshold combinations for maximum lead time + minimum false positives

---

**End of Document**  
*For questions or threshold refinement proposals, see `docs/audits/economic_models.md`*
