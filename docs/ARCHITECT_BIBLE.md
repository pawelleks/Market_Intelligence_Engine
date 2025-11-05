ARCHITECT_BIBLE — PART 1 (TXT)
SYSTEM PURPOSE & PRINCIPLES

Project Purpose:
Build a scalable, reliable market analysis engine that powers multiple analytics pages (Markov chain, HMM regimes, seasonality, trend detection, breadth, etc.).

The system should:
	•	Download & store price data for many tickers
	•	Enrich data (returns, volatility, moving averages, etc.)
	•	Save clean + enriched datasets for fast UI use
	•	Precompute advanced analytics (Markov, HMM, signals)
	•	Serve data to dashboards and eventually API users

⸻

HIGH-LEVEL SYSTEM GOALS
	1.	Fast data access (no slow recalculation in UI)
	2.	Modular architecture (each feature separate)
	3.	Offline compute + online read model
	4.	Expandable dataset (SPY → sectors → indexes → crypto etc.)
	5.	Easy to maintain and extend
	6.	No lookahead bias or overfitting

⸻

PHILOSOPHY
	•	Compute once, reuse everywhere
	•	UI = display, not heavy compute
	•	Raw data never modified
	•	Feature data separate from raw
	•	Analytics separate from features
	•	Each layer feeds the next

⸻

DATA LAYERS

Layer 1 — Raw market data
Input: Yahoo Finance or API
Output folder: data/raw/
Format: Parquet (fast) + CSV backup

Layer 2 — Cleaned data
Fix missing days, adjust dtypes, ensure date index
Folder: data/clean/

Layer 3 — Features
Example fields: returns, vol, MA ratios
Folder: data/features/

Layer 4 — Analytics
Markov chain, HMM, seasonality etc
Folder: data/analytics/*

Layer 5 — UI / Dashboards
Read from analytics layer only

⸻

KEY CONSTRAINTS

No recalculating everything every time
No heavy ML inside dashboard
No single huge script
No touching raw data after save
No guessing — ask if unclear

⸻

OUTPUT FORMAT

Primary: Parquet
Backup: CSV
Index: Date
Columns include ticker

⸻

PERFORMANCE TARGETS

Full dataset refresh: < 30 seconds
Daily update: < 5 seconds
Dashboard load: < 2 seconds
Chart interaction: < 100ms perceived delay

⸻

EXTENSIBILITY GOALS

Future support for:
	•	Sector ETFs
	•	Indices (SPX, NDX, RUT, DJI)
	•	Crypto
	•	Breadth metrics
	•	AI signal scoring
	•	API + monitoring

⸻

NEXT STEPS (in order)

✅ Part 1 — vision (this doc)
➡️ Part 2 — folder structure + files
➡️ Part 3 — data pipeline design
➡️ Part 4 — feature design
➡️ Part 5 — analytics module breakdown

⸻

END PART 1

ARCHITECT_BIBLE — PART 2 (TXT)
PROJECT STRUCTURE & FILE STANDARDS

⸻

OVERVIEW
This section defines the required folder layout.
Goal: clarity, modularity, predictable structure.

No guessing. No mixing responsibilities.

⸻

ROOT PROJECT STRUCTURE

project_root/
│
├── src/
│   ├── data_ingest/
│   ├── data_clean/
│   ├── features/
│   ├── analytics/
│   │   ├── markov/
│   │   ├── hmm/
│   │   └── seasonality/
│   ├── signals/
│   └── utils/
│
├── data/
│   ├── raw/           # untouched market data
│   ├── clean/         # cleaned + aligned prices
│   ├── features/      # all indicators
│   ├── analytics/     # markov, hmm, seasonality, etc
│   └── logs/
│
├── notebooks/         # research only, not production code
│
├── app/               # streamlit / UI
│   ├── pages/
│   └── assets/
│
├── config/            # yaml config files
│
└── docs/
    └── arch/


RULES FOR DIRECTORIES

/src
All reusable logic lives here.

/data
No code here. Only files.
Never modify raw data after save.

/notebooks
Exploration only.
Stuff here never blocks production.

/docs
Architecture and explanations only.

/app
UI only — reads precomputed data.

⸻

NAMING RULES FOR FILES

Module naming convention:
lower_snake_case.py

Examples:
fetch_prices.py
clean_prices.py
build_features.py
markov_model.py
hmm_model.py
seasonality_engine.py
signal_scoring.py

FILE PURPOSE REQUIREMENTS

Each Python file must contain:
	•	clear top comment: purpose
	•	small documented functions
	•	no global state
	•	no notebook code inside

⸻

CONFIG FILES

All settings in YAML, never hard-coded.

config/
    data_sources.yml
    tickers.yml
    features.yml
    parameters.yml

Examples:

tickers.yml
- SPY
- QQQ
- IWM
- DIA

parameters.yml
markov_order: 3
hmm_states: 2
feature_windows: [20, 50, 200]

LOGGING

Write logs to:
data/logs/

Minimum logging events:
	•	data pull
	•	feature build
	•	analytics run
	•	error tracebacks

⸻

ENV FILES

Environment variables in:
.env

Never commit:
API keys
Secrets
Tokens

WHAT IS NOT ALLOWED

❌ flat directory full of scripts
❌ logic hidden in notebooks
❌ writing compute code inside Streamlit
❌ mixing raw + processed files
❌ hardcoding tickers or dates

⸻

NEXT STEPS

After Part 2 (structure), move to:

➡️ Part 3 — Data Pipeline TXT
This defines how data flows through the system.


ARCHITECT_BIBLE — PART 3 (TXT)
DATA PIPELINE FLOW & RULES

⸻

PURPOSE
Define how data moves through the system:
download → clean → enrich → analytics → UI

The pipeline must be:
	•	deterministic
	•	versioned
	•	incremental (update only new data)
	•	auditable (logs + checks)
	•	reproducible

⸻

PIPELINE STAGES (MANDATORY)

Stage 1 — RAW DATA INGEST
input  : tickers.yml
output : data/raw/{ticker}.parquet
source : Yahoo Finance (later: Polygon/FMP/IEX)

Rules:
	•	Pull full history first time
	•	Daily incremental update after
	•	No modification to stored raw files
	•	Store both Parquet + fallback CSV

Validation:
	•	Dates sorted
	•	No duplicate rows
	•	No missing required OHLC fields

⸻

Stage 2 — CLEAN DATA
input  : data/raw/{ticker}.parquet
output : data/clean/{ticker}.parquet

Tasks:
	•	Ensure continuous trading calendar (fill missing days)
	•	Forward-fill only for non-price fields
	•	Validate dtypes (floats, datetime)
	•	Ensure timezone consistency
	•	Remove “bad spikes” only if rules defined

Validation:
	•	Always > 5 years of data unless new ticker
	•	monotonic date index
	•	no NaNs in OHLC after cleaning step

⸻

Stage 3 — FEATURE ENGINEERING
input  : data/clean/{ticker}.parquet
output : data/features/{ticker}.parquet

Included features:
	•	daily returns
	•	log returns
	•	rolling volatility
	•	moving averages & ratios
	•	daily % change
	•	day-of-week / calendar tags
	•	future placeholders for volume profile, breadth feeds

Rules:
	•	Feature names follow Part 9 standards
	•	No lookahead: only past values allowed
	•	Output must preserve date index + ticker column

Validation:
	•	No NaN in final feature file (except first N rows due to windows)
	•	Each feature documented in dictionary

⸻

Stage 4 — ANALYTICS MODELS
input  : data/features/{ticker}.parquet
output : data/analytics/{model}/{ticker}.parquet

Models include:
	•	Markov Chain states
	•	Hidden Markov Model regimes
	•	Seasonality tables
	•	Trend indicators
	•	Signal scores

Rules:
	•	Precompute offline
	•	UI reads only these outputs
	•	Store each model in its own folder
	•	Include model parameters in metadata

⸻

Stage 5 — UI / DASHBOARD
input  : data/analytics/*
output : visualization only

Streamlit or web UI should:
	•	never recalculate big data on fly
	•	always read pre-saved parquet
	•	update visuals instantly

If single calculation > 1 sec → move it back to pipeline.

⸻

PIPELINE EXECUTION MODES

Mode A — Full Rebuild (manual trigger)
rebuild --all

Mode B — Update New Data (daily)
update --latest

Mode C — Rebuild Single Ticker
rebuild --ticker SPY

Mode D — Validate Data:
validate --all

All operations log to:
data/logs/pipeline.log

SCHEDULING & AUTOMATION

Production requirement (future):
	•	daily job at market close + morning refresh
	•	retry if API fails
	•	alert on missing data

Local development:
Manual CLI invocation

⸻

FAIL-SAFE RULES

If any stage fails:
	•	stop pipeline
	•	do not delete previous dataset
	•	log error
	•	suggest fix

No silent failures.

⸻

PERFORMANCE REQUIREMENTS

Full rebuild < 30 seconds (long-term target)
Daily incremental update < 5 seconds
UI load < 2 seconds

All processing must be vectorized pandas, no loops on history.

⸻

SUMMARY FLOW (ASCII)
tickers.yml
    ↓
RAW DOWNLOAD        → data/raw/
    ↓
CLEANING            → data/clean/
    ↓
FEATURE BUILD       → data/features/
    ↓
ANALYTICS MODELS    → data/analytics/
    ↓
UI DASHBOARD        (read only)

END OF PART 3

ARCHITECT_BIBLE — PART 4 (TXT)
FEATURE ENGINEERING STANDARDS

⸻

FEATURE LAYER PURPOSE
Convert cleaned price data into machine-readable metrics for:
	•	trend detection
	•	volatility analysis
	•	regime modeling (Markov/HMM)
	•	seasonality
	•	signal scoring

Feature layer ≠ trading strategy.
It builds inputs, not predictions.

⸻

INPUT
data/clean/{ticker}.parquet

OUTPUT
data/features/{ticker}.parquet

File index = date
Columns include ticker

⸻

FEATURE GROUPS (MANDATORY)
1.	Returns
ret_1d           # adjusted close return
log_ret_1d       # optional log return

2.	Rolling Volatility
rv_20d           # 20-day realized vol (std of returns)
rv_60d

3.	Moving Averages
sma_20
sma_50
sma_200
ema_20
ema_50
ema_200

4.	MA Ratios (Trend strength)
ma_ratio_20_50
ma_ratio_50_200
ma_ratio_20_200

Definition:
ratio = short_ma / long_ma

5.	Momentum / Price distance
dist_from_50dma   # close / sma_50 - 1
dist_from_200dma

6.	Calendar Features
dow      # day of week (0=Mon)
month

7.	Future Expansion Placeholder Fields
(Keep fields pre-defined for stability)
volume_zscore
vol_regime_tag
breadth_dummy

CALCULATION RULES

✅ Vectorized pandas (no loops)
✅ Past-only windows to avoid lookahead
✅ NaN allowed only in initial warm-up period
❌ Do not annualize returns
❌ No forward returns in feature file

Windows must match config, not hard-coded.

⸻

CONFIG-DRIVEN APPROACH

config/features.yml

Example:
rolling_windows:
  sma: [20, 50, 200]
  ema: [20, 50, 200]
  volatility: [20, 60]

Pipeline reads config, not code constants.

⸻

VALIDATION REQUIREMENTS

After feature build:
	•	no NaNs except first N rows due to windows
	•	correct dtypes (float32 preferred)
	•	shape same as input
	•	date index still sorted & unique

If validation fails → stop pipeline

⸻

PERFORMANCE TARGET

Feature build < 1 second per ticker
Memory efficient: cast to float32 whenever possible

⸻

FEATURE VERSIONING

If schema changes:
data/features_v2/


Never overwrite old version.

⸻

OUTPUT SAMPLE (conceptual)
date, ticker, close, ret_1d, rv_20d, sma_50, ma_ratio_20_200, dow, month
2020-01-02, SPY, 322.74, 0.0041, 0.0122, 305.1, 1.038, 3, 1
2020-01-03, SPY, 321.73, -0.0031, 0.0118, 305.3, 1.037, 4, 1
...

DESIGN PHILOSOPHY
	•	Features = clean signals
	•	No trading logic here
	•	Reusable by Markov, HMM, future models
	•	Future indicators added without breaking old ones

⸻

END OF PART 4

ARCHITECT_BIBLE — PART 5 (TXT)
SEASONALITY ENGINE RULES

Purpose:
Quantify historical tendencies by calendar patterns (day-of-week, month, trading day-of-year, weekly). No point forecasts, only historical frequencies and averages.

Inputs:
data/features/{ticker}.parquet with ret_1d and calendar fields (dow, month). Use adjusted close returns.

Outputs:
data/analytics/seasonality_daily.parquet
data/analytics/seasonality_monthly.parquet
data/analytics/seasonality_weekly.parquet
data/analytics/seasonality_dow.parquet

Per seasonal key store:
ret_mean
ret_median
p_up
p_down
vol_mean (e.g., std of ret_1d within group)
n_samples
window_years (e.g., 5y or 10y)

Computation rules:
	•	Backward-looking only (no lookahead)
	•	Align by trading day where applicable
	•	Provide both long-history and rolling 5y/10y variants
	•	Minimum sample size = 10 per bin; otherwise flag low confidence
	•	No annualization of daily metrics
	•	No smoothing beyond rolling windows and percentiles

Performance:
Build < 2 seconds per instrument; parquet outputs < 1MB each.

Validation:
No NaN in final metrics; n_samples >= min threshold or flagged.

UI expectations (logic only):
	•	Heatmap or bar summaries built by the UI from these files
	•	Show p_up and ret_mean; compare long vs rolling windows
	•	Clear note: seasonality = historical tendency, not a forecast

Forbidden:
	•	Optimizing thresholds on future returns
	•	Mixing intraday with daily tables
	•	Overwriting raw returns or injecting lookahead

Future extensions:
Holiday effects, options expiry week, FOMC windows, earnings season drift.

END OF PART 5. 


ARCHITECT_BIBLE — PART 6 (TXT)
MARKOV CHAIN SYSTEM

Purpose:
Use historical price states to estimate transition probabilities between market conditions (Green / Neutral / Red) and compute likelihood of future states.

Markov Chain = probabilistic state machine.
Memory rule: only depends on last K states (order K).

Inputs:
data/features/{ticker}.parquet

Required input fields:
ret_1d (daily % return)
date (index)
ticker

Outputs:
data/analytics/markov/{ticker}.parquet

Outputs contents:
	•	state labels per day
	•	transition matrix (order K)
	•	next-day probability estimate per state
	•	metadata (K-order, thresholds, sample window)
	•	forecast utilities (optional)

State Definitions:
3-state model:
Green  = return > threshold
Neutral = return between ±threshold
Red = return < -threshold

Threshold expressed in decimal (e.g., 0.001 = 10bps)

Binary mode:
Green / Red only (no Neutral)

Config Parameters:
markov:
order: 1–4
threshold_bps: default 10
state_mode: “binary” or “tri”
min_samples_per_state: 10

State Encoding:
Green   = “G”
Neutral = “N”
Red     = “R”

Transition Matrix Format:
Rows = previous K-state pattern
Columns = next state probability

Example row label:
“G,G,R” = last 3 states were Green, Green, Red

Stored values:
mc_state_today
mc_prob_up_next
mc_prob_down_next
mc_prob_neutral_next (only tri-state)
mc_state_window (e.g., “G,G,R”)
mc_transition_matrix (serialized)

Computation Rules:
	•	No future data
	•	Count transitions by frequency
	•	Laplace smoothing: +1 count to each state to avoid zero-probability
	•	Require minimum sample count per row; if below threshold → mark low-confidence

Update Cycle:
Full rebuild first run
Incremental update daily after market close

Performance Rules:
Full instrument build < 0.5 seconds
Load time in app < 50ms

Validation:
	•	Transition rows sum to 1
	•	No NaN values
	•	Check state distribution (warn if >90% one state)
	•	Track max order supported by sample length

UI Expectations (not implemented here):
	•	Heatmap of transition probabilities
	•	Highlight probabilities for current pattern
	•	Text summary of most likely next state
	•	Show sample size per context pattern

Forbidden:
	•	No forward returns
	•	No tuning threshold based on future outcomes
	•	No dynamic optimization based on future regime wins

Future Extensions Allowed:
	•	Multi-asset transition cross-impact model
	•	Intraday Markov chains (lower priority)
	•	Regime-dependent transition matrices

This module = discrete statistical engine, not ML.

END OF PART 6


ARCHITECT_BIBLE — PART 7 (Hidden Markov Model System)

Goal:
The Hidden Markov Model (HMM) engine identifies unobserved market regimes such as bull, bear, and neutral periods. It detects shifts in volatility and return dynamics that standard Markov chains cannot see. HMM is trained offline and produces daily regime probabilities and labels for use in dashboards and signals.

General Concept:
Observed market data (returns and volatility) is generated by hidden states (market regimes). Model estimates:
	•	Probability of each regime for each day
	•	Transition probabilities between regimes
	•	Expected return and volatility in each regime
	•	Most likely current regime
	•	Regime change alerts

Supported:
	•	2-state and 3-state HMM (start with 2)
	•	Gaussian emission model using daily return and rolling volatility as features
	•	Window-based training (rolling X years)
	•	Multi-ticker capability

Inputs:
Source: features parquet file
Required columns:
ret_1d
rv_20d (20-day rolling volatility)

Outputs stored to:
data/analytics/{TICKER}_hmm_probs.parquet
data/analytics/{TICKER}_hmm_states.parquet
data/analytics/{TICKER}_hmm_metrics.parquet

Output fields:
For each date:
prob_bull
prob_bear
(prob_neutral if 3 states)
most_likely_state

Also store regime expected returns and volatilities:
mean_ret_state0, std_ret_state0
mean_ret_state1, std_ret_state1
(if 3 states: include state2)

Also store transition matrix:
state0_to_state0
state0_to_state1
etc.

Naming rules:
Regime states must NOT be named S0, S1, S2 in outputs.
Use human-readable labels based on expected returns:
Highest mean return = bull
Lowest mean return = bear
If 3 states: middle = neutral

Training rules:
Train on rolling historical window (default 5 years)
Do not train on full history every time unless full rebuild requested
Seed model for deterministic results
If fewer than 500 samples available, skip and mark as NA
Never trigger training inside Streamlit UI

Model stability rules:
If regime ordering flips (because model changed mapping), relabel states by mean return
If transition matrix changes more than 50% relative difference window to window, flag instability
If vol regime contradicts return regime (rare), neutral state fallback

Performance constraints:
Training per ticker under 2 seconds on local CPU
Reading stored HMM results: under 50ms

Data pipeline rules:
HMM runs AFTER feature generation
HMM outputs do not modify feature data
Dashboards only read HMM parquet files, never train

Storage requirements:
Save full probability history for explainability
Save final regime per day
Save transition matrix and metadata for each training window
Save logs with:
timestamp, ticker, window length, n_states, train_rows, runtime_seconds

Interpretation logic (for UI):
Bull: positive expected return, lower volatility
Bear: negative expected return, higher volatility
Neutral (optional): near-zero expected return, moderate vol

No assumptions about lookahead allowed.
All predictions must be based on historical data only.
No cheating with future information.

To include in UI:
Current regime label
Probability of each regime today
Chart overlay: price vs regime shading
Historical transition map
Warning if regime probability near threshold (example 50% ± 5%)

Forbidden:
No HMM training in UI
No live lookahead leaks
No training on future data
No altering underlying returns for convenience
No smoothing probabilities with future data

ARCHITECT_BIBLE — PART 5 (Seasonality Engine)

Purpose:
The seasonality engine identifies repeating historical patterns in market performance based on calendar cycles. It provides statistically grounded seasonal tendencies without predicting specific values. This supports context like: “Historically, this week/month tends to be positive or negative.”

Scope:
	•	Daily seasonality (by trading day of year)
	•	Monthly seasonality (by calendar month)
	•	Weekly seasonality (by trading week number)
	•	Day-of-week effect (e.g., Monday bias)
	•	Year-over-year calendar heatmaps (long horizon)
	•	Rolling seasonal profiles (10-year, 5-year windows)

Seasonality does not forecast precise prices. It quantifies historical tendency.

Data Source:
Uses returns generated in feature layer:
ret_1d
ret_5d (optional future expansion)

Inputs required:
Historical daily OHLC and adjusted close
Trading calendar for alignment

Outputs written to:
data/analytics/seasonality_daily.parquet
data/analytics/seasonality_monthly.parquet
data/analytics/seasonality_weekly.parquet
data/analytics/seasonality_dow.parquet  (day-of-week study)

Output structure:
For each seasonal key (e.g., month number, DOY index, DOW index):
mean_return
median_return
prob_up
prob_down
avg_volatility
sample_count

Additionally for day-by-day seasonality:
rolling_window_years used
calendar_date or trading_day_index
percentile bands (10%, 25%, 75%, 90%)

Naming:
season_key (example: month=1, dow=2, doy=145)
ret_mean
ret_median
p_up
p_down
vol_mean
n_samples

Computation rules:
	•	Use adjusted close returns
	•	Align by trading day, not calendar day where relevant
	•	Minimum 10 years preferred for reliable signal
	•	Also create 5-year rolling seasonal view for forward realism
	•	DO NOT use future returns in any seasonal sample window
	•	Data windows must be backward-looking only

Performance requirements:
Full seasonality build < 2 seconds for one instrument
Output parquet < 1MB per dataset
UI lookup < 20ms

Validation:
If sample_count < 10 for any seasonal key, mark as low confidence
No missing values in core metrics
Disallow NaNs

Statistical integrity:
Do not annualize daily seasonal returns
Do not apply smoothing beyond rolling means or percentiles
No lookahead bias
No implied future direction — only historical frequencies

UI output expectations (logic only, no UI code):
	•	Seasonal distribution heatmap (offloaded to visualization layer)
	•	Highlight strong seasonal bias (>60% up vs down imbalance)
	•	Show last 10-year vs long-term patterns
	•	Clear disclaimer: seasonal tendency ≠ forecast

Forbidden:
No optimizing thresholds based on future returns
No mixing intraday and daily seasonal tables
No overwriting raw return values
No implying certainty or predictive guarantee

Future extensions allowed:
Holiday effects (Santa rally, post-holiday drift)
FOMC-based seasonality
Options expiration week effects
Quarterly earnings drift
Global macro calendar overlays

END OF PART 7



ARCHITECT_BIBLE — PART 8 (Trend Detection + Market Breadth System)

Goal:
Create a reliable trend classification and market breadth engine to detect major regime shifts and confirm downturns or uptrends without prediction. Outputs must support research, visualization, and composite signal frameworks.

Trend System Overview:
Two components:
	1.	Trend state classification (Dow Theory inspired)
	2.	Breadth confirmation across major indices and internal market metrics

Trend Philosophy:
Trends change slowly. Signals should prioritize reliability over reactivity. Avoid noise. Confirm direction, do not predict.

Supported Trend States:
UPTREND
DOWNTREND
SIDEWAYS (optional, if neither side passes conviction threshold)

Trend inputs:
Price series from feature layer
Moving averages (short / medium / long)
Higher-highs / higher-lows structure detection (swing logic)
Ret_1d, ret_5d, ret_20d
Volatility (rv_20d)
Rate of change slope (optional future)

Primary indicators for trend logic:
	•	HH/HL vs LH/LL structure (Dow structure rule)
	•	Close relative to 200-day MA
	•	50/200 MA cross alignment
	•	ATR-normalized price distance (volatility adjusted)
	•	Slope of medium-term MA (example: 50-day)
	•	Breadth agreement across multiple assets

Trend confirmation hierarchy:
Structure > MA alignment > slope > volatility context

Trend Rule Requirements:
	•	Must operate fully on past data only
	•	No future information or lookahead
	•	Deterministic rules
	•	Clear precedence rules when mixed signals

Trend Output Columns:
trend_state (UP, DOWN, SIDEWAYS)
trend_strength_score (0-100)
swing_high, swing_low labels (binary)
last_higher_high_date
last_lower_low_date
ma_stack_state (above/below 20/50/200)
distance_from_200ma_pct

Trend data written to:
data/analytics/{TICKER}_trend.parquet

Trend Confidence:
Low confidence when conflicting signals or insufficient data length
Flag unstable trend area

Smoothness rule:
Trend state cannot flip more frequently than a defined minimal swing interval unless catastrophic move
Minimum persistence rule (default = 10 bars) unless major break

⸻

Market Breadth System

Purpose:
Confirm trend by examining participation across indices and internals. Broad market confirmation reduces false positives.

Breadth Universes:
Major indices: SPY, QQQ, DIA, IWM
Optional: sector ETFs (XLF, XLK, XLE, XLV, etc.)
Optional internals: % stocks above MA, adv/decline, new highs/lows (future)

Breadth Metrics:
pct_above_50ma (for chosen universe)
pct_above_200ma
adv_decline_ratio (if available)
new_highs_minus_new_lows (if available)
cross_index_confirmation_score (0-100)

Breadth Output Columns:
breadth_score
breadth_uptrend_flag
breadth_downtrend_flag
agreement_percent (how many indices confirm direction)

Breadth Rules:
Breadth must confirm before declaring high-conviction trend regime
Breadth weakening triggers watch phase rather than immediate reversal

Breadth Storage:
data/analytics/breadth_global.parquet

Simulation Flag:
If universe incomplete, compute with available tickers and document limitations

⸻

Composite Regime Output

Combine:
Trend state
Breadth score
Volatility context (rv_20d)
Market slope

Output:
regime_label (Bullish, Bearish, Neutral)
regime_strength_score (0-100)
bear_risk_warning_flag
bull_confirmation_flag

Regime Engine Output File:
data/analytics/{TICKER}_regime_final.parquet

⸻

Rules & Limitations

Must be:
	•	Backward-looking only
	•	Deterministic
	•	Stable, not whipsaw-prone
	•	Usable as context input for Markov/HMM, not dependent on them

Forbidden:
	•	Curve-fitting thresholds to maximize historical results
	•	Using future highs/lows to mark structure
	•	Using ML black-box classifiers here
	•	Overwriting trend history without version tags

Performance:
Trend + breadth computations < 1 second per asset

Future Extensions Allowed:
	•	Intraday swing detection
	•	Volume trend confirmation
	•	Options flow sentiment blending
	•	Global indices breadth overlay (DAX, FTSE, N225)


END OF PART 8. 



ARCHITECT_BIBLE — PART 9 (Data Pipeline Automation + API Readiness + Deployment)

Objective:
Design a reliable, automated data backbone that updates market data, enriches it, stores it efficiently, and makes it available for analysis, UI, and external API use.

Principles:
Stability > speed > complexity
Never recalc entire history unless needed
Store enriched outputs, not just raw
Each step writes structured immutable data for the next
Pipeline must survive restarts, failures, OS reboot
Logs everything, never silent failure
Manual override always available

⸻

Data Pipeline Architecture

Stages:
	1.	Ingestion (raw market data)
	2.	Cleaning & validation
	3.	Feature enrichment
	4.	Signals & models
	5.	Storage & indexing
	6.	Serving: UI + API + research notebooks

Each stage produces data artifacts (files) in /data tree.

⸻

Directory Structure

/data
/raw                   # untouched market data
/clean                 # cleaned & aligned data
/feature               # returns, vol, MAs, microstructure
/analytics             # Markov, HMM, trend, breadth
/cache                 # interim store for daily computations
/meta                  # logs, manifest files, data dictionary
/backup                # optional archive snapshots

⸻

Manifest / Bookkeeping

Store the following for each ticker:

ticker
source
last_update_timestamp
data_range
columns_available
pipeline_stage_completed
hash_checksum (integrity check)

File: /data/meta/dataset_registry.json

Purpose:
Enables restart without re-fetching past data.
Detects corruption or column mismatch.

⸻

Update Logic

Daily schedule:
Check registry
Download only missing recent bars
Append new rows
Re-compute only affected windows
Mark pipeline stage complete

Should not reprocess entire dataset unless:
schema change
feature definition updated
manual override command

⸻

CLI Tool

Command-line utility for automation:

market_pipeline update all
market_pipeline update SPY
market_pipeline rebuild SPY –stage=feature
market_pipeline validate data
market_pipeline log tail

Logging:
Rotate logs
Store last 7 days text logs
Errors always printed + saved

⸻

Versioning

Feature computations evolve. Must track:

data_version (features)
model_version (HMM, Markov config)
pipeline_version (overall)

Each parquet must embed:
metadata.version fields

⸻

API-Readiness

Future goal: expose data externally.

API must deliver:
clean series
feature columns
regime & signal states
query by ticker + date range

Performance requirement:
Serve 10k rows under 100ms

API design:
REST (initial)
optionally add GraphQL later
WebSocket optional for live feeds

No heavy compute at request time.
Serve precomputed data.

⸻

Deployment Plan

Local development → cloud ready:

Local stack:
Python + Streamlit + parquet storage

Cloud phase:
Move pipeline to container
Run scheduled tasks via:
	•	cron, or
	•	serverless (Cloud Run / AWS Lambda)

File storage options:
S3 / GCS / Azure Blob / HuggingFace Spaces repo LFS

DB Option for metadata only:
SQLite → PostgreSQL (later if needed)

CDN optional when public access.

⸻

Performance Rules

Avoid full recalculation
Prefer incremental updates
Cache everywhere
Memory-safe operations
Streaming parquet reading if large files
Lazy evaluation where possible

⸻

Failure Safety

If new calculation fails:
keep old output
log error
notify
retry once
never corrupt stored data

⸻

Security

Protect API keys
No GitHub leaks
Local .env file
Remote secrets via cloud vault later
Rate limit external API

⸻

Human Control

Manual override commands:
force rebuild
mark stage complete
safe rollback to previous version



END OF PART 9 





ARCHITECT_BIBLE — PART 10 MASTER AI WORKBENCH & PROMPT LIBRARY
(Instructions for AI coding assistants)

Mission:
This file defines how AI must operate on this project.
Goal: consistency, no breaking changes, step-by-step upgrades.

⸻

GLOBAL RULES FOR AI ASSISTANT

ALWAYS:
	•	Ask clarifying questions before coding
	•	Explain changes before writing code
	•	Modify only requested part of the project
	•	Keep code modular & documented
	•	Maintain backward compatibility
	•	Follow architecture defined in earlier parts
	•	Respect data directory structure
	•	Write clean commit messages

NEVER:
	•	Rewrite the entire project unless asked
	•	Remove existing features silently
	•	Store secrets in code
	•	Hard-code paths
	•	Use overly complex patterns prematurely

⸻

MODULARITY RULES

Every feature gets:
	•	Separate module
	•	Clear public API
	•	Dedicated folder under /src

Example modules:
src/data_ingest/
src/data_clean/
src/features/
src/models/
src/signals/
src/utils/

No single file > 500 lines.
Break into components.

⸻

TESTING & VALIDATION RULES

AI must generate:
	•	Unit tests for new functions
	•	Data validation checks for pipelines

Always check:
	•	nulls
	•	outliers
	•	shape mismatch
	•	dtype mismatch
	•	date continuity issues

⸻

DATA HANDLING RULES

Data source priority:
	1.	Local parquet
	2.	Local CSV (fallback)
	3.	Online API

Store:
	•	raw data unchanged
	•	enriched data separate

NEVER:
	•	mutate raw files
	•	recalc full dataset unless manual trigger

⸻

PERFORMANCE RULES

Use:
	•	vectorized pandas
	•	rolling windows
	•	caching

Avoid:
	•	nested python loops on big data
	•	unnecessary re-downloads

⸻

PROMPT LIBRARY — FOR USER

When requesting new features, user will start requests with:

“AI, you are modifying the Market Engine. Follow ARCHITECT_BIBLE rules.”

Examples you will paste to AI:

⸻

Prompt 1: Create a new data module
AI, you are modifying the Market Engine.
Follow ARCHITECT_BIBLE rules.
Task: Add module /src/data_ingest/yfinance_loader.py to download multiple tickers.
Include batching, logging, and retry logic.
Input: tickers.txt
Output: /data/raw/*.parquet

⸻

Prompt 2: Add feature computation
AI, follow ARCHITECT_BIBLE.
Task: Add volatility & moving average ratio features.
Write to /data/feature/*.parquet
Do NOT rewrite raw.
Add validation.

⸻

Prompt 3: Add regime engine
AI, follow ARCHITECT_BIBLE.
Task: Create /src/models/markov.py
Input: daily returns
Output: regime states to /data/analytics/markov/
Include config file, unit tests, and plot function stub.

⸻

Prompt 4: Build daily pipeline script
AI, follow ARCHITECT_BIBLE.
Task: Create CLI tool: market_pipeline.py
Commands:
	•	update
	•	rebuild 
	•	validate
Should run ingestion → clean → feature only on new rows.

⸻

Prompt 5: UI page stub (future)
AI, follow ARCHITECT_BIBLE.
Task: Create Streamlit page stub pages/01_markov.py
Load pre-computed results.
Render table + chart placeholders only.

⸻

PROMPT FOR AI WHEN DEBUGGING

If errors, use this command:

AI, do NOT rewrite everything.
Debug only the failing block.
Explain fix before applying.

⸻

RENOVATION PROMPT (refactor mode)
AI, follow ARCHITECT_BIBLE.
Refactor  for:
	•	readability
	•	comments
	•	error handling
	•	dependency isolation

Do not change logic or outputs.

⸻

FUTURE DEPLOYMENT PROMPT
AI, follow ARCHITECT_BIBLE.
Generate dockerfile + cron job for pipeline server.

⸻

BACKUP PLAN
If AI breaks project:

User command:
“ROLLBACK — restore previous version”

AI behavior:
	•	Undo last change
	•	Recreate deleted files
	•	Restore README, env, pipeline config

⸻

HUMAN SAFETY RULE

If task unclear:
AI must ask questions, not guess.


ARCHITECT_BIBLE — PART 9
DATA DICTIONARY + NAMING STANDARDS
(Pure text — no formatting markup)

Goal:
Consistent naming for all datasets, fields, tables, and model outputs.
Human-readable, machine-friendly, scalable.

⸻

DATA NAMING PRINCIPLES

Rules:
	•	Lowercase snake_case
	•	No spaces, no camelCase
	•	Avoid abbreviations unless industry standard (e.g., ema, rsi)
	•	Prefix derived fields with concept group (ret_, vol_, ma_, hmm_, mc_)
	•	Suffix for horizon: _1d, _5d, _20d, _1w, _1m

Examples:
ret_1d
ret_5d
vol_20d
ma_ratio_50_200
hmm_regime
mc_state

Date column always named:
date

Ticker column always named:
ticker

⸻

CORE RAW DATA FIELDS

Required fields for all instruments:
date
open
high
low
close
adj_close
volume

⸻

STANDARD RETURN COLUMNS

Daily return (primary):
ret_1d

Higher-horizon returns (optional future):
ret_5d
ret_20d

Log returns (optional):
log_ret_1d

⸻

VOLATILITY FIELDS

Rolling realized volatility:
rv_20d
rv_60d

Standard deviation version:
vol_20d
vol_60d

⸻

MOVING AVERAGES

Simple moving averages:
sma_20
sma_50
sma_200

Exponential moving averages:
ema_20
ema_50
ema_200

Ratios (trend strength metrics):
ma_ratio_20_50
ma_ratio_50_200
ma_ratio_20_200

Note:
Ratio = short_ma / long_ma

⸻

MARKOV CHAIN OUTPUT FIELDS

mc_state (string: Green, Neutral, Red)
mc_order (int)
mc_prob_up_next
mc_prob_down_next
mc_prob_neutral_next (only if 3-state model)
mc_matrix (stored as serialized JSON or parquet struct)

⸻

HMM OUTPUT FIELDS

hmm_state (0, 1, 2)
hmm_state_name (Bull, Bear, Neutral)
hmm_prob_bull
hmm_prob_bear
hmm_prob_neutral

Regime durability metrics:
hmm_regime_duration
hmm_regime_strength

⸻

SEASONALITY OUTPUT FIELDS

Seasonality key fields:
dow (day_of_week: 0=Mon)
doy (day_of_year index aligned by trading calendar)
month
week_of_year

Metrics:
season_ret_mean
season_ret_median
season_prob_up
season_vol
season_sample_count

⸻

MACRO + MARKET BREADTH (FUTURE RESERVED)

breadth_advancers
breadth_decliners
net_breadth
adv_decl_ratio
percent_above_50dma
percent_above_200dma

⸻

SIGNAL SCORE ENGINE FIELDS

bear_score
bull_score
trend_score
breadth_score
volatility_regime
macro_score_future_reserved

Combined:
total_signal_score

⸻

FILE NAMING RULES

Raw market data:
data/raw/{ticker}.parquet

Cleaned data:
data/clean/{ticker}.parquet

Features:
data/features/{ticker}.parquet

Seasonality:
data/analytics/seasonality_daily.parquet
data/analytics/seasonality_monthly.parquet
data/analytics/seasonality_dow.parquet
data/analytics/seasonality_weekly.parquet

Markov chain outputs:
data/analytics/markov/{ticker}.parquet

HMM outputs:
data/analytics/hmm/{ticker}.parquet

Signal tables:
data/signals/{ticker}.parquet

⸻

VERSIONING RULE

If schema changes, bump version:
/data/features_v2/
/data/analytics/hmm_v3/

Do not overwrite previous versions.

⸻

DOCUMENTATION REQUIREMENT

Every new field MUST include:
	1.	Name
	2.	Description
	3.	Units
	4.	Calculation method
	5.	Dependencies

⸻

EXAMPLE DICTIONARY ENTRY

Field: ret_1d
Description: one-day percent return using adjusted close
Formula: (adj_close / adj_close.shift(1)) - 1
Unit: decimal (0.01 = 1%)
Depends on: adj_close


END OF PART 10

