# PROJECT ARCHITECTURE & CONSTRAINTS

## ⚠️ NON-NEGOTIABLE DATA STRATEGY
**Do not violate these rules. Do not suggest refactoring these components.**

### 1. Option Chain Data Source
* **Provider:** Massive.com (Flat Files).
* **Role:** PRIMARY SOURCE OF TRUTH.
* **Reasoning:** We rely on daily EOD snapshots for reliability.
* **Prohibited:** Do NOT use `yfinance`, `yahooquery`, or any API for fetching full option chains. They are rate-limited and unreliable for our volume.

### 2. Data Enrichment
* **Provider:** yfinance.
* **Role:** ENRICHMENT ONLY.
* **Usage:** Only used to fetch Underlying Price, OHLCV, and single-contract metadata *after* the chain is loaded from Massive.

### 3. Pipeline Flow
* The pipeline is strictly **Split-Source**: 
    1. Ingest Massive File (Structure).
    2. Enrich with Yahoo (Metadata).
* **Do not merge these into a single API call.**