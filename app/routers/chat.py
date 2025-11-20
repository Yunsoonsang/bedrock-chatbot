"""
채팅 API 라우터
POST /chat 엔드포인트 구현 (SSE 스트리밍)
"""
import json
import uuid
import asyncio
from typing import Optional, Dict, List
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.models.chat import ChatRequest
from app.services.bedrock import BedrockService
from app.config.mock_data import MOCK_GROUP_CODES, MOCK_KB_DOMAINS

router = APIRouter(prefix="/chat", tags=["chat"])
bedrock_service = BedrockService()


@router.get("/group-codes")
async def get_group_codes() -> Dict[str, Dict]:
    """
    GET /chat/group-codes - Group Code 목록 조회
    
    모든 Group Code와 해당 KB Domain 정보를 반환합니다.
    """
    return MOCK_GROUP_CODES


@router.get("/kb-domains")
async def get_kb_domains() -> Dict[str, Dict]:
    """
    GET /chat/kb-domains - KB Domain 목록 조회
    
    모든 KB Domain 정보를 반환합니다.
    """
    return MOCK_KB_DOMAINS


@router.get("/group-code/{group_code}/kb-domains")
async def get_kb_domains_by_group_code(group_code: str) -> Dict:
    """
    GET /chat/group-code/{group_code}/kb-domains - 특정 Group Code의 KB Domain 조회
    
    Args:
        group_code: Group Code (G1-G4)
    
    Returns:
        Group Code 정보와 접근 가능한 KB Domain 목록
    """
    if group_code not in MOCK_GROUP_CODES:
        raise HTTPException(status_code=404, detail=f"Group Code '{group_code}'를 찾을 수 없습니다.")
    
    group_info = MOCK_GROUP_CODES[group_code]
    kb_domains = []
    
    for kb_code in group_info["kb_domains"]:
        if kb_code in MOCK_KB_DOMAINS:
            kb_domains.append(MOCK_KB_DOMAINS[kb_code])
    
    return {
        "group_code": group_code,
        "description": group_info["description"],
        "kb_domains": kb_domains
    }


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
    # conversation_id가 없으면 새로 생성
    conversation_id = request.conversation_id or f"conv-{uuid.uuid4().hex[:12]}"
    
    async def generate_stream():
        """SSE 스트리밍 생성기"""
        try:
            # start 이벤트 전송
            yield format_sse_event("start", {"conversation_id": conversation_id})
            
            # Bedrock Retrieve & Generate 호출
            citations = []
            retrieval_results = []
            full_text = ""
            
            # Bedrock 응답 받기
            async for bedrock_event in bedrock_service.retrieve_and_generate_stream(
                query=request.message,
                conversation_id=conversation_id,
                group_code=request.group_code,
                user_name=request.user_name,
                department=request.department
            ):
                # 에러 처리
                if "error" in bedrock_event:
                    error_info = bedrock_event["error"]
                    yield format_sse_event(
                        "error",
                        {
                            "error": error_info.get("error", "UnknownError"),
                            "message": error_info.get("message", "알 수 없는 오류가 발생했습니다.")
                        }
                    )
                    return
                
                # 응답 데이터 추출
                text = bedrock_event.get("text", "")
                event_citations = bedrock_event.get("citations", [])
                event_retrieval_results = bedrock_event.get("retrievalResults", [])
                
                # 텍스트 스트리밍 전송
                if text:
                    # 텍스트를 작은 청크로 분할 (한글/영문 모두 고려)
                    chunk_size = 10  # 한 번에 전송할 문자 수
                    for i in range(0, len(text), chunk_size):
                        chunk = text[i:i + chunk_size]
                        if chunk:
                            yield format_sse_event("token", {"token": chunk})
                            await asyncio.sleep(0.01)  # 자연스러운 스트리밍을 위한 짧은 지연
                    full_text += text
                
                # 메타데이터 업데이트 (있으면)
                if event_citations:
                    citations = event_citations
                if event_retrieval_results:
                    retrieval_results = event_retrieval_results
            
            # metadata 이벤트 전송 (참조 문서가 있는 경우)
            if citations or retrieval_results:
                yield format_sse_event(
                    "metadata",
                    {
                        "citations": citations,
                        "retrieval_results": retrieval_results
                    }
                )
            
            # done 이벤트 전송
            yield format_sse_event("done", {"finish_reason": "stop"})
            
        except Exception as e:
            # 예외 발생 시 에러 이벤트 전송
            yield format_sse_event(
                "error",
                {
                    "error": "InternalError",
                    "message": f"서버 오류가 발생했습니다: {str(e)}"
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

