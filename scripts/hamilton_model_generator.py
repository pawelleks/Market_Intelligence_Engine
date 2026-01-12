#!/usr/bin/env python3
"""
Hamilton Markov Switching Model for Recession Probability Detection

This script applies Hamilton's regime-switching logic to detect recession probabilities
using Real GDP growth rates. It uses a 2-regime Markov-switching autoregression model
to identify periods of high growth vs. low/negative growth.

Output: hamilton_model.parquet with recession probabilities for each quarter.
"""

import pandas as pd
import numpy as np
from pathlib import Path
import logging
from statsmodels.tsa.regime_switching.markov_autoregression import MarkovAutoregression

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
LOG = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
HP_MODEL_FILE = PROCESSED_DATA_DIR / "hp_model.parquet"
OUTPUT_FILE = PROCESSED_DATA_DIR / "hamilton_model.parquet"


def load_gdp_data():
    """
    Load Real GDP data from the existing HP Filter model output.
    
    Returns:
        pd.DataFrame: DataFrame with 'date' index and 'real_gdp' column
    """
    LOG.info("Loading Real GDP data from hp_model.parquet...")
    
    if not HP_MODEL_FILE.exists():
        raise FileNotFoundError(
            f"HP model file not found at {HP_MODEL_FILE}. "
            "Please run hp_model_generator.py first."
        )
    
    df = pd.read_parquet(HP_MODEL_FILE)
    
    # Ensure we have the required column
    if 'real_gdp' not in df.columns:
        raise ValueError("real_gdp column not found in hp_model.parquet")
    
    # Keep only date and real_gdp
    df = df[['real_gdp']].copy()
    
    LOG.info(f"Loaded {len(df)} quarters of Real GDP data.")
    return df


def calculate_growth_rates(df):
    """
    Calculate quarterly GDP growth rates as log differences.
    
    Formula: 100 * (ln(GDP_t) - ln(GDP_{t-1}))
    
    Args:
        df: DataFrame with 'real_gdp' column
        
    Returns:
        pd.Series: Growth rates (percentage points)
    """
    LOG.info("Calculating quarterly GDP growth rates (log differences)...")
    
    # Calculate log difference and multiply by 100 for percentage points
    growth_rates = 100 * (np.log(df['real_gdp']) - np.log(df['real_gdp'].shift(1)))
    
    # Drop NaN values from differencing
    growth_rates = growth_rates.dropna()
    
    LOG.info(f"Calculated {len(growth_rates)} growth rate observations.")
    LOG.info(f"Mean growth rate: {growth_rates.mean():.2f}%")
    LOG.info(f"Std growth rate: {growth_rates.std():.2f}%")
    
    return growth_rates


def fit_markov_model(growth_rates):
    """
    Fit Hamilton's Markov-switching autoregression model.
    
    Parameters:
        - k_regimes=2 (High Growth vs. Low/Negative Growth)
        - order=1 (AR(1) for stability)
        - switching_variance=True (allow volatility to differ between regimes)
    
    Args:
        growth_rates: pd.Series of GDP growth rates
        
    Returns:
        fitted model object
    """
    LOG.info("Fitting Hamilton Markov-switching model (2 regimes, AR(1))...")
    
    # Initialize model
    model = MarkovAutoregression(
        endog=growth_rates,
        k_regimes=2,
        order=1,
        switching_variance=True
    )
    
    # Fit the model
    LOG.info("Training model... (this may take a moment)")
    fitted_model = model.fit(
        search_reps=20,  # Try multiple starting values
        disp=False  # Suppress iteration output
    )
    
    LOG.info("Model fitting complete.")
    LOG.info(f"\nModel Summary:\n{fitted_model.summary()}")
    
    return fitted_model


def identify_recession_regime(fitted_model):
    """
    Identify which regime corresponds to "Recession" (lower mean growth).
    
    Args:
        fitted_model: Fitted MarkovAutoregression model
        
    Returns:
        int: Index of the recession regime (0 or 1)
    """
    LOG.info("Identifying recession regime...")
    
    # Extract regime means
    # The model parameters are stored in 'params'
    # For a Markov model with AR(1), params includes regime means
    regime_means = fitted_model.params[['const[0]', 'const[1]']].values
    
    LOG.info(f"Regime 0 mean growth: {regime_means[0]:.2f}%")
    LOG.info(f"Regime 1 mean growth: {regime_means[1]:.2f}%")
    
    # Recession regime is the one with lower (or negative) mean growth
    recession_regime = 0 if regime_means[0] < regime_means[1] else 1
    
    LOG.info(f"Recession regime identified: Regime {recession_regime}")
    
    return recession_regime


def extract_probabilities(fitted_model, recession_regime, original_dates):
    """
    Extract smoothed recession probabilities.
    
    Args:
        fitted_model: Fitted MarkovAutoregression model
        recession_regime: Index of recession regime (0 or 1)
        original_dates: DatetimeIndex from original GDP data
        
    Returns:
        pd.DataFrame: DataFrame with date, recession_prob, growth_rate
    """
    LOG.info("Extracting smoothed recession probabilities...")
    
    # Get smoothed marginal probabilities
    smoothed_probs = fitted_model.smoothed_marginal_probabilities
    
    # Extract recession probabilities
    recession_probs = smoothed_probs.iloc[:, recession_regime]
    
    # Create results DataFrame
    # Note: We lost the first observation due to differencing
    # Align dates with growth rate observations
    dates_aligned = original_dates[1:len(recession_probs)+1]
    
    results = pd.DataFrame({
        'date': dates_aligned,
        'recession_prob': recession_probs.values,
        'growth_rate': fitted_model.model.endog
    })
    
    results.set_index('date', inplace=True)
    
    return results


def save_results(results):
    """
    Save results to parquet file.
    
    Args:
        results: DataFrame with recession probabilities
    """
    LOG.info(f"Saving results to {OUTPUT_FILE}...")
    
    # Ensure output directory exists
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Save to parquet
    results.to_parquet(OUTPUT_FILE)
    
    LOG.info(f"Results saved successfully.")


def main():
    """
    Main execution function.
    """
    LOG.info("Initializing Hamilton Markov Switching Model Calculation...")
    
    try:
        # 1. Load GDP data
        gdp_df = load_gdp_data()
        
        # 2. Calculate growth rates
        growth_rates = calculate_growth_rates(gdp_df)
        
        # 3. Fit Markov-switching model
        fitted_model = fit_markov_model(growth_rates)
        
        # 4. Identify recession regime
        recession_regime = identify_recession_regime(fitted_model)
        
        # 5. Extract probabilities
        results = extract_probabilities(fitted_model, recession_regime, gdp_df.index)
        
        # 6. Save results
        save_results(results)
        
        # 7. Print current recession probability
        latest_date = results.index[-1]
        latest_prob = results.iloc[-1]['recession_prob']
        latest_growth = results.iloc[-1]['growth_rate']
        
        print("\n" + "="*60)
        print("Hamilton Markov Switching Model: Latest Results")
        print("="*60)
        print(f"Date:                 {latest_date.strftime('%Y-%m-%d')} (Q{(latest_date.month-1)//3 + 1} {latest_date.year})")
        print(f"Recession Probability: {latest_prob*100:.2f}%")
        print(f"GDP Growth Rate:       {latest_growth:.2f}%")
        print("="*60)
        print()
        
        LOG.info("Hamilton model calculation complete!")
        
    except Exception as e:
        LOG.error(f"Error during Hamilton model calculation: {e}")
        raise


if __name__ == "__main__":
    main()
