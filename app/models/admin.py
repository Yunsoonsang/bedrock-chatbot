"""
관리자 API용 Pydantic 모델
데이터베이스 스키마 v1.0 기준
"""
from pydantic import BaseModel, Field
from typing import Optional, List


class GroupCodeRequest(BaseModel):
    """Group Code 생성/수정 요청 모델"""
    code: str = Field(..., description="Group Code (예: GRP_IN_ALL, GRP_QLT_QM_RP, GRP_TS_ALL, VARCHAR(10))")
    description: Optional[str] = Field(None, description="설명 (TEXT, NULL)")
    kb_domains: List[str] = Field(..., description="접근 가능한 KB Domain 코드 목록 (DB 저장 시 콤마 구분 문자열로 변환)")


class GroupCodeResponse(BaseModel):
    """Group Code 응답 모델 (group_codes 테이블 기준)"""
    code: str = Field(..., description="Group Code (VARCHAR(10), PK)")
    kb_domains: str = Field(..., description="접근 가능한 KB Domain 목록 (TEXT, 콤마 구분)")
    description: Optional[str] = Field(None, description="설명 (TEXT, NULL)")
    created_at: str = Field(..., description="생성일시 (ISO 8601, TIMESTAMP)")
    updated_at: str = Field(..., description="수정일시 (ISO 8601, TIMESTAMP)")


class GroupCodeResponseWithList(BaseModel):
    """Group Code 응답 모델 (API 응답용, kb_domains를 리스트로 변환)"""
    code: str = Field(..., description="Group Code")
    kb_domains: List[str] = Field(default_factory=list, description="접근 가능한 KB Domain 코드 목록")
    description: Optional[str] = Field(None, description="설명")
    created_at: str = Field(..., description="생성일시")
    updated_at: str = Field(..., description="수정일시")


class KBDomainRequest(BaseModel):
    """KB Domain 생성/수정 요청 모델"""
    code: str = Field(..., description="KB Domain 코드 (예: IN_HR, QLT_SPEC, TS_OUT, VARCHAR(10))")
    name: str = Field(..., description="KB Domain 이름 (VARCHAR(100), NOT NULL)")
    s3_path: str = Field(..., description="S3 경로 (VARCHAR(255), NOT NULL)")
    description: Optional[str] = Field(None, description="설명 (TEXT, NULL)")
    has_data: bool = Field(False, description="데이터 존재 여부 (BOOLEAN, 기본값 FALSE)")


class KBDomainResponse(BaseModel):
    """KB Domain 응답 모델 (kb_domains 테이블 기준)"""
    code: str = Field(..., description="KB Domain 코드 (VARCHAR(10), PK)")
    name: str = Field(..., description="KB Domain 이름 (VARCHAR(100), NOT NULL)")
    s3_path: str = Field(..., description="S3 경로 (VARCHAR(255), NOT NULL)")
    description: Optional[str] = Field(None, description="설명 (TEXT, NULL)")
    has_data: bool = Field(False, description="데이터 존재 여부 (BOOLEAN, 기본값 FALSE)")
    created_at: str = Field(..., description="생성일시 (ISO 8601, TIMESTAMP)")
    updated_at: str = Field(..., description="수정일시 (ISO 8601, TIMESTAMP)")


class UploadUrlRequest(BaseModel):
    """파일 업로드 URL 생성 요청 모델"""
    filename: str = Field(..., description="파일명")
    content_type: Optional[str] = Field(None, description="Content-Type (MIME 타입)")
    file_size: Optional[int] = Field(None, description="파일 크기 (bytes)")


class UploadUrlResponse(BaseModel):
    """파일 업로드 URL 응답 모델"""
    presigned_url: str = Field(..., description="S3 업로드용 Pre-signed URL (1시간 유효)")
    file_key: str = Field(..., description="S3 객체 키")
    expires_in: int = Field(3600, description="URL 유효 시간 (초)")
    upload_id: str = Field(..., description="업로드 추적용 ID")

