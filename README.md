# Market Intelligence Engine (MIE)

A real-time market data intelligence platform combining options analytics (Expected Moves, Gamma Exposure, Implied Probability), regime detection (HMM, Markov), and macro indicators (LEI, Business Cycle) -- powered by live ThetaData streaming and batch pipelines.

**Live at**: [blindmonkey.io](https://blindmonkey.io)

## Architecture

The system uses a **hybrid real-time + batch** architecture:

- **Real-Time**: ThetaData WebSocket streaming for live quotes, on-demand Expected Moves via Theta REST API, live GEX recalculation
- **Batch (Daily)**: Overnight pipeline via cron for historical analytics, Parquet archival, and pre-computed JSON snapshots
- **Reverse Proxy**: Caddy handles TLS termination, routing, and HTTPS for the production domain

### Services (Docker Compose)

| Service | Container | Port | Role |
|---------|-----------|------|------|
| **API** | `mie-api` | 8000 | FastAPI backend serving all analytics endpoints |
| **Frontend** | `mie-web` | nginx | React/Vite SPA served by nginx |
| **Caddy** | `mie-caddy` | 80/443 | Reverse proxy, TLS (Let's Encrypt), routing |
| **Theta Terminal** | `mie-theta` | 25510 | ThetaData sidecar for live market data |
| **Scheduler** | `mie-cron` | -- | Daily batch pipeline (supercronic) |

### Data Flow

```
ThetaData WebSocket ──> API (FastAPI) ──> Frontend (React)
                             │
Polygon/Massive CSV ──> Cron Pipeline ──> Parquet/JSON ──> API ──> Frontend
                             │
FRED API ─────────────────> LEI/Business Cycle ──> API ──> Frontend
```

## Features

### Options Analytics
- **Expected Moves V2**: ATM straddle-derived price ranges (0DTE, Weekly, Monthly) with live recalculation during market hours
- **Implied Probability**: Breeden-Litzenberger risk-neutral PDFs, forward projection fan charts, probability surfaces
- **Gamma Exposure (GEX)**: Net dealer gamma per strike, vol trigger levels, historical heatmaps

### Regime Detection
- **Hidden Markov Models (HMM)**: Unsupervised regime classification with configurable states and windows
- **Markov Chains**: Transition probability matrices for market state analysis

### Technical Analysis
- **Minervini Scanner**: Trend template screening across all tickers
- **GAF-CNN**: Gramian Angular Field deep learning predictions
- **Seasonality**: Historical monthly/weekly performance patterns

### Macro Indicators
- **LEI Index**: Leading Economic Indicator composite from FRED
- **Business Cycle**: Cycle state classification from macro data

### Real-Time Streaming
- **Live Dealer Flow**: WebSocket-powered real-time options flow with GEX overlay
- **Live Expected Moves**: Intraday EM recalculation from ThetaData REST API

## Tickers

SPX, SPY, QQQ, IWM

## Quick Start

### Docker (Production)

```bash
# Start all services
docker compose up -d --build

# Verify
docker ps  # Should show 5 containers

# Frontend
open https://localhost  # or https://blindmonkey.io in production
```

### Development (Local)

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn api_server:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev
```

## Deployment

Safe deployment to production with automatic backups and rollback capability:

```bash
REMOTE_USER=deploy REMOTE_HOST=digitalocean SSH_PORT=2244 bash scripts/deploy_safe.sh
```

See `scripts/deploy_safe.sh` for backup/rollback details.

## Documentation

**Core References**:
- `ARCHITECTURE.md` -- System architecture, data flow, and API endpoints
- `CLAUDE.md` -- **Mandatory** architectural constraints and standards for AI agents
- `README.md` -- This file: quick start and feature overview

**Detailed Documentation**:
- `docs/CORE/ARCHITECT_BIBLE.md` -- Comprehensive architecture reference
- `docs/CORE/ARCHITECTURE_PRINCIPLES.md` -- Design principles and patterns
- `docs/features/` -- Feature-specific guides and tutorials
- `docs/research/` -- Research reports and audits
- `docs/architecture/` -- Architecture deep-dives
- `docs/archive/legacy_batch/` -- Deprecated batch-only documentation

**Audit & Specifications**:
- `.shotgun/specification.md` -- Repository audit master specification
- `.shotgun/research/` -- Detailed audit findings and analysis
