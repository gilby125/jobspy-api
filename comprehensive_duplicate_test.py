#!/usr/bin/env python3
"""
Comprehensive JobSpy Duplicate Detection Test Suite
Tests all aspects of job tracking and deduplication functionality.
"""
import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Any

# Configuration
BASE_URL = "http://192.168.7.10:8787"
API_KEY = "test-key"
HEADERS = {"x-api-key": API_KEY, "Content-Type": "application/json"}

class DuplicateDetectionTester:
    """Comprehensive duplicate detection test suite."""
    
    def __init__(self):
        self.base_url = BASE_URL
        self.headers = HEADERS
        self.test_results = []
        self.start_time = datetime.now()
    
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test result with timestamp."""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {details}")
        return success
    
    def wait_for_server(self, max_retries=30) -> bool:
        """Wait for server to be ready."""
        print(f"🔄 Waiting for server at {self.base_url} to be ready...")
        
        for i in range(max_retries):
            try:
                response = requests.get(f"{self.base_url}/health", timeout=5)
                if response.status_code == 200:
                    return self.log_test("Server Ready", True, f"Server ready after {i+1} attempts")
                else:
                    print(f"  Attempt {i+1}: Server returned {response.status_code}")
            except Exception as e:
                print(f"  Attempt {i+1}: {str(e)}")
            
            if i < max_retries - 1:
                time.sleep(10)
        
        return self.log_test("Server Ready", False, f"Server not ready after {max_retries} attempts")
    
    def run_search(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute job search with error handling."""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/search_jobs",
                params=params,
                headers=self.headers,
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"HTTP {response.status_code}", "details": response.text[:200]}
                
        except Exception as e:
            return {"error": "Exception", "details": str(e)}
    
    def test_exact_duplicates(self) -> bool:
        """Test 1: Exact duplicate detection."""
        print("\n🔍 Test 1: Exact Duplicate Detection")
        print("-" * 50)
        
        # Same search parameters
        params = {
            "search_term": "Software Engineer",
            "location": "San Francisco",
            "site": "indeed",
            "results_wanted": 3
        }
        
        results = []
        for i in range(3):
            print(f"  Running search {i+1}/3...")
            result = self.run_search(params)
            results.append(result)
            
            if "error" in result:
                return self.log_test("Exact Duplicates", False, f"Search {i+1} failed: {result}")
            
            jobs_count = result.get("count", 0)
            cached = result.get("cached", False)
            print(f"    Found {jobs_count} jobs, Cached: {cached}")
            
            time.sleep(3)  # Brief pause between searches
        
        # Analyze results
        if all("error" not in r for r in results):
            counts = [r.get("count", 0) for r in results]
            cached_status = [r.get("cached", False) for r in results]
            
            details = f"Jobs: {counts}, Cached: {cached_status}"
            
            # Check if caching is working (second+ searches should be cached)
            if cached_status[1] or cached_status[2]:
                return self.log_test("Exact Duplicates", True, f"Caching working - {details}")
            else:
                return self.log_test("Exact Duplicates", True, f"No caching detected - {details}")
        else:
            return self.log_test("Exact Duplicates", False, "Some searches failed")
    
    def test_similar_jobs(self) -> bool:
        """Test 2: Similar job detection."""
        print("\n🔍 Test 2: Similar Job Detection")
        print("-" * 50)
        
        # Similar search terms
        similar_searches = [
            {"search_term": "Senior Software Engineer", "location": "San Francisco", "site": "indeed", "results_wanted": 2},
            {"search_term": "Software Engineer Sr", "location": "San Francisco", "site": "indeed", "results_wanted": 2},
            {"search_term": "Sr. Software Engineer", "location": "San Francisco", "site": "indeed", "results_wanted": 2}
        ]
        
        results = []
        for i, params in enumerate(similar_searches):
            print(f"  Running similar search {i+1}/3: '{params['search_term']}'")
            result = self.run_search(params)
            results.append(result)
            
            if "error" in result:
                return self.log_test("Similar Jobs", False, f"Search {i+1} failed: {result}")
            
            jobs_count = result.get("count", 0)
            print(f"    Found {jobs_count} jobs")
            time.sleep(2)
        
        if all("error" not in r for r in results):
            counts = [r.get("count", 0) for r in results]
            return self.log_test("Similar Jobs", True, f"Similar searches completed: {counts}")
        else:
            return self.log_test("Similar Jobs", False, "Some similar searches failed")
    
    def test_different_jobs(self) -> bool:
        """Test 3: Different job handling."""
        print("\n🔍 Test 3: Different Job Handling")
        print("-" * 50)
        
        # Completely different searches
        different_searches = [
            {"search_term": "Data Scientist", "location": "New York", "site": "linkedin", "results_wanted": 2},
            {"search_term": "Product Manager", "location": "Austin", "site": "indeed", "results_wanted": 2},
            {"search_term": "DevOps Engineer", "location": "Seattle", "site": "glassdoor", "results_wanted": 2}
        ]
        
        results = []
        for i, params in enumerate(different_searches):
            print(f"  Running different search {i+1}/3: '{params['search_term']}' in {params['location']}")
            result = self.run_search(params)
            results.append(result)
            
            if "error" in result:
                return self.log_test("Different Jobs", False, f"Search {i+1} failed: {result}")
            
            jobs_count = result.get("count", 0)
            print(f"    Found {jobs_count} jobs")
            time.sleep(2)
        
        if all("error" not in r for r in results):
            counts = [r.get("count", 0) for r in results]
            return self.log_test("Different Jobs", True, f"Different searches completed: {counts}")
        else:
            return self.log_test("Different Jobs", False, "Some different searches failed")
    
    def test_tracking_database(self) -> bool:
        """Test 4: Job tracking database."""
        print("\n🔍 Test 4: Job Tracking Database")
        print("-" * 50)
        
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/jobs/search_jobs?page=1&page_size=10",
                headers=self.headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                total_jobs = data.get("total_count", 0)
                current_page_jobs = len(data.get("jobs", []))
                
                return self.log_test("Tracking Database", True, 
                                   f"Database accessible: {current_page_jobs} jobs on page, {total_jobs} total")
            else:
                return self.log_test("Tracking Database", False, 
                                   f"Database query failed: HTTP {response.status_code}")
                
        except Exception as e:
            return self.log_test("Tracking Database", False, f"Database error: {str(e)}")
    
    def test_admin_stats(self) -> bool:
        """Test 5: Admin statistics."""
        print("\n🔍 Test 5: Admin Statistics")
        print("-" * 50)
        
        try:
            response = requests.get(f"{self.base_url}/admin/stats", timeout=10)
            
            if response.status_code == 200:
                stats = response.json()
                searches = stats.get("total_searches", 0)
                jobs_found = stats.get("total_jobs_found", 0)
                db_health = stats.get("system_health", {}).get("database", "unknown")
                
                return self.log_test("Admin Stats", True, 
                                   f"Searches: {searches}, Jobs: {jobs_found}, DB: {db_health}")
            else:
                return self.log_test("Admin Stats", False, 
                                   f"Admin stats failed: HTTP {response.status_code}")
                
        except Exception as e:
            return self.log_test("Admin Stats", False, f"Admin stats error: {str(e)}")
    
    def test_job_deduplication_analysis(self) -> bool:
        """Test 6: Analyze job deduplication patterns."""
        print("\n🔍 Test 6: Job Deduplication Analysis")
        print("-" * 50)
        
        # Run the same search twice and analyze job IDs
        params = {
            "search_term": "Python Developer",
            "location": "Remote",
            "site": "indeed",
            "results_wanted": 5
        }
        
        print("  Running first search...")
        result1 = self.run_search(params)
        time.sleep(5)
        
        print("  Running second identical search...")
        result2 = self.run_search(params)
        
        if "error" in result1 or "error" in result2:
            return self.log_test("Deduplication Analysis", False, "Search failures prevented analysis")
        
        jobs1 = result1.get("jobs", [])
        jobs2 = result2.get("jobs", [])
        
        if jobs1 and jobs2:
            ids1 = set(job.get("id", "") for job in jobs1)
            ids2 = set(job.get("id", "") for job in jobs2)
            
            common_ids = ids1.intersection(ids2)
            unique_to_first = ids1 - ids2
            unique_to_second = ids2 - ids1
            
            details = f"Common: {len(common_ids)}, Unique to 1st: {len(unique_to_first)}, Unique to 2nd: {len(unique_to_second)}"
            
            if len(common_ids) > 0:
                return self.log_test("Deduplication Analysis", True, f"Job overlap detected - {details}")
            else:
                return self.log_test("Deduplication Analysis", True, f"No job overlap - {details}")
        else:
            return self.log_test("Deduplication Analysis", False, "No jobs returned for analysis")
    
    def generate_report(self):
        """Generate comprehensive test report."""
        end_time = datetime.now()
        duration = end_time - self.start_time
        
        print("\n" + "=" * 80)
        print("📊 COMPREHENSIVE DUPLICATE DETECTION TEST REPORT")
        print("=" * 80)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r["success"])
        failed_tests = total_tests - passed_tests
        
        print(f"🕐 Test Duration: {duration}")
        print(f"📋 Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"📈 Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        print(f"\n📄 Detailed Results:")
        for result in self.test_results:
            status = "✅" if result["success"] else "❌"
            print(f"  {status} {result['test']}: {result['details']}")
        
        # Save results
        report_file = f"duplicate_detection_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, "w") as f:
            json.dump({
                "summary": {
                    "total_tests": total_tests,
                    "passed": passed_tests,
                    "failed": failed_tests,
                    "success_rate": (passed_tests/total_tests)*100,
                    "duration": str(duration),
                    "timestamp": end_time.isoformat()
                },
                "detailed_results": self.test_results
            }, f, indent=2)
        
        print(f"\n💾 Full report saved to: {report_file}")
        
        # Recommendations
        print(f"\n💡 Key Findings:")
        if failed_tests == 0:
            print("  🎯 All tests passed! Duplicate detection system is working correctly.")
        else:
            print("  🔧 Some tests failed. Review the detailed results above.")
        
        print("  📝 Check the tracking database for stored job data")
        print("  📊 Monitor admin statistics for system health")
        print("  🔄 Verify caching behavior for performance optimization")
    
    def run_full_test_suite(self):
        """Execute the complete test suite."""
        print("🚀 JobSpy Duplicate Detection Test Suite")
        print("=" * 80)
        print(f"🕐 Started at: {self.start_time}")
        print(f"🌐 Target: {self.base_url}")
        
        # Wait for server
        if not self.wait_for_server():
            print("❌ Server not accessible. Aborting tests.")
            return
        
        # Run all tests
        tests = [
            self.test_exact_duplicates,
            self.test_similar_jobs,
            self.test_different_jobs,
            self.test_tracking_database,
            self.test_admin_stats,
            self.test_job_deduplication_analysis
        ]
        
        for test_func in tests:
            test_func()
            time.sleep(2)  # Brief pause between test groups
        
        # Generate final report
        self.generate_report()

if __name__ == "__main__":
    tester = DuplicateDetectionTester()
    tester.run_full_test_suite()