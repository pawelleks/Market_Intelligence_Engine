"""
CLI stub for Market Intelligence Engine.
Commands: update, rebuild, validate
No business logic implemented — scaffolding only.
"""
import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path so `src` is importable when running cli scripts
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.data_ingest.yfinance_loader import (
    read_tickers,
    fetch_full_history,
    update_ticker_incremental,
    validate_raw,
)
from src.utils.logging import get_logger
from src.features.build_features import build_features_for_all
from src.features.build_features import FEATURES_DIR, _get_windows
from src.analytics.markov.markov_engine import MarkovConfig, build_markov_for_ticker
from src.analytics.hmm.hmm_engine import HMMConfig, build_hmm_for_ticker
from src.analytics.hmm.hmm_engine import build_hmm_standardized_for_ticker
from src.analytics.markov.states_model import build_states_from_features, derive_matrix
from src.analytics.markov.states_model import states_stale
import yaml

LOG = get_logger("cli")


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
    # Feature build commands
    p_bf = sub.add_parser("build-features", help="Build features for tickers")
    p_bf.add_argument("--mode", choices=["full", "update"], default="full")
    p_bf.add_argument("--lookback", type=int, default=90, help="Number of days to recompute for incremental updates")
    p_bf.add_argument("--csv", action="store_true", help="Also write CSV fallback")

    p_uf = sub.add_parser("update-features", help="Update features for tickers (incremental)")
    p_uf.add_argument("--lookback", type=int, default=90)
    p_uf.add_argument("--csv", action="store_true")

    # Smoke check command
    sub.add_parser("smoke-update", help="Lightweight smoke check after FULL+UPDATE: verifies sorted dates and ret_1d continuity for first ticker")

    # Markov builder command
    p_mk = sub.add_parser("build-markov", help="Build offline Markov analytics for a ticker")
    p_mk.add_argument("--ticker", required=True)
    p_mk.add_argument("--order", type=int, default=1)
    p_mk.add_argument("--state-mode", choices=["tri", "binary"], default="tri")
    p_mk.add_argument("--threshold-bps", type=int, default=10)

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

    p_mks_matrix = sub.add_parser("derive-markov-matrix", help="Derive/caches a Markov matrix for a window/order from precomputed states")
    p_mks_matrix.add_argument("--ticker", required=True)
    p_mks_matrix.add_argument("--state-mode", required=True, choices=["tri","binary"])
    p_mks_matrix.add_argument("--threshold-bps", required=True, type=int)
    p_mks_matrix.add_argument("--order", required=True, type=int)
    p_mks_matrix.add_argument("--window", required=True, help="1Y|2Y|5Y|10Y|20Y|MAX or CUSTOM_YYYYMMDD_YYYYMMDD")

    p_mks_grid = sub.add_parser("build-markov-grid", help="Build states then derive matrices for a grid of params")
    p_mks_grid.add_argument("--tickers", required=True, help="@config or comma list")
    p_mks_grid.add_argument("--state-modes", required=True)
    p_mks_grid.add_argument("--thresholds", required=True)
    p_mks_grid.add_argument("--windows", required=True, help="comma list e.g. 1Y,2Y,5Y,10Y,20Y,MAX")
    p_mks_grid.add_argument("--orders", required=True, help="comma list e.g. 1,2,3,4")

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

    return parser


def main(argv=None):
    argv = argv or sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

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
    elif args.command == "build-features":
        results = build_features_for_all(mode=args.mode, lookback=args.lookback, write_csv=args.csv)
        for r in results:
            LOG.info("build-features: %s", r)
            print(r)
    elif args.command == "update-features":
        results = build_features_for_all(mode="update", lookback=args.lookback, write_csv=args.csv)
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
            cfg = MarkovConfig(order=args.order, state_mode=args.state_mode, threshold_bps=args.threshold_bps)
            out = build_markov_for_ticker(args.ticker, cfg)
            print(out)
            LOG.info("build-markov: %s", out)
            sys.exit(0)
        except Exception as e:
            print(f"build-markov ERROR: {e}")
            LOG.exception("build-markov failed")
            sys.exit(6)
    elif args.command == "build-markov-sweep":
        try:
            # Parse orders
            orders = [int(x.strip()) for x in str(args.orders).split(",") if x.strip()]
            from src.analytics.markov.markov_engine import build_markov_order_sweep
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
                            rows.append({
                                "ticker": t,
                                "order": K,
                                "state_mode": mode,
                                "thr_bps": thr,
                                "paths": out,
                            })
                            LOG.info("build-markov-batch ok: %s", rows[-1])
                        except Exception as e:
                            print(f"build-markov-batch ERROR for {t} K={K} mode={mode} thr={thr}: {e}")
                            LOG.exception("build-markov-batch failed")
        # Summary
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
        # Parse tickers
        if str(args.tickers).strip() == "@config":
            tickers = read_tickers()
        else:
            tickers = [t.strip().upper() for t in str(args.tickers).split(",") if t.strip()]
        # Only 5-year window supported now per spec
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
        # Summary
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
        if str(args.tickers).strip() == "@config":
            tickers = read_tickers()
        else:
            tickers = [t.strip().upper() for t in str(args.tickers).split(",") if t.strip()]
        modes = [m.strip() for m in str(args.state_modes).split(",") if m.strip()]
        thrs = [int(x.strip()) for x in str(args.thresholds).split(",") if x.strip()]
        windows = [w.strip() for w in str(args.windows).split(",") if w.strip()]
        orders = [int(x.strip()) for x in str(args.orders).split(",") if x.strip()]
        for t in tickers:
            feat_path = FEATURES_DIR / f"{t}.parquet"
            if not feat_path.exists():
                print(f"build-markov-grid SKIP {t}: missing features {feat_path}")
                continue
            for m in modes:
                for thr in thrs:
                    build_states_from_features(t, thr, m)
                    for w in windows:
                        for K in orders:
                            df = derive_matrix(t, thr, m, K, w)
                            print({"ticker": t, "mode": m, "thr": thr, "window": w, "order": K, "rows": len(df)})
        sys.exit(0)
    elif args.command == "build-hmm":
        try:
            cfg = HMMConfig(n_states=args.states, train_window_years=args.window_years, random_seed=args.seed)
            out = build_hmm_for_ticker(args.ticker, cfg)
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
            # Build states if stale/missing
            if states_stale(t, thr, mode):
                build_states_from_features(t, thr, mode)
            # Derive matrix (cached)
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
                    from src.features.build_features import build_features_for_ticker
                    r = build_features_for_ticker(t, mode="full", lookback=90, write_csv=False)
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
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
