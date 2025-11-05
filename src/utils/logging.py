"""
Logging helpers for the project.
Provides a `get_logger` function that configures console and file handlers.
"""
from pathlib import Path
import logging
import logging.handlers


def get_logger(name: str, level=logging.INFO, log_dir: str = "data/logs") -> logging.Logger:
    """Return a configured logger. Creating directories is performed lazily when this function is called.

    Note: Avoid calling this at import time in modules that are imported by tests to prevent writing files during import.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(level)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(level)
    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File handler
    try:
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        fh = logging.handlers.RotatingFileHandler(log_path / f"{name}.log", maxBytes=10_000_000, backupCount=5)
        fh.setLevel(level)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except Exception:
        # If file-based logging fails, continue with console only
        pass

    logger.propagate = False
    return logger

