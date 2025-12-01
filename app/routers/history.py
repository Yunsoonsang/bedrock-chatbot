"""
대화 이력 관리 API 라우터
데이터베이스 스키마 v1.0 기준
"""
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from typing import Optional
from app.models.history import ConversationListResponse, ConversationDetail, UpdateTitleRequest
from app.models.user import UserInfo
from app.services.db_service import (
    get_conversation, get_user_conversations, update_conversation_title, delete_conversation
)
from app.dependencies import get_user_info_from_request
from datetime import datetime, timezone

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=ConversationListResponse)
async def get_conversation_list(
    request: Request,
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(20, ge=1, le=100, description="페이지 크기"),
    user_info: UserInfo = Depends(get_user_info_from_request)
):
    """
    GET /history - 대화 목록 조회
    
    현재 사용자의 대화 목록을 페이지네이션하여 반환합니다.
    """
    employee_id = user_info.employee_id
    
    if not employee_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_REQUEST",
                "message": "사번 정보가 필요합니다."
            }
        )
    
    conversations, total = await get_user_conversations(
        employee_id=employee_id,
        page=page,
        page_size=page_size
    )
    
    return ConversationListResponse(
        conversations=conversations,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation_detail(
    conversation_id: str,
    request: Request,
    user_info: UserInfo = Depends(get_user_info_from_request)
):
    """
    GET /history/{conversation_id} - 특정 대화 내역 조회
    
    대화 ID로 대화 상세 정보(메시지 포함)를 조회합니다.
    """
    conversation = await get_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "NOT_FOUND",
                "message": "요청한 리소스를 찾을 수 없습니다.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": f"/history/{conversation_id}"
            }
        )
    
    # 소유권 확인
    employee_id = user_info.employee_id
    if employee_id and conversation.employee_id != employee_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "NOT_OWNER",
                "message": "본인의 대화만 접근 가능합니다.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": f"/history/{conversation_id}"
            }
        )
    
    return conversation


@router.put("/{conversation_id}/title")
async def update_conversation_title(
    conversation_id: str,
    request_body: UpdateTitleRequest,
    request: Request,
    user_info: UserInfo = Depends(get_user_info_from_request)
):
    """
    PUT /history/{conversation_id}/title - 대화 제목 수정
    """
    conversation = await get_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "NOT_FOUND",
                "message": "요청한 리소스를 찾을 수 없습니다.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": f"/history/{conversation_id}/title"
            }
        )
    
    # 소유권 확인
    employee_id = user_info.employee_id
    if employee_id and conversation.employee_id != employee_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "NOT_OWNER",
                "message": "본인의 대화만 접근 가능합니다.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": f"/history/{conversation_id}/title"
            }
        )
    
    updated = await update_conversation_title(conversation_id, request_body.title)
    
    if not updated:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNALSERVERERROR",
                "message": "서버 내부 오류가 발생했습니다.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": f"/history/{conversation_id}/title"
            }
        )
    
    return {
        "conversation_id": conversation_id,
        "title": request_body.title,
        "updated_at": updated.updated_at
    }


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    request: Request,
    user_info: UserInfo = Depends(get_user_info_from_request)
):
    """
    DELETE /history/{conversation_id} - 대화 삭제
    """
    conversation = await get_conversation(conversation_id)
    
    if not conversation:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "NOT_FOUND",
                "message": "요청한 리소스를 찾을 수 없습니다.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": f"/history/{conversation_id}"
            }
        )
    
    # 소유권 확인
    employee_id = user_info.employee_id
    if employee_id and conversation.employee_id != employee_id:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "NOT_OWNER",
                "message": "본인의 대화만 접근 가능합니다.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": f"/history/{conversation_id}"
            }
        )
    
    success = await delete_conversation(conversation_id)
    
    if not success:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "INTERNALSERVERERROR",
                "message": "서버 내부 오류가 발생했습니다.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": f"/history/{conversation_id}"
            }
        )
    
    return {
        "conversation_id": conversation_id,
        "deleted": True
    }

