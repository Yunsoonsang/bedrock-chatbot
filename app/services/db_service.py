"""
데이터베이스 서비스 모듈
대화 및 메시지 관련 DB 작업을 처리합니다.
데이터베이스 스키마 v1.0 기준
"""
import json
from typing import Optional, List, Tuple
from datetime import datetime, timezone
from app.database import get_pool
from app.models.history import Conversation, ConversationDetail, Message, MessageMetadata


def get_utc_now():
    """
    UTC 시간을 반환하는 헬퍼 함수 (naive datetime)
    
    데이터베이스 스키마가 TIMESTAMP WITHOUT TIME ZONE인 경우,
    asyncpg는 timezone-aware datetime을 처리할 수 없습니다.
    따라서 UTC로 변환한 후 timezone 정보를 제거하여 naive datetime으로 반환합니다.
    """
    # UTC로 현재 시간을 가져온 후, timezone 정보를 제거하여 naive datetime으로 변환
    # 이렇게 하면 TIMESTAMP WITHOUT TIME ZONE 컬럼에 저장할 수 있습니다
    utc_now = datetime.now(timezone.utc)
    return utc_now.replace(tzinfo=None)


async def get_conversation(conversation_id: str) -> Optional[ConversationDetail]:
    """
    대화 조회 (메시지 포함)
    
    Args:
        conversation_id: 대화 ID (UUID)
    
    Returns:
        ConversationDetail 또는 None
    """
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        # 대화 정보 조회
        conv_row = await conn.fetchrow(
            """
            SELECT conversation_id, corp_id, employee_id, user_name, department, 
                   title, message_count, created_at, updated_at
            FROM conversations
            WHERE conversation_id = $1
            """,
            conversation_id
        )
        
        if not conv_row:
            return None
        
        # 메시지 목록 조회
        message_rows = await conn.fetch(
            """
            SELECT message_id, conversation_id, role, content, metadata, created_at
            FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at ASC
            """,
            conversation_id
        )
        
        # 메시지 변환
        messages = []
        for msg_row in message_rows:
            metadata = None
            if msg_row['metadata']:
                try:
                    metadata_dict = msg_row['metadata'] if isinstance(msg_row['metadata'], dict) else json.loads(msg_row['metadata'])
                    metadata = MessageMetadata(**metadata_dict) if metadata_dict else None
                except (json.JSONDecodeError, TypeError):
                    metadata = None
            
            messages.append(Message(
                message_id=msg_row['message_id'],
                conversation_id=msg_row['conversation_id'],
                role=msg_row['role'],
                content=msg_row['content'],
                metadata=metadata,
                created_at=msg_row['created_at'].isoformat() if hasattr(msg_row['created_at'], 'isoformat') else str(msg_row['created_at'])
            ))
        
        return ConversationDetail(
            conversation_id=str(conv_row['conversation_id']),
            corp_id=conv_row['corp_id'],
            employee_id=conv_row['employee_id'],
            user_name=conv_row['user_name'],
            department=conv_row['department'],
            title=conv_row['title'],
            message_count=conv_row['message_count'],
            created_at=conv_row['created_at'].isoformat() if hasattr(conv_row['created_at'], 'isoformat') else str(conv_row['created_at']),
            updated_at=conv_row['updated_at'].isoformat() if hasattr(conv_row['updated_at'], 'isoformat') else str(conv_row['updated_at']),
            messages=messages
        )


async def create_conversation(
    conversation_id: str,
    corp_id: str,
    employee_id: str,
    user_name: str,
    department: str,
    title: Optional[str] = None
) -> ConversationDetail:
    """
    새 대화 생성
    
    Args:
        conversation_id: 대화 ID (UUID)
        corp_id: 법인 코드
        employee_id: 사번
        user_name: 사용자 이름
        department: 부서명
        title: 대화 제목 (기본값: "새 대화")
    
    Returns:
        ConversationDetail
    """
    pool = await get_pool()
    now = get_utc_now()
    title_value = title or "새 대화"
    
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO conversations (conversation_id, corp_id, employee_id, user_name, 
                                     department, title, message_count, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            conversation_id, corp_id, employee_id, user_name, department, 
            title_value, 0, now, now
        )
    
    return ConversationDetail(
        conversation_id=conversation_id,
        corp_id=corp_id,
        employee_id=employee_id,
        user_name=user_name,
        department=department,
        title=title_value,
        message_count=0,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
        messages=[]
    )


async def add_message(
    conversation_id: str,
    role: str,
    content: str,
    metadata: Optional[MessageMetadata] = None
) -> Optional[Message]:
    """
    메시지 추가
    
    Args:
        conversation_id: 대화 ID
        role: 역할 (user, assistant)
        content: 메시지 내용
        metadata: 메타데이터
    
    Returns:
        Message 또는 None (대화가 없는 경우)
    """
    pool = await get_pool()
    now = get_utc_now()
    
    # metadata를 JSON으로 변환
    metadata_json = None
    if metadata:
        metadata_dict = metadata.model_dump(exclude_none=True)
        metadata_json = json.dumps(metadata_dict, ensure_ascii=False)
    
    async with pool.acquire() as conn:
        # 트랜잭션 시작
        async with conn.transaction():
            # 대화 존재 확인
            conv_row = await conn.fetchrow(
                "SELECT conversation_id FROM conversations WHERE conversation_id = $1",
                conversation_id
            )
            
            if not conv_row:
                return None
            
            # 메시지 삽입
            message_id = await conn.fetchval(
                """
                INSERT INTO messages (conversation_id, role, content, metadata, created_at)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING message_id
                """,
                conversation_id, role, content, metadata_json, now
            )
            
            # 대화의 message_count 업데이트
            await conn.execute(
                """
                UPDATE conversations
                SET message_count = message_count + 1,
                    updated_at = $1
                WHERE conversation_id = $2
                """,
                now, conversation_id
            )
    
    return Message(
        message_id=message_id,
        conversation_id=conversation_id,
        role=role,
        content=content,
        metadata=metadata,
        created_at=now.isoformat()
    )


async def remove_last_message(conversation_id: str, role: Optional[str] = None) -> bool:
    """
    마지막 메시지 제거 (트랜잭션 롤백용)
    
    Args:
        conversation_id: 대화 ID
        role: 역할 필터 (None이면 마지막 메시지, 지정하면 해당 role의 마지막 메시지)
    
    Returns:
        삭제 성공 여부
    """
    pool = await get_pool()
    now = get_utc_now()
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            # 대화 존재 확인
            conv_row = await conn.fetchrow(
                "SELECT conversation_id FROM conversations WHERE conversation_id = $1",
                conversation_id
            )
            
            if not conv_row:
                return False
            
            # 삭제할 메시지 찾기
            if role:
                # 특정 role의 마지막 메시지
                message_row = await conn.fetchrow(
                    """
                    SELECT message_id FROM messages
                    WHERE conversation_id = $1 AND role = $2
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    conversation_id, role
                )
            else:
                # 마지막 메시지
                message_row = await conn.fetchrow(
                    """
                    SELECT message_id FROM messages
                    WHERE conversation_id = $1
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    conversation_id
                )
            
            if not message_row:
                return False
            
            message_id = message_row['message_id']
            
            # 메시지 삭제
            await conn.execute(
                "DELETE FROM messages WHERE message_id = $1",
                message_id
            )
            
            # 대화의 message_count 업데이트
            await conn.execute(
                """
                UPDATE conversations
                SET message_count = GREATEST(message_count - 1, 0),
                    updated_at = $1
                WHERE conversation_id = $2
                """,
                now, conversation_id
            )
    
    return True


async def get_user_conversations(
    employee_id: str,
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[Conversation], int]:
    """
    사용자별 대화 목록 조회
    
    Args:
        employee_id: 사번
        page: 페이지 번호
        page_size: 페이지 크기
    
    Returns:
        (대화 목록, 전체 개수) 튜플
    """
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        # 전체 개수 조회
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM conversations WHERE employee_id = $1",
            employee_id
        )
        
        # 페이징 조회
        offset = (page - 1) * page_size
        rows = await conn.fetch(
            """
            SELECT conversation_id, corp_id, employee_id, user_name, department, 
                   title, message_count, created_at, updated_at
            FROM conversations
            WHERE employee_id = $1
            ORDER BY updated_at DESC
            LIMIT $2 OFFSET $3
            """,
            employee_id, page_size, offset
        )
        
        conversations = []
        for row in rows:
            conversations.append(Conversation(
                conversation_id=str(row['conversation_id']),
                corp_id=row['corp_id'],
                employee_id=row['employee_id'],
                user_name=row['user_name'],
                department=row['department'],
                title=row['title'],
                message_count=row['message_count'],
                created_at=row['created_at'].isoformat() if hasattr(row['created_at'], 'isoformat') else str(row['created_at']),
                updated_at=row['updated_at'].isoformat() if hasattr(row['updated_at'], 'isoformat') else str(row['updated_at'])
            ))
    
    return conversations, total


async def update_conversation_title(conversation_id: str, title: str) -> Optional[ConversationDetail]:
    """
    대화 제목 수정
    
    Args:
        conversation_id: 대화 ID
        title: 새로운 제목
    
    Returns:
        ConversationDetail 또는 None
    """
    pool = await get_pool()
    now = get_utc_now()
    
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE conversations
            SET title = $1, updated_at = $2
            WHERE conversation_id = $3
            """,
            title, now, conversation_id
        )
        
        # 업데이트된 대화 조회
        return await get_conversation(conversation_id)


async def delete_conversation(conversation_id: str) -> bool:
    """
    대화 삭제 (메시지도 함께 삭제)
    
    Args:
        conversation_id: 대화 ID
    
    Returns:
        삭제 성공 여부
    """
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        async with conn.transaction():
            # 대화 존재 확인
            conv_row = await conn.fetchrow(
                "SELECT conversation_id FROM conversations WHERE conversation_id = $1",
                conversation_id
            )
            
            if not conv_row:
                return False
            
            # 메시지 삭제 (CASCADE로 자동 삭제될 수도 있지만 명시적으로)
            await conn.execute(
                "DELETE FROM messages WHERE conversation_id = $1",
                conversation_id
            )
            
            # 대화 삭제
            await conn.execute(
                "DELETE FROM conversations WHERE conversation_id = $1",
                conversation_id
            )
    
    return True

