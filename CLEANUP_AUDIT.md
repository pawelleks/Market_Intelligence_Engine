# Repository Cleanup Audit

**Generated:** 2026-02-17
**Scope:** Root directory files and their usage in Docker, Python scripts, and Frontend.

## Summary
- **Total Files in Root:** ~64
- **Used (Entry Points/Config):** 10
- **Junk/Logs:** ~6
- **Orphaned/Manual Scripts:** ~48

## 1. Used Files (Keep)
*Do not delete these. They are critical for the application build and runtime.*

| File | Reason |
| :--- | :--- |
| `api_server.py` | **Entry Point**. Main FastAPI application definition. |
| `run_api.py` | **Entry Point**. Uvicorn launcher used by `Dockerfile`. |
| `Dockerfile` | **Config**. Defines `mie-api` container image. |
| `Dockerfile.cron` | **Config**. Defines `mie-cron` container image (scheduler). |
| `docker-compose.yml` | **Config**. Defines services and orchestration. |
| `requirements.txt` | **Config**. Python dependencies. |
| `setup.py` | **Config**. Package installation script. |
| `Makefile` | **Config**. Build shortcut commands. |
| `Caddyfile` | **Config**. Caddy reverse proxy configuration. |
| `make_admin.py` | **Tool**. Explicitly copied into Docker image for admin creation. |
| `ThetaTerminal.jar` | **Binary**. Required for Theta Terminal sidecar (copied in Docker). |

## 2. Junk / Temporary Files (Safe to Delete)
*Files matching patterns `*.log`, `*.tmp`, `debug_`, `repro_`.*

| File | Reason |
| :--- | :--- |
| `build_error.log` | Log file. |
| `server.log` | Log file. |
| `pipeline_log.txt` | Log file. |
| `gex_response.json` | Temporary data dump. |
| `options_2025-12-16.csv` | Temporary data dump. |
| `u00261` | Unknown/Junk file. |
| `frontend_test_client.html` | Temporary test file. |
| `temp_env_part` | Temporary file. |
| `repro_dates.py` | Reproduction script for past bug. |
| `reproduce_issue.py` | Reproduction script for past bug. |

## 3. Orphaned / Manual Scripts (Review & Organize)
*These files are not referenced by the automated pipeline (Docker/Cron/Frontend). They are likely manual utility scripts. Recommendation: Move to `scripts/` or `tools/` or delete if obsolete.*

### Debug Scripts
*Suggestion: Move valid ones to `scripts/debug/`, delete others.*
- `debug_chart_data.js`
- `debug_ema_backend.py`
- `debug_enum_str.py`
- `debug_gex.py`
- `debug_gex_chain.py`
- `debug_gex_chain_v2.py`
- `debug_gex_far.py`
- `debug_gex_flip.py`
- `debug_gex_multi.py`
- `debug_massive.py`
- `debug_minsky.py`
- `debug_theta.py`
- `debug_theta_connectivity.py`
- `debug_theta_full.py`

### Inspection Tools
*Suggestion: Move to `scripts/inspect/`.*
- `audit_gex.py`
- `inspect_data.py`
- `inspect_gex_parquet.py`
- `inspect_parquet.py`
- `inspect_theta.py`
- `list_s3_buckets.py`
- `explore_s3.py`

### Testing Scripts (Root Level)
*Suggestion: Move to `tests/` or delete if redundant.*
- `test_api_local.py`
- `test_expirations.py`
- `test_fred_releases_api.py`
- `test_gex_dates.py`
- `test_polygon_gex.py`
- `test_yf.py`

### Deployment/Setup
- `deploy_prediction_analysis.txt` (Notes - move to docs or delete)
- `fix_env.py` (One-off fix script?)
- `init_db.py` (Likely old/manual init)
- `update_db.py` (Likely old/manual update)
- `verify_data.py`
- `verify_theta_simple.py`

## 4. Next Steps
1.  **Delete** all files listed in **Section 2 (Junk)**.
2.  **Move** valuable inspection/debug scripts to `scripts/` subdirectories.
3.  **Delete** obsolete manual scripts from **Section 3**.
4.  **Move** root-level `test_*.py` files to `tests/`.
