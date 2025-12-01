"""
채팅 API용 Pydantic 모델
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    """POST /chat 요청 모델"""
    message: str = Field(..., description="사용자 메시지", max_length=2000)
    conversation_id: Optional[str] = Field(
        None, 
        description="대화 ID (UUID 형식, 없으면 새로 생성)"
        # pattern은 Optional 필드에 적용 시 None 값에서 오류 발생하므로 검증 로직에서 처리
    )
    group_code: Optional[str] = Field(None, description="그룹 코드 (예: GRP_IN_ALL, GRP_QLT_QM_RP, GRP_TS_ALL) - 필수 (API 레벨에서 검증)")
    # 사용자 정보 (명세서에 따르면 Request Body에 포함, Conversations 테이블 저장용)
    corp_id: Optional[str] = Field(None, description="법인 코드 (VARCHAR(20))")
    employee_id: Optional[str] = Field(None, description="사번 (VARCHAR(50))")
    name: Optional[str] = Field(None, description="사용자 이름 (VARCHAR(100), user_name으로 저장)")
    department: Optional[str] = Field(None, description="부서명 (VARCHAR(100))")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "휴가 신청 방법을 알려주세요",
                "conversation_id": "conv-123",
                "group_code": "GRP_IN_ALL",
                "corp_id": "SH001",
                "employee_id": "E001",
                "name": "홍길동",
                "department": "영업1팀"
            }
        }


class SSEEvent(BaseModel):
    """SSE 이벤트 기본 모델"""
    event: str = Field(..., description="이벤트 타입")
    data: Dict[str, Any] = Field(..., description="이벤트 데이터")


class StartEventData(BaseModel):
    """start 이벤트 데이터"""
    conversation_id: str


class TokenEventData(BaseModel):
    """token 이벤트 데이터"""
    token: str


class MetadataEventData(BaseModel):
    """metadata 이벤트 데이터"""
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    retrieval_results: List[Dict[str, Any]] = Field(default_factory=list)


class DoneEventData(BaseModel):
    """done 이벤트 데이터"""
    finish_reason: Optional[str] = None


class ErrorEventData(BaseModel):
    """error 이벤트 데이터"""
    error: str
    message: str

