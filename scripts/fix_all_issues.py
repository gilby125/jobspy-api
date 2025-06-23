#!/usr/bin/env python3
"""
All-in-one script to fix all identified admin endpoint issues:
1. Create missing database tables
2. Test and fix Redis connectivity
3. Improve job site access with better headers/user agents
"""
import sys
import logging
import subprocess
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_script(script_name):
    """Run a Python script and return success status."""
    try:
        script_path = Path(__file__).parent / script_name
        if not script_path.exists():
            logger.error(f"Script not found: {script_path}")
            return False
        
        logger.info(f"Running {script_name}...")
        result = subprocess.run([sys.executable, str(script_path)], 
                              capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0:
            logger.info(f"✅ {script_name} completed successfully")
            if result.stdout:
                logger.info(f"Output: {result.stdout}")
            return True
        else:
            logger.error(f"❌ {script_name} failed with return code {result.returncode}")
            if result.stderr:
                logger.error(f"Error: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error(f"❌ {script_name} timed out after 120 seconds")
        return False
    except Exception as e:
        logger.error(f"❌ {script_name} failed with exception: {e}")
        return False

def check_environment():
    """Check if we're running in the correct environment."""
    try:
        # Check if we can import the app modules
        sys.path.insert(0, str(Path(__file__).parent.parent / "app"))
        from app.core.config import settings
        logger.info("✅ Environment check passed - can access app modules")
        return True
    except ImportError as e:
        logger.error(f"❌ Environment check failed - cannot import app modules: {e}")
        return False

def main():
    """Run all fix scripts in sequence."""
    logger.info("="*60)
    logger.info("Starting comprehensive admin endpoint fixes...")
    logger.info("="*60)
    
    # Check environment
    if not check_environment():
        logger.error("Environment check failed. Make sure you're running this in the container.")
        return 1
    
    # Track results
    results = {}
    
    # 1. Fix database issues
    logger.info("\n1. Fixing database issues...")
    results['database'] = run_script('init_database.py')
    
    # 2. Test Redis connectivity
    logger.info("\n2. Testing Redis connectivity...")
    results['redis'] = run_script('test_redis.py')
    
    # 3. Fix job site connectivity
    logger.info("\n3. Fixing job site connectivity...")
    results['job_sites'] = run_script('fix_job_sites.py')
    
    # Report final results
    logger.info("\n" + "="*60)
    logger.info("FIX RESULTS SUMMARY:")
    logger.info("="*60)
    
    total_fixes = len(results)
    successful_fixes = sum(1 for success in results.values() if success)
    
    for component, success in results.items():
        status = "✅ FIXED" if success else "❌ FAILED"
        logger.info(f"{component.upper()}: {status}")
    
    logger.info(f"\nOverall: {successful_fixes}/{total_fixes} fixes successful")
    
    if successful_fixes == total_fixes:
        logger.info("🎉 All issues have been fixed! Admin endpoints should now work properly.")
        return 0
    else:
        logger.warning("⚠️ Some issues remain. Check the logs above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())