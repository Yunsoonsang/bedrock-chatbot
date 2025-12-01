#!/bin/bash
# Chat API 테스트 스크립트
# Amazon Linux 2023 환경에서 실행

set -e

# 기본 설정
BASE_URL="${BASE_URL:-http://localhost:8000}"
API_URL="${BASE_URL}/chat"

# 홍길동 유저 정보
CORP_ID="SH001"
EMPLOYEE_ID="hong123"
USER_NAME="홍길동"
DEPARTMENT="인사팀"
GROUP_CODE="GRP_IN_ALL"

echo "=========================================="
echo "2. POST /chat 테스트"
echo "=========================================="
echo "API URL: ${API_URL}"
echo "사용자: ${USER_NAME} (${EMPLOYEE_ID})"
echo "질문: 휴가 신청 방법을 안내하세요."
echo ""

# 요청 본문
request_body=$(cat <<EOF
{
  "message": "휴가 신청 방법을 안내하세요.",
  "employee_id": "${EMPLOYEE_ID}",
  "name": "${USER_NAME}",
  "corp_id": "${CORP_ID}",
  "department": "${DEPARTMENT}",
  "group_code": "${GROUP_CODE}"
}
EOF
)

echo "Request Body:"
echo "${request_body}" | jq '.' 2>/dev/null || echo "${request_body}"
echo ""

# SSE 스트리밍 응답 처리
echo "Response (SSE Stream):"
echo "----------------------------------------"

# curl로 SSE 스트리밍 받기 (한 번만 호출)
# 응답 본문과 HTTP 코드를 모두 받기 위해 임시 파일 사용
temp_file=$(mktemp)
http_code=$(curl -s -w "\n%{http_code}" \
  -X POST \
  -H "Content-Type: application/json" \
  -H "X-Corp-Id: ${CORP_ID}" \
  -H "X-Employee-Id: ${EMPLOYEE_ID}" \
  -H "X-User-Name: ${USER_NAME}" \
  -H "X-Department: ${DEPARTMENT}" \
  -d "${request_body}" \
  "${API_URL}" \
  -o "${temp_file}" \
  | tail -n1)

# 응답 본문 출력 (처음 20줄만)
response=$(cat "${temp_file}")
echo "${response}" | head -20
echo ""

# 임시 파일 정리
rm -f "${temp_file}"

# 결과 확인
if [ "${http_code}" -eq 200 ]; then
    echo "✅ Chat API 호출 성공"
    echo "   (SSE 스트리밍 응답이 정상적으로 시작되었습니다)"
    exit 0
else
    echo "❌ Chat API 호출 실패 (HTTP ${http_code})"
    exit 1
fi

