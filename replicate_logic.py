
import json

# The JSON returned by curl
data = {
  "SPX": {
    "close": 6843.22,
    "0dte": {
      "breakeven_move": 57.95,
      "sigma_move": 49.26,
      "upper_breakeven": 6901.17,
      "lower_breakeven": 6785.27,
      "upper_sigma": 6892.48,
      "lower_sigma": 6793.96,
      "date": "Wed Feb 18",
      "target_date": "2026-02-18",
      "dte": 1,
      "data_quality": "good",
      "debug": {
        "atm_strike": 6845.0,
        "call_price": 47.55,
        "put_price": 10.4
      }
    },
    "weekly": {
      "breakeven_move": 98.4,
      "sigma_move": 83.64,
      "upper_breakeven": 6941.62,
      "lower_breakeven": 6744.82,
      "upper_sigma": 6926.86,
      "lower_sigma": 6759.58,
      "date": "Fri Feb 20",
      "target_date": "2026-02-20",
      "dte": 2,
      "data_quality": "good",
      "debug": {
        "atm_strike": 6845.0,
        "call_price": 68.65,
        "put_price": 29.75
      }
    },
    "monthly": {
      "breakeven_move": 163.4,
      "sigma_move": 138.89,
      "upper_breakeven": 7006.62,
      "lower_breakeven": 6679.82,
      "upper_sigma": 6982.11,
      "lower_sigma": 6704.33,
      "date": "Fri Feb 27",
      "target_date": "2026-02-27",
      "dte": 9,
      "data_quality": "good",
      "debug": {
        "atm_strike": 6845.0,
        "call_price": 103.2,
        "put_price": 60.2
      }
    }
  },
  "SPY": {
    "close": 682.85,
    "0dte": {
      "breakeven_move": 5.32,
      "sigma_move": 4.52,
      "upper_breakeven": 688.17,
      "lower_breakeven": 677.53,
      "upper_sigma": 687.37,
      "lower_sigma": 678.33,
      "date": "Wed Feb 18",
      "target_date": "2026-02-18",
      "dte": 1,
      "data_quality": "good",
      "debug": {
        "atm_strike": 683.0,
        "call_price": 2.56,
        "put_price": 2.76
      }
    },
    "weekly": {
      "breakeven_move": 9.65,
      "sigma_move": 8.2,
      "upper_breakeven": 692.5,
      "lower_breakeven": 673.2,
      "upper_sigma": 691.05,
      "lower_sigma": 674.65,
      "date": "Fri Feb 20",
      "target_date": "2026-02-20",
      "dte": 2,
      "data_quality": "good",
      "debug": {
        "atm_strike": 683.0,
        "call_price": 4.87,
        "put_price": 4.79
      }
    },
    "monthly": {
      "breakeven_move": 16.53,
      "sigma_move": 14.05,
      "upper_breakeven": 699.38,
      "lower_breakeven": 666.32,
      "upper_sigma": 696.9,
      "lower_sigma": 668.8,
      "date": "Fri Feb 27",
      "target_date": "2026-02-27",
      "dte": 9,
      "data_quality": "good",
      "debug": {
        "atm_strike": 683.0,
        "call_price": 8.55,
        "put_price": 7.98
      }
    }
  }
}

ticker = "SPY"
item = data.get(ticker)

tenors = [
    {"label": "0DTE", "staticKey": "0dte"},
    {"label": "Weekly", "staticKey": "weekly"},
    {"label": "Monthly", "staticKey": "monthly"}
]

if item:
    close = item.get("close")
    print(f"Close: {close}")
    for t in tenors:
        key = t["staticKey"]
        t_data = item.get(key)
        if t_data:
            print(f"{t['label']}: Move={t_data.get('breakeven_move')}")
        else:
            print(f"{t['label']}: MISSING")
else:
    print("Item is None")
