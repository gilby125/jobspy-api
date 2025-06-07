#!/usr/bin/env python3
"""
Script to check environment variables and configuration settings.
Run this script to debug issues with environment variables.
"""
import os
import sys
import json
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def check_env():
    """Print environment variables and settings."""
    print("=== Environment Variables ===")
    env_vars = {
        "API_KEYS": os.getenv("API_KEYS", ""),
        "ENABLE_API_KEY_AUTH": os.getenv("ENABLE_API_KEY_AUTH", ""),
        "API_KEY_HEADER_NAME": os.getenv("API_KEY_HEADER_NAME", ""),
        "RATE_LIMIT_ENABLED": os.getenv("RATE_LIMIT_ENABLED", ""),
        "DEFAULT_PROXIES": os.getenv("DEFAULT_PROXIES", ""),
        "DEFAULT_SITE_NAMES": os.getenv("DEFAULT_SITE_NAMES", ""),
        "ENABLE_CACHE": os.getenv("ENABLE_CACHE", ""),
        "ENVIRONMENT": os.getenv("ENVIRONMENT", "")
    }
    
    for key, value in env_vars.items():
        print(f"{key}={value!r}")
    
    print("\n=== Testing Settings Loading ===")
    try:
        from app.core.config import settings
        
        print(f"API_KEYS: {settings.API_KEYS}")
        print(f"ENABLE_API_KEY_AUTH: {settings.ENABLE_API_KEY_AUTH}")
        print(f"API_KEY_HEADER_NAME: {settings.API_KEY_HEADER_NAME}")
        print(f"RATE_LIMIT_ENABLED: {settings.RATE_LIMIT_ENABLED}")
        print(f"DEFAULT_PROXIES: {settings.DEFAULT_PROXIES}")
        print(f"DEFAULT_SITE_NAMES: {settings.DEFAULT_SITE_NAMES}")
        print(f"ENABLE_CACHE: {settings.ENABLE_CACHE}")
        print(f"ENVIRONMENT: {settings.ENVIRONMENT}")
        
        print("\nSettings were loaded successfully!")
    except Exception as e:
        print(f"Error loading settings: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_env()
