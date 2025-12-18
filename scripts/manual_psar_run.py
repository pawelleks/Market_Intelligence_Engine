
import sys
from pathlib import Path
# Add src to path
sys.path.append(str(Path.cwd() / "src"))

from mie_lib.analytics.psar import calculate_and_save_psar
import pandas as pd

print("Running calculate_and_save_psar...")
calculate_and_save_psar()

p_path = Path("data/analytics/psar_daily.parquet")
if p_path.exists():
    print(f"File created: {p_path}")
    df = pd.read_parquet(p_path)
    print("Columns:", df.columns.tolist())
    print("Shape:", df.shape)
    print("Sample:\n", df.head())
else:
    print("File NOT created.")
