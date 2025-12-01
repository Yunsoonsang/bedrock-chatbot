# API 테스트 스크립트 가이드

AWS EC2 (Amazon Linux 2023) 환경에서 서버가 정상적으로 작동하는지 단계별로 테스트할 수 있는 스크립트입니다.

## 사전 요구사항

### 1. 필수 도구 설치

```bash
# jq 설치 (JSON 파싱용)
sudo yum install -y jq

# curl 확인 (일반적으로 기본 설치됨)
curl --version
```

### 2. 환경 변수 설정 (선택사항)

기본값은 `http://localhost:8000`입니다. 다른 서버를 테스트하려면 환경 변수를 설정하세요:

```bash
export BASE_URL="http://your-server-ip:8000"
```

## 테스트 실행 방법

### 개별 테스트 실행

각 테스트를 개별적으로 실행할 수 있습니다:

```bash
# 1. Health Check
bash scripts/test_health.sh

# 2. Chat API
bash scripts/test_chat.sh

# 3. Group Codes API
bash scripts/test_group_codes.sh

# 4. KB Domains API
bash scripts/test_kb_domains.sh

# 5. History API
bash scripts/test_history.sh
```

### 전체 테스트 실행

모든 테스트를 순차적으로 실행:

```bash
bash scripts/run_all_tests.sh
```

## 테스트 항목 상세

### 1. Health Check (`test_health.sh`)

- **엔드포인트**: `GET /health`
- **목적**: 서버가 정상적으로 응답하는지 확인
- **성공 기준**: HTTP 200 응답

### 2. Chat API (`test_chat.sh`)

- **엔드포인트**: `POST /chat`
- **사용자**: 홍길동 (사번: hong123)
- **질문**: "휴가 신청 방법을 안내하세요."
- **그룹 코드**: GRP_IN_ALL
- **목적**: 채팅 API가 정상적으로 SSE 스트리밍 응답을 반환하는지 확인
- **성공 기준**: HTTP 200 응답 및 SSE 스트리밍 시작

### 3. Group Codes API (`test_group_codes.sh`)

- **엔드포인트**: `GET /admin/group-codes`
- **사용자**: 홍길동 (관리자 권한)
- **목적**: Group Code 목록이 정상적으로 조회되는지 확인
- **성공 기준**: HTTP 200 응답 및 Group Code 목록 반환

### 4. KB Domains API (`test_kb_domains.sh`)

- **엔드포인트**: `GET /admin/kb-domains`
- **사용자**: 홍길동 (관리자 권한)
- **목적**: KB Domain 목록이 정상적으로 조회되는지 확인
- **성공 기준**: HTTP 200 응답 및 KB Domain 목록 반환

### 5. History API (`test_history.sh`)

- **엔드포인트**: `GET /history`
- **사용자**: 홍길동 (사번: hong123)
- **목적**: 홍길동 유저의 대화 목록이 정상적으로 조회되는지 확인
- **성공 기준**: HTTP 200 응답 및 대화 목록 반환

## 테스트 사용자 정보

모든 테스트는 다음 사용자 정보를 사용합니다:

- **법인 코드**: SH001
- **사번**: hong123
- **이름**: 홍길동
- **부서**: 인사팀
- **그룹 코드**: GRP_IN_ALL (Chat API에서 사용)
- **권한**: admin (Group Codes, KB Domains API에서 사용)

## 문제 해결

### curl: command not found

```bash
sudo yum install -y curl
```

### jq: command not found

```bash
sudo yum install -y jq
```

### Connection refused

- 서버가 실행 중인지 확인: `curl http://localhost:8000/health`
- 방화벽 설정 확인
- BASE_URL 환경 변수가 올바른지 확인

### Permission denied

스크립트에 실행 권한 부여:

```bash
chmod +x scripts/*.sh
```

### HTTP 401/403 에러

- 사용자 헤더 정보가 올바르게 전달되는지 확인
- 관리자 API의 경우 `X-Role: admin` 헤더가 필요합니다

## 주의사항

1. **서버 실행 확인**: 테스트 실행 전에 서버가 실행 중인지 확인하세요.
2. **데이터베이스 연결**: RDS 연결이 정상인지 확인하세요.
3. **AWS 자격증명**: Bedrock API 호출을 위해 AWS 자격증명이 설정되어 있어야 합니다.
4. **네트워크**: EC2 인스턴스에서 인터넷 연결이 가능해야 합니다.

## 스크립트 위치

모든 스크립트는 `scripts/` 디렉토리에 있습니다:

```
scripts/
├── README.md              # 이 파일
├── test_health.sh         # Health Check 테스트
├── test_chat.sh           # Chat API 테스트
├── test_group_codes.sh    # Group Codes API 테스트
├── test_kb_domains.sh     # KB Domains API 테스트
├── test_history.sh        # History API 테스트
└── run_all_tests.sh       # 전체 테스트 실행
```
