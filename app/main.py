"""
FastAPI 애플리케이션 진입점
"""
import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.routers import chat
from app.config import settings

# uvicorn의 lifespan 관련 CancelledError 로깅 억제 (서버 종료 시 정상적인 동작)
logging.getLogger("uvicorn.lifespan").setLevel(logging.WARNING)

# FastAPI 앱 생성
app = FastAPI(
    title="삼화페인트 AI 챗봇 API",
    description="AWS Bedrock 기반 RAG 챗봇 백엔드 API",
    version="1.0.0"
)

# 정적 파일 서빙 (웹 클라이언트)
app.mount("/static", StaticFiles(directory="static"), name="static")

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


@app.get("/")
async def root():
    """루트 엔드포인트 - 웹 클라이언트로 리다이렉트"""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/static/web/index.html")


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

