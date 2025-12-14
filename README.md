# Market Intelligence Engine (MIE)

A high-performance market analytics platform combining traditional quantitative models (Markov, HMM) with advanced Deep Learning (GAF-CNN) to provide actionable market intelligence.

## Architecture

The project follows a modern, containerized microservices architecture:

-   **Frontend**: React (Vite) + Tailwind CSS + Recharts/Plotly (Port 5173).
-   **Backend**: FastAPI (Python) serving analytics endpoints (Port 8000).
-   **Scheduler**: background service managing data pipelines and daily builds.
-   **Services**: All components are orchestrated via **Docker Compose**.

## Features

-   **Markov Market States**: Statistical analysis of market regimes (Up/Down/Neutral) using transition matrices.
-   **Hidden Markov Models (HMM)**: Unsupervised learning to detect hidden market regimes (Volatile/Trending).
-   **GAF Analysis**: Convolutional Neural Networks (CNN) applied to Gramian Angular Fields for visual pattern recognition.
-   **Seasonality**: Historical seasonal trend analysis (daily/monthly).
-   **Reliability**: Expected moves and win-rate tracking.

## Quick Start (Docker)

The recommended way to run the full application stack is via Docker.

### 1. Start Services
```bash
docker-compose up -d --build
```
This starts:
-   `mie-web` (Frontend): http://localhost:5173
-   `mie-api` (Backend): http://localhost:8000
-   `mie-cron` (Scheduler): Runs daily tasks at 22:00 UTC.

### 2. Verify Status
```bash
docker-compose ps
```

### 3. Stop Services
```bash
docker-compose down
```

## CLI Usage (Python)

For development or manual data operations, you can use the `mie` CLI tool.
(Note: Ensure you are in the python virtual environment)

```bash
# Main entrypoint
python -m mie_lib.cli.mie --help

# Rebuild everything (Raw -> Features -> Analytics)
python -m mie_lib.cli.mie rebuild-everything

# Update daily data
python -m mie_lib.cli.mie update-everything

# Train GAF Model
python -m mie_lib.cli.mie train-gaf --ticker SPY --epochs 20
```

## Development Setup (Local)

If you wish to develop without Docker:

### Backend
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -r requirements.txt
uvicorn src.mie_lib.api.app:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Documentation

Detailed documentation is available in `docs/`:
-   `docs/CORE/ARCHITECT_BIBLE.md`: System Architecture.
-   `docs/CORE/CLI_REFERENCE.md`: Full CLI command reference.
-   `docs/DEVELOPMENT/`: Developer guides and standards.
