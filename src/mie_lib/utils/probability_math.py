import numpy as np
from scipy.interpolate import UnivariateSpline, griddata, PchipInterpolator
from scipy.ndimage import gaussian_filter1d
from scipy.integrate import cumulative_trapezoid
from typing import List, Dict, Any, Tuple
import logging

LOG = logging.getLogger(__name__)

class BreedenLitzenberger:
    """
    Implements the Breeden-Litzenberger result to extract Risk-Neutral Probability Density Functions (PDFs)
    from Option Prices.
    
    Formula: PDF(K) = e^(rT) * (d^2 C / dK^2)
    """

    def __init__(self, risk_free_rate: float = 0.04, equity_risk_premium: float = 0.04):
        self.r = risk_free_rate
        self.erp = equity_risk_premium

    def calculate_pdf(
        self,
        strikes: List[float],
        call_prices: List[float],
        dte_days: float,
        smooth_factor: float = None
    ) -> Dict[str, Any]:
        """
        Calculates the PDF from a set of Strike and Call Prices.

        Args:
            strikes: List of strike prices.
            call_prices: List of corresponding call option prices.
            dte_days: Days to expiration.
            smooth_factor: Smoothing factor 's' for UnivariateSpline. 
                           Higher = smoother (less noise, potentially less detail).
                           None or 0 = no smoothing (interpolation).

        Returns:
            Dictionary containing:
            - 'strikes': The x-axis values (Price)
            - 'pdf': The y-axis values (Probability Density)
            - 'T': Time to maturity used
            - 'drift_adjusted_strikes': Strikes shifted for Real-World drift
        """
        # 1. Prepare Data
        if len(strikes) != len(call_prices) or len(strikes) < 5:
            LOG.warning("Insufficient data for PDF calculation.")
            return {}

        # Sort by strike
        data = sorted(zip(strikes, call_prices), key=lambda x: x[0])
        K_arr = np.array([x[0] for x in data])
        C_arr = np.array([x[1] for x in data])

        # Deduplicate strikes (SPX+SPXW can have same strike): average prices
        unique_K, inv_idx = np.unique(K_arr, return_inverse=True)
        if len(unique_K) < len(K_arr):
            avg_C = np.zeros(len(unique_K))
            counts = np.zeros(len(unique_K))
            for i, idx in enumerate(inv_idx):
                avg_C[idx] += C_arr[i]
                counts[idx] += 1
            K_arr = unique_K
            C_arr = avg_C / counts

        # Filter out zero/negative call prices (bad bids)
        valid = C_arr > 0
        if valid.sum() < 5:
            LOG.warning("Insufficient non-zero call prices after filtering zeros.")
            return {}
        K_arr = K_arr[valid]
        C_arr = C_arr[valid]

        # Trim far-OTM tail where prices are at minimum tick (noise)
        # Sparse, flat data at the boundary causes interpolation artifacts
        MIN_USEFUL_PRICE = 0.02
        while len(K_arr) > 10 and C_arr[-1] < MIN_USEFUL_PRICE:
            K_arr = K_arr[:-1]
            C_arr = C_arr[:-1]

        if len(K_arr) < 5:
            LOG.warning("Insufficient data after tail trimming.")
            return {}

        T = max(dte_days / 365.25, 0.001) # Avoid divide by zero

        # 2. Monotone Interpolation (PCHIP)
        # PchipInterpolator preserves shape monotonicity — prevents
        # oscillation at boundaries where strike spacing is sparse
        try:
            pchip = PchipInterpolator(K_arr, C_arr)

            # 3. Second Derivative → Probability Density
            # PDF(K) = e^(rT) * d²C/dK²
            densities = pchip.derivative(nu=2)(K_arr)
            
            # 4. Apply Breeden-Litzenberger Formula: PDF = e^(rT) * C''
            # Note: C'' should be positive (convexity of option prices). 
            # Noise might create negative curvature. specific handling: clip to 0.
            
            pdf_raw = np.exp(self.r * T) * densities
            pdf_clean = np.maximum(pdf_raw, 0.0) # Clip negative probabilities

            # Gaussian Smoothing (User Request) to remove jaggedness
            # sigma=2.0 provides a good balance for discrete strike gaps
            pdf_smooth = gaussian_filter1d(pdf_clean, sigma=2.0)
            
            # Normalize area to 1
            # Trapezoidal integration
            area = float(np.trapz(pdf_smooth, K_arr))
            if area > 0:
                pdf_normalized = pdf_smooth / area
            else:
                pdf_normalized = pdf_clean

            # 6. CDF and Probability Above (Survival Function)
            # CDF = Ex integral of PDF
            # Prob Above = 1 - CDF
            try:
                # Use trapezoidal cumulative integration
                # cumulative_trapezoid returns array of len(N-1) by default, or N if initial is set
                cdf = cumulative_trapezoid(pdf_normalized, K_arr, initial=0)
                # Ensure it ends at 1.0 (normalization might have slight error)
                if cdf[-1] > 0:
                    cdf = cdf / cdf[-1]
                
                prob_above = 1.0 - cdf
            except Exception as e:
                LOG.warning(f"Failed to calculate CDF: {e}")
                prob_above = np.zeros_like(K_arr)

            # 5. Drift Adjustment (Real-World Transformation)
            # Simple shift of the distribution center
            # X_real = X_rn * exp(ERP * T)
            drift_factor = np.exp(self.erp * T)
            adjusted_strikes = K_arr * drift_factor

            return {
                "T": T,
                "strikes": K_arr.tolist(),
                "price_axis": K_arr.tolist(), # Raw Market (Risk-Neutral)
                "pdf": pdf_normalized.tolist(),
                "prob_above": prob_above.tolist(),
                "real_world_price_axis": adjusted_strikes.tolist(),
                "metadata": {
                    "area": area,
                    "smoothing": smooth_factor
                }
            }

        except Exception as e:
            LOG.error(f"Error in Breeden-Litzenberger calculation: {e}", exc_info=True)
            return {}

    def generate_surface(
        self, 
        chain_results: List[Dict[str, Any]], 
        current_spot: float,
        days_out: int = 45,
        grid_points_x: int = 50, # DTE
        grid_points_y: int = 100 # Strikes
    ) -> Dict[str, Any]:
        """
        Generates a dense surface grid (Price x Time) for Probability Above.
        Interpolates missing days and prices.
        """
        try:
            # 1. Collect all valid data points (DTE, Strike, Prob)
            points = []
            values = []

            for res in chain_results:
                dte = res['dte']
                if dte > days_out + 5: # Limit interpolation source
                    continue
                
                # Get distribution data
                if 'distribution' not in res:
                    continue
                    
                strikes = res['distribution'].get('real_world_price_axis', res['distribution']['strikes'])
                probs = res['distribution'].get('prob_above', [])

                if not probs or len(strikes) != len(probs):
                    continue

                for k, p in zip(strikes, probs):
                    points.append([dte, k])
                    values.append(p)

            if not points:
                return {}

            points = np.array(points)
            values = np.array(values)

            # 2. Create Target Grid
            # DTE: 0 to 45
            grid_dte = np.linspace(0, days_out, grid_points_x)
            
            # Strikes: Spot +/- 15%
            min_k = current_spot * 0.85
            max_k = current_spot * 1.15
            grid_strikes = np.linspace(min_k, max_k, grid_points_y)

            # Meshgrid for interpolation
            # We want a heatmap matrix: Rows = Strikes, Cols = DTE
            # griddata expects points and returns Z for (X, Y)
            
            # Generate coordinate pairs for the grid
            GX, GY = np.meshgrid(grid_dte, grid_strikes)
            
            # 3. Interpolate
            # 'linear' is safer than cubic for probabilities (bounded 0-1)
            # fill_value=nan, but we might want to extrapolate or clip
            grid_z = griddata(points, values, (GX, GY), method='linear', fill_value=np.nan)

            # Handle NaNs (Extrapolation) - Simple nearest fill or 0/1 clamping
            # For now, let's replace NaNs with nearest valid if possible, or just 0/1 based on strike
            # A simple heuristic: High strike NaN -> 0, Low strike NaN -> 1
            
            mask_nan = np.isnan(grid_z)
            if np.any(mask_nan):
                # Fallback to nearest for gaps
                grid_z_near = griddata(points, values, (GX, GY), method='nearest')
                grid_z[mask_nan] = grid_z_near[mask_nan]

            return {
                "dte_axis": grid_dte.tolist(),
                "strike_axis": grid_strikes.tolist(),
                "prob_above_surface": grid_z.tolist() # 2D Array [Strike][DTE]
            }

        except Exception as e:
            LOG.error(f"Error generating surface: {e}", exc_info=True)
            return {}

    def calculate_quantiles_from_pdf(self, strikes: List[float], probabilities: List[float]) -> Dict[str, float]:
        """
        Calculates price quantiles (p05...p95) from a PDF.
        """
        try:
            if not strikes or not probabilities or len(strikes) != len(probabilities):
                return {}
            
            strikes_arr = np.array(strikes)
            pdf_arr = np.array(probabilities)
            
            # Normalize PDF
            area = np.trapz(pdf_arr, strikes_arr)
            if area > 0: pdf_arr /= area
            
            # CDF
            cdf_arr = cumulative_trapezoid(pdf_arr, strikes_arr, initial=0)
            if cdf_arr[-1] > 0: cdf_arr /= cdf_arr[-1] # Ensure 0-1 range
            
            # Inverse CDF Interpolation (High-Res Deciles for Heatmap)
            # p05, p10, p20, p30, p40, p50, p60, p70, p80, p90, p95
            q_values = [0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95]
            q_keys = ["p05", "p10", "p20", "p30", "p40", "p50", "p60", "p70", "p80", "p90", "p95"]
            
            prices = np.interp(q_values, cdf_arr, strikes_arr)
            
            return {k: float(v) for k, v in zip(q_keys, prices)}
        except Exception as e:
            LOG.warning(f"Quantile calculation failed: {e}")
            return {}

    def generate_forward_projection_quantiles(
        self,
        chain_results: List[Dict[str, Any]],
        current_spot: float,
        days_out: int = 45
    ) -> List[Dict[str, Any]]:
        """
        Generates Quantile Fan Chart data (Forward Projection).
        Calculates p05...p95 for each expiration and interpolates daily.
        """
        try:
            from datetime import date, timedelta
            
            q_keys = ["p05", "p10", "p20", "p30", "p40", "p50", "p60", "p70", "p80", "p90", "p95"]

            # 1. Extract Quantiles for each Expiration
            exp_points = [] # list of (dte, {quantiles})
            
            # Add T=0 point (Current Spot)
            t0_point = {'dte': 0}
            for k in q_keys:
                t0_point[k] = current_spot
            exp_points.append(t0_point)

            for res in chain_results:
                dte = res['dte']
                if dte > days_out + 10: continue
                
                dist = res.get('distribution', {})
                strikes = dist.get('real_world_price_axis', dist.get('strikes', []))
                probs = dist.get('pdf', [])
                
                if not strikes or not probs: continue
                
                quantiles = self.calculate_quantiles_from_pdf(strikes, probs)
                if quantiles:
                    quantiles['dte'] = dte
                    exp_points.append(quantiles)

            if len(exp_points) < 2:
                return []
                
            # Sort by DTE
            exp_points.sort(key=lambda x: x['dte'])
            
            # 2. Daily Interpolation (0 to days_out)
            final_projection = []
            today = date.today()
            
            dtes = np.array([ep['dte'] for ep in exp_points])
            
            # Prepare Cubic Splines for all 11 keys
            from scipy.interpolate import CubicSpline
            splines = {}
            for k in q_keys:
                y = np.array([ep[k] for ep in exp_points])
                splines[k] = CubicSpline(dtes, y, bc_type='natural')
            
            for i in range(days_out + 1):
                target_date = today + timedelta(days=i)
                x = float(i)
                
                row = {
                    "date": target_date.isoformat(),
                    "dte": i
                }
                for k in q_keys:
                    row[k] = float(splines[k](x))
                    
                final_projection.append(row)
                
            return final_projection

        except Exception as e:
            LOG.error(f"Error generating fan chart: {e}", exc_info=True)
            return []
