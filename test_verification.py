#!/usr/bin/env python3
"""
Test Suite Verification Script
This script verifies the completeness and structure of the test suite.
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set


def analyze_test_files() -> Dict[str, any]:
    """Analyze all test files and extract information."""
    test_dir = Path("tests")
    if not test_dir.exists():
        return {"error": "tests directory not found"}
    
    test_files = list(test_dir.glob("test_*.py"))
    
    analysis = {
        "total_files": len(test_files),
        "files": [],
        "total_tests": 0,
        "total_lines": 0,
        "test_categories": {
            "unit": 0,
            "integration": 0,
            "e2e": 0,
            "performance": 0,
            "error_handling": 0
        }
    }
    
    for test_file in test_files:
        file_info = analyze_test_file(test_file)
        analysis["files"].append(file_info)
        analysis["total_tests"] += file_info["test_count"]
        analysis["total_lines"] += file_info["line_count"]
        
        # Categorize tests
        if "unit" in test_file.name:
            analysis["test_categories"]["unit"] += file_info["test_count"]
        elif "integration" in test_file.name:
            analysis["test_categories"]["integration"] += file_info["test_count"]
        elif "e2e" in test_file.name or "workflow" in test_file.name:
            analysis["test_categories"]["e2e"] += file_info["test_count"]
        elif "performance" in test_file.name or "load" in test_file.name:
            analysis["test_categories"]["performance"] += file_info["test_count"]
        elif "error" in test_file.name or "edge" in test_file.name:
            analysis["test_categories"]["error_handling"] += file_info["test_count"]
    
    return analysis


def analyze_test_file(file_path: Path) -> Dict[str, any]:
    """Analyze a single test file."""
    try:
        content = file_path.read_text()
        
        # Count test methods
        test_methods = re.findall(r'def test_\w+\(', content)
        
        # Count test classes
        test_classes = re.findall(r'class Test\w+\(', content)
        
        # Count lines
        lines = content.split('\n')
        
        # Count fixtures
        fixtures = re.findall(r'@pytest\.fixture', content)
        
        # Count mocked functions
        mocks = re.findall(r'@patch\(|with patch\(', content)
        
        # Count async tests
        async_tests = re.findall(r'async def test_\w+\(', content)
        
        return {
            "name": file_path.name,
            "test_count": len(test_methods),
            "class_count": len(test_classes),
            "line_count": len(lines),
            "fixture_count": len(fixtures),
            "mock_count": len(mocks),
            "async_test_count": len(async_tests),
            "size_kb": file_path.stat().st_size / 1024
        }
    except Exception as e:
        return {
            "name": file_path.name,
            "error": str(e),
            "test_count": 0,
            "line_count": 0
        }


def check_test_coverage() -> Dict[str, List[str]]:
    """Check which services/modules have test coverage."""
    app_dir = Path("app")
    services_dir = app_dir / "services"
    routes_dir = app_dir / "routes"
    
    coverage = {
        "services_tested": [],
        "services_missing": [],
        "routes_tested": [],
        "routes_missing": []
    }
    
    # Check services
    if services_dir.exists():
        for service_file in services_dir.glob("*.py"):
            if service_file.name.startswith("__"):
                continue
            
            service_name = service_file.stem
            test_file = Path(f"tests/test_{service_name}.py")
            
            if test_file.exists():
                coverage["services_tested"].append(service_name)
            else:
                coverage["services_missing"].append(service_name)
    
    # Check routes
    if routes_dir.exists():
        for route_file in routes_dir.glob("*.py"):
            if route_file.name.startswith("__"):
                continue
            
            route_name = route_file.stem
            # Look for integration tests that might cover routes
            possible_tests = [
                f"tests/test_{route_name}_integration.py",
                f"tests/test_api_{route_name}_integration.py",
                f"tests/test_{route_name}.py"
            ]
            
            tested = any(Path(test).exists() for test in possible_tests)
            
            if tested:
                coverage["routes_tested"].append(route_name)
            else:
                coverage["routes_missing"].append(route_name)
    
    return coverage


def validate_test_structure() -> List[str]:
    """Validate test structure and best practices."""
    issues = []
    
    # Check if conftest.py exists
    if not Path("tests/conftest.py").exists():
        issues.append("Missing tests/conftest.py - should contain shared fixtures")
    
    # Check if __init__.py exists in tests
    if not Path("tests/__init__.py").exists():
        issues.append("Missing tests/__init__.py - recommended for test package")
    
    # Check test file naming
    test_files = list(Path("tests").glob("*.py"))
    for test_file in test_files:
        if not test_file.name.startswith("test_") and test_file.name not in ["conftest.py", "__init__.py"]:
            issues.append(f"Test file {test_file.name} doesn't follow naming convention (test_*.py)")
    
    return issues


def generate_test_report():
    """Generate comprehensive test report."""
    print("=" * 60)
    print("JOBSPY API - COMPREHENSIVE TEST SUITE REPORT")
    print("=" * 60)
    
    # Analyze test files
    analysis = analyze_test_files()
    
    if "error" in analysis:
        print(f"❌ Error: {analysis['error']}")
        return
    
    print(f"\n📊 TEST SUITE OVERVIEW")
    print(f"{'─' * 30}")
    print(f"Total Test Files: {analysis['total_files']}")
    print(f"Total Test Methods: {analysis['total_tests']}")
    print(f"Total Lines of Test Code: {analysis['total_lines']:,}")
    
    print(f"\n📋 TEST CATEGORIES")
    print(f"{'─' * 30}")
    for category, count in analysis["test_categories"].items():
        print(f"{category.replace('_', ' ').title()}: {count} tests")
    
    print(f"\n📁 TEST FILES DETAIL")
    print(f"{'─' * 30}")
    for file_info in sorted(analysis["files"], key=lambda x: x.get("test_count", 0), reverse=True):
        if "error" in file_info:
            print(f"❌ {file_info['name']}: {file_info['error']}")
        else:
            print(f"✅ {file_info['name']}: {file_info['test_count']} tests, "
                  f"{file_info['fixture_count']} fixtures, "
                  f"{file_info['async_test_count']} async tests, "
                  f"{file_info['size_kb']:.1f}KB")
    
    # Check coverage
    coverage = check_test_coverage()
    
    print(f"\n🎯 COVERAGE ANALYSIS")
    print(f"{'─' * 30}")
    print(f"Services with tests: {len(coverage['services_tested'])}")
    for service in coverage['services_tested']:
        print(f"  ✅ {service}")
    
    if coverage['services_missing']:
        print(f"Services missing tests: {len(coverage['services_missing'])}")
        for service in coverage['services_missing']:
            print(f"  ❌ {service}")
    
    print(f"Routes with tests: {len(coverage['routes_tested'])}")
    for route in coverage['routes_tested']:
        print(f"  ✅ {route}")
    
    if coverage['routes_missing']:
        print(f"Routes missing tests: {len(coverage['routes_missing'])}")
        for route in coverage['routes_missing']:
            print(f"  ❌ {route}")
    
    # Validate structure
    issues = validate_test_structure()
    
    print(f"\n🔍 TEST STRUCTURE VALIDATION")
    print(f"{'─' * 30}")
    if not issues:
        print("✅ All test structure checks passed")
    else:
        for issue in issues:
            print(f"⚠️  {issue}")
    
    # Summary
    print(f"\n📈 SUMMARY")
    print(f"{'─' * 30}")
    
    total_services = len(coverage['services_tested']) + len(coverage['services_missing'])
    service_coverage = len(coverage['services_tested']) / total_services * 100 if total_services > 0 else 0
    
    total_routes = len(coverage['routes_tested']) + len(coverage['routes_missing'])
    route_coverage = len(coverage['routes_tested']) / total_routes * 100 if total_routes > 0 else 0
    
    print(f"Service Coverage: {service_coverage:.1f}% ({len(coverage['services_tested'])}/{total_services})")
    print(f"Route Coverage: {route_coverage:.1f}% ({len(coverage['routes_tested'])}/{total_routes})")
    print(f"Test Quality Score: {calculate_quality_score(analysis, issues)}/100")
    
    # Test types implemented
    print(f"\n🧪 TEST TYPES IMPLEMENTED")
    print(f"{'─' * 30}")
    test_types = [
        ("Unit Tests", analysis["test_categories"]["unit"] > 0),
        ("Integration Tests", analysis["test_categories"]["integration"] > 0),
        ("End-to-End Tests", analysis["test_categories"]["e2e"] > 0),
        ("Performance Tests", analysis["test_categories"]["performance"] > 0),
        ("Error Handling Tests", analysis["test_categories"]["error_handling"] > 0),
    ]
    
    for test_type, implemented in test_types:
        status = "✅" if implemented else "❌"
        print(f"{status} {test_type}")


def calculate_quality_score(analysis: Dict, issues: List[str]) -> int:
    """Calculate a test quality score out of 100."""
    score = 0
    
    # File count (0-20 points)
    if analysis["total_files"] >= 8:
        score += 20
    else:
        score += (analysis["total_files"] / 8) * 20
    
    # Test count (0-20 points)
    if analysis["total_tests"] >= 100:
        score += 20
    else:
        score += (analysis["total_tests"] / 100) * 20
    
    # Test category coverage (0-30 points)
    categories_covered = sum(1 for count in analysis["test_categories"].values() if count > 0)
    score += (categories_covered / 5) * 30
    
    # Structure quality (0-20 points)
    if len(issues) == 0:
        score += 20
    else:
        score += max(0, 20 - len(issues) * 5)
    
    # Code volume (0-10 points)
    if analysis["total_lines"] >= 1000:
        score += 10
    else:
        score += (analysis["total_lines"] / 1000) * 10
    
    return min(100, int(score))


if __name__ == "__main__":
    generate_test_report()