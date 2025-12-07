# Docker Installation & Usage Guide

This project is fully containerized using Docker and Docker Compose, providing a consistent development environment with all necessary services, including a backend API, frontend web server, and a dedicated job scheduler.

## Prerequisites

-   **Docker**: [Get Docker](https://docs.docker.com/get-docker/)
-   **Docker Compose**: Included with Docker Desktop.

## Quick Start

1.  **Build and Start the Stack**
    Run the following command in the project root:
    ```bash
    docker-compose up --build
    ```
    This will build the Python and Node.js images and start all services.

2.  **Access the Application**
    -   **Frontend (Web App)**: [http://localhost:5173](http://localhost:5173)
    -   **Backend (API Docs)**: [http://localhost:8000/docs](http://localhost:8000/docs)

## Service Overview

| Service | Name | Port | Description |
| :--- | :--- | :--- | :--- |
| **API** | `mie-api` | `8000` | FastAPI backend serving data and logic. |
| **Web** | `mie-web` | `5173` | React/Vite frontend development server. |
| **Cron** | `mie-cron` | N/A | Scheduler running daily update jobs at 23:00. |

## Data & Configuration

-   **Data Persistence**: The `/app/data` directory inside containers is mounted to your local `./data` folder. Processed Parquet/JSON files will saved locally.
-   **Configuration**: The `/app/config` directory is mounted to `./config`. You can edit `analysis_scope.yml` or `ticker_list.yml` locally, and the changes will be reflected immediately.
-   **Logs**: Cron job output is directed to the container logs. View them with:
    ```bash
    docker logs -f mie-cron
    ```

## Daily Updates (Cron)

The `mie-cron` service runs `scripts/daily_job.sh` automatically at **23:00** every day. This script:
1.  Updates raw price data (`update-raw`).
2.  Builds technical features (`build-features`).
3.  Refreshes the Minervini Scanner (`build-minervini-daily`).
4.  Updates Markov and Seasonality models.

**Manual Trigger:**
To run the update job immediately without waiting for the schedule:
```bash
docker exec -it mie-cron /app/daily_job.sh
```

## Troubleshooting

-   **Rebuild**: If you change dependencies (requirements.txt or package.json), rebuild the images:
    ```bash
    docker-compose up --build
    ```
-   **Stop**: Press `Ctrl+C` or run:
    ```bash
    docker-compose down
    ```
