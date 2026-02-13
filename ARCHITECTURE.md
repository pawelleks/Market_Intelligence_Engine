# Architecture -- Market Intelligence Engine

## System Overview

MIE is a **hybrid real-time + batch** market analytics platform. Real-time data flows through ThetaData (WebSocket streaming and REST API), while batch analytics are pre-computed by a nightly cron pipeline and served as static JSON/Parquet artifacts.

## Service Architecture

```
                    ┌─────────────────────────────────┐
                    │         Caddy (mie-caddy)       │
                    │   TLS termination, routing      │
                    │   Port 80/443                   │
                    └──────┬──────────────┬───────────┘
                           │              │
                    /api/* │              │ /*
                           ▼              ▼
              ┌────────────────┐  ┌──────────────────┐
              │  API (mie-api) │  │ Frontend (mie-web)│
              │  FastAPI :8000 │  │  nginx (static)   │
              └───────┬────────┘  └──────────────────┘
                      │
           ┌──────────┼──────────┐
           ▼          ▼          ▼
    ┌────────────┐ ┌───────┐ ┌──────────────────┐
    │ Theta Term │ │ Data  │ │ Cron (mie-cron)  │
    │ (mie-theta)│ │ Volume│ │ Batch pipeline   │
    │ :25510     │ │       │ │ (supercronic)    │
    └────────────┘ └───────┘ └──────────────────┘
```

### Container Roles

| Container | Image | Purpose |
|-----------|-------|---------|
| `mie-api` | Custom (Dockerfile) | FastAPI server: all REST endpoints, WebSocket relay, live computation |
| `mie-web` | Custom (Dockerfile.prod) | React/Vite SPA built and served by nginx |
| `mie-caddy` | caddy:latest | Reverse proxy: routes `/api/*` to API, `/*` to nginx, manages TLS certs |
| `mie-theta` | Custom (deploy/theta_sidecar) | ThetaData Terminal: provides REST API (:25510) and WebSocket (:11000) for live market data |
| `mie-cron` | Custom (Dockerfile.cron) | Runs daily batch pipeline via supercronic at 22:00 UTC |

## Data Strategy

### Real-Time Data (ThetaData)

- **WebSocket streaming** (port 11000): Live quotes, trades, options flow
- **REST API** (port 25510): On-demand EOD prices, option chains, bulk snapshots
- **Used by**: Live Expected Moves (`/api/v1/expected_moves/theta/latest/{ticker}`), Real-Time Dealer Flow page

### Batch Data (Daily Pipeline)

- **Polygon.io**: Historical OHLCV prices (primary)
- **Massive.com**: Full options chain CSV snapshots (GEX calculation)
- **Yahoo Finance**: VIX1D, fallback price data
- **FRED**: Economic indicators (LEI, business confidence, credit spreads)

### Split-Source Constraint (CRITICAL)

> [!CAUTION]
> **Options chain data MUST use Massive CSV files. Do NOT refactor to use API calls.**

This is a **mandatory architectural constraint** that must be followed without exception:

**Rationale**:
- **Cost**: Massive flat files are included in the data subscription; API calls are metered and expensive
- **Determinism**: CSV snapshots are reproducible; API responses vary by timing
- **Compliance**: Bulk data licensing terms differ from API terms
- **Consistency**: Historical backtesting requires fixed snapshots

**Enforcement**:
- Options chains MUST be loaded from `data/raw/massive/options/options_{DATE}.csv`
- Polygon API is for **spot prices only**, not full option chains
- ThetaData REST API is the **only exception** for real-time Expected Moves calculation

**Code Locations**:
- `src/mie_lib/data_ingest/providers/polygon.py` - Spot prices only
- `src/mie_lib/data_ingest/providers/massive.py` - Options chain CSV loading
- `src/mie_lib/analytics/expected_moves/theta_expected_moves_engine.py` - Exception for real-time

**See**: `CLAUDE.md` for complete architectural constraints documentation

## API Endpoints Reference

> [!NOTE]
> All endpoints are classified as **BATCH** (pre-computed), **REAL-TIME** (on-demand calculation), or **HYBRID** (cache-first with fallback).

### Expected Moves

| Endpoint | Mode | Description | Response Time |
|----------|------|-------------|---------------|
| `GET /api/v1/expected_moves/latest` | Batch | Latest EM from daily pipeline (JSON file serving) | <50ms |
| `GET /api/v1/expected_moves/massive/latest` | Batch | Alias for `/latest` | <50ms |
| `GET /api/v1/expected_moves/static/latest` | Batch | Pre-computed static EM (cron-generated) | <10ms |
| `GET /api/v1/expected_moves/theta/latest/{ticker}` | **Real-Time** | **Live EM from ThetaData REST** (independent calc) | 2-5s |
| `GET /api/v1/expected_moves/reliability/summary` | Batch | Aggregated hit rate statistics from Parquet archive | <200ms |
| `GET /api/v1/expected_moves/reliability/history` | Batch | Historical EM records with optional ticker/expiry filtering | <100ms |

**Parameters**:
- `/reliability/history`: `?ticker={TICKER}&expiry_type={WEEKLY|MONTHLY|0DTE}` (both optional)

**Data Sources**:
- `/latest`, `/massive/latest`: `data/analytics/options/latest.json` (batch pipeline output)
- `/static/latest`: `public/data/expected_moves_static.json` (cron job output)
- `/theta/latest/{ticker}`: ThetaData REST API port 25510 (live calculation)
- `/reliability/*`: `data/analytics/expected_moves/*_expected_moves.parquet`

### Gamma Exposure (GEX)

| Endpoint | Mode | Description | Response Time |
|----------|------|-------------|---------------|
| `GET /api/v1/gex/latest/{ticker}` | **Hybrid** | Serves from cache (15-min TTL) → disk → on-demand calc | <50ms (cached) / 1-3s (calc) |
| `GET /api/v1/gex/latest/{ticker}?force_refresh=true` | **Real-Time** | **Bypasses cache, triggers live calculation** | 1-3s |
| `GET /api/v1/gex/history/heatmap/{ticker}` | Batch | Historical GEX profiles pivoted for heatmap visualization | <500ms |

> [!IMPORTANT]
> **Hidden Parameter**: `force_refresh=true` bypasses both memory cache and disk storage, forcing live GEX calculation from current option chain data.

**Cache Strategy**:
```
Request → Memory Cache (15-min TTL)
              ↓ miss
          Disk (Daily Build JSON)
              ↓ miss or force_refresh=true
          On-Demand Calculation (GEXEngine)
```

**Data Sources**:
- Cache/Disk: `data/analytics/gex/{TICKER}_profile_latest.json`
- History: `data/analytics/gex/history/{TICKER}_profile_*.parquet`
- On-demand: Fetches live option chain from Polygon/Massive

### HMM (Hidden Markov Model)

| Endpoint | Mode | Description | Response Time |
|----------|------|-------------|---------------|
| `GET /api/v1/hmm/backtest/{ticker}` | Batch | Pre-computed backtest results | <50ms |
| `GET /api/v1/hmm/signals/{ticker}/{n_states}/{window_years}` | Batch | Buy/sell signals for specific model config | <100ms |

**Data Sources**:
- `/backtest/{ticker}`: `data/analytics/hmm/backtest_results_{TICKER}.json`
- `/signals/*`: `data/analytics/hmm/{TICKER}/signals/signals_{n_states}_{window}.parquet`

### Macro

| Endpoint | Mode | Description |
|----------|------|-------------|
| `GET /api/v1/lei_index` | Batch | Leading Economic Indicator composite |
| `GET /api/v1/business_cycle` | Batch | Business cycle state classification |

## Expected Moves Calculation

Three independent backends calculate Expected Moves:

### Backend 1: Massive/Polygon (Batch)
- **When**: Daily pipeline, post-market
- **Source**: Massive CSV option chains + Polygon spot prices
- **Formula**: `EM = ATM_Call_Mid + ATM_Put_Mid` (straddle price)
- **Output**: `data/analytics/options/latest.json`

### Backend 2: Static Pre-Computed (Batch)
- **When**: Cron job (`jobs/process_expected_moves_static.py`)
- **Source**: ThetaData REST API for spot + options
- **Formula**: `EM = Straddle_Price * 0.85` (sigma factor)
- **Output**: `public/data/expected_moves_static.json`

### Backend 3: Theta Live (Real-Time)
- **When**: On-demand per API request
- **Source**: ThetaData REST API (port 25510)
- **Flow**: Fetch spot -> Determine expirations -> Fetch ATM straddle -> Bad tick filter -> `EM = Straddle * 0.85`
- **Module**: `src/mie_lib/analytics/expected_moves/theta_expected_moves_engine.py`

### Sigma Factor (0.85)
The 0.85 multiplier converts a 1-sigma straddle price to a more probable expected range. A raw ATM straddle represents ~1 standard deviation; multiplying by 0.85 produces a range that historically contains the close ~68% of the time.

## GEX Cache Strategy

```
Request ──> Memory Cache (15-min TTL)
                │ miss
                ▼
            Disk (Daily Build JSON)
                │ miss
                ▼
            On-Demand Calculation (GEXEngine)
```

- `force_refresh=true` bypasses both cache layers
- On-demand calculation takes 1-3 seconds (fetches live option chain)

## Data Persistence

| Layer | Format | Location | Purpose |
|-------|--------|----------|---------|
| Raw prices | Parquet | `data/raw/{TICKER}.parquet` | Historical OHLCV |
| Raw options | CSV | `data/raw/massive/options/options_{DATE}.csv` | Daily option chain snapshot |
| Features | Parquet | `data/features/{TICKER}.parquet` | Technical indicators |
| Analytics | Parquet/JSON | `data/analytics/{MODULE}/` | Module-specific outputs |
| Snapshots | JSON | `data/analytics_snapshots/` | Frontend-optimized copies |
| Public | JSON | `public/data/` | Pre-computed data served directly by nginx |
| Users | SQLite | `data/users.db` | User accounts and preferences |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `POLYGON_API_KEY` | Yes | Polygon.io market data |
| `MASSIVE_API_KEY` | Yes | Massive.com option chains |
| `THETADATA_USERNAME` | Yes | ThetaData Terminal login |
| `THETADATA_PASSWORD` | Yes | ThetaData Terminal password |
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth for user auth |
| `JWT_SECRET_KEY` | Yes | JWT token signing |
| `OPENAI_API_KEY` | Yes | AI context generation |
| `FRED_API_KEY` | Yes | FRED economic data |
| `SENDGRID_API_KEY` | Yes | Email notifications |
| `THETA_HOST` | No | Theta container hostname (default: `theta_terminal`) |
| `THETA_REST_PORT` | No | Theta REST port (default: `25510`) |
