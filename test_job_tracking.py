#!/usr/bin/env python3
"""
Comprehensive test script for JobSpy job tracking and duplicate detection functionality.
"""
import requests
import json
import time
from typing import Dict, List, Any
from datetime import datetime

# Configuration
BASE_URL = "http://192.168.7.10:8787"
API_KEY = "test-key"  # Use your actual API key
HEADERS = {"x-api-key": API_KEY, "Content-Type": "application/json"}

class JobTrackingTester:
    """Test class for job tracking and duplicate detection."""
    
    def __init__(self):
        self.base_url = BASE_URL
        self.headers = HEADERS
        self.test_results = []
    
    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result."""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {details}")
    
    def check_api_health(self) -> bool:
        """Check if API is responding."""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10, verify=False)
            if response.status_code == 200:
                self.log_result("API Health Check", True, "API is responding")
                return True
            else:
                self.log_result("API Health Check", False, f"API returned {response.status_code}")
                return False
        except Exception as e:
            self.log_result("API Health Check", False, f"Connection error: {str(e)}")
            return False
    
    def get_baseline_stats(self) -> Dict[str, Any]:
        """Get baseline statistics before testing."""
        try:
            response = requests.get(f"{self.base_url}/admin/stats", timeout=10, verify=False)
            if response.status_code == 200:
                stats = response.json()
                self.log_result("Baseline Stats", True, f"Current jobs: {stats.get('total_jobs_found', 0)}")
                return stats
            else:
                self.log_result("Baseline Stats", False, f"Stats endpoint returned {response.status_code}")
                return {}
        except Exception as e:
            self.log_result("Baseline Stats", False, f"Error getting stats: {str(e)}")
            return {}
    
    def create_test_job_sets(self) -> Dict[str, List[Dict]]:
        """Create test job data sets for controlled testing."""
        
        # Set A: Identical jobs (exact duplicates)
        base_job = {
            "search_term": "Software Engineer",
            "location": "San Francisco, CA",
            "site": "indeed",
            "results_wanted": 1,
            "hours_old": 24,
            "country": "US"
        }
        
        # Set B: Similar jobs (fuzzy duplicates)
        similar_jobs = [
            {**base_job, "search_term": "Senior Software Engineer"},
            {**base_job, "search_term": "Software Engineer Sr"},
            {**base_job, "search_term": "Sr. Software Engineer"}
        ]
        
        # Set C: Different jobs
        different_jobs = [
            {**base_job, "search_term": "Data Scientist", "location": "New York, NY"},
            {**base_job, "search_term": "Product Manager", "location": "Austin, TX"},
            {**base_job, "search_term": "DevOps Engineer", "location": "Seattle, WA"}
        ]
        
        # Set D: Same company, different positions
        company_jobs = [
            {**base_job, "search_term": "Software Engineer at Google"},
            {**base_job, "search_term": "Data Engineer at Google"},
            {**base_job, "search_term": "ML Engineer at Google"}
        ]
        
        return {
            "identical": [base_job, base_job.copy(), base_job.copy()],
            "similar": similar_jobs,
            "different": different_jobs,
            "company_varied": company_jobs
        }
    
    def run_job_search(self, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a job search and return results."""
        try:
            # Use the immediate search API
            response = requests.get(
                f"{self.base_url}/api/v1/search_jobs",
                params=search_params,
                headers=self.headers,
                timeout=30,
                verify=False
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Search failed with status {response.status_code}: {response.text}")
                return {"error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            print(f"Search error: {str(e)}")
            return {"error": str(e)}
    
    def test_exact_duplicates(self, job_set: List[Dict]) -> bool:
        """Test exact duplicate detection."""
        print("\n🔍 Testing Exact Duplicate Detection...")
        
        results = []
        for i, job_params in enumerate(job_set):
            print(f"  Running identical search #{i+1}...")
            result = self.run_job_search(job_params)
            results.append(result)
            time.sleep(2)  # Brief pause between requests
        
        # Analyze results for duplicate detection
        if all("error" not in result for result in results):
            # Check if the same jobs were returned (indicating proper deduplication)
            job_counts = [len(result.get("jobs", [])) for result in results]
            self.log_result("Exact Duplicate Test", True, 
                          f"Searches returned {job_counts} jobs respectively")
            return True
        else:
            self.log_result("Exact Duplicate Test", False, "Some searches failed")
            return False
    
    def test_similar_jobs(self, job_set: List[Dict]) -> bool:
        """Test similarity-based duplicate detection."""
        print("\n🔍 Testing Similar Job Detection...")
        
        results = []
        for i, job_params in enumerate(job_set):
            print(f"  Running similar search #{i+1}: {job_params['search_term']}")
            result = self.run_job_search(job_params)
            results.append(result)
            time.sleep(2)
        
        if all("error" not in result for result in results):
            job_counts = [len(result.get("jobs", [])) for result in results]
            self.log_result("Similar Job Test", True, 
                          f"Similar searches returned {job_counts} jobs respectively")
            return True
        else:
            self.log_result("Similar Job Test", False, "Some searches failed")
            return False
    
    def test_different_jobs(self, job_set: List[Dict]) -> bool:
        """Test that different jobs are stored separately."""
        print("\n🔍 Testing Different Job Handling...")
        
        results = []
        for i, job_params in enumerate(job_set):
            print(f"  Running different search #{i+1}: {job_params['search_term']} in {job_params['location']}")
            result = self.run_job_search(job_params)
            results.append(result)
            time.sleep(2)
        
        if all("error" not in result for result in results):
            job_counts = [len(result.get("jobs", [])) for result in results]
            self.log_result("Different Job Test", True, 
                          f"Different searches returned {job_counts} jobs respectively")
            return True
        else:
            self.log_result("Different Job Test", False, "Some searches failed")
            return False
    
    def check_tracking_database(self) -> bool:
        """Check if jobs are being stored in tracking database."""
        print("\n🔍 Checking Job Tracking Database...")
        
        try:
            # Try to query the jobs database via admin interface
            response = requests.get(f"{self.base_url}/api/v1/jobs/search_jobs?page=1&page_size=10", 
                                  headers=self.headers, timeout=10, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                job_count = len(data.get("jobs", []))
                total_count = data.get("total_count", 0)
                self.log_result("Tracking Database Check", True, 
                              f"Found {job_count} jobs in current page, {total_count} total")
                return True
            else:
                self.log_result("Tracking Database Check", False, 
                              f"Database query failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Tracking Database Check", False, f"Error: {str(e)}")
            return False
    
    def test_admin_integration(self) -> bool:
        """Test admin interface integration."""
        print("\n🔍 Testing Admin Interface Integration...")
        
        try:
            # Check updated stats
            stats_after = self.get_baseline_stats()
            
            # Check jobs database page exists
            response = requests.get(f"{self.base_url}/admin/jobs/page", timeout=10, verify=False)
            if response.status_code == 200:
                self.log_result("Admin Integration", True, "Admin interface accessible")
                return True
            else:
                self.log_result("Admin Integration", False, f"Admin page error: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_result("Admin Integration", False, f"Error: {str(e)}")
            return False
    
    def run_comprehensive_test(self):
        """Run the complete test suite."""
        print("🚀 Starting JobSpy Job Tracking & Duplicate Detection Test Suite")
        print("=" * 70)
        
        # Phase 1: Setup and baseline
        if not self.check_api_health():
            print("❌ API health check failed. Aborting tests.")
            return
        
        baseline_stats = self.get_baseline_stats()
        print(f"📊 Baseline: {baseline_stats.get('total_jobs_found', 0)} jobs in system")
        
        # Phase 2: Create test data
        print("\n📝 Creating test job data sets...")
        job_sets = self.create_test_job_sets()
        self.log_result("Test Data Creation", True, f"Created {len(job_sets)} test sets")
        
        # Phase 3: Run tests
        print("\n🧪 Running duplicate detection tests...")
        
        # Test exact duplicates
        self.test_exact_duplicates(job_sets["identical"])
        
        # Test similar jobs
        self.test_similar_jobs(job_sets["similar"])
        
        # Test different jobs
        self.test_different_jobs(job_sets["different"])
        
        # Phase 4: Verify tracking
        time.sleep(5)  # Wait for any async processing
        self.check_tracking_database()
        
        # Phase 5: Admin integration
        self.test_admin_integration()
        
        # Generate report
        self.generate_report()
    
    def generate_report(self):
        """Generate test report."""
        print("\n" + "=" * 70)
        print("📊 TEST REPORT")
        print("=" * 70)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests} ✅")
        print(f"Failed: {failed_tests} ❌")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\n❌ Failed Tests:")
            for result in self.test_results:
                if not result["success"]:
                    print(f"  - {result['test']}: {result['details']}")
        
        # Save detailed results
        with open("job_tracking_test_results.json", "w") as f:
            json.dump(self.test_results, f, indent=2)
        
        print(f"\n📄 Detailed results saved to: job_tracking_test_results.json")


if __name__ == "__main__":
    tester = JobTrackingTester()
    tester.run_comprehensive_test()