"""
환경 변수 설정 관리
env.txt 파일에서 환경 변수를 로드합니다.
"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # AWS 설정
    aws_region: str = "ap-northeast-2"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    
    # Bedrock 설정
    knowledge_base_id: str = "RI1TSG1NON"
    foundation_model_id: str = "anthropic.claude-sonnet-4-20250514-v1:0"  # 텍스트 생성용 Foundation Model ID (참고용)
    
    # Inference Profile 설정 (성능 비교를 위해 환경변수로 관리)
    # Inference Profile ARN 또는 Inference Profile ID 사용 가능
    # Inference Profile ID만 지정하면 ARN을 자동 생성 (권장)
    inference_profile_id: Optional[str] = "apac.anthropic.claude-sonnet-4-20250514-v1:0"
    # 또는 전체 ARN 직접 지정 (선택사항)
    inference_profile_arn: Optional[str] = None
    # AWS Account ID (Inference Profile ARN 자동 생성 시 필요)
    aws_account_id: Optional[str] = "679801244612"
    
    # API 설정
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    
    class Config:
        env_file = "env.txt"
        env_file_encoding = "utf-8"
        case_sensitive = False


# 전역 설정 인스턴스
settings = Settings()
