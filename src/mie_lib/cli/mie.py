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
from datetime import date, datetime, timezone, timedelta
from pathlib import Path

import yaml

# Ensure project root is on sys.path so `src` is importable when running cli scripts
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

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
from mie_lib.utils.paths import HMM_DIR, MARKOV_DIR
from mie_lib.seasonality_engine import generate_seasonality_base

LOG = get_logger("cli")

# ---------- Default Markov grid configuration (authoritative) ----------
DEFAULT_MARKOV_GRID_STATE_MODES = ["binary", "tri"]
DEFAULT_MARKOV_GRID_THRESHOLDS = [i for i in range(0, 151, 5)]  # 0..150 by 5
DEFAULT_MARKOV_GRID_WINDOWS = ["1Y", "2Y", "5Y", "10Y", "20Y", "MAX"]
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

# ---------------- Feature build handler (refactored) -----------------

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
    if tickers_arg and tickers_arg.strip() and tickers_arg.strip() != "@config":
        tickers = [t.strip() for t in tickers_arg.split(",") if t.strip()]
    else:
        # fall back to yaml config, then ingest loader if empty
        tickers = _load_yaml_tickers() or read_tickers()
    if not tickers:
        print("build-features ERROR: no tickers resolved")
        sys.exit(2)
    summary: list[dict] = []
    for t in tickers:
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
    # Non-zero exit if any aborted to surface pipeline issues but keep loop running
    aborted = [r for r in summary if r.get("status") == "error"]
    if aborted:
        sys.exit(3)
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
    ticker = (getattr(args, "ticker", None) or cfg.spot_ticker).upper()
    provider = _resolve_expected_moves_provider_arg(getattr(args, "provider", None), cfg)
    lookback = int(getattr(args, "lookback", 5) or 5)
    include_weekly = bool(getattr(args, "include_weekly_reference", False))
    results = update_expected_moves(
        ticker=ticker,
        lookback_days=lookback,
        provider=provider,
        include_weekly_reference=include_weekly,
    )
    LOG.info(
        "update-expected-moves complete ticker=%s days=%s provider=%s", ticker, len(results), provider.__class__.__name__
    )
    print({"ticker": ticker, "days": len(results)})
    return results


def handle_build_expected_moves_snapshots(args):
    cfg = ExpectedMovesConfig.load()
    tickers_arg = getattr(args, "tickers", None)
    if tickers_arg:
        tickers = [t.strip().upper() for t in tickers_arg.split(",") if t.strip()]
    else:
        tickers = [cfg.spot_ticker.upper()]
    if not tickers:
        raise SystemExit("build-expected-moves-snapshots: no tickers resolved")

    destination_root = Path(getattr(args, "output_dir", "") or DEFAULT_EM_SNAPSHOT_DEST)
    tmp_root = Path(getattr(args, "tmp_dir", "") or DEFAULT_EM_SNAPSHOT_TMP)
    allow_missing = bool(getattr(args, "allow_missing", False))
    weekly_cfg = cfg.weekly_reference or {}
    expect_weekly_reference = bool(weekly_cfg.get("enabled", True))

    summary = build_expected_moves_snapshots(
        tickers=tickers,
        destination_root=destination_root,
        tmp_root=tmp_root,
        allow_missing=allow_missing,
        expect_weekly_reference=expect_weekly_reference,
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
    if tickers_arg:
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


def handle_build_markov_snapshots(args):
    tickers_arg = getattr(args, "tickers", None)
    if tickers_arg:
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

    summary = build_markov_snapshots(
        tickers=tickers,
        destination_root=destination_root,
        tmp_root=tmp_root,
        allow_missing=allow_missing,
        windows=windows,
    )
    ok = summary.get("copied_count", 0)
    missing = len(summary.get("missing", []))
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
    Handler for building daily GEX snapshots from Massive Flat Files.
    """
    from datetime import date, datetime, timedelta
    from mie_lib.data_ingest.massive_options_loader import MassiveOptionsLoader
    from mie_lib.analytics.gex.gex_engine import GEXEngine
    from mie_lib.analytics.gex.storage import save_gex_profile
    import yfinance as yf # Only for spot price if needed
    import pandas as pd
    import logging
    
    logger = logging.getLogger(__name__)
    
    target_date = args.date if args.date else date.today().strftime("%Y-%m-%d")
    tickers = _load_yaml_tickers()
    if args.tickers:
        if args.tickers == "@config":
            pass # already loaded
        else:
            tickers = _parse_csv_str_list(args.tickers, [])
            
    logger.info(f"Starting Offline GEX Build for {target_date} for {len(tickers)} tickers...")
    
    loader = MassiveOptionsLoader()
    engine = GEXEngine()
    
    # 1. Load Data
    logger.info(f"Loading options flat file for {target_date}...")
    df_all = loader.load_day_aggregates(target_date, tickers)
    
    if df_all.empty:
        logger.error(f"FATAL: No CSV data found for {target_date}. Please download Massive files or run 'fetch-options-snapshot'.")
        return 1
        
    # 2. Process Each Ticker
    for ticker in tickers:
        try:
            # Filter from CSV
            df_ticker = pd.DataFrame()
            if not df_all.empty:
                 df_ticker = df_all[df_all['underlying_ticker'] == ticker]
            
            # STRICT MODE: If CSV is empty, we SKIP. No YFinance fallback.
            if df_ticker.empty:
                logger.warning(f"Skipping {ticker}: No data in CSV.")
                continue

            # 1. Determine Spot Price (Needed for CSV calculation)
            spot = None
            try:
                # Override if provided by CLI (Simulation Mode)
                if getattr(args, "spot", None) is not None:
                     spot = float(args.spot)
                     logger.info(f"Using manual spot override: {spot}")
                else:
                    # Only fetch spot if we have data to process
                    yf_t = yf.Ticker(ticker)
                    try:
                        spot = yf_t.fast_info['last_price']
                    except:
                        # Fallback to history
                        hist = yf_t.history(period="1d")
                        if not hist.empty:
                            spot = hist['Close'].iloc[-1]
            except Exception as e:
                logger.warning(f"Could not fetch spot for {ticker}: {e}")
                continue

            # 2. Generate Candidate from CSV
            if spot:
                candidate_data = engine.calculate_gex_from_frame(ticker, df_ticker, spot)
                if candidate_data:
                    save_gex_profile(ticker, candidate_data)
                    logger.info(f"Saved GEX for {ticker} using CSV data ({len(df_ticker)} rows).")
                else:
                    logger.warning(f"Failed to calculate GEX for {ticker} (CSV data present but calc failed).")
            else:
                 logger.warning(f"Skipping {ticker}: No Spot Price available.")
            
        except Exception as e:
            logger.error(f"Failed to build GEX for {ticker}: {e}")
            
    logger.info("Daily GEX Build Completed.")
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
    import yfinance as yf
    import pandas as pd
    from pathlib import Path
    
    logger = logging.getLogger(__name__)
    today_str = date.today().strftime("%Y-%m-%d")
    output_dir = Path("data/raw/massive/options")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"options_{today_str}.csv"
    
    tickers = _load_yaml_tickers()
    if args.tickers and args.tickers != "@config":
        tickers = _parse_csv_str_list(args.tickers, [])
        
    logger.info(f"Fetching options snapshot for {len(tickers)} tickers...")
    
    all_rows = []
    
    for ticker in tickers:
        logger.info(f"Fetching {ticker}...")
        try:
            yf_t = yf.Ticker(ticker)
            exps = yf_t.options
            
            if not exps:
                logger.warning(f"  No expirations for {ticker}")
                continue
                
            for exp in exps:
                try:
                    chain = yf_t.option_chain(exp)
                    
                    # Process Calls
                    for _, row in chain.calls.iterrows():
                        osi = _format_osi(ticker, exp, 'call', row['strike'])
                        all_rows.append({
                            "day": today_str,
                            "underlying_ticker": ticker,
                            "option_ticker": osi,
                            "open_interest": row.get('openInterest', 0) or 0,
                            "implied_volatility": row.get('impliedVolatility', 0) or 0,
                            "gamma": 0, 
                            "delta": 0,
                        })
                        
                    # Process Puts
                    for _, row in chain.puts.iterrows():
                        osi = _format_osi(ticker, exp, 'put', row['strike'])
                        all_rows.append({
                            "day": today_str,
                            "underlying_ticker": ticker,
                            "option_ticker": osi,
                            "open_interest": row.get('openInterest', 0) or 0,
                            "implied_volatility": row.get('impliedVolatility', 0) or 0,
                            "gamma": 0,
                            "delta": 0,
                        })
                        
                except Exception as e:
                    logger.warning(f"  Error fetching {exp}: {e}")
                    
        except Exception as e:
            logger.error(f"Failed to process {ticker}: {e}")
            
    df = pd.DataFrame(all_rows)
    logger.info(f"Total contracts fetched: {len(df)}")
    
    if not df.empty:
        df.to_csv(output_file, index=False)
        logger.info(f"Saved snapshot to {output_file}")
    else:
        logger.warning("No data fetched.")
    
    return 0


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
    sub.add_parser("update-raw", help="Incrementally update raw data for tickers (append+dedupe)")
    sub.add_parser("rebuild-raw", help="Rebuild raw data for all tickers (full history)")
    sub.add_parser("validate-raw", help="Validate raw data files for tickers")

    # --- GEX (New) ---
    p_gex = sub.add_parser("build-gex-daily", help="Build Daily GEX from Massive Flat Files (Offline)")
    p_gex.add_argument("--date", type=str, help="YYYY-MM-DD (Default Today)")
    p_gex.add_argument("--tickers", type=str, default="@config")
    p_gex.add_argument("--spot", type=float, help="Manual spot price override")
    p_gex.set_defaults(func=handle_build_gex_daily)

    p_fetch_gex = sub.add_parser("fetch-options-snapshot", help="Fetch fresh options snapshot from YFinance (Optional)")
    p_fetch_gex.add_argument("--tickers", type=str, default="@config")
    p_fetch_gex.set_defaults(func=handle_fetch_options_snapshot)

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
    sub.add_parser(
        "update-everything",
        help=(
            "Incremental update: update RAW/FEATURES/SEASONALITY, refresh MARKOV/HMM for all YAML tickers."
        ),
    )

    # Minervini Scanner
    p_min = sub.add_parser("build-minervini-daily", help="Build Daily Minervini Scanner Snapshot")
    p_min.add_argument("--date", type=str, help="YYYY-MM-DD (Default Today)")
    p_min.add_argument("--tickers", type=str, default="@config")

    return parser


def main(argv=None):
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
        tickers = read_tickers()
        for t in tickers:
            res = update_ticker_incremental(t)
            LOG.info("update-raw result: %s", res)
            print(res)
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
        results = _build_features_for_all(mode="update", lookback=args.lookback, write_csv=args.csv)
        for r in results:
            LOG.info("update-features: %s", r)
            print(r)
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
        # Resolve tickers
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
        win_years = int(str(args.windows).split(",")[0])
        states_list = [int(x.strip()) for x in str(args.states).split(",") if x.strip()]
        rows = []
        for t in tickers:
            feat_path = FEATURES_DIR / f"{t}.parquet"
            if not feat_path.exists():
                print(f"build-hmm-grid SKIP {t}: missing features {feat_path}")
                continue
            for ns in states_list:
                out = build_hmm_standardized_for_ticker(t, n_states=ns, train_window_years=win_years)
                rows.append({"ticker": t, "n_states": ns, "paths": out})
        print("ticker,n_states,probs,states,metrics,metadata,skipped")
        for r in rows:
            p = r["paths"]
            print(f"{r['ticker']},{r['n_states']},{p.get('probs')},{p.get('states')},{p.get('metrics')},{p.get('metadata')},{p.get('skipped', False)}")
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
        if not getattr(args, "tickers", None) or str(args.tickers).strip() == "@config":
            tickers = _default_markov_tickers()
        else:
            tickers = [t.strip().upper() for t in str(args.tickers).split(",") if t.strip()]
        modes = _parse_csv_str_list(getattr(args, "state_modes", None), DEFAULT_MARKOV_GRID_STATE_MODES)
        thrs = _parse_csv_int_list(getattr(args, "thresholds", None), DEFAULT_MARKOV_GRID_THRESHOLDS)
        windows = _parse_csv_str_list(getattr(args, "windows", None), DEFAULT_MARKOV_GRID_WINDOWS)
        orders = _parse_csv_int_list(getattr(args, "orders", None), DEFAULT_MARKOV_GRID_ORDERS)

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
                        build_states_from_features(t, thr, m)
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
        from scripts.seasonality.build_facts import build_facts_for_ticker, load_seasonality_config
        cfg = load_seasonality_config()
        horizons = cfg.get("LOOKBACK_WINDOWS", [5,10,20,30,50,"ALL"])
        rows = []
        for t in tickers:
            out = build_facts_for_ticker(t, horizons=horizons, dry_run=getattr(args, "dry_run", False))
            rows.append({"ticker": t, "written": [str(p) for p in out]})
        print(json.dumps(rows))
        sys.exit(0)
    elif args.command == "update-seasonality":
        if getattr(args, "tickers", "ALL") == "ALL":
            try:
                tickers = read_tickers()
            except Exception:
                tickers = []
        else:
            tickers = [t.strip().upper() for t in str(args.tickers).split(",") if t.strip()]
        from scripts.seasonality.update import update_seasonality
        out = update_seasonality(tickers, since=getattr(args, "since", None), dry_run=getattr(args, "dry_run", False))
        print(json.dumps([str(p) for p in out]))
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
        py = sys.executable
        mie = os.fspath(Path(__file__).resolve())
        # RAW full
        _run([py, mie, "rebuild-raw"])
        # FEATURES full + CSV
        _run([py, mie, "build-features", "--mode", "full", "--csv"])
        # SEASONALITY base + facts
        _run([py, mie, "build-seasonality-base"])  # reads tickers from config
        _run([py, mie, "build-seasonality-facts"])  # reads tickers from config
        # MARKOV grid (explicit params per spec)
        _run([py, mie, "build-markov-grid",
              "--state-modes", "binary,tri",
              "--thresholds", ",".join(str(i) for i in range(0,151,5)),
              "--windows", "1Y,2Y,5Y,10Y,20Y,MAX",
              "--orders", "1,2,3,4"])  # uses default tickers resolver
        # HMM grid (require tickers arg -> @config)
        _run([py, mie, "build-hmm-grid", "--tickers", "@config", "--windows", "5", "--states", "2,3"])
        print("✅ Done.")
        sys.exit(0)
    elif args.command == "update-everything":
        # Validate tickers resolve from YAML
        tickers = _load_yaml_tickers()
        if not tickers:
            print("update-everything ERROR: no tickers resolved from config/tickers.yml")
            sys.exit(2)
        py = sys.executable
        mie = os.fspath(Path(__file__).resolve())
        # RAW incremental
        _run([py, mie, "update-raw"])
        # FEATURES incremental + CSV
        _run([py, mie, "build-features", "--mode", "update", "--lookback", "90", "--csv"])
        # SEASONALITY incremental
        _run([py, mie, "update-seasonality"])
        # MARKOV grid refresh
        _run([py, mie, "build-markov-grid",
              "--state-modes", "binary,tri",
              "--thresholds", ",".join(str(i) for i in range(0,151,5)),
              "--windows", "1Y,2Y,5Y,10Y,20Y,MAX",
              "--orders", "1,2,3,4"])  # uses default tickers resolver
        # HMM grid refresh
        _run([py, mie, "build-hmm-grid", "--tickers", "@config", "--windows", "5", "--states", "2,3"])
        print("✅ Done.")
        sys.exit(0)
    elif args.command == "build-seasonality":
        if not args.ticker:
            print("Error: --ticker is required for build-seasonality")
            return
        print(f"Building Seasonality Base Data for {args.ticker}...")
        generate_seasonality_base(args.ticker)
    elif args.command == "build-minervini-daily":
        from mie_lib.analytics.scanner.minervini_build import build_minervini_snapshot
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
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    # Execute CLI when run as a script
    main()
