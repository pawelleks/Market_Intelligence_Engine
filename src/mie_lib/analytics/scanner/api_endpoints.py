from fastapi import APIRouter, HTTPException
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/scanner/minervini", tags=["Scanner"])

SNAPSHOT_FILE = Path("data/analytics/scanner/minervini_latest.json")

@router.get("/latest")
def get_latest_minervini_scan():
    """Returns the latest Minervini Trend Template scan results."""
    if not SNAPSHOT_FILE.exists():
        raise HTTPException(status_code=404, detail="No scan data available. Run 'mie build-minervini-daily'.")
        
    try:
        with open(SNAPSHOT_FILE, 'r') as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Failed to read scanner data: {e}")
        raise HTTPException(status_code=500, detail="Failed to read scanner data")
