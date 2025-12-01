"""
Mock 데이터베이스 서비스
실제 데이터베이스가 없으므로 메모리 기반으로 구현
데이터베이스 스키마 v1.0 기준
"""
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional
from app.models.history import Conversation, ConversationDetail, Message, MessageMetadata


class MockDatabase:
    """Mock 데이터베이스 클래스"""
    
    def __init__(self):
        # 대화 저장소: {conversation_id: ConversationDetail}
        self.conversations: Dict[str, ConversationDetail] = {}
        # 사용자별 대화 목록: {employee_id: [conversation_id, ...]}
        self.user_conversations: Dict[str, List[str]] = {}
    
    def create_conversation(
        self,
        conversation_id: str,
        corp_id: str,
        employee_id: str,
        user_name: str,
        department: str,
        title: Optional[str] = None
    ) -> ConversationDetail:
        """
        새 대화 생성 (Conversations 테이블 기준)
        
        Args:
            conversation_id: 대화 ID (UUID 형식)
            corp_id: 법인 코드 (VARCHAR(20), NOT NULL)
            employee_id: 사번 (VARCHAR(50), NOT NULL)
            user_name: 사용자 이름 (VARCHAR(100), NOT NULL)
            department: 부서명 (VARCHAR(100), NOT NULL)
            title: 대화 제목 (VARCHAR(255), 기본값 "새 대화")
        """
        now = datetime.now(timezone.utc).isoformat()
        
        conversation = ConversationDetail(
            conversation_id=conversation_id,
            corp_id=corp_id,
            employee_id=employee_id,
            user_name=user_name,
            department=department,
            title=title or "새 대화",
            message_count=0,
            created_at=now,
            updated_at=now,
            messages=[]
        )
        
        self.conversations[conversation_id] = conversation
        
        if employee_id not in self.user_conversations:
            self.user_conversations[employee_id] = []
        if conversation_id not in self.user_conversations[employee_id]:
            self.user_conversations[employee_id].append(conversation_id)
        
        return conversation
    
    def get_conversation(self, conversation_id: str) -> Optional[ConversationDetail]:
        """대화 조회"""
        return self.conversations.get(conversation_id)
    
    def update_conversation_title(self, conversation_id: str, title: str) -> Optional[ConversationDetail]:
        """대화 제목 수정"""
        conversation = self.conversations.get(conversation_id)
        if conversation:
            conversation.title = title
            conversation.updated_at = datetime.now(timezone.utc).isoformat()
        return conversation
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """대화 삭제"""
        conversation = self.conversations.get(conversation_id)
        if conversation:
            employee_id = conversation.employee_id
            if employee_id and employee_id in self.user_conversations:
                if conversation_id in self.user_conversations[employee_id]:
                    self.user_conversations[employee_id].remove(conversation_id)
            del self.conversations[conversation_id]
            return True
        return False
    
    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[MessageMetadata] = None
    ) -> Optional[Message]:
        """
        메시지 추가 (Messages 테이블 기준)
        
        Args:
            conversation_id: 대화 ID (UUID)
            role: 역할 (user, assistant)
            content: 메시지 내용 (TEXT)
            metadata: 메타데이터 (JSONB) - Bedrock Knowledge Base RAG 과정 정보
        """
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return None
        
        message = Message(
            message_id=None,  # DB에서 자동 생성 (BIGSERIAL)
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata=metadata,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        conversation.messages.append(message)
        conversation.message_count = len(conversation.messages)
        conversation.updated_at = datetime.now(timezone.utc).isoformat()
        
        return message
    
    def remove_last_message(self, conversation_id: str, role: Optional[str] = None) -> bool:
        """
        마지막 메시지 제거 (트랜잭션 롤백용)
        
        Args:
            conversation_id: 대화 ID
            role: 역할 필터 (None이면 마지막 메시지, 지정하면 해당 role의 마지막 메시지)
        
        Returns:
            삭제 성공 여부
        """
        conversation = self.conversations.get(conversation_id)
        if not conversation or not conversation.messages:
            return False
        
        if role:
            # 특정 role의 마지막 메시지 찾기
            for i in range(len(conversation.messages) - 1, -1, -1):
                if conversation.messages[i].role == role:
                    conversation.messages.pop(i)
                    conversation.message_count = len(conversation.messages)
                    conversation.updated_at = datetime.now(timezone.utc).isoformat()
                    return True
        else:
            # 마지막 메시지 제거
            conversation.messages.pop()
            conversation.message_count = len(conversation.messages)
            conversation.updated_at = datetime.now(timezone.utc).isoformat()
            return True
        
        return False
    
    def get_user_conversations(
        self,
        employee_id: str,
        page: int = 1,
        page_size: int = 20
    ) -> tuple[List[Conversation], int]:
        """사용자별 대화 목록 조회"""
        conversation_ids = self.user_conversations.get(employee_id, [])
        total = len(conversation_ids)
        
        # 최신순 정렬 (updated_at 기준)
        conversations_list = []
        for conv_id in conversation_ids:
            conv = self.conversations.get(conv_id)
            if conv:
                conversations_list.append(conv)
        
        # updated_at 기준 내림차순 정렬
        conversations_list.sort(key=lambda x: x.updated_at, reverse=True)
        
        # 페이징
        start = (page - 1) * page_size
        end = start + page_size
        paginated = conversations_list[start:end]
        
        # Conversation 객체로 변환 (메시지 제외)
        result = [
            Conversation(
                conversation_id=conv.conversation_id,
                corp_id=conv.corp_id,
                employee_id=conv.employee_id,
                user_name=conv.user_name,
                department=conv.department,
                title=conv.title,
                message_count=conv.message_count,
                created_at=conv.created_at,
                updated_at=conv.updated_at
            )
            for conv in paginated
        ]
        
        return result, total
    
    def check_ownership(self, conversation_id: str, employee_id: str) -> bool:
        """대화 소유권 확인"""
        conversation = self.conversations.get(conversation_id)
        if not conversation:
            return False
        return conversation.employee_id == employee_id


# 전역 Mock 데이터베이스 인스턴스
mock_db = MockDatabase()

