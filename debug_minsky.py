
import pandas as pd
from mie_lib.utils.paths import PROCESSED_DATA_DIR

print("\n--- CHECKING VALIDATION OUTPUT ---")
path = PROCESSED_DATA_DIR / "minsky_market_validation.parquet"
if not path.exists():
    print("File not found")
else:
    df = pd.read_parquet(path)
    print("Columns:", df.columns.tolist())
    print("Index:", df.index)
    print("Head:\n", df.head(3))
