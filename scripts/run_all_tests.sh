#!/bin/bash
# 전체 테스트 실행 스크립트
# Amazon Linux 2023 환경에서 실행

set -e

# 스크립트 디렉토리 경로 설정
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 기본 설정
BASE_URL="${BASE_URL:-http://localhost:8000}"

# 색상 정의
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "전체 API 테스트 시작"
echo "=========================================="
echo "Base URL: ${BASE_URL}"
echo "Script Directory: ${SCRIPT_DIR}"
echo ""

# 테스트 결과 추적
PASSED=0
FAILED=0
TOTAL=0

# 테스트 실행 함수
run_test() {
    local test_name=$1
    local test_script=$2
    
    TOTAL=$((TOTAL + 1))
    echo ""
    echo "${YELLOW}[${TOTAL}/5] ${test_name}${NC}"
    echo "----------------------------------------"
    
    if bash "${SCRIPT_DIR}/${test_script}"; then
        echo ""
        echo "${GREEN}✅ ${test_name} 통과${NC}"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo ""
        echo "${RED}❌ ${test_name} 실패${NC}"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

# 각 테스트 실행
run_test "Health Check" "test_health.sh"
run_test "Chat API" "test_chat.sh"
run_test "Group Codes API" "test_group_codes.sh"
run_test "KB Domains API" "test_kb_domains.sh"
run_test "History API" "test_history.sh"

# 결과 요약
echo ""
echo "=========================================="
echo "테스트 결과 요약"
echo "=========================================="
echo "전체 테스트: ${TOTAL}"
echo "${GREEN}통과: ${PASSED}${NC}"
echo "${RED}실패: ${FAILED}${NC}"
echo ""

if [ ${FAILED} -eq 0 ]; then
    echo "${GREEN}✅ 모든 테스트 통과!${NC}"
    exit 0
else
    echo "${RED}❌ 일부 테스트 실패${NC}"
    exit 1
fi

