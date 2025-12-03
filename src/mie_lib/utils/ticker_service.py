import yaml
from pathlib import Path
from typing import List, Dict, Any, Set, Tuple

# Assume config files are located in the project's root 'config/' directory
CONFIG_DIR = Path("config")

def _load_yaml(filename: str) -> Dict[str, Any]:
    """Loads a YAML file from the config directory safely."""
    path = CONFIG_DIR / filename
    if not path.exists():
        return {}
    try:
        with open(path, 'r') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Warning: Failed to load config file {filename}: {e}")
        return {}

def get_available_tickers() -> List[str]:
    """Loads the base list of all available tickers."""
    data = _load_yaml("ticker_list.yml")
    tickers = data.get("tickers", [])
    return [t.upper() for t in tickers if isinstance(t, str)]

def get_ticker_groups() -> Dict[str, List[str]]:
    """Loads and normalizes the user-defined analytical groups."""
    data = _load_yaml("ticker_groups.yml")
    groups = data.get("groups", {})
    normalized_groups = {}
    for group_name, ticker_list in groups.items():
        if isinstance(ticker_list, list):
            # Normalize group name to uppercase to ensure case-insensitive matching
            normalized_groups[group_name.upper()] = [t.upper() for t in ticker_list if isinstance(t, str)]
    return normalized_groups

def get_tickers_for_analysis(analysis_key: str) -> List[str]:
    """
    Determines the final, unique list of tickers available for a specific analysis page 
    by resolving groups defined in analysis_scope.yml.
    """
    scope_data = _load_yaml("analysis_scope.yml")
    ticker_groups = get_ticker_groups()
    
    # Get the list of groups/tickers defined for the specific analysis_key
    scope_list = scope_data.get("scope", {}).get(analysis_key, [])
    
    final_tickers: Set[str] = set()
    
    for item in scope_list:
        if isinstance(item, str):
            # Check if item is a group (case-insensitive)
            if item.upper() in ticker_groups:
                # Item is a group name, add all tickers from that group
                final_tickers.update(ticker_groups[item.upper()])
            else:
                # Item is assumed to be an individual ticker
                final_tickers.add(item.upper())

    # Filter to ensure only tickers present in the master list are included
    master_list = get_available_tickers()
    return sorted([t for t in final_tickers if t in master_list])
