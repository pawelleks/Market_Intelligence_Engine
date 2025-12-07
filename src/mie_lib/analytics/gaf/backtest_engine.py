import pandas as pd
import numpy as np
import logging
from datetime import timedelta
import yfinance as yf
from sklearn.metrics import accuracy_score, precision_score, recall_score, confusion_matrix
import tensorflow as tf

from mie_lib.analytics.gaf.encoder import GAFEncoder
from mie_lib.analytics.gaf.model import create_gaf_cnn_model

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GAFBacktester:
    def __init__(self, ticker="SPY", start_date="2020-01-01", end_date="2024-12-31", window_size=20, retrain_interval_days=90):
        self.ticker = ticker
        self.start_date = pd.to_datetime(start_date)
        self.end_date = pd.to_datetime(end_date)
        self.window_size = window_size
        self.retrain_interval_days = retrain_interval_days
        self.encoder = GAFEncoder(image_size=window_size)
        
        # Check strict fetch start date
        self.fetch_start_date = self.start_date - timedelta(days=window_size * 3) # Extra buffer for weekends
        
        self.results = []

    def fetch_data(self):
        """Fetches historical data from yfinance."""
        logger.info(f"Fetching data for {self.ticker} from {self.fetch_start_date}...")
        df = yf.download(self.ticker, start=self.fetch_start_date, end=self.end_date, progress=False)
        if df.columns.nlevels > 1:
            df.columns = df.columns.droplevel(1)  # Fix multi-index if present
            
        df = df.rename(columns={
            "Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume", "Adj Close": "adj_close"
        })
        # Use adj_close if avail
        if 'adj_close' in df.columns:
            df['price'] = df['adj_close']
        else:
            df['price'] = df['close']
            
        return df.sort_index()

    def make_target(self, df):
        """Creates binary target: 1 if Next Day Close > Current Day Close."""
        df['target'] = (df['price'].shift(-1) > df['price']).astype(int)
        return df.dropna()

    def generate_all_images(self, df):
        """
        Pre-computes Dual-Channel GAF images (Price + Volume).
        Returns: (images, valid_indices) -> shape (N, 40, 40, 2)
        """
        logger.info(f"Pre-computing Dual-Channel GAF images (Window={self.window_size})...")
        prices = df['price'].values
        volumes = df['volume'].values
        
        # Prepare Batch Data for speed
        batch_prices = []
        batch_volumes = []
        valid_indices = []
        
        for i in range(self.window_size, len(prices)):
            p_window = prices[i-self.window_size : i]
            v_window = volumes[i-self.window_size : i]
            
            batch_prices.append(p_window)
            batch_volumes.append(v_window)
            
            # Fix Off-By-One: 
            # Window encompasses prices[i-window_size : i]. Last price is at index i-1.
            # We want the target associated with index i-1 (which predicts move i-1 -> i).
            # The 'target' column at row K predicts K -> K+1.
            # So, for window ending at i-1, we want target at i-1.
            valid_indices.append(df.index[i-1])
            
        if not batch_prices:
            return np.array([]), []
            
        # Bulk Encode
        X_price = np.array(batch_prices)
        X_vol = np.array(batch_volumes)
        
        # Returns (N, H, W, 2)
        images = self.encoder.encode_batch(X_price, X_vol)
        
        return images, valid_indices

    def run(self):
        # 1. Prepare Data
        df = self.fetch_data()
        df = self.make_target(df) # Removes last row (NaN target)
        
        if df.empty:
            logger.error("No data found.")
            return

        # 2. Pre-compute Images
        # Note: 'images' index aligns with 'valid_indices'. 
        # df.loc[valid_indices[k]] is the row where we make prediction
        images, valid_indices = self.generate_all_images(df)
        
        # Create a mapping/aligned arrays for easy slicing
        # We need X (images) and y (targets) aligned
        # Filter df to valid_indices
        valid_df = df.loc[valid_indices]
        y_all = valid_df['target'].values
        dates_all = valid_df.index
        
        X_all = images
        
        # 3. Walk-Forward Loop
        # Find index where backtest starts
        start_idx = np.searchsorted(dates_all, self.start_date)
        
        current_idx = start_idx
        total_samples = len(dates_all)
        
        logger.info(f"Starting Walk-Forward Validation from {self.start_date} (Index {start_idx}/{total_samples})")
        
        model = None
        days_since_train = 100000 # Force train first time
        
        predictions = []
        actuals = []
        dates = []
        
        # Iterate day by day (simulating production)
        # Optimization: We can predict in batches between retrains? 
        # Strict WF means we predict t+1 using model trained on :t.
        # But commonly we assume model is fixed for 'retrain_interval'.
        
        while current_idx < total_samples:
            
            # A. Retrain if needed
            if days_since_train >= self.retrain_interval_days:
                logger.info(f"Retraining model at {dates_all[current_idx].date()}...")
                
                # Train on ALL past data available up to current_idx
                # X_train: [:current_idx]
                # y_train: [:current_idx]
                
                # Split Train/Val (last 10% of past data)
                train_cutoff = int(current_idx * 0.9)
                
                X_train = X_all[:train_cutoff]
                y_train = y_all[:train_cutoff]
                X_val = X_all[train_cutoff:current_idx]
                y_val = y_all[train_cutoff:current_idx]
                
                if len(X_train) < 100:
                    logger.warning("Not enough data to train yet. Skipping.")
                    current_idx += 1
                    continue
                    
                # Create/Reset Model (Dual Channel input)
                model = create_gaf_cnn_model(input_shape=(self.window_size, self.window_size, 2))
                
                # Silent training
                model.fit(X_train, y_train, 
                          validation_data=(X_val, y_val), 
                          epochs=20, 
                          batch_size=32, 
                          verbose=0)
                
                days_since_train = 0
            
            # B. Predict for the next interval (until next retrain)
            # We can predict the whole chunk [current_idx : current_idx + retrain_interval] 
            # using the current fixed model. This is standard "Rolling Window".
            
            end_chunk_idx = min(current_idx + self.retrain_interval_days, total_samples)
            
            chunk_X = X_all[current_idx : end_chunk_idx]
            chunk_dates = dates_all[current_idx : end_chunk_idx]
            chunk_y = y_all[current_idx : end_chunk_idx]
            
            if model:
                # Predict Batch
                probs = model.predict(chunk_X, verbose=0)
                preds = (probs > 0.5).astype(int).flatten()
                
                predictions.extend(preds)
                actuals.extend(chunk_y)
                dates.extend(chunk_dates)
            else:
                # Fill with zeros or NaNs if no model yet
                pass

            # Advance time
            processed_count = end_chunk_idx - current_idx
            current_idx = end_chunk_idx
            days_since_train += processed_count # Ideally aligned with days, but using samples is proxy
            
        # 4. Compile Results
        results_df = pd.DataFrame({
            'date': dates,
            'prediction': predictions,
            'actual': actuals
        })
        results_df['correct'] = results_df['prediction'] == results_df['actual']
        
        self.print_metrics(results_df)
        self.save_results(results_df)
        return results_df

    def save_results(self, df):
        """Saves backtest metrics and summary to a JSON file for the UI."""
        from pathlib import Path
        import json
        
        acc = accuracy_score(df['actual'], df['prediction'])
        prec = precision_score(df['actual'], df['prediction'], zero_division=0)
        rec = recall_score(df['actual'], df['prediction'], zero_division=0)
        cm = confusion_matrix(df['actual'], df['prediction'])
        
        output_data = {
            "ticker": self.ticker,
            "period": f"{self.start_date.date()} to {self.end_date.date()}",
            "total_days": len(df),
            "accuracy": round(acc * 100, 2),
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "confusion_matrix": cm.tolist(),
            "timestamp": pd.Timestamp.now().isoformat()
        }
        
        # Save to data/analytics/gaf/backtest_latest.json
        output_path = Path("data/analytics/gaf/backtest_latest.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
            
        logger.info(f"Saved backtest results to {output_path}")

    def print_metrics(self, df):
        acc = accuracy_score(df['actual'], df['prediction'])
        prec = precision_score(df['actual'], df['prediction'])
        rec = recall_score(df['actual'], df['prediction'])
        cm = confusion_matrix(df['actual'], df['prediction'])
        
        print("\n=== GAF Backtest Results ===")
        print(f"Ticker: {self.ticker}")
        print(f"Period: {self.start_date.date()} to {self.end_date.date()}")
        print(f"Total Trading Days: {len(df)}")
        print(f"Accuracy: {acc:.2%}")
        print(f"Precision: {prec:.4f}")
        print(f"Recall:    {rec:.4f}")
        print("Confusion Matrix:")
        print(cm)
        print("============================")
