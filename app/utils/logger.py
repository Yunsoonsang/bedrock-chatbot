"""
로깅 유틸리티
에러 발생 시 로그 파일에 저장
"""
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# 로그 디렉토리 생성
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# 로그 파일 경로
LOG_FILE = LOG_DIR / "chatbot_errors.log"


def setup_logger() -> logging.Logger:
    """
    채팅봇 에러 로깅용 Logger 설정
    
    Returns:
        설정된 Logger 인스턴스
    """
    logger = logging.getLogger("chatbot.errors")
    logger.setLevel(logging.ERROR)
    
    # 기존 핸들러가 있으면 제거 (중복 방지)
    if logger.handlers:
        return logger
    
    # 파일 핸들러 설정
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.ERROR)
    
    # 포맷터 설정 (구조화된 로그)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    
    return logger


# 전역 Logger 인스턴스
chatbot_logger = setup_logger()


def log_chat_error(
    conversation_id: Optional[str],
    employee_id: Optional[str],
    message: Optional[str],
    error_type: str,
    error_message: str,
    additional_info: Optional[Dict[str, Any]] = None
):
    """
    채팅 에러 로그 저장
    
    Args:
        conversation_id: 대화 ID
        employee_id: 사번
        message: 사용자 메시지
        error_type: 에러 타입 (예: "BedrockError", "StreamingError")
        error_message: 에러 메시지
        additional_info: 추가 정보 (선택)
    """
    log_data = {
        "conversation_id": conversation_id or "N/A",
        "employee_id": employee_id or "N/A",
        "user_message": message[:100] if message else "N/A",  # 메시지 일부만 (개인정보 보호)
        "error_type": error_type,
        "error_message": error_message,
    }
    
    if additional_info:
        log_data.update(additional_info)
    
    # 로그 메시지 포맷팅
    log_message = (
        f"ConversationID={log_data['conversation_id']} | "
        f"EmployeeID={log_data['employee_id']} | "
        f"Message={log_data['user_message']} | "
        f"ErrorType={log_data['error_type']} | "
        f"ErrorMessage={log_data['error_message']}"
    )
    
    chatbot_logger.error(log_message)



