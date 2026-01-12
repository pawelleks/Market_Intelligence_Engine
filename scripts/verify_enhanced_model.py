import pandas as pd
from pathlib import Path

# Setup paths
REPO_ROOT = Path(".").resolve()
DATA_DIR = REPO_ROOT / "data"

MACRO_ANALYSIS_DIR = DATA_DIR / "analytics" / "macro"
output_file = MACRO_ANALYSIS_DIR / "processed_lei_coi_enhanced.parquet"

def verify_output():
    if not output_file.exists():
        print(f"FAILED: {output_file} does not exist.")
        return

    df = pd.read_parquet(output_file)
    print(f"File loaded. Shape: {df.shape}")
    print(f"Columns: {df.columns.tolist()}")
    
    expected_columns = ['date', 'LEI_Final', 'COI_Final', 'Recession_Signal_Active']
    missing = [c for c in expected_columns if c not in df.columns]
    
    if missing:
        print(f"FAILED: Missing columns {missing}")
        return
        
    print("\nLast 5 rows:")
    print(df.tail())
    
    # Check signal logic
    # Recession_Signal_Active should be True if LEI_Final < -1.0
    errors = df[df['Recession_Signal_Active'] != (df['LEI_Final'] < -1.0)]
    
    if not errors.empty:
        print(f"\nFAILED: Found {len(errors)} rows with incorrect signal logic:")
        print(errors.head())
    else:
        print("\nSUCCESS: Recession Signal logic verified.")

if __name__ == "__main__":
    verify_output()
