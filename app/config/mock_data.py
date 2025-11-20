"""로컬 개발 및 시연용 Mock 데이터"""

# Group Code → KB Domain 매핑 (API 명세서 기준)
MOCK_GROUP_CODES = {
    "G1": {
        "kb_domains": ["R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8"],
        "description": "모든 KB Domain 접근 가능"
    },
    "G2": {
        "kb_domains": ["R1", "R2", "R3"],
        "description": "사내 내규만 접근"
    },
    "G3": {
        "kb_domains": ["R4", "R5", "R6", "R7", "R8"],
        "description": "품질 및 기술 문서 접근"
    },
    "G4": {
        "kb_domains": ["R1", "R2", "R3", "R5"],
        "description": "사내 내규 및 법규 접근"
    }
}

# KB Domain 정보
MOCK_KB_DOMAINS = {
    "R1": {
        "code": "R1",
        "name": "사내내규-인사총무",
        "s3_path": "사내내규/인사총무/",
        "description": "인사, 총무 관련 사내 규정",
        "has_data": True
    },
    "R2": {
        "code": "R2",
        "name": "사내내규-표준관리",
        "s3_path": "사내내규/표준관리/",
        "description": "사내 표준 관리 절차",
        "has_data": True
    },
    "R3": {
        "code": "R3",
        "name": "사내내규-안전보건",
        "s3_path": "사내내규/안전보건/",
        "description": "안전보건 관련 규정",
        "has_data": False
    },
    "R4": {
        "code": "R4",
        "name": "품질-시방서및규격",
        "s3_path": "품질/1.시방서및규격/",
        "description": "제품 시방서 및 기술 규격",
        "has_data": True
    },
    "R5": {
        "code": "R5",
        "name": "품질-인증법규",
        "s3_path": "품질/2.인증법규/",
        "description": "인증 관련 법규",
        "has_data": True
    },
    "R6": {
        "code": "R6",
        "name": "품질-표준관리",
        "s3_path": "품질/3.표준관리/",
        "description": "품질 표준 관리 절차",
        "has_data": True
    },
    "R7": {
        "code": "R7",
        "name": "TS(내부)",
        "s3_path": "TS(내부)/",
        "description": "내부 기술 지원 자료",
        "has_data": False
    },
    "R8": {
        "code": "R8",
        "name": "TS(외부)",
        "s3_path": "TS(외부)/",
        "description": "외부 기술 지원 자료",
        "has_data": True
    }
}

# 시연용 테스트 사용자 (그룹별 1명씩)
MOCK_USERS = {
    "G1_USER": {
        "corp_id": "SH001",
        "employee_id": "G1_USER",
        "name": "전체접근_테스터",
        "department": "시연용",
        "group_code": "G1"
    },
    "G2_USER": {
        "corp_id": "SH001",
        "employee_id": "G2_USER",
        "name": "내규전용_테스터",
        "department": "시연용",
        "group_code": "G2"
    },
    "G3_USER": {
        "corp_id": "SH001",
        "employee_id": "G3_USER",
        "name": "기술문서_테스터",
        "department": "시연용",
        "group_code": "G3"
    },
    "G4_USER": {
        "corp_id": "SH001",
        "employee_id": "G4_USER",
        "name": "내규법규_테스터",
        "department": "시연용",
        "group_code": "G4"
    }
}

# 시연용 질문 시나리오
DEMO_SCENARIOS = {
    "G1": [
        "휴가 신청 방법을 알려주세요",  # R1에서 검색
        "제품 시방서를 확인하고 싶습니다",  # R4에서 검색
        "인증 법규 관련 정보가 필요합니다"  # R5에서 검색
    ],
    "G2": [
        "휴가 신청 방법을 알려주세요",  # R1에서 검색 (성공)
        "제품 시방서를 확인하고 싶습니다"  # R4 접근 불가 → 검색 결과 없음
    ],
    "G3": [
        "휴가 신청 방법을 알려주세요",  # R1 접근 불가 → 검색 결과 없음
        "제품 시방서를 확인하고 싶습니다"  # R4에서 검색 (성공)
    ],
    "G4": [
        "휴가 신청 방법을 알려주세요",  # R1에서 검색 (성공)
        "제품 시방서를 확인하고 싶습니다",  # R4 접근 불가 → 검색 결과 없음
        "인증 법규 관련 정보가 필요합니다"  # R5에서 검색 (성공)
    ]
}

