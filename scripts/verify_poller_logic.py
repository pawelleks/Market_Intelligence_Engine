import os
import asyncio
import logging
from thetadata import ThetaClient, StockReqType

# Configure Logging
logging.basicConfig(level=logging.INFO)
LOG = logging.getLogger("verifier")

async def test_poller():
    username = os.getenv("THETADATA_USERNAME")
    passwd = os.getenv("THETADATA_PASSWORD")
    
    # Debug password (mask middle)
    if passwd:
        masked = passwd[0] + "*"*(len(passwd)-2) + passwd[-1]
        LOG.info(f"Loaded Password: {masked} (Length: {len(passwd)})")
        if passwd.startswith("'") and passwd.endswith("'"):
            LOG.info("Detected quotes, stripping...")
            passwd = passwd[1:-1]
    
    LOG.info(f"Connecting with User: {username}")
    
    client = ThetaClient(username=username, passwd=passwd, host="theta_terminal")
    client.connect()
    LOG.info("Connected to Command Port.")
    
    loop = asyncio.get_running_loop()
    
    tickers = ["SPY", "SPX", "QQQ", "IWM"]
    
    for i in range(5):
        LOG.info(f"--- Poll Iteration {i} ---")
        for ticker in tickers:
            try:
                LOG.info(f"Polling {ticker}...")
                quote = await loop.run_in_executor(
                    None, 
                    lambda: client.get_last_stock(req=StockReqType.TRADE, root=ticker)
                )
                
                if quote is None or quote.empty:
                    LOG.info(f"TRADE failed, trying QUOTE for {ticker}...")
                    quote = await loop.run_in_executor(
                        None, 
                        lambda: client.get_last_stock(req=StockReqType.QUOTE, root=ticker)
                    )
                
                if quote is not None and not quote.empty:
                    price = quote['price'].iloc[0]
                    LOG.info(f"SUCCESS: {ticker} = {price}")
                else:
                    LOG.error(f"FAILED: No data for {ticker}")
                    
            except Exception as e:
                LOG.error(f"Error polling {ticker}: {e}")
        
        await asyncio.sleep(1)

    client.close()

if __name__ == "__main__":
    asyncio.run(test_poller())
