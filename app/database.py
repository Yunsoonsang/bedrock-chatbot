"""
데이터베이스 연결 및 세션 관리
PostgreSQL (RDS) 연결을 위한 모듈
"""
import asyncpg
from typing import Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# 전역 연결 풀
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """
    데이터베이스 연결 풀 반환 (싱글톤 패턴)
    
    Returns:
        asyncpg.Pool: 데이터베이스 연결 풀
    """
    global _pool
    
    if _pool is None:
        database_url = settings.get_database_url()
        if not database_url:
            raise ValueError("DATABASE_URL이 설정되지 않았습니다. .env 파일을 확인해주세요.")
        
        # DATABASE_URL에서 연결 정보 추출
        # postgresql://user:password@host:port/database?sslmode=require
        
        # 연결 초기화 함수: 각 connection마다 타임존을 UTC로 설정
        async def init_connection(conn):
            await conn.execute("SET timezone = 'UTC'")
        
        _pool = await asyncpg.create_pool(
            database_url,
            min_size=settings.db_pool_size,
            max_size=settings.db_pool_size + settings.db_max_overflow,
            command_timeout=settings.db_pool_timeout,
            init=init_connection,  # 타임존을 UTC로 설정
        )
        logger.info("데이터베이스 연결 풀이 생성되었습니다.")
    
    return _pool


async def close_pool():
    """
    데이터베이스 연결 풀 종료
    """
    global _pool
    
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("데이터베이스 연결 풀이 종료되었습니다.")


async def execute_query(query: str, *args) -> list:
    """
    SELECT 쿼리 실행
    
    Args:
        query: SQL 쿼리
        *args: 쿼리 파라미터
    
    Returns:
        쿼리 결과 리스트
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def execute_one(query: str, *args) -> Optional[dict]:
    """
    단일 행 SELECT 쿼리 실행
    
    Args:
        query: SQL 쿼리
        *args: 쿼리 파라미터
    
    Returns:
        쿼리 결과 딕셔너리 또는 None
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def execute_insert(query: str, *args) -> str:
    """
    INSERT 쿼리 실행 (RETURNING id 사용 시)
    
    Args:
        query: SQL 쿼리
        *args: 쿼리 파라미터
    
    Returns:
        삽입된 행의 ID 또는 결과
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchrow(query, *args)
        return result[0] if result else None


async def execute_update(query: str, *args) -> int:
    """
    UPDATE/DELETE 쿼리 실행
    
    Args:
        query: SQL 쿼리
        *args: 쿼리 파라미터
    
    Returns:
        영향받은 행의 수
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(query, *args)
        return int(result.split()[-1]) if result else 0


async def test_connection() -> bool:
    """
    데이터베이스 연결 테스트
    
    Returns:
        연결 성공 여부
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            result = await conn.fetchval("SELECT 1")
            return result == 1
    except Exception as e:
        logger.error(f"데이터베이스 연결 테스트 실패: {e}")
        return False

