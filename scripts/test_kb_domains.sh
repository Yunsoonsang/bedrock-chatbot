#!/bin/bash
# KB Domains API 테스트 스크립트
# Amazon Linux 2023 환경에서 실행

set -e

# 기본 설정
BASE_URL="${BASE_URL:-http://localhost:8000}"
API_URL="${BASE_URL}/admin/kb-domains"

# 홍길동 유저 정보 (관리자 권한)
CORP_ID="SH001"
EMPLOYEE_ID="hong123"
USER_NAME="홍길동"
DEPARTMENT="인사팀"

echo "=========================================="
echo "4. GET /admin/kb-domains 테스트"
echo "=========================================="
echo "API URL: ${API_URL}"
echo "사용자: ${USER_NAME} (${EMPLOYEE_ID})"
echo ""

# KB Domains 조회 요청
response=$(curl -s -w "\n%{http_code}" \
  -X GET \
  -H "X-Corp-Id: ${CORP_ID}" \
  -H "X-Employee-Id: ${EMPLOYEE_ID}" \
  -H "X-User-Name: ${USER_NAME}" \
  -H "X-Department: ${DEPARTMENT}" \
  -H "X-Role: admin" \
  "${API_URL}")

http_code=$(echo "${response}" | tail -n1)
body=$(echo "${response}" | sed '$d')

echo "HTTP Status Code: ${http_code}"
echo "Response Body:"
echo "${body}" | jq '.' 2>/dev/null || echo "${body}"
echo ""

# 결과 확인
if [ "${http_code}" -eq 200 ]; then
    echo "✅ KB Domains 조회 성공"
    
    # KB Domain 개수 확인
    count=$(echo "${body}" | jq 'length' 2>/dev/null || echo "0")
    echo "   조회된 KB Domain 개수: ${count}"
    
    # 각 KB Domain 출력
    if command -v jq &> /dev/null; then
        echo ""
        echo "KB Domains 목록:"
        echo "${body}" | jq -r 'to_entries[] | "  - \(.key): \(.value.name // "이름 없음")"' 2>/dev/null || true
    fi
    
    exit 0
else
    echo "❌ KB Domains 조회 실패 (HTTP ${http_code})"
    echo "Response: ${body}"
    exit 1
fi


