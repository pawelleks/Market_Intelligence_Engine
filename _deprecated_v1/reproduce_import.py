
import sys
import os
from pathlib import Path

# Mimic the path setup in mie.py
ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

print(f"Testing import of scripts.seasonality.update with ROOT={ROOT}")

try:
    from scripts.seasonality.update import update_seasonality
    print("SUCCESS: Module imported successfully.")
except ImportError as e:
    print(f"FAILED: {e}")
    sys.exit(1)
except Exception as e:
    print(f"FAILED: Unexpected error {e}")
    sys.exit(1)
