#!/usr/bin/env python3
"""
Script to detect environment variable conflicts between different sources.
This helps diagnose issues where values in code, .env, or Docker might conflict.
"""
import json
import os
import sys
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def color_text(text, color_code):
    """Add color to terminal output."""
    return f"\033[{color_code}m{text}\033[0m"

def red(text):
    return color_text(text, 31)

def green(text):
    return color_text(text, 32)

def yellow(text):
    return color_text(text, 33)

def get_docker_env_vars():
    """Get environment variables from docker-compose.yml."""
    docker_compose_path = Path("docker-compose.yml")
    if not docker_compose_path.exists():
        return {}
    
    try:
        import yaml
        with open(docker_compose_path, 'r') as f:
            docker_compose = yaml.safe_load(f)
        
        if not docker_compose or 'services' not in docker_compose:
            return {}
            
        for service in docker_compose['services'].values():
            if 'environment' in service:
                env_vars = {}
                for env in service['environment']:
                    if isinstance(env, str) and '=' in env:
                        key, value = env.split('=', 1)
                        env_vars[key] = value
                    elif isinstance(env, dict):
                        env_vars.update(env)
                return env_vars
        return {}
    except Exception as e:
        print(f"Error parsing docker-compose.yml: {e}")
        return {}

def get_dotenv_vars():
    """Get environment variables from .env and .env.local."""
    env_vars = {}
    try:
        import dotenv
        # Load .env
        env_path = Path(".env")
        if env_path.exists():
            env_vars.update(dotenv.dotenv_values(env_path))
        
        # Load .env.local which overrides .env
        local_env_path = Path(".env.local")
        if local_env_path.exists():
            env_vars.update(dotenv.dotenv_values(local_env_path))
    except ImportError:
        print("python-dotenv not installed. Please install with: pip install python-dotenv")
    
    return env_vars

def debug_env_conflicts():
    """Find and report conflicts between environment variable sources."""
    print(yellow("=== Environment Variable Conflict Detector ===\n"))
    
    # Get environment variables from different sources
    os_env_vars = {k: v for k, v in os.environ.items() if k.isupper()}
    dotenv_vars = get_dotenv_vars()
    docker_vars = get_docker_env_vars()
    
    # Check for key environment variables
    key_vars = [
        "ENABLE_API_KEY_AUTH", "API_KEYS", "RATE_LIMIT_ENABLED", 
        "ENABLE_CACHE", "ENVIRONMENT", "LOG_LEVEL"
    ]
    
    print(yellow("Checking key environment variables:"))
    for var in key_vars:
        values = {}
        if var in os_env_vars:
            values["OS"] = os_env_vars[var]
        if var in dotenv_vars:
            values["dotenv"] = dotenv_vars[var]
        if var in docker_vars:
            values["docker"] = docker_vars[var]
            
        if not values:
            print(f"  {var}: {yellow('Not set in any source')}")
            continue
            
        if len(set(values.values())) > 1:
            print(f"  {var}: {red('CONFLICT DETECTED')}")
            for source, value in values.items():
                print(f"    - {source}: {value}")
        else:
            value = next(iter(values.values()))
            sources = ", ".join(values.keys())
            print(f"  {var}: {green(value)} (from {sources})")
    
    # Check app config (after environment variables are resolved)
    print("\n" + yellow("Checking application config:"))
    try:
        from app.core.config import settings
        from app.utils.auth_health import check_auth_configuration
        
        # Check for auth configuration inconsistencies
        auth_status = check_auth_configuration()
        if auth_status["inconsistent_config"]:
            print(red("  Authentication configuration issue detected:"))
            for rec in auth_status["recommendations"]:
                print(f"    - {rec}")
        else:
            print(green("  Authentication configuration is consistent"))
            
        # Check other important settings
        print("\n" + yellow("Final resolved configuration:"))
        print(f"  ENABLE_API_KEY_AUTH: {settings.ENABLE_API_KEY_AUTH}")
        print(f"  API_KEYS configured: {bool(settings.API_KEYS)}")
        print(f"  API_KEYS count: {len(settings.API_KEYS)}")
        print(f"  RATE_LIMIT_ENABLED: {settings.RATE_LIMIT_ENABLED}")
        print(f"  ENABLE_CACHE: {settings.ENABLE_CACHE}")
        print(f"  ENVIRONMENT: {settings.ENVIRONMENT}")
        print(f"  LOG_LEVEL: {settings.LOG_LEVEL}")
        
    except ImportError:
        print(red("  Could not import app.config. Make sure you're running from the project root"))
    
if __name__ == "__main__":
    try:
        debug_env_conflicts()
    except Exception as e:
        print(red(f"Error: {e}"))
        import traceback
        traceback.print_exc()
