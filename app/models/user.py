"""
사용자 및 인증 관련 Pydantic 모델
"""
from pydantic import BaseModel, Field
from typing import Optional


class UserInfo(BaseModel):
    """사용자 정보 모델 (Request Body에 포함)"""
    corp_id: Optional[str] = Field(None, description="법인 코드")
    employee_id: Optional[str] = Field(None, description="사번")
    name: Optional[str] = Field(None, description="사용자 이름")
    department: Optional[str] = Field(None, description="부서명")
    role: Optional[str] = Field(None, description="사용자 역할 (admin, user)")



