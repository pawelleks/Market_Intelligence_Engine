# Legacy Batch Documentation (Archived)

These documents describe the original batch-only pipeline architecture of the Market Intelligence Engine. They have been superseded by the real-time + batch hybrid architecture documented in the project root `ARCHITECTURE.md` and `README.md`.

**Archived on**: 2026-02-12
**Reason**: The system evolved from a pure batch pipeline to a real-time data intelligence engine with ThetaData WebSocket streaming, live Expected Moves via Theta REST API, and on-demand GEX calculation. These documents describe only the batch side and may be misleading if read in isolation.

## Archived Files

| File | Original Location | Description |
|------|-------------------|-------------|
| `daily_pipeline_run.md` | `docs/` | Batch pipeline walkthrough (orchestrator.sh) |
| `DAILY_PIPELINE.md` | `docs/CORE/` | Daily pipeline step-by-step breakdown |
| `PIPELINE_ARCHITECTURE.md` | `docs/CORE/` | CLI dependency graph and batch workflow |
| `DATA_PIPELINE.md` | `docs/OPERATIONS/` | Data update and maintenance guide |
| `CLI_REFERENCE.md` | `docs/CORE/` | Batch CLI command reference |
| `EXPECTED_MOVES_SPEC.md` | `docs/CORE/` | Original EM spec (pre-Theta, Firestore-era) |
| `data_check.md` | `docs/` | Batch data integrity check script |

## Note

The batch pipeline (orchestrator.sh, cron jobs) still runs daily. These docs are not incorrect, but they are incomplete -- they don't cover real-time capabilities, Theta integration, or the hybrid data strategy. For the current architecture, see `ARCHITECTURE.md` at the project root.
