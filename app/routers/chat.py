"""
채팅 API 라우터
POST /chat 엔드포인트 구현 (SSE 스트리밍)
데이터베이스 스키마 v1.0 기준
"""
import json
import uuid
import re
import asyncio
from typing import Optional, Dict, List
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.chat import ChatRequest
from app.models.history import Conversation, MessageMetadata, MessageMetadataSource
from app.services.bedrock import BedrockService
from app.services.db_service import (
    get_conversation, create_conversation, add_message, remove_last_message
)
from app.config import settings
from app.utils.logger import log_chat_error

router = APIRouter(prefix="/chat", tags=["chat"])
bedrock_service = BedrockService()


def format_sse_event(event_type: str, data: dict) -> str:
    """
    SSE 이벤트 포맷팅
    
    Args:
        event_type: 이벤트 타입 (start, token, metadata, done, error)
        data: 이벤트 데이터
    
    Returns:
        SSE 형식 문자열
    """
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("")
async def chat(request: ChatRequest):
    """
    POST /chat - SSE 스트리밍 채팅 API
    
    사용자 메시지를 받아 Bedrock Knowledge Base에서 답변을 생성하고
    Server-Sent Events(SSE) 형식으로 스트리밍 응답을 반환합니다.
    
    이벤트 타입:
    - start: 대화 시작, conversation_id 전달
    - token: 스트리밍 텍스트 토큰
    - metadata: 참조 문서 정보 (선택적)
    - done: 완료 정보
    - error: 에러 발생 시
    """
    # 메시지 길이 검증
    if len(request.message) > 2000:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "MESSAGETOOLONG",
                "message": "메시지가 너무 깁니다.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": "/chat"
            }
        )
    
    # 필수 사용자 정보 검증
    if not request.employee_id:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_REQUEST",
                "message": "사번(employee_id)은 필수입니다.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": "/chat"
            }
        )
    
    # 필수 group_code 검증
    if not request.group_code:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "INVALID_REQUEST",
                "message": "그룹 코드(group_code)는 필수입니다.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": "/chat"
            }
        )
    
    # conversation_id가 없으면 UUID 형식으로 새로 생성
    # 제공된 경우 UUID 형식 검증 및 기존 대화 확인
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    existing_conversation = None
    
    if request.conversation_id:
        if not re.match(uuid_pattern, request.conversation_id):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_REQUEST",
                    "message": "conversation_id는 UUID 형식이어야 합니다.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": "/chat"
                }
            )
        conversation_id = request.conversation_id
        # 기존 대화 확인
        existing_conversation = await get_conversation(conversation_id)
        if existing_conversation:
            # 기존 대화의 employee_id와 요청의 employee_id 일치 확인
            if request.employee_id and existing_conversation.employee_id != request.employee_id:
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": "NOT_OWNER",
                        "message": "본인의 대화만 접근 가능합니다.",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "path": "/chat"
                    }
                )
    else:
        conversation_id = Conversation.generate_conversation_id()
    
    # 대화 이력 저장 (신규 대화인 경우)
    is_new_conversation = False
    if not existing_conversation:
        is_new_conversation = True
        # 필수 필드 검증 및 기본값 설정
        # 실제 운영 환경에서는 기본값 사용 지양, 명시적 값 요구
        corp_id = request.corp_id
        if not corp_id:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_REQUEST",
                    "message": "법인 코드(corp_id)는 필수입니다.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": "/chat"
                }
            )
        
        user_name = request.name
        if not user_name:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_REQUEST",
                    "message": "사용자 이름(name)은 필수입니다.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": "/chat"
                }
            )
        
        department = request.department
        if not department:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "INVALID_REQUEST",
                    "message": "부서명(department)은 필수입니다.",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": "/chat"
                }
            )
        
        await create_conversation(
            conversation_id=conversation_id,
            corp_id=corp_id,
            employee_id=request.employee_id,
            user_name=user_name,
            department=department,
            title=None  # 첫 메시지로 제목 생성 가능
        )
    
    async def generate_stream():
        """SSE 스트리밍 생성기"""
        start_time = datetime.now(timezone.utc)
        user_message_saved = False  # 사용자 메시지 저장 여부 추적
        
        try:
            # start 이벤트 전송 (명세서 형식에 맞춤)
            yield format_sse_event("start", {
                "conversation_id": conversation_id,
                "timestamp": start_time.isoformat()
            })
            
            # 사용자 메시지 저장 (트랜잭션 시작)
            # 성공 시에만 유지되도록, 에러 발생 시 롤백 예정
            await add_message(
                conversation_id=conversation_id,
                role="user",
                content=request.message,
                metadata=None
            )
            user_message_saved = True
            
            # Bedrock Retrieve & Generate 호출
            citations = []
            retrieval_results = []
            full_text = ""
            total_tokens = 0  # Bedrock 응답에서 추출
            
            # Bedrock 응답 받기
            async for bedrock_event in bedrock_service.retrieve_and_generate_stream(
                query=request.message,
                conversation_id=conversation_id,
                group_code=request.group_code,
                user_name=request.name,
                department=request.department
            ):
                # 에러 처리
                if "error" in bedrock_event:
                    error_info = bedrock_event["error"]
                    error_type = error_info.get("error", "INTERNAL_ERROR")
                    error_message = error_info.get("message", "알 수 없는 오류가 발생했습니다.")
                    
                    # 에러 로그 저장 (서버 로그)
                    log_chat_error(
                        conversation_id=conversation_id,
                        employee_id=request.employee_id,
                        message=request.message,
                        error_type=f"Bedrock{error_type}",
                        error_message=error_message,
                        additional_info={
                            "group_code": request.group_code,
                            "corp_id": request.corp_id
                        }
                    )
                    
                    # 사용자 메시지 롤백 (트랜잭션 롤백)
                    if user_message_saved:
                        await remove_last_message(conversation_id, role="user")
                    
                    yield format_sse_event(
                        "error",
                        {
                            "error": error_type,
                            "message": error_message,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        }
                    )
                    return
                
                # usage 정보 추출 (tokens 정보)
                if "usage" in bedrock_event:
                    usage = bedrock_event["usage"]
                    total_tokens = usage.get("total_tokens", 0)
                
                # 응답 데이터 추출
                text = bedrock_event.get("text", "")
                event_citations = bedrock_event.get("citations", [])
                event_retrieval_results = bedrock_event.get("retrievalResults", [])
                
                # 텍스트 스트리밍 전송 (명세서: token 이벤트의 content 필드)
                if text:
                    # 텍스트를 작은 청크로 분할 (한글/영문 모두 고려)
                    chunk_size = 10  # 한 번에 전송할 문자 수
                    for i in range(0, len(text), chunk_size):
                        chunk = text[i:i + chunk_size]
                        if chunk:
                            yield format_sse_event("token", {"content": chunk})
                            await asyncio.sleep(0.01)  # 자연스러운 스트리밍을 위한 짧은 지연
                    full_text += text
                
                # 메타데이터 업데이트 (있으면)
                if event_citations:
                    citations = event_citations
                if event_retrieval_results:
                    retrieval_results = event_retrieval_results
            
            # metadata 이벤트 전송 (참조 문서가 있는 경우, 명세서 형식에 맞춤)
            metadata_sources = []
            if citations or retrieval_results:
                # citations를 명세서 형식으로 변환 (kb_domain 추출 포함)
                for citation in citations:
                    title = citation.get("title", "Unknown")
                    s3_uri = citation.get("s3_uri", "")
                    
                    # KB Domain 추출 (S3 URI 기반) - async 함수이므로 await 필요
                    kb_domain = None
                    if s3_uri:
                        kb_domain = await bedrock_service._extract_kb_domain_from_s3_uri(s3_uri)
                    
                    # 페이지 번호 추출 (가능한 경우)
                    page = None
                    # relevance 추출 (retrieval_results에서 가져올 수 있으면)
                    relevance = None
                    document_id = s3_uri.split("/")[-1] if s3_uri else ""
                    
                    metadata_sources.append(MessageMetadataSource(
                        title=title,
                        page=page,
                        relevance=relevance,
                        document_id=document_id,
                        kb_domain=kb_domain
                    ))
                
                # SSE 이벤트용 sources (dict 형식)
                sse_sources = [
                    {
                        "title": src.title,
                        "page": src.page,
                        "relevance": src.relevance,
                        "document_id": src.document_id,
                        "kb_domain": src.kb_domain
                    }
                    for src in metadata_sources
                ]
                
                yield format_sse_event("metadata", {"sources": sse_sources})
            
            # done 이벤트 전송 (명세서 형식에 맞춤)
            end_time = datetime.now(timezone.utc)
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            yield format_sse_event("done", {
                "total_tokens": total_tokens,
                "finish_reason": "complete",
                "duration_ms": duration_ms
            })
            
            # Assistant 메시지 저장 (metadata 포함)
            if full_text:
                # MessageMetadata 생성
                message_metadata = None
                if metadata_sources or total_tokens or duration_ms:
                    message_metadata = MessageMetadata(
                        sources=metadata_sources,
                        tokens=total_tokens if total_tokens > 0 else None,
                        model=settings.inference_profile_id or settings.foundation_model_id,
                        duration_ms=duration_ms
                    )
                
                await add_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=full_text,
                    metadata=message_metadata
                )
            
        except Exception as e:
            # 예외 발생 시 에러 로그 저장 (서버 로그)
            error_type = type(e).__name__
            error_message = str(e)
            
            log_chat_error(
                conversation_id=conversation_id,
                employee_id=request.employee_id,
                message=request.message,
                error_type=f"Streaming{error_type}",
                error_message=error_message,
                additional_info={
                    "group_code": request.group_code,
                    "corp_id": request.corp_id
                }
            )
            
            # 사용자 메시지 롤백 (트랜잭션 롤백)
            if user_message_saved:
                await remove_last_message(conversation_id, role="user")
            
            # 에러 이벤트 전송
            yield format_sse_event(
                "error",
                {
                    "error": "INTERNAL_ERROR",
                    "message": f"서버 오류가 발생했습니다: {error_message}",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Nginx 버퍼링 비활성화
        }
    )

