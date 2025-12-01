"""
관리자 API 라우터
데이터베이스 스키마 v1.0 기준
"""
import uuid
import boto3
from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, List
from datetime import datetime, timezone
from app.models.admin import (
    GroupCodeRequest, GroupCodeResponse, GroupCodeResponseWithList,
    KBDomainRequest, KBDomainResponse,
    UploadUrlRequest, UploadUrlResponse
)
from app.models.user import UserInfo
from app.dependencies import require_admin, get_user_info_from_request
from app.database import get_pool
from app.config import settings
# Mock 데이터는 로컬 테스트용으로만 사용 (use_mock_data=True일 때만 활성화)
# 실제 운영 환경에서는 데이터베이스에서 데이터를 가져옵니다
if settings.use_mock_data:
    from app.config.mock_data import MOCK_GROUP_CODES, MOCK_KB_DOMAINS
else:
    # Mock 데이터 비활성화 시 빈 딕셔너리 사용
    MOCK_GROUP_CODES = {}
    MOCK_KB_DOMAINS = {}

router = APIRouter(prefix="/admin", tags=["admin"])


# ==================== Group Code 관리 ====================

@router.get("/group-codes", response_model=Dict[str, GroupCodeResponseWithList])
async def get_group_codes(
    request: Request,
    user_info: UserInfo = Depends(get_user_info_from_request)
):
    """GET /admin/group-codes - Group Code 목록 조회 (관리자용)"""
    require_admin(user_info)
    
    result = {}
    
    if settings.use_mock_data:
        # Mock 데이터 사용
        now = datetime.now(timezone.utc).isoformat()
        for code, info in MOCK_GROUP_CODES.items():
            kb_domains_list = info.get("kb_domains", [])
            if isinstance(kb_domains_list, str):
                kb_domains_list = [d.strip() for d in kb_domains_list.split(",") if d.strip()]
            
            result[code] = GroupCodeResponseWithList(
                code=code,
                description=info.get("description"),
                kb_domains=kb_domains_list,
                created_at=info.get("created_at", now),
                updated_at=info.get("updated_at", now)
            )
    else:
        # 데이터베이스에서 조회
        pool = await get_pool()
        rows = await pool.fetch("SELECT * FROM group_codes ORDER BY code")
        
        for row in rows:
            kb_domains_str = row['kb_domains']
            kb_domains_list = [d.strip() for d in kb_domains_str.split(",") if d.strip()] if kb_domains_str else []
            
            result[row['code']] = GroupCodeResponseWithList(
                code=row['code'],
                description=row.get('description', ''),
                kb_domains=kb_domains_list,
                created_at=row['created_at'].isoformat() if row.get('created_at') else datetime.now(timezone.utc).isoformat(),
                updated_at=row['updated_at'].isoformat() if row.get('updated_at') else datetime.now(timezone.utc).isoformat()
            )
    
    return result


@router.post("/group-codes", response_model=GroupCodeResponse, status_code=201)
async def create_group_code(
    request: GroupCodeRequest,
    http_request: Request,
    user_info: UserInfo = Depends(get_user_info_from_request)
):
    """POST /admin/group-codes - Group Code 생성"""
    require_admin(user_info)
    
    pool = await get_pool()
    now = datetime.now(timezone.utc)
    
    async with pool.acquire() as conn:
        # 기존 Group Code 확인
        existing = await conn.fetchrow(
            "SELECT code FROM group_codes WHERE code = $1",
            request.code
        )
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_REQUEST",
                    "message": "이미 존재하는 Group Code입니다.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": "/admin/group-codes"
                }
            )
        
        # KB Domain 유효성 검사
        if request.kb_domains:
            placeholders = ','.join([f'${i+1}' for i in range(len(request.kb_domains))])
            kb_domains_query = f"SELECT code FROM kb_domains WHERE code IN ({placeholders})"
            existing_kb_domains = await conn.fetch(kb_domains_query, *request.kb_domains)
            existing_kb_codes = {row['code'] for row in existing_kb_domains}
            
            for kb_code in request.kb_domains:
                if kb_code not in existing_kb_codes:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "INVALID_REQUEST",
                            "message": f"존재하지 않는 KB Domain 코드: {kb_code}",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "path": "/admin/group-codes"
                        }
                    )
        
        # DB에 저장 (콤마 구분 문자열로 변환)
        kb_domains_str = ",".join(request.kb_domains) if request.kb_domains else ""
        
        await conn.execute(
            """
            INSERT INTO group_codes (code, description, kb_domains, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            request.code, request.description, kb_domains_str, now, now
        )
    
    # 응답은 리스트 형식으로 변환
    return GroupCodeResponseWithList(
        code=request.code,
        description=request.description,
        kb_domains=request.kb_domains,
        created_at=now.isoformat(),
        updated_at=now.isoformat()
    )


@router.put("/group-codes/{code}", response_model=GroupCodeResponse)
async def update_group_code(
    code: str,
    request: GroupCodeRequest,
    http_request: Request,
    user_info: UserInfo = Depends(get_user_info_from_request)
):
    """PUT /admin/group-codes/{code} - Group Code 수정"""
    require_admin(user_info)
    
    pool = await get_pool()
    now = datetime.now(timezone.utc)
    
    async with pool.acquire() as conn:
        # 기존 Group Code 확인
        existing = await conn.fetchrow(
            "SELECT code, created_at FROM group_codes WHERE code = $1",
            code
        )
        
        if not existing:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "NOT_FOUND",
                    "message": "요청한 리소스를 찾을 수 없습니다.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": f"/admin/group-codes/{code}"
                }
            )
        
        # KB Domain 유효성 검사
        if request.kb_domains:
            placeholders = ','.join([f'${i+1}' for i in range(len(request.kb_domains))])
            kb_domains_query = f"SELECT code FROM kb_domains WHERE code IN ({placeholders})"
            existing_kb_domains = await conn.fetch(kb_domains_query, *request.kb_domains)
            existing_kb_codes = {row['code'] for row in existing_kb_domains}
            
            for kb_code in request.kb_domains:
                if kb_code not in existing_kb_codes:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "INVALID_REQUEST",
                            "message": f"존재하지 않는 KB Domain 코드: {kb_code}",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "path": f"/admin/group-codes/{code}"
                        }
                    )
        
        # 수정 (DB 저장 시 콤마 구분 문자열로 변환)
        kb_domains_str = ",".join(request.kb_domains) if request.kb_domains else ""
        
        await conn.execute(
            """
            UPDATE group_codes
            SET description = $1, kb_domains = $2, updated_at = $3
            WHERE code = $4
            """,
            request.description, kb_domains_str, now, code
        )
    
    # 응답은 리스트 형식으로 변환
    created_at = existing['created_at'].isoformat() if hasattr(existing['created_at'], 'isoformat') else str(existing['created_at'])
    return GroupCodeResponseWithList(
        code=code,
        description=request.description,
        kb_domains=request.kb_domains,
        created_at=created_at,
        updated_at=now.isoformat()
    )


@router.delete("/group-codes/{code}")
async def delete_group_code(
    code: str,
    request: Request,
    user_info: UserInfo = Depends(get_user_info_from_request)
):
    """DELETE /admin/group-codes/{code} - Group Code 삭제"""
    require_admin(user_info)
    
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        # 기존 Group Code 확인
        existing = await conn.fetchrow(
            "SELECT code FROM group_codes WHERE code = $1",
            code
        )
        
        if not existing:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "NOT_FOUND",
                    "message": "요청한 리소스를 찾을 수 없습니다.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": f"/admin/group-codes/{code}"
                }
            )
        
        # 삭제
        await conn.execute(
            "DELETE FROM group_codes WHERE code = $1",
            code
        )
    
    return {
        "code": code,
        "deleted": True
    }


# ==================== KB Domain 관리 ====================

@router.get("/kb-domains", response_model=Dict[str, KBDomainResponse])
async def get_kb_domains(
    request: Request,
    user_info: UserInfo = Depends(get_user_info_from_request)
):
    """GET /admin/kb-domains - KB Domain 목록 조회 (관리자용)"""
    require_admin(user_info)
    
    result = {}
    
    if settings.use_mock_data:
        # Mock 데이터 사용
        now = datetime.now(timezone.utc).isoformat()
        for code, info in MOCK_KB_DOMAINS.items():
            result[code] = KBDomainResponse(
                code=info["code"],
                name=info["name"],
                s3_path=info["s3_path"],
                description=info.get("description"),
                has_data=info.get("has_data", False),
                created_at=info.get("created_at", now),
                updated_at=info.get("updated_at", now)
            )
    else:
        # 데이터베이스에서 조회
        pool = await get_pool()
        rows = await pool.fetch("SELECT * FROM kb_domains ORDER BY code")
        
        for row in rows:
            result[row['code']] = KBDomainResponse(
                code=row['code'],
                name=row['name'],
                s3_path=row['s3_path'],
                description=row.get('description', ''),
                has_data=row.get('has_data', False),
                created_at=row['created_at'].isoformat() if row.get('created_at') else datetime.now(timezone.utc).isoformat(),
                updated_at=row['updated_at'].isoformat() if row.get('updated_at') else datetime.now(timezone.utc).isoformat()
            )
    
    return result


@router.post("/kb-domains", response_model=KBDomainResponse, status_code=201)
async def create_kb_domain(
    request: KBDomainRequest,
    http_request: Request,
    user_info: UserInfo = Depends(get_user_info_from_request)
):
    """POST /admin/kb-domains - KB Domain 생성"""
    require_admin(user_info)
    
    pool = await get_pool()
    now = datetime.now(timezone.utc)
    
    async with pool.acquire() as conn:
        # 기존 KB Domain 확인
        existing = await conn.fetchrow(
            "SELECT code FROM kb_domains WHERE code = $1",
            request.code
        )
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_REQUEST",
                    "message": "이미 존재하는 KB Domain 코드입니다.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": "/admin/kb-domains"
                }
            )
        
        # DB에 저장
        await conn.execute(
            """
            INSERT INTO kb_domains (code, name, s3_path, description, has_data, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            request.code, request.name, request.s3_path, request.description, 
            request.has_data, now, now
        )
    
    return KBDomainResponse(
        code=request.code,
        name=request.name,
        s3_path=request.s3_path,
        description=request.description,
        has_data=request.has_data,
        created_at=now.isoformat(),
        updated_at=now.isoformat()
    )


@router.put("/kb-domains/{code}", response_model=KBDomainResponse)
async def update_kb_domain(
    code: str,
    request: KBDomainRequest,
    http_request: Request,
    user_info: UserInfo = Depends(get_user_info_from_request)
):
    """PUT /admin/kb-domains/{code} - KB Domain 수정"""
    require_admin(user_info)
    
    pool = await get_pool()
    now = datetime.now(timezone.utc)
    
    async with pool.acquire() as conn:
        # 기존 KB Domain 확인
        existing = await conn.fetchrow(
            "SELECT code, created_at FROM kb_domains WHERE code = $1",
            code
        )
        
        if not existing:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "NOT_FOUND",
                    "message": "요청한 리소스를 찾을 수 없습니다.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": f"/admin/kb-domains/{code}"
                }
            )
        
        # 수정
        await conn.execute(
            """
            UPDATE kb_domains
            SET name = $1, s3_path = $2, description = $3, has_data = $4, updated_at = $5
            WHERE code = $6
            """,
            request.name, request.s3_path, request.description, request.has_data, now, code
        )
    
    created_at = existing['created_at'].isoformat() if hasattr(existing['created_at'], 'isoformat') else str(existing['created_at'])
    return KBDomainResponse(
        code=request.code,
        name=request.name,
        s3_path=request.s3_path,
        description=request.description,
        has_data=request.has_data,
        created_at=created_at,
        updated_at=now.isoformat()
    )


@router.delete("/kb-domains/{code}")
async def delete_kb_domain(
    code: str,
    request: Request,
    user_info: UserInfo = Depends(get_user_info_from_request)
):
    """DELETE /admin/kb-domains/{code} - KB Domain 삭제"""
    require_admin(user_info)
    
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        # 기존 KB Domain 확인
        existing = await conn.fetchrow(
            "SELECT code FROM kb_domains WHERE code = $1",
            code
        )
        
        if not existing:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "NOT_FOUND",
                    "message": "요청한 리소스를 찾을 수 없습니다.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": f"/admin/kb-domains/{code}"
                }
            )
        
        # Group Code에서 참조하는지 확인
        group_rows = await conn.fetch(
            "SELECT code, kb_domains FROM group_codes"
        )
        
        for group_row in group_rows:
            kb_domains_str = group_row.get('kb_domains', '')
            if kb_domains_str:
                kb_domains_list = [d.strip() for d in kb_domains_str.split(",") if d.strip()]
                if code in kb_domains_list:
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "error": "INVALID_REQUEST",
                            "message": f"다음 Group Code에서 사용 중입니다: {group_row['code']}",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "path": f"/admin/kb-domains/{code}"
                        }
                    )
        
        # 삭제
        await conn.execute(
            "DELETE FROM kb_domains WHERE code = $1",
            code
        )
    
    return {
        "code": code,
        "deleted": True
    }


# ==================== 파일 업로드 URL 생성 ====================

@router.post("/upload-url", response_model=UploadUrlResponse)
async def create_upload_url(
    request: UploadUrlRequest,
    http_request: Request,
    user_info: UserInfo = Depends(get_user_info_from_request)
):
    """POST /admin/upload-url - 파일 업로드용 Pre-signed URL 생성
    
    S3에 파일을 업로드하기 위한 Pre-signed URL을 생성합니다.
    """
    require_admin(user_info)
    
    # 허용 파일 타입 검사
    ALLOWED_EXTENSIONS = {
        ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
        ".txt", ".csv", ".md", ".html", ".htm"
    }
    ALLOWED_CONTENT_TYPES = {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "text/plain",
        "text/csv",
        "text/markdown",
        "text/html"
    }
    
    # 파일 확장자 검사
    filename_lower = request.filename.lower()
    file_ext = None
    for ext in ALLOWED_EXTENSIONS:
        if filename_lower.endswith(ext):
            file_ext = ext
            break
    
    if not file_ext:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALIDFILETYPE",
                "message": "허용되지 않은 파일 형식입니다.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": "/admin/upload-url"
            }
        )
    
    # 파일 크기 검사 (최대 50MB)
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    if request.file_size and request.file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "FILETOOLARGE",
                "message": "파일 크기가 너무 큽니다.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": "/admin/upload-url"
            }
        )
    
    # S3 클라이언트 생성
    # 자격증명이 있으면 명시적으로 전달 (로컬 개발용)
    # 없으면 boto3가 자동으로 자격증명 체인을 사용 (EC2 IAM 역할 포함)
    s3_kwargs = {
        "service_name": "s3",
        "region_name": settings.aws_region,
    }
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        s3_kwargs["aws_access_key_id"] = settings.aws_access_key_id
        s3_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    
    s3_client = boto3.client(**s3_kwargs)
    
    # S3 버킷명 (환경 변수에서 가져오거나 기본값 사용)
    # 실제로는 Knowledge Base의 데이터 소스 S3 버킷을 사용해야 함
    bucket_name = getattr(settings, "s3_bucket_name", "samhwa-kb-uploads")
    
    # 파일 키 생성 (업로드 ID 포함)
    upload_id = str(uuid.uuid4())
    file_key = f"uploads/{upload_id}/{request.filename}"
    
    # Pre-signed URL 생성 (1시간 유효)
    expires_in = 3600
    
    try:
        presigned_url = s3_client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": bucket_name,
                "Key": file_key,
                "ContentType": request.content_type or "application/octet-stream"
            },
            ExpiresIn=expires_in
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNALSERVERERROR",
                "message": f"S3 Pre-signed URL 생성 실패: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": "/admin/upload-url"
            }
        )
    
    return UploadUrlResponse(
        presigned_url=presigned_url,
        file_key=file_key,
        expires_in=expires_in,
        upload_id=upload_id
    )

