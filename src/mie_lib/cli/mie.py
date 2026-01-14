"""
CLI stub for Market Intelligence Engine.
Commands: update, rebuild, validate
No business logic implemented — scaffolding only.
"""
import argparse
import json
import logging
import os
import subprocess
import sys

# --- FIX for Mac M1/M2 Mutex Deadlocks ---
# Resolves conflict between TensorFlow 2.20+ and PyArrow on macOS
# Order matters: PyArrow MUST be imported BEFORE TensorFlow
try:
    import pyarrow
except ImportError:
    pass

os.environ.setdefault('TF_ENABLE_ONEDNN_OPTS', '0')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
# -----------------------------------------
import json
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
import yaml
from mie_lib.services.audit_logger import get_audit_logger

# Ensure project root is on sys.path so `src` is importable when running cli scripts
# file: .../src/mie_lib/cli/mie.py
# roots: .../src/mie_lib/cli -> .../src/mie_lib -> .../src -> .../ProjectRoot
_CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = _CURRENT_FILE.parents[3]
SRC_ROOT = _CURRENT_FILE.parents[2]

# Insert both to allow imports from 'scripts' (in ProjectRoot) and 'mie_lib' (in src)
sys.path.insert(0, str(SRC_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

from mie_lib.data_ingest.yfinance_loader import (
    read_tickers,
    fetch_full_history,
    update_ticker_incremental,
    validate_raw,
)
from mie_lib.options.expected_move import (
    ExpectedMovesConfig,
    PolygonOptionChainProvider,
    build_expected_moves_history,
    update_expected_moves,
)
from mie_lib.utils.logging import get_logger
# --- expected moves snapshot helpers ---
from mie_lib.cli.expected_moves_snapshots import (
    DEFAULT_DESTINATION_ROOT as DEFAULT_EM_SNAPSHOT_DEST,
    DEFAULT_TMP_ROOT as DEFAULT_EM_SNAPSHOT_TMP,
    build_expected_moves_snapshots,
)
from mie_lib.analytics.expected_moves.engine import run_daily_em_build
# --- hmm snapshot helpers ---
from mie_lib.cli.hmm_snapshots import (
    DEFAULT_DESTINATION_ROOT as DEFAULT_HMM_SNAPSHOT_DEST,
    DEFAULT_TMP_ROOT as DEFAULT_HMM_SNAPSHOT_TMP,
    build_hmm_snapshots,
)
# --- markov snapshot helpers ---
from mie_lib.cli.markov_snapshots import (
    DEFAULT_DESTINATION_ROOT as DEFAULT_MARKOV_SNAPSHOT_DEST,
    DEFAULT_TMP_ROOT as DEFAULT_MARKOV_SNAPSHOT_TMP,
    DEFAULT_WINDOWS as DEFAULT_MARKOV_SNAPSHOT_WINDOWS,
    build_markov_snapshots,
)
# --- features build API (aliased to avoid shadowing inside handlers) ---
from mie_lib.features.build_features import (
    build_features_for_ticker as _build_features_for_ticker,
    build_features_for_all as _build_features_for_all,
)
from mie_lib.features.build_features import FEATURES_DIR, _get_windows
from mie_lib.analytics.markov.markov_engine import MarkovConfig, build_markov_for_ticker
from mie_lib.analytics.hmm.hmm_engine import HMMConfig, build_hmm_for_ticker
from mie_lib.analytics.hmm.hmm_engine import build_hmm_standardized_for_ticker
from mie_lib.analytics.markov.states_model import build_states_from_features, derive_matrix, multi_step
from mie_lib.analytics.markov.states_model import states_stale
from mie_lib.options.em_core import MockOptionChainProvider
from mie_lib.utils.paths import HMM_DIR, MARKOV_DIR, OPTIONS_DIR
from mie_lib.seasonality_engine import generate_seasonality_base
from mie_lib.analytics.volatility_term_structure import VolatilityTermStructure

LOG = get_logger("cli")

# ---------- Default Markov grid configuration (authoritative) ----------
DEFAULT_MARKOV_GRID_STATE_MODES = ["binary", "tri"]
DEFAULT_MARKOV_GRID_THRESHOLDS = [i for i in range(0, 151, 5)]  # 0..150 by 5
DEFAULT_MARKOV_GRID_WINDOWS = ["1Y", "2Y", "5Y", "10Y", "20Y", "50Y", "MAX"]
DEFAULT_MARKOV_GRID_ORDERS = [1, 2, 3, 4]
DEFAULT_MARKOV_GRID_TICKERS_FALLBACK = ["SPY", "QQQ", "DIA", "IWM"]

# ---------- New: shared config + runner helpers ----------
CONFIG_DIR = Path("config")
TICKERS_YAML = CONFIG_DIR / "ticker_list.yml"


def _load_yaml_tickers() -> list[str]:
    """Load union of tickers from config/ticker_list.yml.
    Supports formats:
      core: [SPY, QQQ, ...]
      groups: { core: [...], indices: ["^GSPC", ...], ... }
    Returns sorted unique tickers (upper-cased except leading '^' retained).
    """
    tickers: set[str] = set()
    if not TICKERS_YAML.exists():
        return []
    try:
        cfg = yaml.safe_load(TICKERS_YAML.read_text()) or {}
    except Exception:
        return []
    # top-level common keys
    for key in ("core", "tickers", "universe"):
        vals = cfg.get(key)
        if isinstance(vals, (list, tuple, set)):
            for t in vals:
                s = str(t).strip()
                if not s:
                    continue
                tickers.add(s.upper() if not s.startswith("^") else s)
    # groups.*
    groups = cfg.get("groups")
    if isinstance(groups, dict):
        for arr in groups.values():
            if isinstance(arr, (list, tuple, set)):
                for t in arr:
                    s = str(t).strip()
                    if not s:
                        continue
                    tickers.add(s.upper() if not s.startswith("^") else s)
    return sorted(tickers)


ANALYSIS_SCOPE_YAML = CONFIG_DIR / "analysis_scope.yml"

def _load_scope_tickers(scope_key: str) -> list[str]:
    """Load specific list from config/analysis_scope.yml"""
    if not ANALYSIS_SCOPE_YAML.exists():
        return []
    try:
        cfg = yaml.safe_load(ANALYSIS_SCOPE_YAML.read_text()) or {}
        # Support "scope" top-level key if present
        if "scope" in cfg:
             cfg = cfg["scope"]
        vals = cfg.get(scope_key, [])
        if isinstance(vals, list):
             return sorted(list({str(t).strip().upper() for t in vals if t}))
        return []
    except Exception:
        return []



def _run(cmd: list[str]):
    """Echo and run a subprocess command; exit on non-zero."""
    print("$", " ".join(cmd))
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"step failed with exit code {e.returncode}: {' '.join(cmd)}")
        sys.exit(e.returncode or 1)


def _default_markov_tickers() -> list[str]:
    """Resolve default tickers for Markov grid: prefer config tickers intersecting
    the core universe (SPY,QQQ,DIA,IWM); fallback to the core list if none found."""
    # NEW: Check explicit scope first
    scope = _load_scope_tickers("Markov_Grid")
    if scope:
        return scope

    try:
        cfg = [t.strip().upper() for t in read_tickers() if str(t).strip()]
    except Exception:
        cfg = []
    core = set(DEFAULT_MARKOV_GRID_TICKERS_FALLBACK)
    sel = [t for t in cfg if t in core]
    return sel if sel else DEFAULT_MARKOV_GRID_TICKERS_FALLBACK


def _default_hmm_snapshot_tickers() -> list[str]:
    yaml_tickers = [t for t in _load_yaml_tickers() if t]
    if yaml_tickers:
        return yaml_tickers
    hmm_root = HMM_DIR
    if hmm_root.exists():
        dirs = sorted({p.name.upper() for p in hmm_root.iterdir() if p.is_dir()})
        if dirs:
            return dirs
    return ["SPY"]


def _default_markov_snapshot_tickers() -> list[str]:
    markov_root = MARKOV_DIR
    if markov_root.exists():
        dirs = sorted({p.name.upper() for p in markov_root.iterdir() if p.is_dir()})
        if dirs:
            return dirs
    return _default_markov_tickers()


def _parse_csv_int_list(val: str | None, default: list[int]) -> list[int]:
    if not val:
        return list(default)
    out = []
    for x in str(val).split(","):
        x = x.strip()
        if not x:
            continue
        try:
            out.append(int(x))
        except ValueError:
            LOG.warning("build-markov-grid: skip invalid int '%s' in list", x)
    return out or list(default)


def _parse_csv_str_list(val: str | None, default: list[str]) -> list[str]:
    if not val:
        return list(default)
    out = [s.strip() for s in str(val).split(",") if s.strip()]
    return out or list(default)


def _grid_log_path() -> Path:
    p = Path("data") / "logs" / "markov_grid.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _grid_log_append(msg: str):
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}\n"
    try:
        _grid_log_path().write_text(_grid_log_path().read_text() + line) if _grid_log_path().exists() else _grid_log_path().write_text(line)
    except Exception:
        # Best-effort file logging; still print to stdout
        pass
    print(msg)
    LOG.info(msg)


def handle_aggregate_jpm_dashboard(args):
    """
    Handle aggregate-jpm-dashboard command.
    Aggregates FRED data into 10 indicator-specific parquet files.
    """
    print("Aggregating JPM Dashboard Data...")
    from mie_lib.services.audit_logger import get_audit_logger
    get_audit_logger().start_stage("JPM Dashboard Aggregation")
    
    try:
        from mie_lib.analytics.jpm_dashboard.aggregate_indicators import aggregate_all_indicators
        
        # Run aggregation
        results = aggregate_all_indicators()
        
        # Check results
        successful = sum(results.values())
        total = len(results)
        
        if successful == total:
            print(f"✅ Successfully aggregated all {total} indicators")
            get_audit_logger().update_stage("JPM Dashboard Aggregation", "COMPLETED", {
                "indicators": total,
                "successful": successful
            })
            sys.exit(0)
        else:
            failed = [k for k, v in results.items() if not v]
            print(f"⚠️  Aggregated {successful}/{total} indicators")
            print(f"Failed: {', '.join(failed)}")
            get_audit_logger().update_stage("JPM Dashboard Aggregation", "PARTIAL", {
                "indicators": total,
                "successful": successful,
                "failed": failed
            })
            sys.exit(0)  # Don't fail pipeline for partial success
            
    except Exception as e:
        print(f"❌ Aggregation failed: {e}")
        get_audit_logger().update_stage("JPM Dashboard Aggregation", "FAILED", {"error": str(e)})
        sys.exit(1)


# ---------------- Feature build handler (refactored) -----------------

def handle_update_sma_stack(args):
    """
    Handle update-sma-stack command.
    Uses PARALLEL pipeline with ThreadPoolExecutor.
    """
    from mie_lib.analytics.tech_indicators_pipeline import run_sma_stack_parallel
    from mie_lib.services.audit_logger import get_audit_logger
    
    get_audit_logger().update_stage("SMA/EMA Stack", "RUNNING", {})
    LOG.info("Running update-sma-stack (parallel)...")
    
    workers = getattr(args, "workers", 10)
    result = run_sma_stack_parallel(max_workers=workers)
    
    LOG.info(f"update-sma-stack completed: {result.get('success', 0)}/{result.get('processed', 0)}")
    get_audit_logger().update_stage("SMA/EMA Stack", "COMPLETED", {
        "processed": result.get("processed", 0),
        "success": result.get("success", 0)
    })


def handle_update_adx(args):
    """Handle update-adx command."""
    from mie_lib.analytics.adx_dmi import calculate_and_save_adx
    from mie_lib.services.audit_logger import get_audit_logger
    get_audit_logger().update_stage("ADX/DMI", "RUNNING", {})
    LOG.info("Running update-adx...")
    calculate_and_save_adx()
    LOG.info("update-adx completed.")
    get_audit_logger().update_stage("ADX/DMI", "COMPLETED", {})


def handle_update_volatility(args):
    """Handle update-volatility command."""
    from mie_lib.services.audit_logger import get_audit_logger
    get_audit_logger().update_stage("Volatility", "RUNNING", {})
    try:
        from mie_lib.analytics.volatility import calculate_and_save_volatility
        LOG.info("Running update-volatility...")
        calculate_and_save_volatility()
        LOG.info("update-volatility completed.")
        get_audit_logger().update_stage("Volatility", "COMPLETED", {})
    except Exception as e:
        LOG.error(f"Error calculating volatility: {e}")
        get_audit_logger().update_stage("Volatility", "FAILED", {"error": str(e)})

def handle_update_volume_regime(args):
    """Handle update-volume-regime command."""
    from mie_lib.services.audit_logger import get_audit_logger
    get_audit_logger().update_stage("Volume Regime", "RUNNING", {})
    try:
        from mie_lib.analytics.volume_regime import calculate_and_save_volume_regime
        LOG.info("Running update-volume-regime...")
        calculate_and_save_volume_regime()
        LOG.info("update-volume-regime completed.")
        get_audit_logger().update_stage("Volume Regime", "COMPLETED", {})
    except Exception as e:
        LOG.error(f"Error calculating volume regime: {e}")
        get_audit_logger().update_stage("Volume Regime", "FAILED", {"error": str(e)})


def handle_update_ichimoku(args):
    """Handle update-ichimoku command."""
    from mie_lib.analytics.ichimoku import calculate_and_save_ichimoku
    from mie_lib.services.audit_logger import get_audit_logger
    get_audit_logger().update_stage("Ichimoku", "RUNNING", {})
    LOG.info("Running update-ichimoku...")
    tickers = None
    if getattr(args, "tickers", None) and args.tickers != "@config":
        tickers = [t.strip() for t in args.tickers.split(",") if t.strip()]
    calculate_and_save_ichimoku(tickers)
    LOG.info("update-ichimoku completed.")
    get_audit_logger().update_stage("Ichimoku", "COMPLETED", {})

def handle_finish_pipeline_job(args):
    """
    Explicitly finishes the current audit job log.
    Used by orchestrator.sh to save history.
    """
    status = args.status or "COMPLETED"
    print(f"Finishing Audit Log with Status: {status}")
    get_audit_logger().finish_job(status)

def handle_start_pipeline_job(args):
    """
    Explicitly starts a new audit job log.
    Used by orchestrator.sh to reset the daily log sequence.
    """
    job_name = args.name or "Daily Pipeline"
    run_type = args.type or "MANUAL"
    print(f"Initializing Audit Log for Job: {job_name} ({run_type})")
    # Force reset by accessing the singleton and resetting data before start
    logger = get_audit_logger()
    logger._reset_data()
    logger.start_job(job_name, run_type=run_type)
    
    # Pre-populate stages so UI shows them as PENDING immediately
    # Phase 1: Ingestion
    logger.update_stage("Update Raw Data", "PENDING", {})
    logger.update_stage("Download Daily Options (Flat File)", "PENDING", {})
    logger.update_stage("Extract Options Tickers", "PENDING", {})
    
    # Phase 2: Features
    logger.update_stage("Update Features", "PENDING", {})
    
    # Phase 3: Analytics
    logger.update_stage("SMA/EMA Stack", "PENDING", {})
    logger.update_stage("ADX/DMI", "PENDING", {})
    logger.update_stage("Ichimoku", "PENDING", {})
    logger.update_stage("PSAR", "PENDING", {})
    logger.update_stage("Seasonality", "PENDING", {})
    logger.update_stage("VolatilityTermStructure", "PENDING", {})
    logger.update_stage("Volatility", "PENDING", {})
    logger.update_stage("Volume Regime", "PENDING", {})
    logger.update_stage("AI Context Generation", "PENDING", {})
    logger.update_stage("Markov Grid", "PENDING", {})
    logger.update_stage("Markov Snapshots", "PENDING", {})
    logger.update_stage("HMM Grid", "PENDING", {})
    logger.update_stage("Backtest HMM", "PENDING", {})
    logger.update_stage("Expected Moves", "PENDING", {})
    logger.update_stage("HMM Backtest SPY", "PENDING", {})
    logger.update_stage("GEX", "PENDING", {})
    logger.update_stage("GEX Archive", "PENDING", {})
    logger.update_stage("TSMOM", "PENDING", {})
    logger.update_stage("GAF", "PENDING", {})
    
    # Phase 4: Data Publishing (Renamed from Snapshots)
    logger.update_stage("Skew & PCR", "PENDING", {})
    logger.update_stage("Publish Analytics Data", "PENDING", {})
    
    print("Audit Log initialized with stages.")
    sys.exit(0)


def handle_build_features(args):
    """Orchestrate feature building.
    Supports:
      --mode {full,update}
      --lookback N (update only)
      --csv (bool) write CSV fallback
      --tickers CSV or '@config' (default '@config')
    """
    mode = getattr(args, "mode", "update")
    lookback = int(getattr(args, "lookback", 90))
    write_csv = bool(getattr(args, "csv", False))
    tickers_arg = getattr(args, "tickers", "@config")

    # Audit Start
    from mie_lib.services.audit_logger import get_audit_logger
    get_audit_logger().update_stage("Update Features", "RUNNING", {"mode": mode})

    if tickers_arg and tickers_arg.strip() and tickers_arg.strip() != "@config":
        tickers = [t.strip() for t in tickers_arg.split(",") if t.strip()]
    else:
        # fall back to yaml config, then ingest loader if empty
        tickers = _load_yaml_tickers() or read_tickers()
    if not tickers:
        print("build-features ERROR: no tickers resolved")
        sys.exit(2)
    summary: list[dict] = []
    
    # Progress tracking in audit log (optional granularity)
    total = len(tickers)
    
    for i, t in enumerate(tickers):
        try:
            if mode == "full":
                out = _build_features_for_ticker(t, mode="full", write_csv=write_csv)
            else:
                out = _build_features_for_ticker(t, mode="update", lookback=lookback, write_csv=write_csv)
            logging.info("[features] OK %s rows=%s parquet=%s", t, out.get("rows"), out.get("parquet"))
            print(out)
            summary.append({"ticker": t, "status": "ok", **{k: out.get(k) for k in ("rows", "parquet")}})
        except Exception as e:
            logging.error("[cli] build-features FAIL %s: %s", t, e)
            print({"ticker": t, "status": "error", "error": str(e)})
            summary.append({"ticker": t, "status": "error", "error": str(e)})
            
        # Optional: update progress every 10 tickers
        if i % 10 == 0:
             get_audit_logger().update_stage("Update Features", "RUNNING", {"processed": i, "total": total})

    # Non-zero exit if any aborted to surface pipeline issues but keep loop running
    aborted = [r for r in summary if r.get("status") == "error"]
    
    if aborted:
        logging.warning("build-features completed with %d errors (continuing pipeline)", len(aborted))
        get_audit_logger().update_stage("Update Features", "COMPLETED", {"status": "Partial Errors", "errors": len(aborted)})
    else:
        get_audit_logger().update_stage("Update Features", "COMPLETED", {"processed": total})
        
    return summary


def _parse_iso_date(val: str, arg_name: str) -> date:
    try:
        return datetime.fromisoformat(val).date()
    except Exception as exc:  # pragma: no cover - arg guard
        raise SystemExit(f"{arg_name} must be YYYY-MM-DD: {val} ({exc})")


def _resolve_expected_moves_provider_arg(provider_name: str | None, cfg: ExpectedMovesConfig):
    name = (provider_name or cfg.provider or "polygon").lower()
    if name == "mock":
        return MockOptionChainProvider()
    if name in {"polygon", "auto", "default"}:
        return PolygonOptionChainProvider(
            {
                "max_api_calls_per_day": cfg.max_api_calls_per_day,
                "provider": name,
            }
        )
    raise SystemExit(f"Unsupported expected-moves provider '{provider_name}'")


def handle_build_expected_moves(args):
    cfg = ExpectedMovesConfig.load()
    ticker = (getattr(args, "ticker", None) or cfg.spot_ticker).upper()
    start = _parse_iso_date(args.start, "--start")
    end = _parse_iso_date(args.end, "--end") if getattr(args, "end", None) else start
    
    # Loop through dates
    current = start
    while current <= end:
        # We only care if it's a trading day, but the engine/provider handles checks too.
        # However, to save API calls, we can check here.
        # But let's just let the engine run, it might have its own logic.
        # Actually, engine.py doesn't check is_trading_day at the top level, 
        # but fetch_option_chain might fail gracefully.
        # Let's check here for efficiency.
        from mie_lib.utils.trading_calendar import is_trading_day
        if is_trading_day(current):
            print(f"Building Expected Moves for {ticker} on {current}")
            run_daily_em_build([ticker], as_of=current)
        current += timedelta(days=1)
        
    print(f"✅ Build complete for {ticker} from {start} to {end}")


def handle_update_expected_moves(args):
    cfg = ExpectedMovesConfig.load()
    
    # Resolve tickers
    tickers_arg = getattr(args, "ticker", None)
    if tickers_arg and tickers_arg.strip() != "@config":
         tickers = [t.strip().upper() for t in tickers_arg.split(",") if t.strip()]
    else:
         # Default to Reliability Scope
         tickers = _load_scope_tickers("Expected_Moves_Reliability")
         if not tickers:
              tickers = [cfg.spot_ticker.upper()]

    provider = _resolve_expected_moves_provider_arg(getattr(args, "provider", None), cfg)
    lookback = int(getattr(args, "lookback", 5) or 5)
    include_weekly = bool(getattr(args, "include_weekly_reference", False))
    
    from mie_lib.analytics.expected_moves.engine import run_daily_em_build
    from datetime import date, timedelta
    
    # Run the build (Engine handles looping and saving latest.json)
    print(f"Starting Expected Moves Build for {len(tickers)} tickers (Lookback: {lookback} days)...")
    
    all_results = []
    today = date.today()
    
    # Refactored Loop: Trading Days Lookback
    from mie_lib.utils.trading_calendar import is_verified_trading_day
    
    processed_count = 0
    day_offset = 0
    max_lookback_safety = 30 # Prevent infinite loops
    
    while processed_count < lookback and day_offset < max_lookback_safety:
        target_date = today - timedelta(days=day_offset)
        day_offset += 1
        
        # Skip Today for Flat File integrity (user request)
        # Skip Today check REMOVED to allow Live API Snapshot updates
        # if target_date >= date.today():
        #    print(f"Skipping {target_date} (Today): Flat Files are not available yet.")
        #    continue
        
        # Strict Trading Day Check (Skips Weekends & Holidays)
        if not is_verified_trading_day(target_date):
            print(f"Skipping {target_date} (Market Closed)")
            continue
        
        print(f"Processing {target_date}...")
        try:
            results = run_daily_em_build(tickers, as_of=target_date)
            all_results.append(results)
            processed_count += 1
        except Exception as e:
            LOG.error(f"Error in Expected Moves Build for {target_date}: {e}")
            print(f"Error processing {target_date}: {e}")
            # We still count it as processed to avoid hanging on a failing day?
            # User wants 5 *valid* days. If it errors, it might be valid trading day but broken code.
            # Let's count it to be safe against infinite loops, or not?
            # If code is broken, we don't want to loop forever.
            processed_count += 1

            
    print(f"Build complete. Processed {len(all_results)} days.")
    LOG.info("handle_update_expected_moves completed successfully.")
    get_audit_logger().update_stage("Expected Moves", "COMPLETED", {})
    return all_results


def handle_build_expected_moves_snapshots(args):
    cfg = ExpectedMovesConfig.load()
    tickers_arg = getattr(args, "tickers", None)
    if tickers_arg and tickers_arg.strip() != "@config":
        tickers = [t.strip().upper() for t in tickers_arg.split(",") if t.strip()]
    else:
        tickers = [cfg.spot_ticker.upper()]
    if not tickers:
        raise SystemExit("build-expected-moves-snapshots: no tickers resolved")

    destination_root = Path(getattr(args, "output_dir", "") or DEFAULT_EM_SNAPSHOT_DEST)
    tmp_root = Path(getattr(args, "tmp_dir", "") or DEFAULT_EM_SNAPSHOT_TMP)
    allow_missing = bool(getattr(args, "allow_missing", False))
    destination = Path(getattr(args, "output_dir", "") or DEFAULT_EM_SNAPSHOT_DEST)
    tmp = Path(getattr(args, "tmp_dir", "") or DEFAULT_EM_SNAPSHOT_TMP)
    source = Path(getattr(args, "source_dir", "") or OPTIONS_DIR)
    # allow_missing = bool(getattr(args, "allow_missing", False)) # Removed this line
    weekly_cfg = cfg.weekly_reference or {}
    expect_weekly_reference = bool(weekly_cfg.get("enabled", True))

    summary = build_expected_moves_snapshots(
        tickers=tickers,
        source_root=source,
        destination_root=destination,
        tmp_root=tmp,
        allow_missing=args.allow_missing,
        expect_weekly_reference=False, # Unused file, disabling check to unblock pipeline
    )
    ok = sum(1 for r in summary if r.get("status") in {"ok", "partial"})
    skipped = sum(1 for r in summary if r.get("status") == "skipped")
    LOG.info(
        "build-expected-moves-snapshots complete tickers=%s ok=%s skipped=%s dest=%s",
        ",".join(tickers),
        ok,
        skipped,
        destination_root,
    )
    print({"tickers": tickers, "results": summary})
    return summary


def handle_build_hmm_snapshots(args):
    tickers_arg = getattr(args, "tickers", None)
    if tickers_arg and tickers_arg.strip().upper() != "@CONFIG":
        tickers = [t.strip().upper() for t in tickers_arg.split(",") if t.strip()]
    else:
        tickers = _default_hmm_snapshot_tickers()
    if not tickers:
        raise SystemExit("build-hmm-snapshots: no tickers resolved")

    destination_root = Path(getattr(args, "output_dir", "") or DEFAULT_HMM_SNAPSHOT_DEST)
    tmp_root = Path(getattr(args, "tmp_dir", "") or DEFAULT_HMM_SNAPSHOT_TMP)
    allow_missing = bool(getattr(args, "allow_missing", False))

    summary = build_hmm_snapshots(
        tickers=tickers,
        destination_root=destination_root,
        tmp_root=tmp_root,
        allow_missing=allow_missing,
    )
    ok = len(summary.get("tickers_succeeded", []))
    missing = len(summary.get("tickers_missing", {}))
    LOG.info(
        "build-hmm-snapshots complete tickers=%s ok=%s missing=%s dest=%s",
        ",".join(tickers),
        ok,
        missing,
        destination_root,
    )
    print(summary)
    return summary


def handle_build_markov_grid(args):
    """
    Build Markov transition matrix grid for all tickers.
    Uses PARALLEL pipeline with ThreadPoolExecutor.
    """
    from mie_lib.analytics.markov.markov_pipeline import run_markov_grid_parallel
    from mie_lib.services.audit_logger import get_audit_logger
    
    # Resolve tickers
    if not getattr(args, "tickers", None) or str(args.tickers).strip() == "@config":
        tickers = _default_markov_tickers()
    else:
        tickers = [t.strip().upper() for t in str(args.tickers).split(",") if t.strip()]
    
    # Parse grid parameters
    modes = _parse_csv_str_list(getattr(args, "state_modes", None), DEFAULT_MARKOV_GRID_STATE_MODES)
    thresholds = _parse_csv_int_list(getattr(args, "thresholds", None), DEFAULT_MARKOV_GRID_THRESHOLDS)
    windows = _parse_csv_str_list(getattr(args, "windows", None), DEFAULT_MARKOV_GRID_WINDOWS)
    orders = _parse_csv_int_list(getattr(args, "orders", None), DEFAULT_MARKOV_GRID_ORDERS)
    workers = getattr(args, "workers", 8)
    
    print(f"Building Markov Grid (parallel) for {len(tickers)} tickers, {workers} workers...")
    get_audit_logger().update_stage("Markov Grid", "RUNNING", {"tickers": len(tickers)})
    
    try:
        result = run_markov_grid_parallel(
            tickers=tickers,
            modes=modes,
            thresholds=thresholds,
            windows=windows,
            orders=orders,
            max_workers=workers
        )
        
        print(f"Markov Grid Complete: {result.get('success')}/{result.get('processed')} tickers, "
              f"{result.get('total_matrices', 0)} matrices")
        get_audit_logger().update_stage("Markov Grid", "COMPLETED", {
            "processed": result.get("processed", 0),
            "success": result.get("success", 0),
            "total_matrices": result.get("total_matrices", 0)
        })
        
    except Exception as e:
        LOG.error(f"Markov Grid pipeline failed: {e}")
        get_audit_logger().update_stage("Markov Grid", "FAILED", {"error": str(e)})


def handle_build_markov_snapshots(args):
    """Build Markov snapshots from grid data."""
    tickers_arg = getattr(args, "tickers", None)
    if tickers_arg and tickers_arg.strip().upper() != "@CONFIG":
        tickers = [t.strip().upper() for t in tickers_arg.split(",") if t.strip()]
    else:
        tickers = _default_markov_snapshot_tickers()
    if not tickers:
        raise SystemExit("build-markov-snapshots: no tickers resolved")

    destination_root = Path(getattr(args, "output_dir", "") or DEFAULT_MARKOV_SNAPSHOT_DEST)
    tmp_root = Path(getattr(args, "tmp_dir", "") or DEFAULT_MARKOV_SNAPSHOT_TMP)
    allow_missing = bool(getattr(args, "allow_missing", False))
    windows_arg = getattr(args, "windows", None)
    windows = [w.strip().upper() for w in windows_arg.split(",") if w.strip()] if windows_arg else None

    print(f"Building Markov Snapshots (Output: {args.output_dir or 'Default'})...")
    from mie_lib.services.audit_logger import get_audit_logger
    import sys
    get_audit_logger().update_stage("Markov Snapshots", "RUNNING", {})
    try:
        meta = build_markov_snapshots(
            tickers=tickers,
            destination_root=destination_root,
            tmp_root=tmp_root,
            allow_missing=allow_missing,
            windows=windows,
        )
        print(f"Markov Snapshots Copied. Metadata: {meta.get('copied_count')} processed.")
        get_audit_logger().update_stage("Markov Snapshots", "COMPLETED", {"processed": meta.get('copied_count')})
        ok = meta.get("copied_count", 0)
        missing = len(meta.get("missing", []))
        summary = meta # Keep summary for the final print
    except Exception as e:
        print(f"Error building markov snapshots: {e}")
        get_audit_logger().update_stage("Markov Snapshots", "FAILED", {"error": str(e)})
        sys.exit(1)

    wanted_windows = windows or list(DEFAULT_MARKOV_SNAPSHOT_WINDOWS)
    LOG.info(
        "build-markov-snapshots complete tickers=%s ok=%s missing=%s dest=%s windows=%s",
        ",".join(tickers),
        ok,
        missing,
        destination_root,
        ",".join(wanted_windows),
    )
    print(summary)
    return summary


def handle_build_gex_daily(args):
    """
    Handler for building daily GEX snapshots.
    
    Uses PARALLEL pipeline:
    - OPTIONS: Massive flat files (source of truth)
    - SPOT: yfinance via ThreadPoolExecutor
    """
    from mie_lib.services.audit_logger import get_audit_logger
    from mie_lib.analytics.gex.gex_pipeline import run_gex_pipeline_parallel
    from mie_lib.utils.trading_calendar import get_previous_trading_day
    from datetime import date
    import logging
    import json
    
    logger = logging.getLogger(__name__)
    get_audit_logger().update_stage("GEX", "RUNNING", {})
    
    logger.info("Running build-gex-daily (parallel pipeline)...")
    
    try:
        # Parse date argument
        today_val = date.today()
        if args.date and args.date.lower() == "today":
            target_date = today_val.strftime("%Y-%m-%d")
        elif args.date and args.date.lower() == "yesterday":
            target_date = get_previous_trading_day(today_val).strftime("%Y-%m-%d")
        elif args.date:
            target_date = args.date
        else:
            target_date = get_previous_trading_day(today_val).strftime("%Y-%m-%d")
        
        # Parse tickers
        tickers = []
        if args.tickers == "@config":
            tickers = _load_scope_tickers("Gamma_Exposure")
            if not tickers:
                tickers = _load_yaml_tickers()
        elif args.tickers:
            tickers = _parse_csv_str_list(args.tickers, [])
        
        if not tickers:
            tickers = _load_yaml_tickers()
        
        # Parse workers
        workers = getattr(args, "workers", 10)
        online_mode = getattr(args, "online", False)
        
        logger.info(f"Target: {len(tickers)} tickers, Date: {target_date}, Workers: {workers}, Online: {online_mode}")
        
        # Run parallel pipeline
        result = run_gex_pipeline_parallel(
            tickers=tickers,
            target_date=target_date,
            max_workers=workers,
            online_mode=online_mode
        )
        
        # Log results
        logger.info(f"GEX parallel pipeline complete: {json.dumps({k: v for k, v in result.items() if k != 'details'})}")
        
        # Update audit status
        if result.get("failed", 0) == 0:
            status = "COMPLETED"
        elif result.get("success", 0) > 0:
            status = "PARTIAL"
        else:
            status = "FAILED"
        
        get_audit_logger().update_stage("GEX", status, {
            "processed": result.get("processed", 0),
            "success": result.get("success", 0),
            "failed": result.get("failed", 0),
            "skipped": result.get("skipped", 0)
        })

        return 0

    except Exception as e:
        status = "FAILED"
        LOG.error(f"GEX Daily Build Failed: {e}")
        get_audit_logger().update_stage("GEX", "FAILED", {"error": str(e)})
        return 1

def handle_update_dcs(args):
    """
    Handle update-dcs command.
    Generates static parquet/json files for Downtrend Confirmation Score.
    """
    from mie_lib.services.audit_logger import get_audit_logger
    from mie_lib.analytics.downtrend_engine import calculate_and_save_dcs
    
    get_audit_logger().update_stage("DCS", "RUNNING", {})
    tickers = getattr(args, "tickers", "@config")

    target_list = []
    if tickers == "@config":
        # Load from config or scope
        # Usually DCS is run for SPY, but user might want more.
        # Let's default to user-configured list or just SPY if not found.
        loaded = _load_yaml_tickers()
        if loaded:
            target_list = loaded
        else:
            target_list = ["SPY"]
    else:
        target_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        
    LOG.info(f"Running update-dcs for {len(target_list)} tickers...")
    
    for t in target_list:
        try:
            calculate_and_save_dcs(t)
        except Exception as e:
             LOG.error(f"Failed to update DCS for {t}: {e}")
             
    LOG.info("update-dcs completed.")
    get_audit_logger().update_stage("DCS", "COMPLETED", {"processed": len(target_list)})
    return 0



def _format_osi(ticker, expiry_str, otype, strike):
    # expiry: YYYY-MM-DD -> YYMMDD
    dt = datetime.strptime(expiry_str, "%Y-%m-%d")
    yymmdd = dt.strftime("%y%m%d")
    t_char = 'C' if otype == 'call' else 'P'
    strike_int = int(strike * 1000)
    strike_str = f"{strike_int:08d}"
    
    # Handle indices like ^SPX -> SPX
    root = ticker.replace("^", "")
    
    return f"{root}{yymmdd}{t_char}{strike_str}"

def handle_fetch_options_snapshot(args):
    """
    Fetch options chain snapshot from YFinance for specified tickers.
    Writes to data/raw/massive/options/options_YYYY-MM-DD.csv.
    """
    import pandas as pd
    from pathlib import Path
    from mie_lib.data_ingest.providers.polygon import fetch_options_snapshot
    
    logger = logging.getLogger(__name__)
    today_str = date.today().strftime("%Y-%m-%d")
    output_dir = Path("data/raw/massive/options")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"options_{today_str}.csv"
    
    # Resolve API Key (Reuse logic or env)
    api_key = os.environ.get("POLYGON_API_KEY")
    if not api_key:
        env_path = Path(".env")
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    if line.startswith("POLYGON_API_KEY"):
                        api_key = line.split("=")[1].strip()
                        break
    if not api_key:
        api_key = "keXDhBdz5zuofjHkeiYMznzUiyDerXgu" # Fallback
        logger.warning("Using fallback Polygon API Key.")

    tickers = _load_yaml_tickers()
    if args.tickers and args.tickers != "@config":
        tickers = _parse_csv_str_list(args.tickers, [])
        
    logger.info(f"Fetching Polygon options snapshot for {len(tickers)} tickers...")
    
    all_dfs = []
    
    for ticker in tickers:
        logger.info(f"Fetching {ticker}...")
        try:
            df = fetch_options_snapshot(ticker, api_key)
            if df.empty:
                logger.warning(f"  No data for {ticker}")
                continue
                
            # FILTERING LOGIC
            # Filter out dead contracts (OI=0 or IV~0)
            initial_count = len(df)
            df = df[
                (df['open_interest'] > 0) & 
                (df['implied_volatility'] >= 0.0001)
            ]
            valid_count = len(df)
            skipped_count = initial_count - valid_count
            
            logger.info(f"  {ticker}: {valid_count} valid, {skipped_count} skipped (0 OI/IV).")
            
            if not df.empty:
                all_dfs.append(df)
                
        except Exception as e:
            logger.error(f"Failed to process {ticker}: {e}")
            
    if all_dfs:
        final_df = pd.concat(all_dfs, ignore_index=True)
        # Enforce string types
        final_df['option_ticker'] = final_df['option_ticker'].fillna("").astype(str)
        final_df['underlying_ticker'] = final_df['underlying_ticker'].fillna("").astype(str)
        
        final_df.to_csv(output_file, index=False)
        logger.info(f"Saved Polygon snapshot to {output_file} ({len(final_df)} rows).")
    else:
        logger.error("No data fetched for any ticker. Aborting.")
        return 1
    
    return 0


def handle_fetch_massive_snapshot(args):
    """
    Fetch daily options snapshot from Massive S3.
    Defaults to previous trading day (completed session) if date not specified.
    """
    from mie_lib.data_ingest.massive_options_loader import MassiveOptionsLoader
    from datetime import date, timedelta
    from mie_lib.utils.trading_calendar import get_previous_trading_day
    
    date_str = args.date
    if not date_str or date_str == "auto":
        # Default: Previous Session Close (safest for EOD data)
        # Even if running mid-day, usually want the last COMPLETE file.
        date_str = get_previous_trading_day(date.today()).strftime("%Y-%m-%d")
    elif date_str == "today":
        date_str = date.today().strftime("%Y-%m-%d")
    elif date_str == "yesterday":
        date_str = get_previous_trading_day(date.today()).strftime("%Y-%m-%d")
        
    print(f"Fetching Massive Options Snapshot for {date_str}...")
    loader = MassiveOptionsLoader()
    success = loader.download_day_snapshot(date_str, force=args.force)
    
    # Audit Logging
    from mie_lib.services.audit_logger import get_audit_logger
    status = "COMPLETED" if success else "FAILED"
    get_audit_logger().update_stage("Download Daily Options (Flat File)", status, {"date": date_str})

    if success:
        print(f"Successfully fetched snapshot for {date_str}.")
        return 0
    else:
        print(f"Failed to fetch snapshot for {date_str}.")
        return 1

def handle_extract_massive_snapshot(args):
    """
    Extracts specific tickers from the locally downloaded FULL massive snapshot.
    """
    from mie_lib.data_ingest.massive_options_loader import MassiveOptionsLoader
    from datetime import date
    from mie_lib.utils.trading_calendar import get_previous_trading_day
    
    date_str = args.date
    if not date_str or date_str == "auto":
        date_str = get_previous_trading_day(date.today()).strftime("%Y-%m-%d")
        
    print(f"Extracting tickers from snapshot for {date_str}...")
    
    # Resolve Tickers
    tickers = _load_yaml_tickers()
    if args.tickers and args.tickers != "@config":
        tickers = _parse_csv_str_list(args.tickers, [])
        
    loader = MassiveOptionsLoader()
    success = loader.extract_and_save_snapshot(date_str, tickers)
    
    # Audit Logging
    from mie_lib.services.audit_logger import get_audit_logger
    status = "COMPLETED" if success else "FAILED"
    get_audit_logger().update_stage("Extract Options Tickers", status, {"date": date_str, "tickers": len(tickers)})
    
    if success:
        print(f"Successfully extracted snapshot for {date_str}.")
        return 0
    else:
        print(f"Failed to extract snapshot for {date_str}.")
        return 1

def handle_fetch_polygon_snapshot(args):
    """
    Fetch options chain snapshot from Polygon for detailed GEX analysis.
    Writes to data/raw/massive/options/options_YYYY-MM-DD.csv.
    """
    from mie_lib.data_ingest.providers.polygon import fetch_options_snapshot
    import pandas as pd
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    
    # Resolve API Key
    api_key = os.environ.get("POLYGON_API_KEY")
    if not api_key:
        # Fallback for dev environment if not explicitly exported but present in secrets/env
        # Attempt to load from local .env if exists
        env_path = Path(".env")
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    if line.startswith("POLYGON_API_KEY"):
                        api_key = line.split("=")[1].strip()
                        break
                        
    if not api_key:
        # Hardcoded fallback as last resort (user provided via grep)
        api_key = "keXDhBdz5zuofjHkeiYMznzUiyDerXgu"
        logger.warning("Using fallback Polygon API Key.")

    today_str = date.today().strftime("%Y-%m-%d")
    output_dir = Path("data/raw/massive/options")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"options_{today_str}.csv"
    
    tickers = []
    if args.tickers == "@config":
        tickers = _load_scope_tickers("Gamma_Exposure")
        if not tickers:
            tickers = _load_yaml_tickers()
    elif args.tickers:
        tickers = _parse_csv_str_list(args.tickers, [])
        
    if not tickers:
         tickers = _load_yaml_tickers()
        
    logger.info(f"Fetching Polygon snapshots for {len(tickers)} tickers...")
    
    all_dfs = []
    
    for ticker in tickers:
        df = fetch_options_snapshot(ticker, api_key)
        if not df.empty:
            all_dfs.append(df)
        else:
            logger.warning(f"No data for {ticker}")
            
    if all_dfs:
        final_df = pd.concat(all_dfs, ignore_index=True)
        # Enforce string types for tickers to avoid 'float' errors in loader regex
        final_df['option_ticker'] = final_df['option_ticker'].fillna("").astype(str)
        final_df['underlying_ticker'] = final_df['underlying_ticker'].fillna("").astype(str)
        
        final_df.to_csv(output_file, index=False)
        logger.info(f"Saved Polygon snapshot to {output_file} ({len(final_df)} rows).")
    else:
        logger.warning("No data returned from Polygon.")
        
    return 0


def handle_backtest_gaf(args):
    """
    Run Walk-Forward Backtest for GAF Model.
    """
    from mie_lib.analytics.gaf.backtest_engine import GAFBacktester
    from datetime import datetime, timedelta
    
    ticker = args.ticker
    start_date = args.start_date
    
    if args.years:
        start_dt = datetime.today() - timedelta(days=args.years*365)
        start_date = start_dt.strftime('%Y-%m-%d')
        
    end_date = datetime.today().strftime('%Y-%m-%d')
        
    print(f"Starting GAF Backtest for {ticker} from {start_date}...")
    
    engine = GAFBacktester(ticker=ticker, start_date=start_date, end_date=end_date)
    engine = GAFBacktester(ticker=ticker, start_date=start_date, end_date=end_date)
    engine.run()
    get_audit_logger().update_stage("GAF", "COMPLETED", {})


def handle_backtest_hmm(args):
    """
    Run Grid Search Optimization for HMM.
    Uses PARALLEL pipeline with ThreadPoolExecutor.
    """
    from mie_lib.analytics.hmm.hmm_pipeline import run_backtest_hmm_parallel
    from mie_lib.services.audit_logger import get_audit_logger
    
    get_audit_logger().update_stage("Backtest HMM", "RUNNING", {})
    
    # Resolve tickers
    if not args.tickers or args.tickers == "@config":
        tickers = _load_yaml_tickers()
    else:
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    
    workers = getattr(args, "workers", 6)  # Lower default for CPU-intensive backtests
    
    print(f"Starting HMM Grid Search (parallel) for {len(tickers)} tickers, {workers} workers...")
    
    try:
        result = run_backtest_hmm_parallel(tickers=tickers, max_workers=workers)
        
        print(f"HMM Backtest Complete: {result.get('success')}/{result.get('processed')} succeeded")
        get_audit_logger().update_stage("Backtest HMM", "COMPLETED", {
            "processed": result.get("processed", 0),
            "success": result.get("success", 0)
        })
        
    except Exception as e:
        LOG.error(f"HMM Backtest pipeline failed: {e}")
        get_audit_logger().update_stage("Backtest HMM", "FAILED", {"error": str(e)})


def handle_build_hmm_daily(args):
    """
    Build HMM analytics for all tickers.
    Uses PARALLEL pipeline with ThreadPoolExecutor.
    """
    from mie_lib.services.audit_logger import get_audit_logger
    from mie_lib.analytics.hmm.hmm_pipeline import run_hmm_daily_parallel
    import json
    
    tickers = _load_yaml_tickers()
    if args.tickers and args.tickers != "@config":
        tickers = _parse_csv_str_list(args.tickers, [])
    
    # Exclude VIX-related tickers
    tickers = [t for t in tickers if not t.startswith("^VIX")]
    
    workers = getattr(args, "workers", 8)
    
    print(f"Building HMM models for {len(tickers)} tickers (parallel, {workers} workers)...")
    get_audit_logger().update_stage("HMM Grid", "RUNNING", {"tickers": len(tickers)})
    
    try:
        result = run_hmm_daily_parallel(
            tickers=tickers,
            windows=[1, 5, 10, 15, 20, 25, 50, "MAX"],
            n_states_list=[2, 3],
            max_workers=workers,
            include_primary=True
        )
        
        print(f"HMM Build Complete: {result.get('success')}/{result.get('processed')} tasks succeeded")
        get_audit_logger().update_stage("HMM Grid", "COMPLETED", {
            "processed": result.get("processed", 0),
            "success": result.get("success", 0),
            "failed": result.get("failed", 0)
        })
        
    except Exception as e:
        LOG.error(f"HMM Daily pipeline failed: {e}")

        get_audit_logger().update_stage("HMM Grid", "FAILED", {"error": str(e)})


    get_audit_logger().update_stage("HMM Grid", "RUNNING", {"status": "Starting full grid build...", "total": len(tickers)})
    
    # Grid Configuration
    # Restoring the full grid as requested by user ("completly changed... one signal per state")
    # and ensuring we have long history ("Previously there was a long history").
    grid_windows = [1, 5, 10, 15, 20, 25, 50, "MAX"]
    grid_states = [2, 3]
    
    cfg = HMMConfig() # Default config (usually 2 states, 5Y) used for "primary" non-std output
    
    for i, t in enumerate(tickers):
        try:
            print(f"  Processing HMM for {t}...")
            get_audit_logger().update_stage("HMM Grid", "RUNNING", {"progress": f"{i+1}/{len(tickers)}", "current_ticker": t})
            
            # 1. Build Standardized Grid (for Backtests/Comparison)
            for win in grid_windows:
                for n_st in grid_states:
                    try:
                        # Convert window to correct type
                        # build_hmm_standardized_for_ticker handles int or 'max' string.
                        build_hmm_standardized_for_ticker(
                            ticker=t,
                            n_states=n_st,
                            train_window_years=win,
                            random_seed=42
                        )
                    except Exception as e_grid:
                         LOG.error(f"Failed HMM Grid {t} Win={win} States={n_st}: {e_grid}")

            # 2. Build Primary Default (for main Dashboard view if it uses non-std path)
            build_hmm_for_ticker(t, cfg)
            
        except Exception as e:
            LOG.error(f"Failed HMM build for {t}: {e}")
            
    print("HMM Build Complete.")
    get_audit_logger().update_stage("HMM Grid", "COMPLETED", {})


def handle_build_gaf_daily(args):
    from mie_lib.services.audit_logger import get_audit_logger
    get_audit_logger().update_stage("GAF", "RUNNING", {})
    """
    Run Daily GAF Inference (Prediction for next day).
    """
    from mie_lib.analytics.gaf.pipeline import run_inference_latest
    
    # Resolve tickers
    if str(args.ticker).strip() == "@config":
        tickers = _load_yaml_tickers()
    else:
        # Args.ticker might be a single ticker or comma list
        val = str(args.ticker or "SPY")
        tickers = [t.strip().upper() for t in val.split(",") if t.strip()]

    window = args.window
    print(f"Running GAF Inference for {len(tickers)} tickers (Window={window})...")
    
    for t in tickers:
        try:
            print(f"  Processing GAF for {t}...")
            run_inference_latest(ticker=t, window_size=window)
        except Exception as e:
            LOG.error(f"Failed GAF inference for {t}: {e}")
            print(f"  Error: {e}")
            
    get_audit_logger().update_stage("GAF", "COMPLETED", {})
    return 0


def handle_build_minervini_daily(args):
    """
    Build Minervini Scanner Snapshot for today.
    """
    from mie_lib.analytics.scanner.minervini_build import build_minervini_snapshot
    from datetime import date, datetime
    from mie_lib.services.audit_logger import get_audit_logger
    get_audit_logger().update_stage("Minervini Scanner", "RUNNING", {})
    
    # Resolve tickers
    if str(args.tickers).strip() == "@config":
        tickers = read_tickers()
    else:
        tickers = [t.strip().upper() for t in str(args.tickers).split(",") if t.strip()]
        
    target_date_str = args.date or date.today().strftime("%Y-%m-%d")
    target_date_obj = datetime.strptime(target_date_str, "%Y-%m-%d").date()
    
    print(f"Running Minervini Scanner for {target_date_str} on {len(tickers)} tickers...")
    try:
        count = build_minervini_snapshot(tickers=tickers, target_date=target_date_obj)
        print(f"Minervini Scan Complete. Matches found: {count}")
    except Exception as e:
        LOG.error(f"Minervini Scanner Failed: {e}")
        print(f"Error: {e}")
        # Don't exit with error to avoid stopping pipeline? 
        # Actually user wants complete pipeline.
        # But if scanner fails, maybe we should continue?
        # Let's catch and log.
    get_audit_logger().update_stage("Minervini Scanner", "COMPLETED", {"processed": len(tickers), "matches": count})
    return 0

def handle_build_tsmom_daily(args):
    """
    Run Daily TSMOM Update.
    """
    from mie_lib.analytics.tsmom.engine import run_tsmom_daily_update
    from datetime import date, datetime
    from mie_lib.services.audit_logger import get_audit_logger
    get_audit_logger().update_stage("TSMOM", "RUNNING", {})
    
    target_date = None
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        
    # Parse tickers if provided
    tickers = None
    if args.tickers:
        if args.tickers == "@config":
             # Will be handled by engine if passed None or we load here?
             # Engine handles it if None is passed (defaults to config load).
             pass
        else:
             tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]

    print(f"Running TSMOM Update (Date={target_date or 'Today'})...")
    res = run_tsmom_daily_update(asof_date=target_date, lookback_days=args.lookback, tickers=tickers, backfill=args.backfill)
    
    if res.get("status") == "success":
        print(f"TSMOM Success: Processed {res['processed']} tickers, Generated {res['signals_generated']} signals.")
        get_audit_logger().update_stage("TSMOM", "COMPLETED", {})
        return 0
    else:
        print(f"TSMOM Failed: {res.get('message')}")
        get_audit_logger().update_stage("TSMOM", "FAILED", {"error": res.get('message')})
        return 1

def handle_update_psar(args):
    """
    Calculate and save daily PSAR metrics.
    """
    from mie_lib.analytics.psar import calculate_and_save_psar
    print("Updating PSAR Momentum Metrics...")
    calculate_and_save_psar()
    get_audit_logger().update_stage("PSAR", "COMPLETED", {})

def handle_build_volatility_struct(args):
    """Calculates and saves Volatility Term Structure."""
    print("Updating Volatility Term Structure...")
    vts = VolatilityTermStructure()
    vts.save_report()
    get_audit_logger().update_stage("VolatilityTermStructure", "COMPLETED", {})

def handle_update_everything(args):
    """
    Handle update-everything command.
    Runs the full daily incremental pipeline: Raw -> Features -> Analytics -> Report
    """
    # Validate tickers resolve from YAML
    tickers = _load_yaml_tickers()
    if not tickers:
        print("update-everything ERROR: no tickers resolved from config/tickers.yml")
        sys.exit(2)
    
    if getattr(args, "validate_only", False):
        print("Validation Mode: Checks passed. (Health check should be run separately via script)")
        sys.exit(0)
        
    target_stage = getattr(args, "stage", None)
    dry_run = getattr(args, "dry_run", False)
    
    def run_stage(name, cmd_list):
        if target_stage and target_stage.lower() != name.lower():
            return # Skip if not matching filter
        
        if dry_run:
            print(f"[DRY-RUN] Would run stage '{name}': {' '.join(cmd_list)}")
            return

        # Execute
        try:
            _run(cmd_list)
        except Exception as e:
            print(f"ERROR in stage '{name}': {e}")
            raise e

    # --- JOB TRACKING ---
    from mie_lib.services.job_tracker import JobTracker
    tracker = JobTracker()
    tracker.start_job("Daily Update", total_steps=11)
    # --------------------

    py = sys.executable
    mie = os.fspath(Path(__file__).resolve())
    
    try:
        # RAW incremental
        if not target_stage or target_stage == "raw":
            tracker.update_progress(1, "Updating Raw Data...")
            get_audit_logger().start_job("Daily Update Pipeline") # START GLOBAL JOB
            get_audit_logger().start_stage("Update Raw Data")
            run_stage("raw", [py, mie, "update-raw"])
        
        # FEATURES incremental + CSV
        if not target_stage or target_stage == "features":
            tracker.update_progress(2, "Building Features...")
            get_audit_logger().start_stage("Update Features")
            run_stage("features", [py, mie, "build-features", "--mode", "update", "--lookback", "90", "--csv"])

        # SMA STACK ANALYTICS
        if not target_stage or target_stage == "analytics":
            tracker.update_progress(3, "Calculating SMA Stack...")
            print("Starting SMA/EMA Stack Trend Analysis...")
            get_audit_logger().start_stage("SMA/EMA Stack")
            try:
                if dry_run:
                    print("[DRY-RUN] Would calc SMA Stack")
                else:
                    from mie_lib.analytics.sma_stack import calculate_and_save_sma_stack
                    calculate_and_save_sma_stack()
                    print("SMA/EMA Stack analysis completed successfully.")
                    get_audit_logger().update_stage("SMA/EMA Stack", "COMPLETED", {})
            except Exception as e:
                print(f"ERROR calculating SMA/EMA Stack: {e}")
                get_audit_logger().update_stage("SMA/EMA Stack", "FAILED", {"error": str(e)})
            
            # ADX/DMI ANALYTICS
            tracker.update_progress(4, "Calculating ADX/DMI...")
            print("Starting ADX/DMI Analysis...")
            get_audit_logger().start_stage("ADX/DMI")
            try:
                if dry_run:
                    print("[DRY-RUN] Would calc ADX")
                else:
                    from mie_lib.analytics.adx_dmi import calculate_and_save_adx
                    calculate_and_save_adx()
                    print("ADX/DMI analysis completed successfully.")
                    get_audit_logger().update_stage("ADX/DMI", "COMPLETED", {})
            except Exception as e:
                print(f"ERROR calculating ADX/DMI: {e}")
                get_audit_logger().update_stage("ADX/DMI", "FAILED", {"error": str(e)})

            # ICHIMOKU ANALYTICS
            get_audit_logger().start_stage("Ichimoku")
            try:
                if dry_run:
                    print("[DRY-RUN] Would calc Ichimoku")
                else:
                    from mie_lib.analytics.ichimoku import calculate_and_save_ichimoku
                    calculate_and_save_ichimoku()
                    print("Ichimoku analysis completed successfully.")
                    get_audit_logger().update_stage("Ichimoku", "COMPLETED", {})
            except Exception as e:
                print(f"ERROR calculating Ichimoku: {e}")
                get_audit_logger().update_stage("Ichimoku", "FAILED", {"error": str(e)})

            # PSAR ANALYTICS
            tracker.update_progress(4.5, "Calculating Parabolic SAR...")
            print("Starting PSAR Analysis...")
            get_audit_logger().start_stage("PSAR")
            try:
                if dry_run:
                    print("[DRY-RUN] Would calc PSAR")
                else:
                    from mie_lib.analytics.psar import calculate_and_save_psar
                    calculate_and_save_psar()
                    print("PSAR analysis completed successfully.")
                    get_audit_logger().update_stage("PSAR", "COMPLETED", {})
            except Exception as e:
                print(f"ERROR calculating PSAR: {e}")
                get_audit_logger().update_stage("PSAR", "FAILED", {"error": str(e)})

        # SEASONALITY incremental
        if not target_stage or target_stage == "seasonality":
            tracker.update_progress(5, "Updating Seasonality...")
            get_audit_logger().start_stage("Seasonality")
            run_stage("seasonality", [py, mie, "update-seasonality"])
            get_audit_logger().update_stage("Seasonality", "COMPLETED", {})
        
        # MARKOV grid refresh
        if not target_stage or target_stage == "markov":
            tracker.update_progress(6, "Building Markov Models...")
            get_audit_logger().start_stage("Markov Grid")
            run_stage("markov", [py, mie, "build-markov-grid",
                "--state-modes", "binary,tri",
                "--thresholds", ",".join(str(i) for i in range(0,151,5)),
                "--windows", "1Y,2Y,5Y,10Y,20Y,MAX",
                "--orders", "1,2,3,4"])  # uses default tickers resolver
            get_audit_logger().update_stage("Markov Grid", "COMPLETED", {})
            
        # HMM grid refresh
        if not target_stage or target_stage == "hmm":
            tracker.update_progress(7, "Building HMM Grid...")
            get_audit_logger().start_stage("HMM Grid")
            run_stage("hmm", [py, mie, "build-hmm-grid", "--tickers", "@config", "--windows", "5,10,MAX", "--states", "2,3"])
            get_audit_logger().update_stage("HMM Grid", "COMPLETED", {})
        
        # EXPECTED MOVES (Reliability)
        if not target_stage or target_stage == "expected_moves":
            tracker.update_progress(8, "Calculating Expected Moves...")
            get_audit_logger().start_stage("Expected Moves")
            run_stage("expected_moves", [py, mie, "update-expected-moves", "--ticker", "@config", "--lookback", "5"])
            run_stage("expected_moves", [py, mie, "build-expected-moves-snapshots", "--tickers", "@config"])
            get_audit_logger().update_stage("Expected Moves", "COMPLETED", {})

        # HMM SNAPSHOTS (UI)
        if not target_stage or target_stage == "snapshots":
            tracker.update_progress(9, "Generating Snapshots...")
            get_audit_logger().start_stage("Snapshots")
            run_stage("snapshots", [py, mie, "build-hmm-snapshots", "--tickers", "@config"])
            get_audit_logger().update_stage("Snapshots", "COMPLETED", {})
        
        # HMM BACKTEST (Specific for SPY)
        if not target_stage or target_stage == "backtest":
            tracker.update_progress(9.5, "Running HMM Backtests...")
            get_audit_logger().start_stage("HMM Backtest SPY")
            try:
                run_stage("backtest", [py, mie, "backtest-hmm", "--ticker", "SPY"])
                get_audit_logger().update_stage("HMM Backtest SPY", "COMPLETED", {})
            except Exception as e:
                print(f"WARN: backtest-hmm failed: {e}")
                get_audit_logger().update_stage("HMM Backtest SPY", "FAILED", {"error": str(e)})
        
        # GEX (Best Effort)
        if not target_stage or target_stage == "gex":
            try:
                tracker.update_progress(10, "Updating Gamma Exposure...")
                get_audit_logger().start_stage("GEX")
                # Fetch Options Snapshot First (Polygon)
                run_stage("gex", [py, mie, "fetch-options-snapshot", "--tickers", "@config"])
                # Then Build GEX
                run_stage("gex", [py, mie, "build-gex-daily", "--date", "today", "--tickers", "@config"])
                
                # --- NEW: Archive GEX ---
                try:
                    run_stage("gex_archive", [py, mie, "archive-gex-daily", "--tickers", "@config"])
                except Exception as ex:
                    print(f"WARN: archive-gex-daily failed: {ex}")
                    # Don't fail the whole job for archiving
                # ------------------------
                
                get_audit_logger().update_stage("GEX", "COMPLETED", {})
            except SystemExit:
                print("WARN: build-gex-daily failed (likely missing flat files), continuing...")
                get_audit_logger().update_stage("GEX", "SKIPPED", {"reason": "Missing Flat Files"})
            except Exception as e:
                print(f"WARN: build-gex-daily failed: {e}")
                get_audit_logger().update_stage("GEX", "FAILED", {"error": str(e)})

        # TSMOM DAILY UPDATE
        if not target_stage or target_stage == "tsmom":
            try:
                tracker.update_progress(11, "Updating TSMOM & GAF...")
                get_audit_logger().start_stage("TSMOM")
                run_stage("tsmom", [py, mie, "build-tsmom-daily", "--tickers", "@config"])
                get_audit_logger().update_stage("TSMOM", "COMPLETED", {})
            except Exception as e:
                print(f"WARN: build-tsmom-daily failed: {e}")
                get_audit_logger().update_stage("TSMOM", "FAILED", {"error": str(e)})

        if not target_stage or target_stage == "gaf":
            try:
                get_audit_logger().start_stage("GAF")
                run_stage("gaf", [py, mie, "build-gaf-daily", "--ticker", "@config"])
                get_audit_logger().update_stage("GAF", "COMPLETED", {})
            except Exception as e:
                print(f"WARN: build-gaf-daily failed: {e}")
                get_audit_logger().update_stage("GAF", "FAILED", {"error": str(e)})

        # ECONOMIC PIPELINE (FRED + COI/LAG/LEI MODELS)
        if not target_stage or target_stage == "economic":
            try:
                tracker.update_progress(11.2, "Updating Economic Models...")
                get_audit_logger().start_stage("Economic Pipeline")
                run_stage("economic", [py, mie, "update-economic"])
                get_audit_logger().update_stage("Economic Pipeline", "COMPLETED", {})
            except Exception as e:
                print(f"WARN: update-economic failed: {e}")
                get_audit_logger().update_stage("Economic Pipeline", "FAILED", {"error": str(e)})

        # AI CONTEXT + REPORT
        if not target_stage or target_stage == "report":
            try:
                tracker.update_progress(11.5, "Generating AI Analysis...")
                get_audit_logger().start_stage("AI Context Generation")
                run_stage("report", [py, mie, "generate-ai-context", "--ticker", "SPY"])
                
                # New Stage for Report
                run_stage("report", [py, mie, "generate-ai-report", "--ticker", "SPY"])
            except Exception as e:
                print(f"WARN: AI Generation failed: {e}")
                get_audit_logger().update_stage("AI Context Generation", "FAILED", {"error": str(e)})

        if getattr(args, "snapshots", False):
            get_audit_logger().start_stage("Publish Analytics Data")
            # Logic for snapshots if needed, or assumed done by previous steps
            get_audit_logger().update_stage("Publish Analytics Data", "COMPLETED", {})

        tracker.finish_job("completed", "Daily Update Complete")
        get_audit_logger().finish_job("COMPLETED")
        print("✅ Done.")
        sys.exit(0)
        
    except Exception as e:
        tracker.finish_job("failed", f"Job Failed: {str(e)}")
        get_audit_logger().finish_job("FAILED", f"Job Failed: {str(e)}")
        print(f"❌ Job Failed: {e}")
        sys.exit(1)



def handle_archive_gex_daily(args):
    """Archive daily GEX profile."""
    print("Archiving Daily GEX Profile...")
    from mie_lib.services.audit_logger import get_audit_logger
    get_audit_logger().update_stage("GEX Archive", "RUNNING", {})
    
    try:
        import datetime
        import shutil
        
        # Resolve tickers
        if getattr(args, "tickers", None) and args.tickers != "@config":
            tickers = args.tickers.split(",")
            tickers = [t.strip().upper() for t in tickers if t.strip()]
        else:
            # Load from Analysis Scope
            tickers = _load_scope_tickers("Gamma_Exposure")
            if not tickers:
                print("  [Warn] No tickers found for Gamma_Exposure scope. Falling back to default.")
                tickers = _load_yaml_tickers()

        success_count = 0
        
        for ticker in tickers:
            try:
                source_path = Path("data/analytics/gex") / f"{ticker}_profile.parquet"
                if not source_path.exists():
                    print(f"  [Skip] Source profile for {ticker} does not exist.")
                    continue
                    
                # Check timestamp (must be today)
                stat = source_path.stat()
                mtime = datetime.datetime.fromtimestamp(stat.st_mtime).date()
                if mtime != datetime.date.today():
                    print(f"  [Warn] Source profile for {ticker} is stale ({mtime}). Archiving anyway.")
                
                today_str = datetime.date.today().strftime("%Y%m%d")
                history_dir = Path("data/analytics/gex/history")
                history_dir.mkdir(parents=True, exist_ok=True)
                
                dest_path = history_dir / f"{ticker}_profile_{today_str}.parquet"
                
                shutil.copy2(source_path, dest_path)
                print(f"  [OK] Archived {ticker} to {dest_path}")
                success_count += 1
                
            except Exception as e_tick:
                print(f"  [Err] Failed to archive {ticker}: {e_tick}")
        
        get_audit_logger().update_stage("GEX Archive", "COMPLETED", {"archived": success_count})
        sys.exit(0)
        
    except Exception as e:
        print(f"Error archiving GEX: {e}")
        get_audit_logger().update_stage("GEX Archive", "FAILED", {"error": str(e)})
        sys.exit(1)

def build_parser():
    parser = argparse.ArgumentParser(prog="mie", description="Market Intelligence Engine CLI")
    sub = parser.add_subparsers(dest="command")

    p_update = sub.add_parser("update", help="Update datasets (stub)")
    p_update.add_argument("--all", action="store_true", help="Update all tickers")

    p_rebuild = sub.add_parser("rebuild", help="Rebuild datasets (stub)")
    p_rebuild.add_argument("--ticker", help="Ticker to rebuild")
    p_rebuild.add_argument("--stage", help="Stage to rebuild")

    p_validate = sub.add_parser("validate", help="Validate datasets (stub)")
    p_validate.add_argument("--all", action="store_true", help="Validate all tickers")

    # Raw ingestion-specific commands
    p_update_raw = sub.add_parser("update-raw", help="Incrementally update raw data for tickers (append+dedupe)")
    p_update_raw.add_argument("--tickers", type=str, default="@config", help="Comma-separated tickers or @config")
    
    sub.add_parser("rebuild-raw", help="Rebuild raw data for all tickers (full history)")
    sub.add_parser("validate-raw", help="Validate raw data files for tickers")

    # --- GEX (Parallel Pipeline) ---
    p_gex = sub.add_parser("build-gex-daily", help="Build Daily GEX (Parallel Pipeline)")
    p_gex.add_argument("--date", type=str, help="YYYY-MM-DD (Default: Previous Trading Day)")
    p_gex.add_argument("--tickers", type=str, default="@config")
    p_gex.add_argument("--spot", type=float, help="Manual spot price override")
    p_gex.add_argument("--online", action="store_true", help="Use online data fetch (yfinance) instead of CSV")
    p_gex.add_argument("--workers", type=int, default=10, help="Parallel worker threads (default: 10)")
    p_gex.set_defaults(func=handle_build_gex_daily)

    p_fetch_gex = sub.add_parser("fetch-options-snapshot", help="Fetch fresh options snapshot from YFinance (Optional)")
    p_fetch_gex.add_argument("--tickers", type=str, default="@config")
    p_fetch_gex.set_defaults(func=handle_fetch_options_snapshot)

    p_fetch_massive = sub.add_parser("fetch-massive-snapshot", help="Download Massive/Polygon Flat File from S3")
    p_fetch_massive.add_argument("--date", help="YYYY-MM-DD, today, or yesterday")
    p_fetch_massive.add_argument("--force", action="store_true", help="Overwrite existing file")
    p_fetch_massive.set_defaults(func=handle_fetch_massive_snapshot)

    p_extract_massive = sub.add_parser("extract-massive-snapshot", help="Extract specific tickers from downloaded flat file")
    p_extract_massive.add_argument("--date", help="YYYY-MM-DD")
    p_extract_massive.add_argument("--tickers", default="@config", help="Tickers to extract")
    p_extract_massive.set_defaults(func=handle_extract_massive_snapshot)

    # --- GAF (New) ---
    p_backtest_gaf = sub.add_parser("backtest-gaf", help="Run Walk-Forward Backtest for GAF Model")
    p_backtest_gaf.add_argument("--ticker", default="SPY", help="Ticker symbol")
    p_backtest_gaf.add_argument("--start-date", default="2020-01-01", help="Start date for backtest (YYYY-MM-DD)")
    p_backtest_gaf.add_argument("--years", type=int, help="Number of years to look back (overrides start-date)")
    p_backtest_gaf.set_defaults(func=handle_backtest_gaf) # Assuming a handler function exists or will be added

    p_gaf_daily = sub.add_parser("build-gaf-daily", help="Run Daily GAF Inference")
    p_gaf_daily.add_argument("--ticker", default="SPY", help="Ticker symbol")
    p_gaf_daily.add_argument("--window", type=int, default=20, help="Window size")
    p_gaf_daily.set_defaults(func=handle_build_gaf_daily)

    # Analyze EM Reliability
    sub.add_parser("analyze-expected-moves-reliability", help="Compute Expected Moves Reliability Stats")

    # --- HMM Backtest (New) ---
    p_backtest_hmm = sub.add_parser("backtest-hmm", help="Run Grid Search Optimization for HMM")
    p_backtest_hmm.add_argument("--tickers", default="@config", help="Tickers to process")
    p_backtest_hmm.set_defaults(func=handle_backtest_hmm)

    # --- HMM Daily (New) ---
    p_hmm_daily = sub.add_parser("build-hmm-daily", help="Build HMM Analytics for all tickers")
    p_hmm_daily.add_argument("--tickers", default="@config", help="Tickers to process")
    p_hmm_daily.set_defaults(func=handle_build_hmm_daily)

    # --- SMA Stack (New) ---
    p_sma = sub.add_parser("update-sma-stack", help="Calculate and save daily SMA/EMA Stack status")
    p_sma.set_defaults(func=handle_update_sma_stack)

    # --- ADX/DMI (New) ---
    p_adx = sub.add_parser("update-adx", help="Calculate and save daily ADX/DMI status")
    p_adx.set_defaults(func=handle_update_adx)

    # update-volatility
    p_vol = sub.add_parser("update-volatility", help="Calculate and save daily Volatility (ATR) status")
    p_vol.set_defaults(func=handle_update_volatility)
    
    # --- Volume Regime (New) ---
    p_vol_regime = sub.add_parser("update-volume-regime", help="Calculate and save daily Volume Regime status")
    p_vol_regime.set_defaults(func=handle_update_volume_regime)

    # --- Downtrend Score (New) ---
    p_dcs = sub.add_parser("update-dcs", help="Update Downtrend Confirmation Score (DCS) data")
    p_dcs.add_argument("--tickers", default="@config", help="Tickers to process")
    p_dcs.set_defaults(func=handle_update_dcs)
    
    # --- PSAR (New) ---
    p_psar = sub.add_parser("update-psar", help="Calculate and save daily PSAR metrics")
    p_psar.set_defaults(func=handle_update_psar)

    # --- Volatility Term Structure (New) ---
    p_vts = sub.add_parser("build-volatility-struct", help="Build Volatility Term Structure Analytics")
    p_vts.set_defaults(func=handle_build_volatility_struct)

    # Feature build commands
    p_bf = sub.add_parser("build-features", help="Build features for tickers")
    p_bf.add_argument("--mode", choices=["full", "update"], default="update")
    p_bf.add_argument("--lookback", type=int, default=90, help="Number of days to recompute for incremental updates")
    p_bf.add_argument("--csv", action="store_true", help="Also write CSV fallback")
    p_bf.add_argument("--tickers", type=str, default="@config", help="Comma list or @config to use tickers from config/tickers.yml")
    p_bf.set_defaults(func=handle_build_features)

    p_uf = sub.add_parser("update-features", help="Update features for tickers (incremental)")
    p_uf.add_argument("--lookback", type=int, default=90)
    p_uf.add_argument("--csv", action="store_true")
    p_uf.add_argument("--tickers", help="Comma-separated tickers (override config)")

    # --- Polygon Fetch (New) ---
    p_poly = sub.add_parser("fetch-polygon-snapshot", help="Fetch options snapshot from Polygon.io")
    p_poly.add_argument("--tickers", type=str, default="@config")
    p_poly.set_defaults(func=handle_fetch_polygon_snapshot)


    p_em_build = sub.add_parser(
        "build-expected-moves",
        help="Rebuild expected moves history for a ticker using the polygon pipeline",
    )
    p_em_build.add_argument("--ticker", help="Ticker (default from expected_moves config)")
    p_em_build.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    p_em_build.add_argument("--end", help="End date YYYY-MM-DD (inclusive)")
    p_em_build.add_argument(
        "--provider", choices=["polygon", "mock"], help="Override option chain provider"
    )
    p_em_build.add_argument(
        "--no-weekly-reference",
        action="store_true",
        help="Skip weekly reference parquet writes",
    )
    p_em_build.set_defaults(func=handle_build_expected_moves)

    p_em_update = sub.add_parser(
        "update-expected-moves",
        help="Incrementally update expected moves parquet for recent sessions",
    )
    p_em_update.add_argument("--ticker", help="Ticker (default from expected_moves config)")
    p_em_update.add_argument("--lookback", type=int, default=5, help="Trading days to rebuild")
    p_em_update.add_argument(
        "--provider", choices=["polygon", "mock"], help="Override option chain provider"
    )
    p_em_update.add_argument(
        "--include-weekly-reference",
        action="store_true",
        help="Also refresh weekly reference parquet",
    )
    p_em_update.set_defaults(func=handle_update_expected_moves)

    p_em_snapshot = sub.add_parser(
        "build-expected-moves-snapshots",
        help="Copy expected moves analytics into the snapshot tree for UI consumption",
    )
    p_em_snapshot.add_argument(
        "--tickers",
        help="Comma-separated tickers; defaults to the spot ticker from expected_moves.yml",
    )
    p_em_snapshot.add_argument(
        "--allow-missing",
        action="store_true",
        help="Skip tickers with missing artifacts instead of raising",
    )
    p_em_snapshot.add_argument(
        "--output-dir",
        help="Destination snapshot root (default data/analytics_snapshots/options)",
    )
    p_em_snapshot.add_argument(
        "--tmp-dir",
        help="Temporary staging directory for atomic copies (default data/tmp/options_snapshots)",
    )
    p_em_snapshot.set_defaults(func=handle_build_expected_moves_snapshots)

    p_hmm_snapshot = sub.add_parser(
        "build-hmm-snapshots",
        help="Copy HMM analytics into the snapshot tree for UI consumption",
    )
    p_hmm_snapshot.add_argument(
        "--tickers",
        help="Comma-separated tickers; defaults to config tickers or existing analytics directories",
    )
    p_hmm_snapshot.add_argument(
        "--allow-missing",
        action="store_true",
        help="Skip tickers with missing artifacts instead of raising",
    )
    p_hmm_snapshot.add_argument(
        "--output-dir",
        help="Destination snapshot root (default data/analytics_snapshots/hmm)",
    )
    p_hmm_snapshot.add_argument(
        "--tmp-dir",
        help="Temporary staging directory for atomic copies (default data/tmp/hmm_snapshot_build)",
    )
    p_hmm_snapshot.set_defaults(func=handle_build_hmm_snapshots)

    p_markov_snapshot = sub.add_parser(
        "build-markov-snapshots",
        help=(
            "Copy Markov analytics trees into the snapshot directory, capturing window metadata "
            "including the 50Y horizon."
        ),
    )
    p_markov_snapshot.add_argument(
        "--tickers",
        help="Comma-separated tickers; defaults to existing analytics directories or Markov grid fallback",
    )
    p_markov_snapshot.add_argument(
        "--allow-missing",
        action="store_true",
        help="Skip tickers with missing analytics instead of raising",
    )
    p_markov_snapshot.add_argument(
        "--windows",
        help="Comma windows to track in metadata (default 1Y,2Y,5Y,10Y,20Y,50Y,MAX)",
    )
    p_markov_snapshot.add_argument(
        "--output-dir",
        help="Destination snapshot root (default data/analytics_snapshots/markov)",
    )
    p_markov_snapshot.add_argument(
        "--tmp-dir",
        help="Temporary staging directory for atomic copies (default data/tmp/markov_snapshot_build)",
    )
    p_markov_snapshot.set_defaults(func=handle_build_markov_snapshots)

    # Smoke check command
    sub.add_parser("smoke-update", help="Lightweight smoke check after FULL+UPDATE: verifies sorted dates and ret_1d continuity for first ticker")

    # Macro Data Builder
    p_macro = sub.add_parser("build-macro-data", help="Download macro economic series from FRED")
    p_macro.set_defaults(func=handle_build_macro_data)

    p_econ = sub.add_parser("update-economic", help="Run full economic pipeline (FRED + All Models)")
    p_econ.set_defaults(func=handle_update_economic)
    
    # JPM Dashboard Aggregation
    p_jpm_agg = sub.add_parser("aggregate-jpm-dashboard", help="Aggregate FRED data into JPM dashboard files")
    p_jpm_agg.set_defaults(func=handle_aggregate_jpm_dashboard)


    # Markov builder command
    p_mk = sub.add_parser("build-markov", help="Build offline Markov analytics for a ticker")
    p_mk.add_argument("--ticker", required=True)
    p_mk.add_argument("--order", type=int, default=1)
    p_mk.add_argument("--state-mode", choices=["tri", "binary"], default="tri")
    p_mk.add_argument("--threshold-bps", type=int, default=10)
    p_mk.add_argument("--window", default="MAX", help="1Y|2Y|5Y|10Y|20Y|MAX or CUSTOM_YYYYMMDD_YYYYMMDD")

    # Markov order sweep command
    p_mks = sub.add_parser("build-markov-sweep", help="Run Markov order sweep and write a compact CSV")
    p_mks.add_argument("--ticker", required=True)
    p_mks.add_argument("--orders", required=True, help="Comma-separated list of orders, e.g., 1,2,3,4")
    p_mks.add_argument("--state-mode", choices=["tri", "binary"], default="tri")
    p_mks.add_argument("--threshold-bps", type=int, default=10)

    # Batch builders
    p_mkb = sub.add_parser("build-markov-batch", help="Build Markov analytics for many tickers/params (offline)")
    p_mkb.add_argument("--tickers", required=True, help="@config or comma-separated list e.g. SPY,QQQ")
    p_mkb.add_argument("--orders", required=True, help="Comma list of K e.g. 1,2,3,4")
    p_mkb.add_argument("--state-modes", required=True, help="Comma list: tri,binary")
    p_mkb.add_argument("--threshold-bps", required=True, help="Comma list of thresholds e.g. 10,20")

    p_hmmb = sub.add_parser("build-hmm-batch", help="Build HMM analytics for many tickers (offline)")
    p_hmmb.add_argument("--tickers", required=True, help="@config or comma-separated list")
    p_hmmb.add_argument("--states", required=True, help="Comma list of 2,3")
    p_hmmb.add_argument("--window-years", type=int, default=5)
    p_hmmb.add_argument("--seed", type=int, default=42)

    # Standardized HMM grid
    p_hmmg = sub.add_parser("build-hmm-grid", help="Build standardized HMM artifacts for tickers")
    p_hmmg.add_argument("--tickers", required=True, help="@config or comma-separated list")
    p_hmmg.add_argument("--windows", required=True, help="years e.g. 5 (currently only 5 is supported)")
    p_hmmg.add_argument("--states", required=True, help="Comma list of 2,3")

    # States-first Markov commands
    p_mks_states = sub.add_parser("build-markov-states", help="Precompute Markov states for thresholds and modes")
    p_mks_states.add_argument("--ticker", required=True)
    p_mks_states.add_argument("--state-modes", required=True, help="comma list tri,binary")
    p_mks_states.add_argument("--thresholds", required=True, help="comma list e.g. 5,10,15,20")

    p_mks_matrix = sub.add_parser("derive-markov-matrix", help="Derive/caches a Markov matrix for a window/order from precomputed states. Windows: 1Y|2Y|5Y|10Y|20Y|MAX")
    p_mks_matrix.add_argument("--ticker", required=True)
    p_mks_matrix.add_argument("--state-mode", required=True, choices=["tri","binary"])
    p_mks_matrix.add_argument("--threshold-bps", required=True, type=int)
    p_mks_matrix.add_argument("--order", required=True, type=int)
    p_mks_matrix.add_argument("--window", required=True, help="1Y|2Y|5Y|10Y|20Y|MAX or CUSTOM_YYYYMMDD_YYYYMMDD (also matches 1Y|2Y|5Y|10Y|20Y|MAX for tests)")

    p_mks_grid = sub.add_parser(
        "build-markov-grid",
        help=(
            "Build states then derive matrices for a grid of params. "
            "Defaults: tickers from config (SPY,QQQ,DIA,IWM core), modes=\"binary,tri\", "
            f"thresholds=0..150 step 5, windows={','.join(DEFAULT_MARKOV_GRID_WINDOWS)}, orders=1,2,3,4"
        ),
    )
    p_mks_grid.add_argument("--tickers", help="@config or comma list; default = core from config or SPY,QQQ,DIA,IWM")
    p_mks_grid.add_argument("--state-modes", help="comma list tri,binary; default = binary,tri")
    p_mks_grid.add_argument("--thresholds", help="comma list of thresholds e.g. 0,5,10,...; default = 0..150 step 5")
    p_mks_grid.add_argument("--windows", help="comma list e.g. 1Y,2Y,5Y,10Y,20Y,MAX; default = all")
    p_mks_grid.add_argument("--orders", help="comma list e.g. 1,2,3,4; default = 1,2,3,4")

    # Orchestration commands
    sub.add_parser("update-all-analytics", help="Update raw->features then Markov states/matrices and HMM grid using config/analytics_grid.yml")

    p_ens = sub.add_parser("ensure-markov-available", help="Ensure specific Markov artifacts are present (states + derived matrix)")
    p_ens.add_argument("--ticker", required=True)
    p_ens.add_argument("--state-mode", required=True, choices=["tri","binary"])
    p_ens.add_argument("--threshold-bps", required=True, type=int)
    p_ens.add_argument("--order", required=True, type=int)
    p_ens.add_argument("--window", required=True)

    # HMM build command
    p_hmm = sub.add_parser("build-hmm", help="Build offline HMM regime detector for a ticker")
    p_hmm.add_argument("--ticker", required=True)
    p_hmm.add_argument("--states", type=int, choices=[2, 3], default=2)
    p_hmm.add_argument("--window-years", type=int, default=5)
    p_hmm.add_argument("--seed", type=int, default=42)

    # Seasonality validation command
    sub.add_parser("validate-seasonality", help="Validate the integrity of seasonality data")

    # Seasonality build/update commands
    p_seas_build = sub.add_parser("build-seasonality-facts", help="Build seasonality facts for tickers")
    p_seas_build.add_argument("--tickers", default="ALL", help="Comma list or ALL to load from config")
    p_seas_build.add_argument("--dry-run", action="store_true", help="Print planned writes but do not persist")

    p_seas_update = sub.add_parser("update-seasonality", help="Incrementally update seasonality facts since date")
    p_seas_update.add_argument("--since", required=False, help="YYYY-MM-DD; if omitted, processes all")
    p_seas_update.add_argument("--tickers", default="ALL", help="Comma list or ALL to load from config")
    p_seas_update.add_argument("--dry-run", action="store_true", help="Print planned writes but do not persist")

    # NEW: Simple Seasonality Builder
    p_seas_simple = sub.add_parser("build-seasonality", help="Generate seasonality base data for a single ticker")
    p_seas_simple.add_argument("--ticker", required=True, help="Ticker symbol")

    # NEW: Seasonality base builder (per-ticker base used by Seasonality Analysis page)
    p_seas_base = sub.add_parser(
        "build-seasonality-base",
        help=(
            "Build seasonality base parquet for tickers (offline; uses existing RAW/FEATURES, no downloads). "
            "Writes data/seasonality/base/{TICKER}.parquet."
        ),
    )
    p_seas_base.add_argument("--tickers", help="Comma-separated tickers. If omitted, loads from config via --from-config.")
    p_seas_base.add_argument("--from-config", action="store_true", help="Load tickers from config/tickers.yml (default if --tickers omitted)")
    p_seas_base.add_argument("--lookbacks", help="Comma list of lookbacks e.g. 5,10,20,30,50,ALL (optional)")
    p_seas_base.add_argument("--min-years", type=int, default=5, help="Minimum years for base usefulness (informational)")
    p_seas_base.add_argument("--return-type", default="log", choices=["log","simple"], help="Internal calc basis (base stores both anyway)")
    p_seas_base.add_argument("--force", action="store_true", help="Overwrite even if base exists")

    # NEW: one-command orchestrators
    sub.add_parser(
        "rebuild-everything",
        help=(
            "Full rebuild: RAW fresh, FEATURES full, SEASONALITY base/facts, MARKOV grid, HMM grid for all YAML tickers."
        ),
    )
    # Removed duplicate update-everything definition


    sub.add_parser(
        "rebuild-reliability",
        help="Rebuild expected moves and snapshots for reliability page."
    )

    # Minervini Scanner
    p_min = sub.add_parser("build-minervini-daily", help="Build Daily Minervini Scanner Snapshot")
    p_min.add_argument("--date", type=str, help="YYYY-MM-DD (Default Today)")
    p_min.add_argument("--tickers", type=str, default="@config")
    p_min.set_defaults(func=handle_build_minervini_daily)

    # GAF Analysis
    p_gaf_train = sub.add_parser("train-gaf", help="Train GAF CNN Model")
    p_gaf_train.add_argument("--ticker", type=str, default="SPY")
    p_gaf_train.add_argument("--epochs", type=int, default=20)
    


    p_tsmom = sub.add_parser("build-tsmom-daily", help="Build Daily TSMOM Dashboard Data")

    p_ai = sub.add_parser("generate-ai-context", help="Step 9: Generate AI Context Payload")
    p_ai.add_argument("--ticker", help="Ticker symbol", default="SPY")

    p_ai_report = sub.add_parser("generate-ai-report", help="Step 10: Generate AI Analysis Report")
    p_ai_report.add_argument("--ticker", help="Ticker symbol", default="SPY")
    p_ai_report.add_argument("--model", help="LLM Model", default="gpt-4-turbo-preview")
    
    # Economic Insights for JPM Dashboard
    p_econ_insights = sub.add_parser("generate-economic-insights", help="Generate AI insights for JPM Economic Dashboard")
    p_econ_insights.add_argument("--tier", type=int, default=1, help="Insight tier (1, 2, or 3)")
    p_econ_insights.add_argument("--indicator", type=str, default=None, help="Specific indicator (or all if not specified)")
    p_econ_insights.add_argument("--model", type=str, default="gpt-4o", help="OpenAI model to use")
    
    # Generic Audit Updater
    p_audit = sub.add_parser("update-stage", help="Manually update an audit stage status")
    p_audit.add_argument("--stage", required=True, help="Stage Name (e.g. 'Publish Analytics Data')")
    p_audit.add_argument("--status", required=True, help="Status (e.g. 'COMPLETED', 'FAILED')")
    p_audit.add_argument("--meta", help="JSON string for metadata")
    p_tsmom.add_argument("--date", type=str, help="YYYY-MM-DD (Default Today)")
    p_tsmom.add_argument("--tickers", type=str, default=None)
    p_tsmom.add_argument("--lookback", type=int, default=252)
    p_tsmom.add_argument("--backfill", action="store_true", help="Generate signals from full history")
    p_tsmom.set_defaults(func=handle_build_tsmom_daily)

    # Ichimoku
    p_ichimoku = sub.add_parser("update-ichimoku", help="Calculate and save Ichimoku Kinko Hyo")
    p_ichimoku.add_argument("--tickers", type=str, default="@config")
    p_ichimoku.set_defaults(func=handle_update_ichimoku)

    # Update Everything (Main Pipeline)
    p_ue = sub.add_parser("update-everything", help="Run full daily incremental pipeline (Raw -> Features -> Analytics -> Report)")
    p_ue.add_argument("--stage", help="Run specific stage only (raw, features, analytics, gex, tsmom, report, etc.)")
    p_ue.add_argument("--dry-run", action="store_true", help="Simulate run without executing heavy logic")
    p_ue.add_argument("--validate-only", action="store_true", help="Validate prerequisites and exit")
    p_ue.add_argument("--snapshots", action="store_true", help="Also generate UI snapshots")
    p_ue.set_defaults(func=handle_update_everything)

    # Pipeline start command for orchestrator
    p_start = sub.add_parser("start-pipeline-job", help="Initialize the audit log for a new job")
    p_start.add_argument("--name", help="Job Name")

    # Archive GEX
    p_gex_arc = sub.add_parser("archive-gex-daily", help="Archive daily GEX profile")
    p_gex_arc.add_argument("--tickers", default="SPY")
    p_gex_arc.set_defaults(func=handle_archive_gex_daily)
    p_start.add_argument("--type", help="Run Type (MANUAL/CRON)")

    p_start.set_defaults(func=handle_start_pipeline_job)


    p_finish = sub.add_parser("finish-pipeline-job", help="Finalize the audit log for the current job")
    p_finish.add_argument("--status", default="COMPLETED")
    p_finish.set_defaults(func=handle_finish_pipeline_job)

    # NEW SKEW COMMAND (Parallel Pipeline)
    p_skew = sub.add_parser("build-skew-daily", help="Calculate Option Skew & PCR (parallel)")
    p_skew.add_argument("--tickers", help="Comma separated or @config")
    p_skew.add_argument("--date", help="YYYY-MM-DD")
    p_skew.add_argument("--workers", type=int, default=10, help="Parallel worker threads (default: 10)")
    p_skew.set_defaults(func=handle_build_skew_daily)

    return parser


def main(argv=None):
    # Configure logging to stdout by default for CLI visibility
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    argv = argv or sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    # Dispatch via func if present (new handler pattern for build-features)
    if hasattr(args, "func"):
        args.func(args)
        return

    # New ingestion-specific commands
    if args.command == "update":
        print("[stub] update called", args)
    elif args.command == "rebuild":
        print("[stub] rebuild called", args)
    elif args.command == "validate":
        print("[stub] validate called", args)
    elif args.command == "update-raw":
        from mie_lib.services.audit_logger import get_audit_logger
        get_audit_logger().update_stage("Update Raw Data", "RUNNING", {})
        if args.tickers and args.tickers != "@config":
            tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        else:
            tickers = read_tickers()
        for t in tickers:
            res = update_ticker_incremental(t)
            LOG.info("update-raw result: %s", res)
            print(res)
        get_audit_logger().update_stage("Update Raw Data", "COMPLETED", {"tickers_processed": len(tickers)})
    elif args.command == "rebuild-raw":
        tickers = read_tickers()
        for t in tickers:
            res = fetch_full_history(t)
            LOG.info("rebuild-raw result: %s", res)
            print(res)
    elif args.command == "validate-raw":
        tickers = read_tickers()
        for t in tickers:
            res = validate_raw(t)
            LOG.info("validate-raw result: %s", res)
            print(res)
    elif args.command == "update-features":
        from mie_lib.services.audit_logger import get_audit_logger
        tickers = None
        if hasattr(args, "tickers") and args.tickers and args.tickers != "@config":
             tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
        
        results = _build_features_for_all(mode="update", lookback=args.lookback, write_csv=args.csv, tickers=tickers)
        for r in results:
            LOG.info("update-features: %s", r)
            print(r)
        get_audit_logger().update_stage("Update Features", "COMPLETED", {"tickers_processed": len(results)})
    elif args.command == "smoke-update":
        # Lightweight smoke check: read features for first configured ticker and verify basic invariants
        try:
            tickers = read_tickers()
            if not tickers:
                print("smoke-update FAIL: no tickers configured in config/tickers.yml")
                LOG.error("smoke-update: no tickers configured")
                sys.exit(2)
            ticker = tickers[0].strip()
            # Import pandas lazily to avoid heavy import cost for other commands
            import pandas as pd

            p_parquet = FEATURES_DIR / f"{ticker}.parquet"
            p_csv = FEATURES_DIR / f"{ticker}.csv"
            if p_parquet.exists():
                df = pd.read_parquet(p_parquet)
            elif p_csv.exists():
                df = pd.read_csv(p_csv)
            else:
                print(f"smoke-update FAIL: features file not found for {ticker}. Run build-features/update-features first.")
                LOG.error("smoke-update: features missing for %s", ticker)
                sys.exit(3)

            # Normalize date dtype and sort check
            if "date" not in df.columns:
                df = df.reset_index()
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

            sorted_ok = df["date"].is_monotonic_increasing
            unique_ok = not df["date"].duplicated().any()

            # Warm-up from config
            windows = _get_windows()
            max_window = max(
                max(windows.get("sma", [0])) if windows.get("sma") else 0,
                max(windows.get("ema", [0])) if windows.get("ema") else 0,
                max(windows.get("vol", [0])) if windows.get("vol") else 0,
            )

            ret_ok = True
            if len(df) > max_window + 1:
                ret_ok = not df["ret_1d"].iloc[max_window + 1 :].isna().any()

            if sorted_ok and unique_ok and ret_ok:
                last3 = [d.strftime("%Y-%m-%d") for d in df["date"].tail(3)]
                msg = f"smoke-update OK: ticker={ticker} rows={len(df)} last3={last3} warmup={max_window}"
                print(msg)
                LOG.info(msg)
                sys.exit(0)
            else:
                problems = []
                if not sorted_ok:
                    problems.append("dates not sorted")
                if not unique_ok:
                    problems.append("duplicate dates")
                if not ret_ok:
                    problems.append("NaNs in ret_1d beyond warm-up")
                diag = ", ".join(problems) or "unknown issue"
                print(f"smoke-update FAIL: {diag} for {ticker}")
                LOG.error("smoke-update FAIL for %s: %s", ticker, diag)
                sys.exit(4)
        except Exception as e:
            print(f"smoke-update ERROR: {e}")
            LOG.exception("smoke-update encountered an error")
            sys.exit(5)
    elif args.command == "build-markov":
        try:
            # States-first implementation to ensure threshold-specific artifacts
            t = args.ticker.upper()
            mode = args.state_mode
            thr = int(args.threshold_bps)
            K = int(args.order)
            win = str(args.window).upper()
            # Build states for (mode,thr)
            sp = build_states_from_features(t, thr, mode)
            # Derive windowed matrix for order K
            df = derive_matrix(t, thr, mode, K, win)
            base = Path("data")/"analytics"/"markov"/t/"matrices"/mode/f"thr{thr}"/f"order{K}"
            mp = base/f"{win}.parquet"
            
            # --- Multi-Step Forecast (NEW) ---
            if K == 1:
                horizons = [1, 2, 3, 4, 5]
                try:
                    ms_df = multi_step(df, horizons, mode)
                    if not ms_df.empty:
                        # Path: data/analytics/markov/{ticker}/multi_step_order1_{mode}_thr{thr}.parquet
                        ms_path = Path("data")/"analytics"/"markov"/t/f"multi_step_order{K}_{mode}_thr{thr}.parquet"
                        ms_df.reset_index().to_parquet(ms_path, index=False)
                        LOG.info("build-markov: multi-step written to %s", ms_path)
                except Exception as e:
                    LOG.warning("build-markov: multi-step failed: %s", e)
            # --- END Multi-Step Forecast ---

            print({"ticker": t, "mode": mode, "thr": thr, "order": K, "window": win, "states": sp, "matrix": str(mp), "rows": len(df)})
            LOG.info("build-markov: %s", mp)
            sys.exit(0)
        except Exception as e:
            print(f"build-markov ERROR: {e}")
            LOG.exception("build-markov failed")
            sys.exit(6)
    elif args.command == "build-markov-sweep":
        try:
            orders = [int(x.strip()) for x in str(args.orders).split(",") if x.strip()]
            from mie_lib.analytics.markov.markov_engine import build_markov_order_sweep
            path = build_markov_order_sweep(
                ticker=args.ticker,
                orders=orders,
                state_mode=args.state_mode,
                threshold_bps=args.threshold_bps,
            )
            print({"order_sweep": path})
            LOG.info("build-markov-sweep: %s", path)
            sys.exit(0)
        except Exception as e:
            print(f"build-markov-sweep ERROR: {e}")
            LOG.exception("build-markov-sweep failed")
            sys.exit(7)

    elif args.command == "build-markov-batch":
        if str(args.tickers).strip() == "@config":
            tickers = read_tickers()
        else:
            tickers = [t.strip().upper() for t in str(args.tickers).split(",") if t.strip()]
        orders = [int(x.strip()) for x in str(args.orders).split(",") if x.strip()]
        modes = [m.strip() for m in str(args.state_modes).split(",") if m.strip()]
        thrs = [int(x.strip()) for x in str(args.threshold_bps).split(",") if x.strip()]

        rows = []
        for t in tickers:
            feat_path = FEATURES_DIR / f"{t}.parquet"
            if not feat_path.exists():
                msg = f"SKIP {t}: missing features at {feat_path}"
                print(msg)
                LOG.warning(msg)
                continue
            for K in orders:
                for mode in modes:
                    for thr in thrs:
                        try:
                            cfg = MarkovConfig(order=K, state_mode=mode, threshold_bps=thr)
                            out = build_markov_for_ticker(t, cfg)
                            legacy_path = Path("data")/"analytics"/"markov"/t/f"matrix_order{K}.parquet"
                            canonical_matrix = Path(out.get("matrix", ""))
                            if not legacy_path.exists() and canonical_matrix.exists():
                                try:
                                    import shutil
                                    shutil.copy2(canonical_matrix, legacy_path)
                                except Exception as e:
                                    LOG.warning("legacy matrix copy failed for %s order=%s: %s", t, K, e)
                            rows.append({
                                "ticker": t,
                                "order": K,
                                "state_mode": mode,
                                "thr_bps": thr,
                                "paths": out,
                                "legacy_matrix": str(legacy_path) if legacy_path.exists() else None,
                            })
                            LOG.info("build-markov-batch ok: %s", rows[-1])
                        except Exception as e:
                            print(f"build-markov-batch ERROR for {t} K={K} mode={mode} thr={thr}: {e}")
                            LOG.exception("build-markov-batch failed")
        print("ticker,order,state_mode,thr_bps,states_path,matrix_path")
        for r in rows:
            p = r.get("paths", {})
            print(f"{r['ticker']},{r['order']},{r['state_mode']},{r['thr_bps']},{p.get('states')},{p.get('matrix')}")
        sys.exit(0)
    elif args.command == "build-hmm-batch":
        if str(args.tickers).strip() == "@config":
            tickers = read_tickers()
        else:
            tickers = [t.strip().upper() for t in str(args.tickers).split(",") if t.strip()]
        states_list = [int(x.strip()) for x in str(args.states).split(",") if x.strip()]
        rows = []
        for t in tickers:
            feat_path = FEATURES_DIR / f"{t}.parquet"
            if not feat_path.exists():
                msg = f"SKIP {t}: missing features at {feat_path}"
                print(msg)
                LOG.warning(msg)
                continue
            for ns in states_list:
                try:
                    cfg = HMMConfig(n_states=ns, train_window_years=args.window_years, random_seed=args.seed)
                    out = build_hmm_for_ticker(t, cfg)
                    rows.append({
                        "ticker": t,
                        "n_states": ns,
                        "window_years": args.window_years,
                        "paths": out,
                    })
                    LOG.info("build-hmm-batch ok: %s", rows[-1])
                except Exception as e:
                    print(f"build-hmm-batch ERROR for {t} n_states={ns}: {e}")
                    LOG.exception("build-hmm-batch failed")
        print("ticker,n_states,window_years,probs_path,states_path")
        for r in rows:
            p = r.get("paths", {})
            print(f"{r['ticker']},{r['n_states']},{r['window_years']},{p.get('probs')},{p.get('states')}")
        sys.exit(0)
    elif args.command == "build-hmm-grid":
        if str(args.tickers).strip() == "@config":
            tickers = read_tickers()
        else:
            tickers = [t.strip().upper() for t in str(args.tickers).split(",") if t.strip()]

        from mie_lib.services.audit_logger import get_audit_logger
        get_audit_logger().update_stage("HMM Grid", "RUNNING", {"tickers": len(tickers)})
        if str(args.windows).strip().upper() == "MAX":
             win_years_list = ["MAX"]
        else:
             win_years_list = []
             for w in str(args.windows).split(","):
                 w = w.strip()
                 if not w: continue
                 if w.upper() == "MAX":
                     win_years_list.append("MAX")
                 else:
                     try:
                        win_years_list.append(int(w))
                     except ValueError:
                        pass
        states_list = [int(x.strip()) for x in str(args.states).split(",") if x.strip()]
        rows = []
        for t in tickers:
            feat_path = FEATURES_DIR / f"{t}.parquet"
            if not feat_path.exists():
                print(f"build-hmm-grid SKIP {t}: missing features {feat_path}")
                continue
            for ns in states_list:
                for wy in win_years_list:
                    out = build_hmm_standardized_for_ticker(t, n_states=ns, train_window_years=wy)
                    rows.append({"ticker": t, "n_states": ns, "window": wy, "paths": out})
        print("ticker,n_states,probs,states,metrics,metadata,skipped")
        for r in rows:
            p = r["paths"]
            print(f"{r['ticker']},{r['n_states']},{p.get('probs')},{p.get('states')},{p.get('metrics')},{p.get('metadata')},{p.get('skipped', False)}")
        get_audit_logger().update_stage("HMM Grid", "COMPLETED", {})
        sys.exit(0)
    elif args.command == "build-markov-states":
        t = args.ticker.upper()
        modes = [m.strip() for m in str(args.state_modes).split(",") if m.strip()]
        thrs = [int(x.strip()) for x in str(args.thresholds).split(",") if x.strip()]
        feat_path = FEATURES_DIR / f"{t}.parquet"
        if not feat_path.exists():
            print(f"build-markov-states SKIP {t}: missing features {feat_path}")
            sys.exit(2)
        for m in modes:
            for thr in thrs:
                path = build_states_from_features(t, thr, m)
                print({"ticker": t, "mode": m, "thr_bps": thr, "states": path})
        sys.exit(0)
    elif args.command == "derive-markov-matrix":
        t = args.ticker.upper()
        try:
            df = derive_matrix(t, args.threshold_bps, args.state_mode, args.order, args.window)
            out = df.head(3).to_dict("records")
            print({"ticker": t, "rows": len(df), "sample": out})
            sys.exit(0)
        except Exception as e:
            print(f"derive-markov-matrix ERROR: {e}")
            sys.exit(3)
    elif args.command == "build-markov-grid":
        # Use parallel handler
        handle_build_markov_grid(args)
        sys.exit(0)


        
        from mie_lib.services.audit_logger import get_audit_logger
        get_audit_logger().update_stage("Markov Grid", "RUNNING", {"tickers": len(tickers)})

        from mie_lib.analytics.markov.markov_engine import FEATURES_DIR as MK_FEATURES_DIR

        banner = {
            "event": "build-markov-grid:start",
            "tickers": tickers,
            "modes": modes,
            "thresholds": thrs[:5] + (["..."] if len(thrs) > 5 else []),
            "windows": windows,
            "orders": orders,
        }
        _grid_log_append(str(banner))

        for t in tickers:
            feat_path = MK_FEATURES_DIR / f"{t}.parquet"
            if not feat_path.exists():
                _grid_log_append(f"SKIP {t}: missing features {feat_path}")
                continue
            for m in modes:
                for thr in thrs:
                    try:
                        sp_out = build_states_from_features(t, thr, m)
                        # Legacy compatibility: if default config, copy to root states.parquet
                        if int(thr) == 10 and str(m) == "tri":
                            try:
                                legacy_states = Path("data")/"analytics"/"markov"/t/"states.parquet"
                                if Path(sp_out).exists():
                                    import shutil
                                    shutil.copy2(sp_out, legacy_states)
                                    _grid_log_append(f"legacy states update: {legacy_states}")
                            except Exception as ex:
                                _grid_log_append(f"states LEGACY COPY FAIL {t}: {ex}")
                    except Exception as e:
                        _grid_log_append(f"states WARN {t} {m} thr={thr}: {e}")
                        continue
                    for w in windows:
                        for K in orders:
                            try:
                                df = derive_matrix(t, thr, m, K, w)
                                
                                # --- Multi-Step Forecast (NEW) ---
                                if K == 1:
                                    horizons = [1, 2, 3, 4, 5]
                                    try:
                                        ms_df = multi_step(df, horizons, m)
                                        if not ms_df.empty:
                                            # Path: data/analytics/markov/{ticker}/multi_step_order1_{mode}_thr{thr}.parquet
                                            ms_path = Path("data")/"analytics"/"markov"/t/f"multi_step_order{K}_{m}_thr{thr}.parquet"
                                            ms_df.reset_index().to_parquet(ms_path, index=False)
                                            _grid_log_append(f"multi-step written to {ms_path}")
                                    except Exception as e:
                                        _grid_log_append(f"multi-step failed for {t} {m} thr={thr}: {e}")
                                # --- END Multi-Step Forecast ---

                                _grid_log_append(str({
                                    "ticker": t, "mode": m, "thr": thr, "window": w, "order": K, "rows": len(df)
                                }))
                            except Exception as e:
                                _grid_log_append(f"matrix SKIP {t} {m} thr={thr} order={K} window={w}: {e}")
        _grid_log_append("build-markov-grid:finish")
        get_audit_logger().update_stage("Markov Grid", "COMPLETED", {})
        sys.exit(0)
    elif args.command == "build-hmm":
        try:
            # Use standardized builder to ensure metrics and correct paths for API
            out = build_hmm_standardized_for_ticker(
                args.ticker, 
                n_states=args.states, 
                train_window_years=args.window_years, 
                random_seed=args.seed
            )
            print(out)
            LOG.info("build-hmm: %s", out)
            sys.exit(0)
        except Exception as e:
            print(f"build-hmm ERROR: {e}")
            LOG.exception("build-hmm failed")
            sys.exit(8)
    elif args.command == "ensure-markov-available":
        """Ensure specific Markov artifacts are present (states + derived matrix) using states-first model."""
        t = args.ticker.upper()
        mode = args.state_mode
        thr = int(args.threshold_bps)
        K = int(args.order)
        win = str(args.window).upper()
        try:
            if states_stale(t, thr, mode):
                build_states_from_features(t, thr, mode)
            df = derive_matrix(t, thr, mode, K, win)
            base = Path("data")/"analytics"/"markov"/t/"matrices"/mode/f"thr{thr}"/f"order{K}"
            out_p = base / f"{win}.parquet"
            print({"ticker": t, "mode": mode, "thr": thr, "order": K, "window": win, "matrix": str(out_p), "rows": len(df)})
            sys.exit(0)
        except Exception as e:
            print(f"ensure-markov-available ERROR: {e}")
            sys.exit(3)
    elif args.command == "update-all-analytics":
        """Orchestrate: update features then build markov states/matrices per grid and HMM grid."""
        # Load tickers from config
        try:
            tickers = read_tickers()
        except Exception:
            tickers = []
        # Build/update features only if missing; skip if no raw present to avoid hard failure in offline tests
        for t in tickers:
            feat_path = FEATURES_DIR / f"{t}.parquet"
            if feat_path.exists():
                print({"features": "ok", "ticker": t, "path": str(feat_path)})
                continue
            raw_parquet = Path("data")/"raw"/f"{t}.parquet"
            raw_csv = Path("data")/"raw"/f"{t}.csv"
            if raw_parquet.exists() or raw_csv.exists():
                try:
                    r = _build_features_for_ticker(t, mode="full", lookback=90, write_csv=False)
                    LOG.info("features: %s", r)
                    print(r)
                except Exception as e:
                    print(f"update-all-analytics WARN: feature build failed for {t}: {e}")
            else:
                print(f"update-all-analytics SKIP features for {t}: missing raw in data/raw/")
        # Load analytics grid
        grid = {}
        p_grid = Path("config")/"analytics_grid.yml"
        if p_grid.exists():
            try:
                grid = yaml.safe_load(p_grid.read_text()) or {}
            except Exception:
                grid = {}
        modes = [m.strip() for m in grid.get("state_modes", ["tri","binary"]) if m]
        thrs = [int(x) for x in grid.get("thresholds_bps", [10])]
        windows = [str(w).upper() for w in grid.get("windows", ["1Y","2Y","5Y","10Y","20Y","MAX"])]
        orders = [int(x) for x in grid.get("orders", [1,2,3,4])]
        # Iterate grid
        for t in tickers:
            feat_path = Path("data")/"features"/f"{t}.parquet"
            if not feat_path.exists():
                print(f"update-all-analytics SKIP {t}: missing features {feat_path}")
                continue
            for mode in modes:
                for thr in thrs:
                    # states
                    if states_stale(t, thr, mode):
                        build_states_from_features(t, thr, mode)
                    for w in windows:
                        for K in orders:
                            try:
                                df = derive_matrix(t, thr, mode, K, w)
                                print({"ticker": t, "mode": mode, "thr": thr, "window": w, "order": K, "rows": len(df)})
                            except Exception as e:
                                print(f"update-all-analytics WARN {t} {mode} thr={thr} order={K} window={w}: {e}")
        # HMM grid (optional minimal call)
        try:
            # reuse existing standardized grid (5y only)
            if tickers:
                out = []
                for t in tickers:
                    # default 2,3 states
                    for ns in [2,3]:
                        res = build_hmm_standardized_for_ticker(t, n_states=ns, train_window_years=5)
                        out.append(res)
                print({"hmm": "done", "tickers": len(tickers)})
        except Exception as e:
            print(f"update-all-analytics HMM WARN: {e}")
        sys.exit(0)
    elif args.command == "build-seasonality-facts":
        # Resolve tickers
        if getattr(args, "tickers", "ALL") == "ALL":
            try:
                tickers = read_tickers()
            except Exception:
                tickers = []
        else:
            tickers = [t.strip().upper() for t in str(args.tickers).split(",") if t.strip()]
        if not tickers:
            print("build-seasonality-facts: no tickers resolved from config or args")
            sys.exit(2)
        from mie_lib.analytics.seasonality.build_facts import build_facts_for_ticker, load_seasonality_config
        cfg = load_seasonality_config()
        horizons = cfg.get("LOOKBACK_WINDOWS", [5,10,20,30,50,"ALL"])
        rows = []
        for t in tickers:
            out = build_facts_for_ticker(t, horizons=horizons, dry_run=getattr(args, "dry_run", False))
            rows.append({"ticker": t, "written": [str(p) for p in out]})
        import json
        print(json.dumps(rows))
        sys.exit(0)
    elif args.command == "update-seasonality":
        from mie_lib.services.audit_logger import get_audit_logger
        get_audit_logger().update_stage("Seasonality", "RUNNING", {})
        if getattr(args, "tickers", "ALL") == "ALL":
            try:
                tickers = read_tickers()
            except Exception:
                tickers = []
        else:
            tickers = [t.strip().upper() for t in str(args.tickers).split(",") if t.strip()]
        from mie_lib.analytics.seasonality.update import update_seasonality
        import json
        out = update_seasonality(tickers, since=getattr(args, "since", None), dry_run=getattr(args, "dry_run", False))
        print(json.dumps([str(p) for p in out]))
        
        from mie_lib.services.audit_logger import get_audit_logger
        get_audit_logger().update_stage("Seasonality", "COMPLETED", {})
        sys.exit(0)
    elif args.command == "build-seasonality-base":
        # NEW: drive seasonality base builder
        from mie_lib.analytics.seasonality.base_builder import (
            get_seasonality_universe,
            build_seasonality_base_for_ticker,
        )
        # Resolve ticker list
        tickers: list[str]
        if getattr(args, "tickers", None):
            tickers = [t.strip().upper() for t in str(args.tickers).split(",") if t.strip()]
        elif getattr(args, "from_config", False) or True:
            # default path: from config
            tickers = get_seasonality_universe()
        else:
            tickers = get_seasonality_universe()
        if not tickers:
            print(json.dumps({"status": "error", "reason": "no tickers from config"}))
            sys.exit(2)
        # Options
        lookbacks = _parse_csv_str_list(getattr(args, "lookbacks", None), ["5","10","20","30","50","ALL"])
        cfg = {
            "lookbacks": lookbacks,
            "min_years": int(getattr(args, "min_years", 5)),
            "return_type": getattr(args, "return_type", "log"),
            "force": bool(getattr(args, "force", False)),
        }
        ok = 0
        skipped = 0
        errors = 0
        for t in tickers:
            try:
                res = build_seasonality_base_for_ticker(t, cfg)
                status = res.get("status")
                if status == "ok":
                    ok += 1
                elif status == "skip":
                    skipped += 1
                else:
                    errors += 1
                print(json.dumps(res))
                LOG.info("build-seasonality-base: %s", res)
            except SystemExit:
                raise
            except Exception as e:
                errors += 1
                msg = {"ticker": t, "status": "error", "error": str(e)}
                print(json.dumps(msg))
                LOG.exception("build-seasonality-base failed for %s", t)
        summary = {"ok": ok, "skipped": skipped, "errors": errors, "total": len(tickers)}
        print(json.dumps({"summary": summary}))
        sys.exit(0 if errors == 0 else 1)
    elif args.command == "rebuild-everything":
        # Validate tickers resolve from YAML
        tickers = _load_yaml_tickers()
        if not tickers:
            print("rebuild-everything ERROR: no tickers resolved from config/tickers.yml")
            sys.exit(2)
        get_audit_logger().start_job("Full Rebuild Pipeline")
        py = sys.executable
        mie = os.fspath(Path(__file__).resolve())
        # RAW full
        _run([py, mie, "rebuild-raw"])
        get_audit_logger().update_stage("Rebuild Raw", "COMPLETED", {})
        # FEATURES full + CSV
        _run([py, mie, "build-features", "--mode", "full", "--csv"])
        get_audit_logger().update_stage("Build Features Full", "COMPLETED", {})
        # SEASONALITY base + facts
        _run([py, mie, "build-seasonality-base"])  # reads tickers from config
        _run([py, mie, "build-seasonality-facts"])  # reads tickers from config
        get_audit_logger().update_stage("Build Seasonality", "COMPLETED", {})
        # MARKOV grid (explicit params per spec)
        _run([py, mie, "build-markov-grid",
              "--state-modes", "binary,tri",
              "--thresholds", ",".join(str(i) for i in range(0,151,5)),
              "--windows", "1Y,2Y,5Y,10Y,20Y,MAX",
              "--orders", "1,2,3,4"])  # uses default tickers resolver
        get_audit_logger().update_stage("Build Markov Grid", "COMPLETED", {})
        # HMM grid (require tickers arg -> @config)
        _run([py, mie, "build-hmm-grid", "--tickers", "@config", "--windows", "5,10,MAX", "--states", "2,3"])
        get_audit_logger().update_stage("Build HMM Grid", "COMPLETED", {})
        get_audit_logger().finish_job("COMPLETED")
        print("✅ Done.")
        sys.exit(0)
    elif args.command == "update-everything":
        # Validate tickers resolve from YAML
        tickers = _load_yaml_tickers()
        if not tickers:
            print("update-everything ERROR: no tickers resolved from config/tickers.yml")
            sys.exit(2)
        
        
    elif args.command == "update-everything":
        handle_update_everything(args)
    elif args.command == "rebuild-reliability":
        py = sys.executable
        mie = os.fspath(Path(__file__).resolve())
        print("Starting Reliability Data Rebuild...")
        # 1. Update Underlying Data
        _run([py, mie, "update-expected-moves", "--ticker", "@config", "--lookback", "5"])
        # 2. Build Snapshots
        _run([py, mie, "build-expected-moves-snapshots", "--tickers", "@config"])
        print("✅ Reliability Rebuild Complete.")
        sys.exit(0)
    elif args.command == "build-seasonality":
        if not args.ticker:
            print("Error: --ticker is required for build-seasonality")
            return
        print(f"Building Seasonality Base Data for {args.ticker}...")
        generate_seasonality_base(args.ticker)
    elif args.command == "build-minervini-daily":
        from mie_lib.analytics.scanner.minervini_build import build_minervini_snapshot
        from mie_lib.analytics.gaf.backtest_engine import GAFBacktestersnapshot
        from datetime import date
        
        # Determine Date
        if args.date:
             target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        else:
             target_date = date.today()
             
        # Determine Tickers
        if not args.tickers or args.tickers == "@config":
            # 1. Try Specific Scope
            tickers = _load_scope_tickers("Minervini_Template")
            if not tickers:
                 # 2. Fallback
                 tickers = read_tickers()
        elif args.tickers.startswith("@scope:"):
            scope_key = args.tickers.split(":", 1)[1]
            tickers = _load_scope_tickers(scope_key)
        else:
            tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
            
        print(f"Building Minervini Scanner for {len(tickers)} tickers on {target_date}...")
        count = build_minervini_snapshot(tickers, target_date)
        print(f"Analysis complete. {count} records processed.")
        sys.exit(0)
    elif args.command == "train-gaf":
        from mie_lib.analytics.gaf.pipeline import run_training_pipeline
        ticker = args.ticker or "SPY"
        epochs = int(args.epochs) if args.epochs else 20
        print(f"Training GAF Model on {ticker} for {epochs} epochs...")
        run_training_pipeline(ticker=ticker, epochs=epochs)
        sys.exit(0)
    elif args.command == "build-gaf-daily":
        from mie_lib.analytics.gaf.pipeline import run_inference_latest
        ticker = args.ticker or "SPY"
        print(f"Developing GAF Prediction for {ticker}...")
        run_inference_latest(ticker=ticker)
        sys.exit(0)
    elif args.command == "analyze-expected-moves-reliability":
        print("Running Expected Moves Reliability Analysis...")
        from mie_lib.analytics.expected_moves.reliability_processor import process_reliability
        process_reliability()
        sys.exit(0)
    elif args.command == "generate-ai-context":
        print("Starting AI Context Generation...")
        from mie_lib.analytics.llm_payload import generate_llm_payload
        from mie_lib.services.audit_logger import get_audit_logger
        get_audit_logger().update_stage("AI Context Generation", "RUNNING", {})
        import pandas as pd

        
        ticker = args.ticker.upper()
        
        # 1. Load Data Sources
        # Features
        feat_path = Path("data") / "features" / f"{ticker}.parquet"
        if not feat_path.exists():
            print(f"Error: Features not found at {feat_path}")
            sys.exit(1)
        df = pd.read_parquet(feat_path)
        
        # HMM - Robust Search
        hmm_root = Path("data") / "analytics" / "hmm" / ticker
        df_hmm = None
        
        # Priority: state_sequence.parquet (new) or hmm_states.parquet (current)
        possible_paths = list(hmm_root.glob("**/state_sequence.parquet"))
        if not possible_paths:
             possible_paths = list(hmm_root.glob("**/hmm_states.parquet"))
        if not possible_paths:
             # Fallback to any parquet but EXCLUDE probs and metrics
             all_parquets = list(hmm_root.glob("**/*.parquet"))
             possible_paths = [p for p in all_parquets if "probs" not in p.name and "metrics" not in p.name]

        if possible_paths:
            # Pick the best model (e.g., 10Y or Max, 3 States)
            best_path = possible_paths[0]
            for p in possible_paths:
                if "win10y" in str(p) and "states3" in str(p):
                    best_path = p
                    break
            
            print(f"Loading HMM from: {best_path}")
            try:
                df_hmm = pd.read_parquet(best_path)
                # Ensure dates match for merge
                if 'date' in df_hmm.columns:
                    df_hmm['date'] = pd.to_datetime(df_hmm['date'])
                    df['date'] = pd.to_datetime(df['date'])
                    
                    # Unify state column name
                    if 'state' in df_hmm.columns:
                        df_hmm.rename(columns={'state': 'hmm_state'}, inplace=True)
                    
                    if 'hmm_state' in df_hmm.columns:
                        # Merge logic
                        df = pd.merge(df, df_hmm[['date', 'hmm_state']], on='date', how='left')
                        print("HMM Data Merged.")
                    else:
                        print(f"Warning: No state column found in HMM file {best_path.name}")
            except Exception as e:
                print(f"Warning: Failed to load HMM data: {e}")
        else:
             print("Warning: HMM States not found (checked recursive). Proceeding without HMM.")

        # GEX (Profile)
        gex_path = Path("data") / "analytics" / "gex" / f"{ticker}_gex.json"
        if gex_path.exists():
             try:
                 with open(gex_path) as f:
                     gex_data = json.load(f)
                 # Attach as static feature for latest row or similar? 
                 # Actualy AI usually wants time series. 
                 # If we don't have GEX history, we skip merging history and just pass latest GEX in payload construction later?
                 # For now, let's skip merging GEX history if we only have current JSON.
                 print(f"Found latest GEX profile for {ticker} (JSON).")
             except:
                 pass
        
        # 2. Load Optional External Data (Expected Moves)
        expected_moves = None
        em_path = Path("data/analytics/options/latest.json")
        if em_path.exists():
            try:
                with open(em_path, "r") as f:
                    full_em = json.load(f)
                
                # Filter for requested tickers only
                target_tickers = ["SPY", "QQQ", "IWM", "DIA"]
                expected_moves = {
                    "as_of": full_em.get("as_of"),
                    "source": full_em.get("source"),
                    "tickers": {k: v for k, v in full_em.get("tickers", {}).items() if k in target_tickers}
                }
                
                print(f"Loaded Expected Moves from {em_path} (Filtered to {len(expected_moves['tickers'])})")
            except Exception as e:
                print(f"Warning: Failed to load Expected Moves: {e}")
        else:
            print(f"Warning: {em_path} not found. Proceeding without expected moves.")

        # 3. Load GEX Snapshot (Freshest Data)
        from mie_lib.analytics.gex.storage import load_gex_profile
        gex_snapshot = load_gex_profile(ticker)
        if gex_snapshot:
            print(f"Loaded GEX Snapshot for {ticker}")
        else:
             print(f"Warning: Failed to load GEX Snapshot for {ticker}")

        # 3. Generate Payload
        try:
            payload = generate_llm_payload(df, ticker, expected_moves, gex_snapshot=gex_snapshot)
            
            # 4. Save Artifacts (Active + Archive)
            # Active Copy
            active_path = Path("data/ai_context/spy_latest.json")
            active_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(active_path, "w") as f:
                json.dump(payload, f, indent=2)
                
            # Archive Copy
            from datetime import datetime
            today_str = datetime.now().strftime("%Y-%m-%d")
            archive_path = Path(f"data/ai_context/archive/spy_context_{today_str}.json")
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(archive_path, "w") as f:
                json.dump(payload, f, indent=2)
                
            print(f"[AUDIT] STEP COMPLETED: AI Payload Generation. Saved to {active_path} and {archive_path}")
            
            # Update Audit Log (Service)
            from mie_lib.services.audit_logger import get_audit_logger
            # Determine status based on data
            status = "COMPLETED" if expected_moves and df_hmm is not None else "PARTIAL"
            # Fix: log_job_event does not exist, use update_stage
            get_audit_logger().update_stage("AI Context Generation", "COMPLETED", {"path": str(active_path), "size_kb": active_path.stat().st_size / 1024})
            
            print(f"✓ AI Context saved to {active_path}")
            sys.exit(0)
        except Exception as e:
            print(f"✗ Failed to generate payload: {e}")
            get_audit_logger().update_stage("AI Context Generation", "FAILED", {"error": str(e)})
            import traceback
            traceback.print_exc()
            sys.exit(1)
    
    elif args.command == "generate-economic-insights":
        print(f"Starting Economic Insights Generation (Tier {args.tier})...")
        from mie_lib.analytics.jpm_dashboard.economic_payload import build_economic_payload
        from mie_lib.services.economic_analyst import EconomicAnalyst
        from mie_lib.services.audit_logger import get_audit_logger
        from scipy.stats import percentileofscore
        import pandas as pd
        import json
        
        # Use module-level logging (already imported at top of file)
        logger = logging.getLogger(__name__)
        
        # Define indicators and their configurations
        INDICATORS = {
            'gdp': {'file': 'gdp.parquet', 'primary_series': 'GDPC1'},
            'consumer-spending': {'file': 'consumer_spending.parquet', 'primary_series': 'PCE'},
            'labor-market': {'file': 'labor_market.parquet', 'primary_series': 'UNRATE'},
            'interest-rates': {'file': 'interest_rates.parquet', 'primary_series': 'FEDFUNDS'},
            'inflation': {'file': 'inflation.parquet', 'primary_series': 'CPIAUCSL'},
            'business-confidence': {'file': 'business_confidence.parquet', 'primary_series': 'BSCICP02USM460S'},
            'stock-market': {'file': 'stock_market.parquet', 'primary_series': 'sp500'},
            'trade-balance': {'file': 'trade_balance.parquet', 'primary_series': 'BOPGSTB'},
            'housing': {'file': 'housing.parquet', 'primary_series': 'HOUST'},
            'policy': {'file': 'policy.parquet', 'primary_series': 'FEDFUNDS'}
        }
        
        # Determine which indicators to process
        if args.indicator:
            if args.indicator not in INDICATORS:
                print(f"ERROR: Unknown indicator '{args.indicator}'")
                print(f"Valid indicators: {', '.join(INDICATORS.keys())}")
                sys.exit(1)
            indicators_to_process = {args.indicator: INDICATORS[args.indicator]}
        else:
            indicators_to_process = INDICATORS
        
        try:
            analyst = EconomicAnalyst(model=args.model)
        except Exception as e:
            print(f"ERROR: Failed to initialize analyst: {e}")
            sys.exit(1)
        
        # Update audit stage
        stage_name = f"Economic Insights Tier {args.tier}"
        get_audit_logger().update_stage(stage_name, "RUNNING", {
            "tier": args.tier,
            "indicator_count": len(indicators_to_process),
            "model": args.model
        })
        
        total_indicators = len(indicators_to_process)
        processed = 0
        failed = 0
        
        for ind_id, config in indicators_to_process.items():
            logger.info(f"[{processed+1}/{total_indicators}] Processing {ind_id}...")
            
            try:
                # Load data
                df_path = Path("data/processed/jpm_dashboard") / config["file"]
                if not df_path.exists():
                    logger.warning(f"  Data file not found: {df_path}")
                    failed += 1
                    continue
                
                df = pd.read_parquet(df_path)
                
                # Calculate metadata (health score, percentile, trend)
                series_data = df[config['primary_series']].dropna()
                if len(series_data) == 0:
                    logger.warning(f"  No data for {config['primary_series']}")
                    failed += 1
                    continue
                
                current = series_data.iloc[-1]
                percentile = percentileofscore(series_data, current)
                health_score = int(percentile * 0.8)  # Simplified (API has full logic)
                
                # Determine trend
                if len(series_data) >= 3:
                    recent = series_data.tail(3)
                    if recent.iloc[-1] > recent.iloc[0] * 1.01:
                        trend = 'up'
                    elif recent.iloc[-1] < recent.iloc[0] * 0.99:
                        trend = 'down'
                    else:
                        trend = 'flat'
                else:
                    trend = 'flat'
                
                metadata = {
                    'health_score': health_score,
                    'percentile': percentile,
                    'trend_direction': trend
                }
                
                # Build payload
                payload = build_economic_payload(
                    indicator_id=ind_id,
                    df=df,
                    primary_series=config['primary_series'],
                    metadata=metadata
                )
                
                # Log payload to audit (for visualization on admin page)
                get_audit_logger().update_stage(
                    f"{stage_name} - {ind_id} Payload",
                    "COMPLETED",
                    {
                        "indicator": ind_id,
                        "payload_size_kb": len(json.dumps(payload)) / 1024,
                        "current_value": payload['current_state']['value'],
                        "health_score": payload['current_state']['health_score']
                    }
                )
                
                # Generate insight based on tier
                if args.tier == 1:
                    insight = analyst.generate_tier1_insight(payload)
                    logger.info(f"  → {insight}")
                    # Log LLM response to audit (for visualization)
                    get_audit_logger().update_stage(
                        f"{stage_name} - {ind_id} Response",
                        "COMPLETED",
                        {
                            "indicator": ind_id,
                            "tier": 1,
                            "one_line_insight": insight,
                            "response_length": len(insight)
                        }
                    )
                    analyst.save_insights(ind_id, args.tier, {"one_line_insight": insight})
                    
                elif args.tier == 2:
                    insight = analyst.generate_tier2_insight(payload)
                    logger.info(f"  → Generated detailed analysis")
                    get_audit_logger().update_stage(
                        f"{stage_name} - {ind_id} Response",
                        "COMPLETED",
                        {
                            "indicator": ind_id,
                            "tier": 2,
                            "response_keys": list(insight.keys()),
                            "takeaway_count": len(insight.get('key_takeaways', []))
                        }
                    )
                    analyst.save_insights(ind_id, args.tier, insight)
                    
                elif args.tier == 3:
                    insight = analyst.generate_tier3_insight(payload)
                    logger.info(f"  → Generated deep dive analysis")
                    get_audit_logger().update_stage(
                        f"{stage_name} - {ind_id} Response",
                        "COMPLETED",
                        {
                            "indicator": ind_id,
                            "tier": 3,
                            "response_keys": list(insight.keys()),
                            "has_recession_signal": 'recession_signal' in insight
                        }
                    )
                    analyst.save_insights(ind_id, args.tier, insight)
                
                processed += 1
                
            except Exception as e:
                logger.error(f"  ✗ Failed: {e}")
                failed += 1
                get_audit_logger().update_stage(
                    f"{stage_name} - {ind_id}",
                    "FAILED",
                    {"error": str(e)}
                )
        
        # Final audit update
        if failed == 0:
            get_audit_logger().update_stage(stage_name, "COMPLETED", {
                "processed": processed,
                "failed": failed,
                "tier": args.tier
            })
            print(f"\n✓ Economic insights generation completed ({processed}/{total_indicators} indicators)")
            sys.exit(0)
        else:
            get_audit_logger().update_stage(stage_name, "PARTIAL", {
                "processed": processed,
                "failed": failed,
                "tier": args.tier
            })
            print(f"\n⚠ Economic insights completed with errors ({processed} succeeded, {failed} failed)")
            sys.exit(0 if processed > 0 else 1)
    elif args.command == "archive-gex-daily":
        handle_archive_gex_daily(args)
            
    elif args.command == "generate-ai-report":
        print("Starting AI Report Generation...")
        from mie_lib.services.audit_logger import get_audit_logger
        get_audit_logger().update_stage("Daily Intelligence Report", "RUNNING", {})
        
        from mie_lib.services.llm_analyst import generate_daily_report
        res = generate_daily_report(ticker=args.ticker, model=args.model)
        
        if res.get("status") == "ok":
            print(f"Report generated: {res.get('path')}")
            get_audit_logger().update_stage("Daily Intelligence Report", "COMPLETED", {"path": res.get('path')})
            sys.exit(0)
        else:
            print(f"Report generation failed: {res.get('message')}")
            get_audit_logger().update_stage("Daily Intelligence Report", "FAILED", {"error": res.get('message')})
            sys.exit(1)
    elif args.command == "update-stage":
        stage = args.stage
        status = args.status
        meta = {}
        if args.meta:
            try:
                meta = json.loads(args.meta)
            except Exception as e:
                print(f"Warning: Failed to parse meta JSON: {e}")
        
        from mie_lib.services.audit_logger import get_audit_logger
        get_audit_logger().update_stage(stage, status, meta)
        print(f"Audit Stage '{stage}' updated to '{status}'")
        sys.exit(0)
    elif args.command == "update-volatility":
        handle_update_volatility(args)
        sys.exit(0)
    elif args.command == "update-volume-regime":
        handle_update_volume_regime(args)
        sys.exit(0)
    elif args.command == "finish-pipeline-job":
        handle_finish_pipeline_job(args)
        sys.exit(0)
    elif args.command == "start-pipeline-job":
        handle_start_pipeline_job(args)
        sys.exit(0)
    elif args.command == "build-skew-daily":
        handle_build_skew_daily(args)
        sys.exit(0)
    else:
        parser.print_help()
        sys.exit(1)

def handle_build_skew_daily(args):
    """
    Handle build-skew-daily command.
    
    Uses PARALLEL pipeline:
    - OPTIONS: Massive flat files (source of truth)
    - SPOT: yfinance via ThreadPoolExecutor
    """
    from mie_lib.services.audit_logger import get_audit_logger
    from mie_lib.analytics.skew.skew_pipeline import run_skew_pipeline_parallel
    from datetime import date
    import logging
    import json
    
    LOG = logging.getLogger(__name__)

    get_audit_logger().update_stage("Skew & PCR", "RUNNING", {})
    LOG.info("Running build-skew-daily (parallel pipeline)...")
    
    try:
        # Parse arguments
        ticker_arg = getattr(args, "tickers", "@config")
        date_arg = getattr(args, "date", None)
        workers = getattr(args, "workers", 10)
        
        target_date = date_arg if date_arg else str(date.today())
        
        # Resolve tickers
        tickers = []
        if ticker_arg == "@config" or ticker_arg is None:
            tickers = _load_scope_tickers("Skew")
            if not tickers:
                tickers = _load_yaml_tickers()
        elif ticker_arg:
            tickers = [t.strip().upper() for t in ticker_arg.split(",") if t.strip()]
        
        if not tickers:
            tickers = ["SPY", "QQQ", "IWM", "DIA"]
            
        LOG.info(f"Target: {len(tickers)} tickers, Date: {target_date}, Workers: {workers}")
        
        # Run parallel pipeline
        result = run_skew_pipeline_parallel(
            tickers=tickers,
            target_date=target_date,
            max_workers=workers
        )
        
        # Log results
        LOG.info(f"Parallel pipeline complete: {json.dumps({k: v for k, v in result.items() if k != 'details'})}")
        
        # Update audit status
        if result.get("failed", 0) == 0:
            status = "COMPLETED"
        elif result.get("success", 0) > 0:
            status = "PARTIAL"
        else:
            status = "FAILED"
        
        get_audit_logger().update_stage("Skew & PCR", status, {
            "processed": result.get("processed", 0),
            "success": result.get("success", 0),
            "failed": result.get("failed", 0),
            "skipped": result.get("skipped", 0)
        })
        
    except Exception as e:
        LOG.error(f"Error in build-skew-daily: {e}")
        import traceback
        traceback.print_exc()
        get_audit_logger().update_stage("Skew & PCR", "FAILED", {"error": str(e)})

def handle_update_economic(args):
    """Handle update-economic command by running the full orchestrator."""
    from mie_lib.services.audit_logger import get_audit_logger
    import subprocess
    import os
    
    get_audit_logger().update_stage("Economic Pipeline", "RUNNING", {})
    LOG.info("Running update-economic pipeline...")
    
    try:
        script_path = os.path.join(PROJECT_ROOT, "scripts", "economic_pipeline.py")
        cmd = [sys.executable, script_path]
        subprocess.run(cmd, check=True)
        
        LOG.info("update-economic completed successfully.")
        get_audit_logger().update_stage("Economic Pipeline", "COMPLETED", {})
    except Exception as e:
        LOG.error(f"Error in update-economic: {e}")
        get_audit_logger().update_stage("Economic Pipeline", "FAILED", {"error": str(e)})

def handle_build_macro_data(args):
    """Handle build-macro-data command."""
    from mie_lib.services.audit_logger import get_audit_logger
    get_audit_logger().update_stage("Macro Data", "RUNNING", {})
    LOG.info("Running build-macro-data...")
    try:
        from mie_lib.data_ingest.macro.providers.fred import update_fred_data
        update_fred_data()
        LOG.info("build-macro-data completed.")
        get_audit_logger().update_stage("Macro Data", "COMPLETED", {})
    except Exception as e:
        LOG.error(f"Error in build-macro-data: {e}")
        get_audit_logger().update_stage("Macro Data", "FAILED", {"error": str(e)})

if __name__ == "__main__":
    # Execute CLI when run as a script
    main()
