"""
채팅 API용 Pydantic 모델
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    """POST /chat 요청 모델"""
    message: str = Field(..., description="사용자 메시지")
    conversation_id: Optional[str] = Field(None, description="대화 ID (없으면 새로 생성)")
    group_code: Optional[str] = Field(None, description="그룹 코드 (G1-G4: 권한 그룹)")
    user_name: Optional[str] = Field(None, description="사용자 이름 (프롬프트에 활용, 향후 확장용)")
    department: Optional[str] = Field(None, description="부서명 (프롬프트에 활용, 향후 확장용)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "휴가 신청 방법을 알려주세요",
                "conversation_id": "conv-123",
                "group_code": "G1",
                "user_name": "홍길동",
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

