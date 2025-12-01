"""
환경 변수 설정 관리
.env 파일에서 환경 변수를 로드합니다.
AWS EC2에서는 .env 파일을 사용하며, 로컬 개발 시에도 .env 파일을 사용합니다.
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
    
    # 데이터베이스 설정 (AWS RDS PostgreSQL)
    db_host: Optional[str] = None
    db_port: int = 5432
    db_name: Optional[str] = None
    db_user: Optional[str] = None
    db_password: Optional[str] = None
    # DATABASE_URL이 있으면 우선 사용 (개별 필드보다 우선)
    database_url: Optional[str] = None
    # 연결 풀 설정
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    # SSL 설정 (AWS RDS는 SSL 권장)
    db_ssl_mode: str = "require"
    
    # Mock 데이터 사용 여부 (로컬 테스트용, 기본값: False)
    use_mock_data: bool = False
    
    # API 문서 활성화 여부 (보안상 기본값: False)
    enable_docs: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    def get_database_url(self) -> Optional[str]:
        """
        데이터베이스 연결 URL 생성
        
        Returns:
            DATABASE_URL이 있으면 그대로 반환, 없으면 개별 필드로부터 생성
        """
        if self.database_url:
            return self.database_url
        
        if not all([self.db_host, self.db_name, self.db_user, self.db_password]):
            return None
        
        # PostgreSQL 연결 URL 생성
        # 형식: postgresql://user:password@host:port/database?sslmode=require
        ssl_param = f"?sslmode={self.db_ssl_mode}" if self.db_ssl_mode else ""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}{ssl_param}"


# 전역 설정 인스턴스
settings = Settings()
