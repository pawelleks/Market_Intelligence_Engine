import os
from pathlib import Path

# mie_lib/services/terms_service.py

# Path to the terms directory relative to this file
# This file is in src/mie_lib/services/
# Terms are in src/mie_lib/terms/
TERMS_DIR = Path(__file__).resolve().parent.parent / "terms"
CURRENT_TERMS_VERSION = "1.0"

def load_terms(version: str = CURRENT_TERMS_VERSION) -> str:
    """Load terms content by version."""
    terms_file = TERMS_DIR / f"terms_v{version}.md"
    
    if not terms_file.exists():
        raise FileNotFoundError(f"Terms version {version} not found at {terms_file}")
    
    with open(terms_file, 'r', encoding='utf-8') as f:
        return f.read()

def get_current_terms_version() -> str:
    """Get current active terms version."""
    return CURRENT_TERMS_VERSION

def needs_terms_update(user) -> bool:
    """Check if user needs to accept updated terms."""
    # If user hasn't accepted any terms
    if not user.terms_accepted:
        return True
    
    # If accepted version is different from current
    # (assuming newer versions require re-acceptance)
    if user.terms_version != CURRENT_TERMS_VERSION:
        return True
    
    return False
