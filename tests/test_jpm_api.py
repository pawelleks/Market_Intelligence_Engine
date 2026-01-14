#!/usr/bin/env python3
"""
JPM Dashboard API Test Suite

Tests all endpoints for the JPM Economic Dashboard API.
Run this after starting the API server to verify all endpoints work correctly.

Usage:
    python tests/test_jpm_api.py
    
    # Or with custom API URL:
    API_BASE_URL=http://production-server:8000 python tests/test_jpm_api.py
"""

import os
import sys
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

# Colors for terminal output
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[1;33m'
NC = '\033[0m'  # No Color


def print_test_header(test_num: int, description: str, endpoint: str):
    """Print formatted test header."""
    print(f"\nTest {test_num}: {description}")
    print(f"Endpoint: {endpoint}")


def print_result(passed: bool, details: str = ""):
    """Print test result with color coding."""
    if passed:
        print(f"{GREEN}✓ PASS{NC}")
        if details:
            print(f"  {details}")
    else:
        print(f"{RED}✗ FAIL{NC}")
        if details:
            print(f"  {details}")


def test_health() -> Tuple[bool, str]:
    """Test health endpoint."""
    print_test_header(1, "Health Check", "GET /api/v1/jpm-dashboard/health")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/jpm-dashboard/health", timeout=10)
        
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}"
        
        data = response.json()
        
        if "status" not in data:
            return False, "Response missing 'status' field"
        
        if "indicators" not in data:
            return False, "Response missing 'indicators' field"
        
        return True, f"Status: {data.get('status')}, {len(data.get('indicators', []))} indicators"
        
    except requests.exceptions.RequestException as e:
        return False, f"Request error: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"


def test_overview() -> Tuple[bool, str]:
    """Test overview endpoint."""
    print_test_header(2, "Dashboard Overview", "GET /api/v1/jpm-dashboard/overview")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/jpm-dashboard/overview", timeout=10)
        
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}"
        
        data =response.json()
        
        if "indicators" not in data:
            return False, "Response missing 'indicators' field"
        
        indicators = data["indicators"]
        
        if len(indicators) != 10:
            return False, f"Expected 10 indicators, got {len(indicators)}"
        
        # Verify structure of first indicator
        if indicators:
            first = indicators[0]
            required_fields = ["category", "name", "current_value", "sparkline"]
            missing = [f for f in required_fields if f not in first]
            if missing:
                return False, f"Indicator missing fields: {missing}"
        
        return True, f"{len(indicators)} indicators with sparklines"
        
    except Exception as e:
        return False, f"Error: {str(e)}"


def test_indicator_detail(category: str = "labor-market") -> Tuple[bool, str]:
    """Test indicator detail endpoint."""
    print_test_header(3, f"Indicator Detail ({category})", f"GET /api/v1/jpm-dashboard/indicators/{category}")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/jpm-dashboard/indicators/{category}", timeout=10)
        
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}"
        
        data = response.json()
        
        required_fields = ["category", "primary_metric", "secondary_metrics"]
        missing = [f for f in required_fields if f not in data]
        
        if missing:
            return False, f"Response missing fields: {missing}"
        
        # Check inside primary_metric for name and data
        primary = data.get("primary_metric", {})
        if "name" not in primary:
            return False, "primary_metric missing 'name'"
        if "data" not in primary:
            return False, "primary_metric missing 'data'"
            
        hist_count = len(primary.get("data", []))
        
        return True, f"Category: {data['category']}, {hist_count} data points"
        
    except Exception as e:
        return False, f"Error: {str(e)}"


def test_series_detail(series_id: str = "UNRATE") -> Tuple[bool, str]:
    """Test series detail endpoint."""
    print_test_header(4, f"Series Detail ({series_id})", f"GET /api/v1/jpm-dashboard/series/{series_id}")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/v1/jpm-dashboard/series/{series_id}", timeout=10)
        
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}"
        
        data = response.json()
        
        required_fields = ["series_id", "data", "metadata"]
        missing = [f for f in required_fields if f not in data]
        
        if missing:
            return False, f"Response missing fields: {missing}"
        
        data_points = len(data.get("data", []))
        
        return True, f"Series: {data['series_id']}, {data_points} data points"
        
    except Exception as e:
        return False, f"Error: {str(e)}"


def test_all_categories() -> Tuple[int, int]:
    """Test all 10 categories."""
    print_test_header(5, "All Categories", "Testing all 10 indicator categories")
    
    categories = [
        "gdp", "consumer-spending", "labor-market", "interest-rates",
        "inflation", "business-confidence", "stock-market", "trade-balance",
        "housing", "policy"
    ]
    
    pass_count = 0
    
    for category in categories:
        try:
            response = requests.get(
                f"{API_BASE_URL}/api/v1/jpm-dashboard/indicators/{category}",
                timeout=10
            )
            
            if response.status_code == 200:
                print(f"  {GREEN}✓{NC} {category}")
                pass_count += 1
            else:
                print(f"  {RED}✗{NC} {category} (HTTP {response.status_code})")
                
        except Exception as e:
            print(f"  {RED}✗{NC} {category} (Error: {e})")
    
    return pass_count, len(categories)


def test_date_range_query() -> Tuple[bool, str]:
    """Test date range query parameter."""
    print_test_header(6, "Date Range Query", "GET /api/v1/jpm-dashboard/indicators/inflation?start_date=...&end_date=...")
    
    try:
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        
        response = requests.get(
            f"{API_BASE_URL}/api/v1/jpm-dashboard/indicators/inflation",
            params={"start_date": start_date, "end_date": end_date},
            timeout=10
        )
        
        if response.status_code != 200:
            return False, f"HTTP {response.status_code}"
        
        data = response.json()
        primary_data = data.get("primary_metric", {}).get("data", [])
        
        return True, f"Date range query successful, {len(primary_data)} points"
        
    except Exception as e:
        return False, f"Error: {str(e)}"


def test_error_handling() -> Tuple[bool, str]:
    """Test error handling (404 for invalid category)."""
    print_test_header(7, "Error Handling", "GET /api/v1/jpm-dashboard/indicators/invalid-category")
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/v1/jpm-dashboard/indicators/invalid-category",
            timeout=10
        )
        
        if response.status_code == 404:
            return True, "Correctly returns 404 for invalid category"
        else:
            return False, f"Expected 404, got {response.status_code}"
            
    except Exception as e:
        return False, f"Error: {str(e)}"


def main():
    """Run all tests and report results."""
    print("=" * 70)
    print("JPM Dashboard API Test Suite")
    print("=" * 70)
    print(f"Testing API at: {API_BASE_URL}")
    print()
    
    # Run tests
    test_results = []
    
    # Test 1: Health
    passed, details = test_health()
    print_result(passed, details)
    test_results.append(passed)
    
    # Test 2: Overview
    passed, details = test_overview()
    print_result(passed, details)
    test_results.append(passed)
    
    # Test 3: Indicator Detail
    passed, details = test_indicator_detail()
    print_result(passed, details)
    test_results.append(passed)
    
    # Test 4: Series Detail
    passed, details = test_series_detail()
    print_result(passed, details)
    test_results.append(passed)
    
    # Test 5: All Categories
    pass_count, total = test_all_categories()
    test_results.append(pass_count == total)
    print(f"\n  Categories passing: {pass_count}/{total}")
    
    # Test 6: Date Range
    passed, details = test_date_range_query()
    print_result(passed, details)
    test_results.append(passed)
    
    # Test 7: Error Handling
    passed, details = test_error_handling()
    print_result(passed, details)
    test_results.append(passed)
    
    # Summary
    print()
    print("=" * 70)
    total_tests = len(test_results)
    total_passed = sum(test_results)
    
    print(f"Tests passed: {total_passed}/{total_tests}")
    print()
    
    if all(test_results):
        print(f"{GREEN}✓ All tests PASSED!{NC}")
        return 0
    else:
        print(f"{RED}✗ Some tests FAILED{NC}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
