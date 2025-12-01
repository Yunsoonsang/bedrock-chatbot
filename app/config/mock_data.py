"""로컬 개발 및 시연용 Mock 데이터
데이터베이스 스키마 v1.0 기준
실제 데이터베이스 구축 시 이 파일은 제거되거나 DB 초기 데이터로 대체됨
"""

from datetime import datetime, timezone

# 현재 시간 (초기 데이터 생성 시점)
_INIT_TIME = datetime.now(timezone.utc).isoformat()

# Group Code → KB Domain 매핑 (group_codes 테이블 기준)
# kb_domains는 TEXT 타입으로 콤마 구분 문자열 저장
MOCK_GROUP_CODES = {
    "GRP_IN_ALL": {
        "kb_domains": "IN_SAFETY,IN_HR,IN_STD",  # TEXT, 콤마 구분
        "description": "모든팀이 볼수있는 권한",
        "created_at": _INIT_TIME,
        "updated_at": _INIT_TIME
    },
    "GRP_QLT_QM_RP": {
        "kb_domains": "QLT_SPEC,QLT_LAW,QLT_STD",  # TEXT, 콤마 구분
        "description": "품질경영팀, 연구기획팀",
        "created_at": _INIT_TIME,
        "updated_at": _INIT_TIME
    },
    "GRP_TS_ALL": {
        "kb_domains": "TS_OUT,TS_IN",  # TEXT, 콤마 구분
        "description": "Ts팀, 영업소전체",
        "created_at": _INIT_TIME,
        "updated_at": _INIT_TIME
    }
}

# KB Domain 정보 (kb_domains 테이블 기준)
MOCK_KB_DOMAINS = {
    "IN_SAFETY": {
        "code": "IN_SAFETY",
        "name": "사내내규-안전보건",
        "s3_path": "사내내규/안전보건/",
        "description": "안전보건 관련 규정",
        "has_data": False,  # 스키마 기본값 FALSE
        "created_at": _INIT_TIME,
        "updated_at": _INIT_TIME
    },
    "IN_HR": {
        "code": "IN_HR",
        "name": "사내내규-인사총무",
        "s3_path": "사내내규/인사총무/",
        "description": "인사, 총무 관련 사내 규정",
        "has_data": True,  # 스키마 기본값은 FALSE이지만, 초기 데이터는 True
        "created_at": _INIT_TIME,
        "updated_at": _INIT_TIME
    },
    "IN_STD": {
        "code": "IN_STD",
        "name": "사내내규-표준관리",
        "s3_path": "사내내규/표준관리/",
        "description": "사내 표준 관리 절차",
        "has_data": True,
        "created_at": _INIT_TIME,
        "updated_at": _INIT_TIME
    },
    "QLT_SPEC": {
        "code": "QLT_SPEC",
        "name": "품질-시방서규격",
        "s3_path": "품질/1.시방서규격/",
        "description": "제품 시방서 및 기술 규격",
        "has_data": True,
        "created_at": _INIT_TIME,
        "updated_at": _INIT_TIME
    },
    "QLT_LAW": {
        "code": "QLT_LAW",
        "name": "품질-인증법규",
        "s3_path": "품질/2.인증법규/",
        "description": "인증 관련 법규",
        "has_data": True,
        "created_at": _INIT_TIME,
        "updated_at": _INIT_TIME
    },
    "QLT_STD": {
        "code": "QLT_STD",
        "name": "품질-표준관리",
        "s3_path": "품질/3.표준관리/",
        "description": "품질 표준 관리 절차",
        "has_data": True,
        "created_at": _INIT_TIME,
        "updated_at": _INIT_TIME
    },
    "TS_OUT": {
        "code": "TS_OUT",
        "name": "TS(외부)",
        "s3_path": "TS(외부)/",
        "description": "외부 기술 지원 자료",
        "has_data": True,
        "created_at": _INIT_TIME,
        "updated_at": _INIT_TIME
    },
    "TS_IN": {
        "code": "TS_IN",
        "name": "TS(내부)",
        "s3_path": "TS(내부)/",
        "description": "내부 기술 지원 자료",
        "has_data": False,  # 스키마 기본값 FALSE
        "created_at": _INIT_TIME,
        "updated_at": _INIT_TIME
    }
}

# 시연용 테스트 사용자 (그룹별 1명씩) - 비활성화됨
# 실제 데이터베이스 사용 시 제거 예정
# MOCK_USERS = {
#     "G1_USER": {
#         "corp_id": "SH001",
#         "employee_id": "G1_USER",
#         "name": "전체접근_테스터",
#         "department": "시연용",
#         "group_code": "G1"
#     },
#     "G2_USER": {
#         "corp_id": "SH001",
#         "employee_id": "G2_USER",
#         "name": "내규전용_테스터",
#         "department": "시연용",
#         "group_code": "G2"
#     },
#     "G3_USER": {
#         "corp_id": "SH001",
#         "employee_id": "G3_USER",
#         "name": "기술문서_테스터",
#         "department": "시연용",
#         "group_code": "G3"
#     },
#     "G4_USER": {
#         "corp_id": "SH001",
#         "employee_id": "G4_USER",
#         "name": "내규법규_테스터",
#         "department": "시연용",
#         "group_code": "G4"
#     }
# }

# 시연용 질문 시나리오 - 비활성화됨
# 실제 데이터베이스 사용 시 제거 예정
# DEMO_SCENARIOS = {
#     "G1": [
#         "휴가 신청 방법을 알려주세요",  # R1에서 검색
#         "제품 시방서를 확인하고 싶습니다",  # R4에서 검색
#         "인증 법규 관련 정보가 필요합니다"  # R5에서 검색
#     ],
#     "G2": [
#         "휴가 신청 방법을 알려주세요",  # R1에서 검색 (성공)
#         "제품 시방서를 확인하고 싶습니다"  # R4 접근 불가 → 검색 결과 없음
#     ],
#     "G3": [
#         "휴가 신청 방법을 알려주세요",  # R1 접근 불가 → 검색 결과 없음
#         "제품 시방서를 확인하고 싶습니다"  # R4에서 검색 (성공)
#     ],
#     "G4": [
#         "휴가 신청 방법을 알려주세요",  # R1에서 검색 (성공)
#         "제품 시방서를 확인하고 싶습니다",  # R4 접근 불가 → 검색 결과 없음
#         "인증 법규 관련 정보가 필요합니다"  # R5에서 검색 (성공)
#     ]
# }




