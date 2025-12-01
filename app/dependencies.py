"""
FastAPI 의존성 함수들 (인증, 권한 체크 등)
"""
from fastapi import HTTPException, Request, Header
from typing import Optional
from app.models.user import UserInfo


def get_user_info_from_request(
    request: Request,
    x_corp_id: Optional[str] = Header(None, alias="X-Corp-Id"),
    x_employee_id: Optional[str] = Header(None, alias="X-Employee-Id"),
    x_user_name: Optional[str] = Header(None, alias="X-User-Name"),
    x_department: Optional[str] = Header(None, alias="X-Department"),
    x_role: Optional[str] = Header(None, alias="X-Role")
) -> UserInfo:
    """
    Request에서 사용자 정보 추출
    
    - /admin 경로로 요청이 오면 자동으로 admin 권한 부여 (고객사에서 관리)
    - 그 외 경로는 user 권한 (클라이언트가 role을 보내지 않으므로)
    - 사용자 데이터는 고객사가 관리하므로, 저희는 SSO 쿠키 기반 인증만 처리
    """
    # 경로 확인: /admin으로 시작하면 admin 권한 자동 부여
    # 고객사에서 /admin 경로 접근을 제어하므로, 여기서 요청이 오면 admin으로 간주
    is_admin_path = request.url.path.startswith("/admin")
    role = "admin" if is_admin_path else (x_role or "user")
    
    # Header에서 먼저 시도
    if x_employee_id:
        return UserInfo(
            corp_id=x_corp_id,
            employee_id=x_employee_id,
            name=x_user_name,
            department=x_department,
            role=role
        )
    
    # Cookie에서 시도 (실제 SSO 연동 시)
    # TODO: SSO 쿠키 파싱 로직 추가
    
    # 기본값 반환 (시연용)
    return UserInfo(
        corp_id=None,
        employee_id=None,
        name=None,
        department=None,
        role=role
    )


def require_admin(user_info: Optional[UserInfo] = None) -> UserInfo:
    """
    Admin 권한 체크 의존성
    """
    if not user_info:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "UNAUTHORIZED",
                "message": "인증 정보가 없습니다."
            }
        )
    
    if user_info.role != "admin":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "FORBIDDEN",
                "message": "접근 권한이 없습니다."
            }
        )
    
    return user_info



