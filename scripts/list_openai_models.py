#!/usr/bin/env python3
"""
List OpenAI Models

Queries the OpenAI API to list all available models for the current API key.
Filters for 'gpt' models to reduce noise.
"""
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))

# from mie_lib.utils.paths import ROOT
ROOT = PROJECT_ROOT
env_path = ROOT / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            if line.strip() and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip("'").strip('"')

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai library not installed.")
    sys.exit(1)

def list_models():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not found in environment.")
        return

    client = OpenAI(api_key=api_key)
    
    try:
        print(f"Querying OpenAI API with key ending in ...{api_key[-4:]}")
        models = client.models.list()
        
        print("\n=== Available GPT Models ===")
        found_any = False
        # Sort by id for readability
        for m in sorted(models.data, key=lambda x: x.id):
            if "gpt" in m.id:
                print(f" - {m.id}")
                found_any = True
        
        if not found_any:
            print("No models containing 'gpt' found. Listing all:")
            for m in sorted(models.data, key=lambda x: x.id):
                print(f" - {m.id}")
                
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    list_models()
