
import pandas as pd
from pandas.tseries.offsets import BusinessDay

dates = pd.date_range(start="2023-12-25", end="2024-01-05", freq='B')
df = pd.DataFrame({"price": range(len(dates))}, index=dates)

# Logic: Next Business Day is in a different month
# Note: This logic assumes standard M-F business days. Holidays might be tricky if not accounted for.
# But for TSMOM, "approximate" month end is usually fine, or standard BDay is the standard proxy.
df['next_bday'] = df.index + BusinessDay(1)
df['is_ME'] = df['next_bday'].dt.month != df.index.month

print(df)
