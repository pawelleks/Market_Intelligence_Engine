
import unittest
import pandas as pd
import numpy as np
from datetime import date
from mie_lib.analytics.tsmom.engine import calculate_tsmom_for_ticker

class TestTsmomMonthlyGate(unittest.TestCase):
    def test_intra_month_volatility_logic(self):
        """
        Verify that TSMOM signal holds through intra-month volatility.
        Scenario:
          - Starts with positive signal from previous month.
          - Mid-month: ret_12m dips negative (Theoretical = -1).
          - Assertion: tsmom_dir REMAINS 1 (since we only update on month ends).
        """
        # Create 30 days of data
        dates = pd.date_range(start="2023-01-01", periods=30, freq='B')
        df = pd.DataFrame(index=dates)
        
        # Fake "price" to manipulate ret_12m
        # We manually inject ret_12m for testing calculating logic directly if possible, 
        # but the function computes it from price. 
        # So we mock price.
        # ret_12m = P(t) / P(t-252) - 1.
        # Let's just mock the 'ret_12m' column computation or override expected behavior?
        # The function overwrites 'ret_12m'.
        # So we must set prices.
        # Assume lookback=1 for simplicity? Function allows param.
        lookback = 1
        
        # Day 0: Price 100
        # Day 1 (Month Start): Price 105 -> Ret = 0.05 (>0) -> Signal +1
        # Day 15 (Mid Month): Price 95 -> Ret = -0.05 (<0) -> Signal -1 (Theoretical)
        # Day 29 (Next Month Start... wait, we need Month End to trigger change).
        
        prices = [100.0] * 30
        df['price'] = prices
        
        # Set prices to control returns relative to lookback (offset 1)
        # We need P[t-1] to reference previous day.
        
        # Day 1 (Jan 2): We want ret > 0. P[0]=100. P[1]=110.
        df.iloc[1, df.columns.get_loc('price')] = 110.0
        
        # Day 15 (Jan ~20): We want ret < 0. P[14]=100. P[15]=90.
        df.iloc[15, df.columns.get_loc('price')] = 90.0
        
        # Run Calc
        # Note: calculate_tsmom_for_ticker will compute is_month_end.
        # Jan 2023 ends on Jan 31.
        # Our data is Jan 2 to Feb 10 approx.
        # So somewhere around index ~21/22 is Jan 31 (Month End).
        
        res = calculate_tsmom_for_ticker("TEST", df, lookback_days=1)
        
        # Check Day 15 (Mid Month)
        day_15 = res.iloc[15]
        print(f"Day 15 Date: {day_15.name}, Ret: {day_15['ret_12m']}, ME: {day_15['is_month_end']}")
        
        # Assertions for Mid-Month Volatility
        self.assertEqual(day_15['theoretical_signal'], -1, "Theoretical signal should track daily return (-1)")
        
        # The Actual Signal (tsmom_dir) should be FORWARD FILLED from the LAST MONTH END (PREVIOUS YEAR END).
        # Since our data starts Jan 1, the "previous" month end is unknown/NaN -> 0.
        # So Day 15 should actually be 0? 
        # Wait, if we start cold, ffill from nothing is NaN/0.
        # We need to simulate a previous Month End to establish a position to HOLD.
        
        # Let's adjust data to contain a Dec 31 Month End at row 0.
        # dates starting 2022-12-30.
        dates_v2 = pd.date_range(start="2022-12-28", periods=40, freq='B')
        df2 = pd.DataFrame(index=dates_v2)
        df2['price'] = 100.0
        
        # Dec 30 (Fri) is likely Month End (or business day approx).
        # Next BDay is Jan 2 (New Month). So Dec 30 is ME.
        # Row 2 (Dec 30).
        # Let's make Dec 30 signal POSITIVE. 
        # P[Dec 29] = 100. P[Dec 30] = 110. Ret > 0.
        # Signal @ Dec 30 = +1.
        df2.iloc[1, df2.columns.get_loc('price')] = 100.0 # Dec 29
        df2.iloc[2, df2.columns.get_loc('price')] = 110.0 # Dec 30
        
        # Now Jan 15 (mid month).
        # We want ret < 0.
        # P[Jan 14] = 100. P[Jan 15] = 90.
        # Locate index for approx Jan 15.
        idx_jan15 = 12 
        df2.iloc[idx_jan15, df2.columns.get_loc('price')] = 90.0 # Drop price to create neg return vs previous day
        
        res2 = calculate_tsmom_for_ticker("TEST", df2, lookback_days=1)
        
        # Verify Dec 30 is Month End
        row_dec30 = res2.iloc[2]
        self.assertTrue(row_dec30['is_month_end'], f"Dec 30 should be month end. Date: {row_dec30.name}")
        self.assertEqual(row_dec30['tsmom_dir'], 1, "Signal at Dec 30 should be 1")
        
        # Verify Jan 15 (Mid Month)
        row_jan15 = res2.iloc[idx_jan15]
        self.assertFalse(row_jan15['is_month_end'], "Jan 15 should NOT be month end")
        self.assertEqual(row_jan15['theoretical_signal'], -1, "Mid-month dip should show Theoretical -1")
        self.assertEqual(row_jan15['tsmom_dir'], 1, "Actual Position should HOLD 1 from Dec 30 despite dip")
        
        print("✅ Intra-month volatility test passed: Theoretical flipped, Actual held.")

if __name__ == '__main__':
    unittest.main()
