
import os
import shutil
from datetime import datetime
import logging

# Config
DATA_DIR = "data/analytics/gex"
HISTORY_DIR = os.path.join(DATA_DIR, "history")
SOURCE_FILE = os.path.join(DATA_DIR, "SPY_profile.parquet")
LOG_FILE = "logs/archive_gex.log"

def archive_daily():
    if not os.path.exists(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)
        
    logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s %(message)s')
    
    if not os.path.exists(SOURCE_FILE):
        logging.warning(f"Source file not found: {SOURCE_FILE}")
        return

    today_str = datetime.now().strftime("%Y%m%d")
    dest_filename = f"SPY_profile_{today_str}.parquet"
    dest_path = os.path.join(HISTORY_DIR, dest_filename)
    
    try:
        shutil.copy2(SOURCE_FILE, dest_path)
        logging.info(f"Archived {SOURCE_FILE} to {dest_path}")
        print(f"Successfully archived today's GEX profile to {dest_path}")
    except Exception as e:
        logging.error(f"Failed to archive: {e}")
        print(f"Error archiving GEX: {e}")

if __name__ == "__main__":
    archive_daily()
