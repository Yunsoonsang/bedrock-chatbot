"""
FastAPI 애플리케이션 진입점
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat
from app.config import settings

# uvicorn의 lifespan 관련 CancelledError 로깅 억제 (서버 종료 시 정상적인 동작)
logging.getLogger("uvicorn.lifespan").setLevel(logging.WARNING)

# FastAPI 앱 생성
# 보안상 API 문서는 기본적으로 비활성화 (enable_docs=True로 설정 시 활성화)
docs_url = "/docs" if settings.enable_docs else None
redoc_url = "/redoc" if settings.enable_docs else None
openapi_url = "/openapi.json" if settings.enable_docs else None

app = FastAPI(
    title="삼화페인트 AI 챗봇 API",
    description="AWS Bedrock 기반 RAG 챗봇 백엔드 API",
    version="1.0.0",
    docs_url=docs_url,
    redoc_url=redoc_url,
    openapi_url=openapi_url
)

# CORS 설정 (시연용 - 모든 origin 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(chat.router)
from app.routers import history, admin
app.include_router(history.router)
app.include_router(admin.router)


@app.get("/")
async def root():
    """루트 엔드포인트"""
    response = {
        "message": "삼화페인트 AI 챗봇 API",
        "version": "1.0.0",
        "health": "/health"
    }
    # 문서가 활성화된 경우에만 docs 정보 포함
    if settings.enable_docs:
        response["docs"] = "/docs"
    return response


@app.get("/health")
async def health_check():
    """헬스체크 엔드포인트"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True
    )

