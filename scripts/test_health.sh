#!/bin/bash
# Health Check 테스트 스크립트
# Amazon Linux 2023 환경에서 실행

set -e

# 기본 설정
BASE_URL="${BASE_URL:-http://localhost:8000}"
API_URL="${BASE_URL}/health"

echo "=========================================="
echo "1. Health Check 테스트"
echo "=========================================="
echo "API URL: ${API_URL}"
echo ""

# Health Check 요청
response=$(curl -s -w "\n%{http_code}" "${API_URL}")
http_code=$(echo "${response}" | tail -n1)
body=$(echo "${response}" | sed '$d')

echo "HTTP Status Code: ${http_code}"
echo "Response Body:"
echo "${body}" | jq '.' 2>/dev/null || echo "${body}"
echo ""

# 결과 확인
if [ "${http_code}" -eq 200 ]; then
    echo "✅ Health Check 성공"
    exit 0
else
    echo "❌ Health Check 실패 (HTTP ${http_code})"
    exit 1
fi


