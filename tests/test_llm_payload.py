import pandas as pd
from mie_lib.analytics.llm_payload import generate_llm_payload
from datetime import datetime
import json

# Mock DataFrame
df = pd.DataFrame({
    'date': [datetime.now().date()], 
    'close': [100], 
    'hmm_state': [0],
    'total_net_gex': [1000]
})

# Generate Payload for SPY (needs to have seasonality data for this to be fully real, 
# but if file missing it returns empty list which is also valid structure-wise)
payload = generate_llm_payload(df, "SPY")

print(json.dumps(payload, indent=2, default=str))
