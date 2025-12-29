import os
import json
import re
from pathlib import Path
from datetime import datetime
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from mie_lib.utils.paths import DATA_DIR, ROOT

def _load_env_fallback():
    """Manually parse .env file if available."""
    env_path = ROOT / ".env"
    if env_path.exists():
        try:
            lines = env_path.read_text().splitlines()
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k == "OPENAI_API_KEY" and v:
                     os.environ["OPENAI_API_KEY"] = v
        except Exception: pass

def generate_daily_report(ticker: str = "SPY", model: str = "gpt-4-turbo-preview") -> dict:
    """
    Reads the latest AI Context JSON and the System Prompt,
    generates a daily market analysis report via LLM,
    and saves it to the reports directory.
    """
    # 0. Load Env Var Fallback
    if not os.environ.get("OPENAI_API_KEY"):
         _load_env_fallback()

    # 1. Paths
    context_path = DATA_DIR / "ai_context" / "spy_latest.json" # Assuming spy_latest is the canonical active one
    prompt_path = ROOT / "prompts" / "market_analyst.txt"
    
    report_dir = DATA_DIR / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_active_path = report_dir / "daily_report_latest.json"
    
    # 2. Validation
    if not context_path.exists():
        return {"status": "error", "message": f"Context file not found: {context_path}"}
    if not prompt_path.exists():
        return {"status": "error", "message": f"Prompt file not found: {prompt_path}"}
    
    # 3. Load Inputs
    try:
        with open(context_path, "r") as f:
            context_data = json.load(f)
    except Exception as e:
        return {"status": "error", "message": f"Failed to load context: {e}"}
    
    try:
        system_prompt = prompt_path.read_text(encoding="utf-8")
    except Exception as e:
        return {"status": "error", "message": f"Failed to load prompt: {e}"}
    
    context_str = json.dumps(context_data, indent=2)
    
    # 4. Call LLM
    api_key = os.environ.get("OPENAI_API_KEY")
    content = ""
    
    if not api_key:
        print("Warning: OPENAI_API_KEY not set. Generating mock report.")
        content = f"# Daily Market Intelligence (MOCK)\n\n**Signal:** NEUTRAL\n**Conviction:** 0%\n\n**Warning:** API Key missing. This is a placeholder report for {ticker}."
    else:
        if OpenAI is None:
             return {"status": "error", "message": "openai library not installed"}
        
        client = OpenAI(api_key=api_key)
        
        start_msg = f"Here is the Market State Vector for {ticker} (Date: {datetime.now().strftime('%Y-%m-%d')}):\n\n{context_str}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": start_msg}
        ]
        
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.7
            )
            content = response.choices[0].message.content
        except Exception as e:
            return {"status": "error", "message": f"OpenAI API error: {e}"}

    # 5. Save Output
    # Simple parsing of Signal/Conviction from Markdown
    signal_match = re.search(r"\*\*Signal:\*\*\s*(.*)", content, re.IGNORECASE)
    conviction_match = re.search(r"\*\*Conviction:\*\*\s*(.*)", content, re.IGNORECASE)
    
    signal = signal_match.group(1).strip(" []") if signal_match else "NEUTRAL"
    conviction = conviction_match.group(1).strip(" []%") if conviction_match else "0"
    
    # Clean conviction to just number if possible
    conviction_val = ''.join(filter(str.isdigit, conviction))
    if not conviction_val: conviction_val = 0
    else: conviction_val = int(conviction_val)

    hmm_desc = context_data.get("regime", {}).get("hmm", {}).get("desc", "Unknown")

    output = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "ticker": ticker,
        "content": content,
        "scorecard": {
            "signal": signal,
            "conviction": conviction_val,
            "regime": hmm_desc
        }
    }
    
    try:
        with open(report_active_path, "w") as f:
            json.dump(output, f, indent=2)
            
        # Archive
        today_str = datetime.now().strftime("%Y-%m-%d")
        archive_path = report_dir / "archive" / f"daily_report_{today_str}.json"
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with open(archive_path, "w") as f:
            json.dump(output, f, indent=2)
    except Exception as e:
        return {"status": "error", "message": f"Failed to save report: {e}"}
        
    return {"status": "ok", "path": str(report_active_path)}
