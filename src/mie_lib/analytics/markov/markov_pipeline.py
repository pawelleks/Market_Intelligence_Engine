"""
Parallel Markov Pipeline.

Parallelizes Markov grid building using ThreadPoolExecutor.
Each ticker's full grid (modes × thresholds × windows × orders) is processed as a unit.

The Markov processing is primarily DataFrame operations and file I/O,
so threading provides good parallelization benefit.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Tuple
import shutil

LOG = logging.getLogger(__name__)


@dataclass
class MarkovTaskResult:
    """Result of processing one ticker's Markov grid."""
    ticker: str
    success: bool
    matrix_count: int = 0
    error: str = None


def _process_markov_grid_for_ticker(
    ticker: str,
    modes: List[str],
    thresholds: List[int],
    windows: List[str],
    orders: List[int]
) -> MarkovTaskResult:
    """
    Process complete Markov grid for a single ticker.
    Thread-safe: each call processes one ticker's files independently.
    """
    try:
        from mie_lib.analytics.markov.markov_engine import (
            build_states_from_features,
            derive_matrix,
            multi_step,
            FEATURES_DIR
        )
        
        feat_path = FEATURES_DIR / f"{ticker}.parquet"
        if not feat_path.exists():
            return MarkovTaskResult(
                ticker=ticker,
                success=False,
                error=f"missing features {feat_path}"
            )
        
        matrix_count = 0
        
        for m in modes:
            for thr in thresholds:
                try:
                    sp_out = build_states_from_features(ticker, thr, m)
                    
                    # Legacy compatibility: copy default config to root states.parquet
                    if int(thr) == 10 and str(m) == "tri":
                        try:
                            legacy_states = Path("data") / "analytics" / "markov" / ticker / "states.parquet"
                            if Path(sp_out).exists():
                                shutil.copy2(sp_out, legacy_states)
                        except Exception:
                            pass  # Ignore legacy copy failures
                            
                except Exception as e:
                    LOG.warning(f"States failed for {ticker} {m} thr={thr}: {e}")
                    continue
                
                for w in windows:
                    for K in orders:
                        try:
                            df = derive_matrix(ticker, thr, m, K, w)
                            matrix_count += 1
                            
                            # Multi-Step Forecast for order=1
                            if K == 1:
                                try:
                                    horizons = [1, 2, 3, 4, 5]
                                    ms_df = multi_step(df, horizons, m)
                                    if not ms_df.empty:
                                        ms_path = Path("data") / "analytics" / "markov" / ticker / f"multi_step_order{K}_{m}_thr{thr}.parquet"
                                        ms_df.reset_index().to_parquet(ms_path, index=False)
                                except Exception:
                                    pass  # Ignore multi-step failures
                                    
                        except Exception as e:
                            LOG.debug(f"Matrix skip {ticker} {m} thr={thr} order={K} window={w}: {e}")
        
        return MarkovTaskResult(
            ticker=ticker,
            success=True,
            matrix_count=matrix_count
        )
        
    except Exception as e:
        LOG.error(f"Markov grid failed for {ticker}: {e}")
        return MarkovTaskResult(
            ticker=ticker,
            success=False,
            error=str(e)
        )


def run_markov_grid_parallel(
    tickers: List[str],
    modes: List[str] = None,
    thresholds: List[int] = None,
    windows: List[str] = None,
    orders: List[int] = None,
    max_workers: int = 8
) -> Dict[str, Any]:
    """
    Parallel Markov Grid pipeline.
    
    Each ticker's full grid is processed as a unit in parallel.
    
    Args:
        tickers: List of tickers to process
        modes: State modes (e.g., ["binary", "tri"])
        thresholds: Threshold values in bps (e.g., [0, 5, 10, ...])
        windows: Training windows (e.g., ["1Y", "5Y", "MAX"])
        orders: Markov orders (e.g., [1, 2])
        max_workers: Thread pool size
        
    Returns:
        Dict with results and statistics
    """
    if modes is None:
        modes = ["binary", "tri"]
    if thresholds is None:
        thresholds = [0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50]
    if windows is None:
        windows = ["1Y", "2Y", "5Y", "10Y", "15Y", "MAX"]
    if orders is None:
        orders = [1, 2]
    
    total_combos_per_ticker = len(modes) * len(thresholds) * len(windows) * len(orders)
    
    LOG.info(f"Starting parallel Markov Grid: {len(tickers)} tickers × {total_combos_per_ticker} combos, {max_workers} workers")
    
    results = {
        "processed": 0,
        "success": 0,
        "failed": 0,
        "total_matrices": 0
    }
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {
            executor.submit(
                _process_markov_grid_for_ticker,
                ticker, modes, thresholds, windows, orders
            ): ticker
            for ticker in tickers
        }
        
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                result: MarkovTaskResult = future.result(timeout=600)  # 10 min per ticker
                results["processed"] += 1
                
                if result.success:
                    results["success"] += 1
                    results["total_matrices"] += result.matrix_count
                else:
                    results["failed"] += 1
                    LOG.warning(f"Markov failed for {ticker}: {result.error}")
                    
            except Exception as e:
                LOG.error(f"Markov task exception for {ticker}: {e}")
                results["processed"] += 1
                results["failed"] += 1
    
    LOG.info(f"Markov Grid complete: {results['success']}/{results['processed']} tickers, {results['total_matrices']} matrices")
    
    return results
