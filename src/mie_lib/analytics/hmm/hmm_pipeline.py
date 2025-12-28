"""
Parallel HMM Pipeline.

Parallelizes HMM model building and backtesting using ThreadPoolExecutor.
Processes multiple (ticker, window, n_states) combinations concurrently.

Note: HMM training is CPU-intensive, so we use thread-based parallelism
for I/O overlap and multi-core utilization via GIL-releasing NumPy operations.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Any, Tuple
import traceback

LOG = logging.getLogger(__name__)


@dataclass
class HMMTaskResult:
    """Result of a single HMM task."""
    ticker: str
    window: Any  # int or "MAX"
    n_states: int
    success: bool
    error: str = None


def _build_hmm_for_combo(
    ticker: str,
    window: Any,
    n_states: int,
    random_seed: int = 42
) -> HMMTaskResult:
    """
    Build HMM model for a single (ticker, window, n_states) combination.
    Thread-safe: each call creates its own model and writes to a unique path.
    """
    try:
        from mie_lib.analytics.hmm.hmm_engine import build_hmm_standardized_for_ticker
        
        build_hmm_standardized_for_ticker(
            ticker=ticker,
            n_states=n_states,
            train_window_years=window,
            random_seed=random_seed
        )
        
        return HMMTaskResult(
            ticker=ticker,
            window=window,
            n_states=n_states,
            success=True
        )
        
    except Exception as e:
        LOG.error(f"HMM failed for {ticker} win={window} states={n_states}: {e}")
        return HMMTaskResult(
            ticker=ticker,
            window=window,
            n_states=n_states,
            success=False,
            error=str(e)
        )


def _build_primary_hmm_for_ticker(ticker: str) -> HMMTaskResult:
    """Build the primary (default config) HMM for a ticker."""
    try:
        from mie_lib.analytics.hmm.hmm_engine import build_hmm_for_ticker, HMMConfig
        
        cfg = HMMConfig()  # Default config
        build_hmm_for_ticker(ticker, cfg)
        
        return HMMTaskResult(
            ticker=ticker,
            window="default",
            n_states=cfg.n_states,
            success=True
        )
        
    except Exception as e:
        LOG.error(f"Primary HMM failed for {ticker}: {e}")
        return HMMTaskResult(
            ticker=ticker,
            window="default",
            n_states=0,
            success=False,
            error=str(e)
        )


def run_hmm_daily_parallel(
    tickers: List[str],
    windows: List[Any] = None,
    n_states_list: List[int] = None,
    max_workers: int = 8,
    include_primary: bool = True
) -> Dict[str, Any]:
    """
    Parallel HMM Daily pipeline.
    
    Builds HMM models for all (ticker, window, n_states) combinations in parallel.
    
    Args:
        tickers: List of tickers to process
        windows: List of training windows (e.g., [1, 5, 10, "MAX"])
        n_states_list: List of state counts (e.g., [2, 3])
        max_workers: Thread pool size
        include_primary: If True, also build primary (default) HMM for each ticker
        
    Returns:
        Dict with results and statistics
    """
    if windows is None:
        windows = [1, 5, 10, 15, 20, 25, 50, "MAX"]
    if n_states_list is None:
        n_states_list = [2, 3]
    
    # Build task list: all (ticker, window, n_states) combinations
    tasks = []
    for ticker in tickers:
        for window in windows:
            for n_states in n_states_list:
                tasks.append((ticker, window, n_states))
    
    total_tasks = len(tasks)
    if include_primary:
        total_tasks += len(tickers)
    
    LOG.info(f"Starting parallel HMM Grid: {len(tickers)} tickers, {len(windows)} windows, "
             f"{len(n_states_list)} state configs = {len(tasks)} grid tasks + "
             f"{len(tickers) if include_primary else 0} primary tasks")
    
    results = {
        "processed": 0,
        "success": 0,
        "failed": 0,
        "details": [],
        "errors": []
    }
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        
        # Submit grid tasks
        for ticker, window, n_states in tasks:
            future = executor.submit(_build_hmm_for_combo, ticker, window, n_states)
            futures[future] = ("grid", ticker, window, n_states)
        
        # Submit primary tasks
        if include_primary:
            for ticker in tickers:
                future = executor.submit(_build_primary_hmm_for_ticker, ticker)
                futures[future] = ("primary", ticker, None, None)
        
        # Collect results
        for future in as_completed(futures):
            task_type, ticker, window, n_states = futures[future]
            try:
                result: HMMTaskResult = future.result(timeout=300)  # 5 min timeout per task
                results["processed"] += 1
                
                if result.success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append({
                        "ticker": ticker,
                        "window": window,
                        "n_states": n_states,
                        "error": result.error
                    })
                    
            except Exception as e:
                LOG.error(f"Task exception for {ticker}: {e}")
                results["processed"] += 1
                results["failed"] += 1
                results["errors"].append({
                    "ticker": ticker,
                    "window": window,
                    "n_states": n_states,
                    "error": str(e)
                })
    
    LOG.info(f"HMM Grid complete: {results['success']}/{results['processed']} succeeded")
    
    # Trim errors for response
    results["errors"] = results["errors"][:10]
    
    return results


def run_backtest_hmm_parallel(
    tickers: List[str],
    max_workers: int = 6
) -> Dict[str, Any]:
    """
    Parallel HMM Backtest pipeline.
    
    Runs grid search backtesting for each ticker in parallel.
    
    Args:
        tickers: List of tickers to backtest
        max_workers: Thread pool size (lower default due to CPU intensity)
        
    Returns:
        Dict with results and statistics
    """
    LOG.info(f"Starting parallel HMM Backtest: {len(tickers)} tickers, {max_workers} workers")
    
    def _backtest_ticker(ticker: str) -> Tuple[str, bool, str]:
        try:
            from mie_lib.analytics.hmm.backtest_engine import HMMBacktester
            
            engine = HMMBacktester(ticker=ticker)
            engine.run_grid_search()
            return (ticker, True, None)
            
        except Exception as e:
            LOG.error(f"Backtest failed for {ticker}: {e}")
            return (ticker, False, str(e))
    
    results = {
        "processed": 0,
        "success": 0,
        "failed": 0
    }
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_ticker = {
            executor.submit(_backtest_ticker, ticker): ticker
            for ticker in tickers
        }
        
        for future in as_completed(future_to_ticker):
            ticker = future_to_ticker[future]
            try:
                t, success, error = future.result(timeout=600)  # 10 min timeout
                results["processed"] += 1
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
            except Exception as e:
                LOG.error(f"Backtest exception for {ticker}: {e}")
                results["processed"] += 1
                results["failed"] += 1
    
    LOG.info(f"HMM Backtest complete: {results['success']}/{results['processed']} succeeded")
    
    return results
