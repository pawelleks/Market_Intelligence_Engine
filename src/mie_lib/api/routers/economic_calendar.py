from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
import httpx
import json
import os
import time
from pathlib import Path
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("economic_calendar")

router = APIRouter(
    prefix="/api/v1/macro/calendar",
    tags=["macro", "calendar"]
)

# Constants
FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"
CACHE_DIR = Path("data/cache")
CACHE_FILE = CACHE_DIR / "economic_calendar.json"
CACHE_TTL = 3600  # 60 minutes in seconds

# Ensure cache directory exists
CACHE_DIR.mkdir(parents=True, exist_ok=True)

@router.get("")
async def get_economic_calendar():
    """
    Fetch weekly economic calendar data with server-side proxying and caching.
    """
    # 1. Check local cache
    if CACHE_FILE.exists():
        file_age = time.time() - os.path.getmtime(CACHE_FILE)
        if file_age < CACHE_TTL:
            try:
                with open(CACHE_FILE, "r") as f:
                    data = json.load(f)
                LOG.info("Serving economic calendar from cache (fresh)")
                return JSONResponse(content={"status": "ok", "source": "cache", "data": data})
            except Exception as e:
                LOG.error(f"Failed to read cache file: {e}")

    # 2. Cache expired or missing -> Fetch from external URL
    LOG.info(f"Fetching economic calendar from {FEED_URL}")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(FEED_URL)
            response.raise_for_status()
            data = response.json()
            
            # Save to cache
            with open(CACHE_FILE, "w") as f:
                json.dump(data, f)
            
            LOG.info("Successfully fetched and cached economic calendar")
            return JSONResponse(content={"status": "ok", "source": "remote", "data": data})
            
    except Exception as e:
        LOG.error(f"Failed to fetch economic calendar: {e}")
        
        # 3. Handle error gracefully: Serve last known good cache if available
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r") as f:
                    data = json.load(f)
                LOG.warning("External fetch failed. Serving stale cache.")
                return JSONResponse(content={
                    "status": "warning", 
                    "source": "stale_cache", 
                    "error": str(e),
                    "data": data
                })
            except Exception as ce:
                LOG.error(f"Failed to read stale cache: {ce}")
        
        raise HTTPException(
            status_code=502, 
            detail=f"Failed to fetch economic calendar and no cache available: {str(e)}"
        )
