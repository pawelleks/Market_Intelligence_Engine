import pandas as pd
import numpy as np
import os

# Define the correct schema
def correct_schema(file_path):
    try:
        df = pd.read_parquet(file_path)

        # Correct column data types
        dtype_corrections = {
            "date": "datetime64[ns, UTC]",
            "doy_trading": np.int32,
            "open": np.float32,
            "high": np.float32,
            "low": np.float32,
            "close": np.float32,
            "r": np.float32,
            "lr": np.float32,
        }

        for col, dtype in dtype_corrections.items():
            if col in df.columns:
                df[col] = df[col].astype(dtype)

        # Correct timezone for the 'date' column
        # Debugging: Inspect the 'date' column
        if "date" in df.columns:
            print(f"Inspecting 'date' column in {file_path}:")
            print(df["date"].head())
            print(df["date"].dtype)

            # Debugging: Catch specific issues with the 'date' column
            try:
                if pd.api.types.is_datetime64_any_dtype(df["date"]):
                    if df["date"].dt.tz is None:
                        df["date"] = df["date"].dt.tz_localize("UTC")
                    else:
                        df["date"] = df["date"].dt.tz_convert("UTC")
            except Exception as date_error:
                print(f"Error processing 'date' column in {file_path}: {date_error}")

            # Debugging: Inspect the entire 'date' column for inconsistencies
            print(f"Full 'date' column inspection for {file_path}:")
            print(df["date"].apply(type).value_counts())

        # Save the corrected file
        corrected_path = file_path.replace(".parquet", "_corrected.parquet")
        df.to_parquet(corrected_path, engine="pyarrow")
        print(f"Corrected schema saved to: {corrected_path}")

    except Exception as e:
        print(f"Error correcting schema for {file_path}: {e}")

if __name__ == "__main__":
    base_paths = ["data/seasonality/", "data/analytics/seasonality/"]
    for base_path in base_paths:
        if os.path.exists(base_path):
            for root, _, files in os.walk(base_path):
                for file in files:
                    if file.endswith(".parquet"):
                        correct_schema(os.path.join(root, file))
