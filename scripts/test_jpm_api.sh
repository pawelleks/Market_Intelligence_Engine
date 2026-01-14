#!/bin/bash
# JPM Dashboard API Test Script
# Tests all 4 endpoints and verifies responses

set -e  # Exit on error

API_BASE_URL=${API_BASE_URL:-http://localhost:8000}
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "Testing JPM Dashboard API at $API_BASE_URL"
echo "============================================"
echo ""

# Test 1: Health Check
echo "Test 1: Health Check"
echo "Endpoint: GET /api/v1/jpm-dashboard/health"
RESPONSE=$(curl -s -w "\n%{http_code}" "$API_BASE_URL/api/v1/jpm-dashboard/health")
HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✓ PASS${NC} - Status: $HTTP_CODE"
    echo "Response preview: $(echo $BODY | python3 -m json.tool 2>/dev/null | head -5 || echo $BODY | head -c 100)"
else
    echo -e "${RED}✗ FAIL${NC} - Status: $HTTP_CODE"
    echo "Response: $BODY"
    exit 1
fi
echo ""

# Test 2: Overview
echo "Test 2: Dashboard Overview"
echo "Endpoint: GET /api/v1/jpm-dashboard/overview"
RESPONSE=$(curl -s -w "\n%{http_code}" "$API_BASE_URL/api/v1/jpm-dashboard/overview")
HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✓ PASS${NC} - Status: $HTTP_CODE"
    INDICATOR_COUNT=$(echo $BODY | python3 -c "import sys, json; print(len(json.load(sys.stdin)['indicators']))" 2>/dev/null || echo "N/A")
    echo "Indicators returned: $INDICATOR_COUNT (expected: 10)"
    
    if [ "$INDICATOR_COUNT" -eq 10 ]; then
        echo -e "${GREEN}✓ All 10 indicators present${NC}"
    else
        echo -e "${YELLOW}⚠ Warning: Expected 10 indicators, got $INDICATOR_COUNT${NC}"
    fi
else
    echo -e "${RED}✗ FAIL${NC} - Status: $HTTP_CODE"
    echo "Response: $BODY"
    exit 1
fi
echo ""

# Test 3: Specific Indicator
echo "Test 3: Labor Market Indicator Detail"
echo "Endpoint: GET /api/v1/jpm-dashboard/indicators/labor-market"
RESPONSE=$(curl -s -w "\n%{http_code}" "$API_BASE_URL/api/v1/jpm-dashboard/indicators/labor-market")
HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✓ PASS${NC} - Status: $HTTP_CODE"
    CATEGORY=$(echo $BODY | python3 -c "import sys, json; print(json.load(sys.stdin)['category'])" 2>/dev/null || echo "N/A")
    echo "Category: $CATEGORY"
else
    echo -e "${RED}✗ FAIL${NC} - Status: $HTTP_CODE"
    echo "Response: $BODY"
    exit 1
fi
echo ""

# Test 4: Single Series
echo "Test 4: Single Series (UNRATE)"
echo "Endpoint: GET /api/v1/jpm-dashboard/series/UNRATE"
RESPONSE=$(curl -s -w "\n%{http_code}" "$API_BASE_URL/api/v1/jpm-dashboard/series/UNRATE")
HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | head -n -1)

if [ "$HTTP_CODE" -eq 200 ]; then
    echo -e "${GREEN}✓ PASS${NC} - Status: $HTTP_CODE"
    SERIES_ID=$(echo $BODY | python3 -c "import sys, json; print(json.load(sys.stdin)['series_id'])" 2>/dev/null || echo "N/A")
    echo "Series: $SERIES_ID"
else
    echo -e "${RED}✗ FAIL${NC} - Status: $HTTP_CODE"
    echo "Response: $BODY"
    exit 1
fi
echo ""

# Test 5: All Categories
echo "Test 5: Testing All 10 Categories"
CATEGORIES=("gdp" "consumer-spending" "labor-market" "interest-rates" "inflation" "business-confidence" "stock-market" "trade-balance" "housing" "policy")
PASS_COUNT=0

for category in "${CATEGORIES[@]}"; do
    RESPONSE=$(curl -s -w "\n%{http_code}" "$API_BASE_URL/api/v1/jpm-dashboard/indicators/$category")
    HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
    
    if [ "$HTTP_CODE" -eq 200 ]; then
        echo -e "  ${GREEN}✓${NC} $category"
        ((PASS_COUNT++))
    else
        echo -e "  ${RED}✗${NC} $category (HTTP $HTTP_CODE)"
    fi
done

echo ""
echo "Categories passing: $PASS_COUNT/10"

if [ "$PASS_COUNT" -eq 10 ]; then
    echo -e "${GREEN}✓ All categories working!${NC}"
else
    echo -e "${YELLOW}⚠ Some categories failing${NC}"
fi

echo ""
echo "============================================"
echo -e "${GREEN}✓ All tests completed!${NC}"
echo ""
echo "Summary:"
echo "  - Health check: ✓"
echo "  - Overview endpoint: ✓"
echo "  - Indicator detail: ✓"
echo "  - Series detail: ✓"
echo "  - Category coverage: $PASS_COUNT/10"
