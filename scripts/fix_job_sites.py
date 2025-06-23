#!/usr/bin/env python3
"""
Script to fix job site access issues (403 errors) by improving user agents and headers.
This script patches the JobSpy library configuration.
"""
import sys
import logging
import requests
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "app"))

from app.core.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Modern user agents that are less likely to be blocked
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

def test_site_connectivity():
    """Test connectivity to major job sites with improved headers."""
    test_sites = {
        "indeed": "https://www.indeed.com",
        "linkedin": "https://www.linkedin.com/jobs",
        "glassdoor": "https://www.glassdoor.com",
        "google": "https://jobs.google.com"
    }
    
    results = {}
    
    for site_name, url in test_sites.items():
        logger.info(f"Testing connectivity to {site_name}...")
        
        # Use modern headers that mimic real browsers
        headers = {
            'User-Agent': USER_AGENTS[0],  # Use the first user agent
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
            status_code = response.status_code
            
            if status_code == 200:
                logger.info(f"✅ {site_name}: SUCCESS (Status: {status_code})")
                results[site_name] = "accessible"
            elif status_code == 403:
                logger.warning(f"⚠️ {site_name}: BLOCKED (Status: {status_code})")
                results[site_name] = "error_403"
            else:
                logger.warning(f"⚠️ {site_name}: UNEXPECTED (Status: {status_code})")
                results[site_name] = f"error_{status_code}"
                
        except requests.exceptions.Timeout:
            logger.error(f"❌ {site_name}: TIMEOUT")
            results[site_name] = "timeout"
        except requests.exceptions.ConnectionError:
            logger.error(f"❌ {site_name}: CONNECTION_ERROR")
            results[site_name] = "connection_error"
        except Exception as e:
            logger.error(f"❌ {site_name}: ERROR - {e}")
            results[site_name] = "error"
    
    return results

def create_jobspy_config_patch():
    """Create a configuration patch to improve JobSpy's request headers."""
    patch_content = '''
"""
JobSpy configuration patch to improve site connectivity.
This module patches the default headers and user agents used by JobSpy.
"""

# Modern user agents that are less likely to be blocked
MODERN_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]

# Improved headers to mimic real browser requests
IMPROVED_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Cache-Control': 'max-age=0'
}

def get_random_user_agent():
    """Get a random modern user agent."""
    import random
    return random.choice(MODERN_USER_AGENTS)

def get_improved_headers(user_agent=None):
    """Get improved headers with specified or random user agent."""
    headers = IMPROVED_HEADERS.copy()
    headers['User-Agent'] = user_agent or get_random_user_agent()
    return headers
'''
    
    patch_file = Path(__file__).parent.parent / "app" / "utils" / "jobspy_patch.py"
    patch_file.parent.mkdir(exist_ok=True)
    
    with open(patch_file, 'w') as f:
        f.write(patch_content)
    
    logger.info(f"Created JobSpy configuration patch at: {patch_file}")
    return patch_file

def main():
    """Test job site connectivity and create configuration patches."""
    try:
        logger.info("Starting job site connectivity fixes...")
        
        # Test current connectivity
        logger.info("Testing current site connectivity...")
        results = test_site_connectivity()
        
        # Report results
        accessible_sites = [site for site, status in results.items() if status == "accessible"]
        blocked_sites = [site for site, status in results.items() if "error_403" in status]
        
        logger.info(f"Accessible sites: {', '.join(accessible_sites) if accessible_sites else 'None'}")
        logger.info(f"Blocked sites (403): {', '.join(blocked_sites) if blocked_sites else 'None'}")
        
        # Create configuration patch
        logger.info("Creating JobSpy configuration patch...")
        patch_file = create_jobspy_config_patch()
        
        # Provide recommendations
        logger.info("Recommendations:")
        if blocked_sites:
            logger.info("- Consider using rotating proxies for blocked sites")
            logger.info("- Implement request delays and random intervals")
            logger.info("- Use the created jobspy_patch.py module in your job searches")
        
        if len(accessible_sites) > 0:
            logger.info(f"- Focus on accessible sites: {', '.join(accessible_sites)}")
        
        logger.info("Job site connectivity fixes completed!")
        return 0
        
    except Exception as e:
        logger.error(f"Job site fix script failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())