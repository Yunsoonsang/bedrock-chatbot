"""
대화 이력 관련 Pydantic 모델
데이터베이스 스키마 v1.0 기준
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid


class MessageMetadataSource(BaseModel):
    """메시지 metadata의 source 항목 (Bedrock Knowledge Base RAG 결과)"""
    title: str = Field(..., description="문서명")
    page: Optional[int] = Field(None, description="페이지 번호")
    relevance: Optional[float] = Field(None, description="관련도 점수 (0.0 ~ 1.0)")
    document_id: Optional[str] = Field(None, description="문서 고유 ID")
    kb_domain: Optional[str] = Field(None, description="KB Domain 코드 (예: IN_HR, QLT_SPEC, TS_OUT, citations에서 S3 URI 기반 자동 추출)")


class MessageMetadata(BaseModel):
    """메시지 metadata (JSONB 구조)"""
    sources: List[MessageMetadataSource] = Field(default_factory=list, description="참조 문서 목록")
    tokens: Optional[int] = Field(None, description="사용된 토큰 수")
    model: Optional[str] = Field(None, description="사용된 모델명")
    duration_ms: Optional[int] = Field(None, description="응답 생성 소요 시간 (밀리초)")


class Message(BaseModel):
    """대화 메시지 모델 (Messages 테이블 기준)"""
    message_id: Optional[int] = Field(None, description="메시지 고유 ID (BIGSERIAL, DB 자동 생성, 로깅/히스토리용)")
    conversation_id: str = Field(..., description="대화 ID (UUID, FK)", pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    role: str = Field(..., description="역할 (user, assistant)", pattern=r'^(user|assistant)$')
    content: str = Field(..., description="메시지 내용 (TEXT)")
    metadata: Optional[MessageMetadata] = Field(None, description="메타데이터 (JSONB) - Bedrock Knowledge Base RAG 과정 정보")
    created_at: str = Field(..., description="생성 시간 (ISO 8601, TIMESTAMP)")


class Conversation(BaseModel):
    """대화 정보 모델 (Conversations 테이블 기준)"""
    conversation_id: str = Field(..., description="대화 ID (UUID, PK)", pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
    corp_id: str = Field(..., description="법인 코드 (VARCHAR(20), NOT NULL)", max_length=20)
    employee_id: str = Field(..., description="사번 (VARCHAR(50), NOT NULL)", max_length=50)
    user_name: str = Field(..., description="사용자 이름 (VARCHAR(100), NOT NULL)", max_length=100)
    department: str = Field(..., description="부서명 (VARCHAR(100), NOT NULL)", max_length=100)
    title: str = Field(..., description="대화 제목 (VARCHAR(255), NOT NULL)", max_length=255)
    message_count: int = Field(0, description="메시지 개수 (INTEGER, 기본값 0)", ge=0)
    created_at: str = Field(..., description="생성 시간 (ISO 8601, TIMESTAMP)")
    updated_at: str = Field(..., description="최종 업데이트 시간 (ISO 8601, TIMESTAMP)")
    
    @classmethod
    def generate_conversation_id(cls) -> str:
        """새로운 UUID 형식의 conversation_id 생성"""
        return str(uuid.uuid4())


class ConversationDetail(Conversation):
    """대화 상세 정보 모델 (메시지 포함)"""
    messages: List[Message] = Field(default_factory=list, description="메시지 목록")


class ConversationListResponse(BaseModel):
    """대화 목록 응답 모델"""
    conversations: List[Conversation] = Field(default_factory=list)
    total: int = Field(0, description="전체 대화 수")
    page: int = Field(1, description="현재 페이지")
    page_size: int = Field(20, description="페이지 크기")


class UpdateTitleRequest(BaseModel):
    """대화 제목 수정 요청 모델"""
    title: str = Field(..., description="새로운 제목 (VARCHAR(255), NOT NULL)", max_length=255)

