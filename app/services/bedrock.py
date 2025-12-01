"""
AWS Bedrock Knowledge Base 연동 서비스
"""
import boto3
import asyncio
import json
from typing import AsyncIterator, Dict, Any, Optional, List, Tuple
from urllib.parse import urlparse
from app.config import settings
from app.database import get_pool
# Mock 데이터는 로컬 테스트용으로만 사용 (use_mock_data=True일 때만 활성화)
# 실제 운영 환경에서는 데이터베이스에서 데이터를 가져옵니다
if settings.use_mock_data:
    from app.config.mock_data import MOCK_GROUP_CODES, MOCK_KB_DOMAINS
else:
    # Mock 데이터 비활성화 시 빈 딕셔너리 사용
    MOCK_GROUP_CODES = {}
    MOCK_KB_DOMAINS = {}


class BedrockService:
    """Bedrock Knowledge Base 서비스"""
    
    def __init__(self):
        """Bedrock 클라이언트 초기화
        
        자격증명 처리:
        - 환경 변수에 자격증명이 있으면 (로컬 개발) → 명시적으로 전달
        - 환경 변수에 자격증명이 없으면 (EC2 IAM 역할) → boto3가 자동으로 IAM 역할 사용
        """
        client_kwargs = {
            "service_name": "bedrock-agent-runtime",
            "region_name": settings.aws_region,
        }
        
        # 환경 변수에 자격증명이 있으면 사용 (로컬 개발용)
        # 없으면 boto3가 자동으로 자격증명 체인을 사용 (EC2 IAM 역할 포함)
        if settings.aws_access_key_id and settings.aws_secret_access_key:
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        
        self.client = boto3.client(**client_kwargs)
        self.knowledge_base_id = settings.knowledge_base_id
        self.foundation_model_id = settings.foundation_model_id
        
        # Inference Profile 설정
        # Inference Profile ARN이 직접 지정되어 있으면 사용, 없으면 ID로부터 ARN 생성
        if settings.inference_profile_arn:
            self.inference_profile_arn = settings.inference_profile_arn
        elif settings.inference_profile_id and settings.aws_account_id:
            self.inference_profile_arn = (
                f"arn:aws:bedrock:{settings.aws_region}:{settings.aws_account_id}:"
                f"inference-profile/{settings.inference_profile_id}"
            )
        else:
            # 기본값 (Claude Sonnet 4)
            self.inference_profile_arn = (
                f"arn:aws:bedrock:{settings.aws_region}:679801244612:"
                f"inference-profile/apac.anthropic.claude-sonnet-4-20250514-v1:0"
            )
    
    async def retrieve_and_generate_stream(
        self,
        query: str,
        conversation_id: Optional[str] = None,
        group_code: Optional[str] = None,
        user_name: Optional[str] = None,
        department: Optional[str] = None
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Bedrock Knowledge Base에서 Retrieve & Generate 수행 후 스트리밍 형태로 변환
        group_code별 필터링 적용
        
        Args:
            query: 사용자 쿼리
            conversation_id: 대화 ID (선택)
            group_code: 그룹 코드 (선택, 예: GRP_IN_ALL, GRP_QLT_QM_RP, GRP_TS_ALL)
            user_name: 사용자 이름 (선택, 프롬프트에 활용)
            department: 부서명 (선택, 프롬프트에 활용)
        
        Yields:
            이벤트 딕셔너리 (text, citations, retrievalResults)
        """
        try:
            # 1단계: Retrieve - 검색만 수행
            allowed_s3_paths = await self._get_allowed_s3_paths(group_code)
            
            retrieve_params = {
                "knowledgeBaseId": self.knowledge_base_id,
                "retrievalQuery": {
                    "text": query
                },
                "retrievalConfiguration": {
                    "vectorSearchConfiguration": {
                        "numberOfResults": 10  # 최대 검색 결과 수
                    }
                }
            }
            
            # Retrieve API 호출
            loop = asyncio.get_event_loop()
            retrieve_response = await loop.run_in_executor(
                None,
                lambda: self.client.retrieve(**retrieve_params)
            )
            
            retrieval_results = retrieve_response.get("retrievalResults", [])
            
            # 2단계: 필터링 및 권한 체크
            filter_result = await self._filter_retrieval_results(retrieval_results, allowed_s3_paths)
            filtered_results = filter_result["allowed"]
            blocked_domains = filter_result["blocked_domains"]
            has_permission_violation = filter_result["has_permission_violation"]
            
            # 필터링 후 결과가 없는 경우 처리
            if not filtered_results:
                # 원본 검색 결과가 있었지만 모두 필터링된 경우
                if retrieval_results:
                    permission_msg = await self._generate_permission_message(blocked_domains, group_code)
                    yield {
                        "text": f"죄송합니다. 문의하신 내용은 현재 계정으로 접근할 수 없는 영역입니다.{permission_msg}",
                        "citations": [],
                        "retrievalResults": []
                    }
                    return
                else:
                    # 검색 결과 자체가 없는 경우
                    yield {
                        "text": "죄송합니다. 해당 내용은 제가 참고할 수 있는 문서에서 찾을 수 없습니다.\n\n다음 방법을 추천드립니다:\n1. 관련 부서 담당자에게 문의\n2. 질문을 더 구체적으로 다시 작성해주세요",
                        "citations": [],
                        "retrievalResults": []
                    }
                    return
            
            # 3단계: 필터링된 컨텍스트로 답변 생성
            # 컨텍스트 구성
            context_texts = []
            citations = []
            
            for result in filtered_results:
                content = result.get("content", {})
                text = content.get("text", "")
                if text:
                    context_texts.append(text)
                
                # Citation 정보 수집
                location = result.get("location", {})
                if "s3Location" in location:
                    s3_uri = location["s3Location"].get("uri", "")
                    
                    # S3 URI에서 파일명 추출
                    title = self._extract_filename_from_s3_uri(s3_uri)
                    
                    # metadata에서 title이 있으면 우선 사용
                    metadata = result.get("metadata", {})
                    if metadata and "title" in metadata:
                        title = metadata["title"]
                    elif metadata and "source_metadata" in metadata:
                        source_metadata = metadata["source_metadata"]
                        if "title" in source_metadata:
                            title = source_metadata["title"]
                    
                    citations.append({
                        "title": title,
                        "s3_uri": s3_uri,
                        "generatedResponsePart": {
                            "textResponsePart": {
                                "text": text[:100] + "..." if len(text) > 100 else text
                            }
                        },
                        "retrievedReferences": [{
                            "location": location,
                            "content": content
                        }]
                    })
            
            context = "\n\n".join(context_texts)
            
            # 권한 제한 메시지 (필요시)
            permission_note = ""
            if has_permission_violation:
                permission_note = await self._generate_permission_message(blocked_domains, group_code)
            
            # 프롬프트 구성
            prompt = await self._build_filtered_prompt(
                query=query,
                context=context,
                user_name=user_name,
                department=department,
                group_code=group_code,
                permission_note=permission_note
            )
            
            # 4단계: invoke_model로 답변 생성 (스트리밍)
            full_text = ""
            async for chunk in self._invoke_model_stream(prompt):
                # 에러 체크
                if "error" in chunk:
                    yield chunk
                    return
                
                # 텍스트 청크 수집 및 yield
                if "text" in chunk:
                    full_text += chunk["text"]
                    yield {"text": chunk["text"]}
            
            # 최종 메타데이터 yield (텍스트가 있는 경우)
            if full_text:
                yield {
                    "citations": citations,
                    "retrievalResults": filtered_results
                }
                
        except Exception as e:
            # 에러 발생 시 에러 이벤트 yield
            error_event = {
                "error": {
                    "error": "BedrockError",
                    "message": str(e)
                }
            }
            yield error_event
    
    async def _invoke_model_stream(self, prompt: str) -> AsyncIterator[Dict[str, Any]]:
        """
        Bedrock 모델을 호출하여 스트리밍 응답 생성
        
        Args:
            prompt: 프롬프트 텍스트
        
        Yields:
            텍스트 청크 딕셔너리
        """
        try:
            # Bedrock Runtime 클라이언트 생성 (invoke_model용)
            # 자격증명이 있으면 명시적으로 전달, 없으면 boto3가 자동으로 IAM 역할 사용
            runtime_kwargs = {
                "service_name": "bedrock-runtime",
                "region_name": settings.aws_region,
            }
            if settings.aws_access_key_id and settings.aws_secret_access_key:
                runtime_kwargs["aws_access_key_id"] = settings.aws_access_key_id
                runtime_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
            
            runtime_client = boto3.client(**runtime_kwargs)
            
            # Claude 모델 요청 형식
            request_body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 4096,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            # 스트리밍 호출 - Inference Profile ARN을 직접 사용
            # Bedrock에서는 on-demand throughput 모델을 직접 호출할 수 없고
            # Inference Profile을 통해 호출해야 함
            response = runtime_client.invoke_model_with_response_stream(
                modelId=self.inference_profile_arn,
                body=json.dumps(request_body)
            )
            
            stream = response.get("body")
            usage_info = None  # usage 정보 저장용
            
            if stream:
                for event in stream:
                    if "chunk" in event:
                        chunk_bytes = event["chunk"].get("bytes")
                        if chunk_bytes:
                            chunk = json.loads(chunk_bytes)
                            
                            # content_block.delta 형식 확인
                            if "contentBlockDelta" in chunk:
                                delta = chunk["contentBlockDelta"].get("delta", {})
                                if "text" in delta:
                                    yield {"text": delta["text"]}
                            # delta 형식 확인 (하위 호환성)
                            elif "delta" in chunk:
                                delta = chunk["delta"]
                                if "text" in delta:
                                    yield {"text": delta["text"]}
                            
                            # usage 정보 추출 (message_stop 이벤트에서)
                            if "messageStop" in chunk:
                                usage = chunk["messageStop"].get("usage", {})
                                if usage:
                                    usage_info = {
                                        "input_tokens": usage.get("inputTokens", 0),
                                        "output_tokens": usage.get("outputTokens", 0),
                                        "total_tokens": usage.get("inputTokens", 0) + usage.get("outputTokens", 0)
                                    }
                            
                            # 완료 신호
                            if chunk.get("type") == "message_stop" or chunk.get("type") == "content_block_stop":
                                # usage 정보가 있으면 yield
                                if usage_info:
                                    yield {"usage": usage_info}
                                break
                            
        except Exception as e:
            error_msg = str(e)
            # AWS 자격증명 관련 에러 감지
            if "NoCredentialsError" in str(type(e)) or "Unable to locate credentials" in error_msg:
                error_msg = "AWS 자격증명을 찾을 수 없습니다. 환경 변수 또는 IAM 역할을 확인하세요."
            elif "AccessDenied" in error_msg or "UnauthorizedOperation" in error_msg:
                error_msg = "AWS 권한이 부족합니다. 필요한 권한을 확인하세요."
            elif "InvalidParameter" in error_msg or "ValidationException" in error_msg:
                error_msg = f"잘못된 요청 파라미터입니다: {error_msg}"
            
            yield {
                "error": {
                    "error": "InvokeModelError",
                    "message": error_msg
                }
            }
    
    async def _get_allowed_s3_paths(self, group_code: Optional[str] = None) -> List[str]:
        """
        Group Code에 허용된 S3 경로 목록 반환
        
        Args:
            group_code: Group Code (예: GRP_IN_ALL, GRP_QLT_QM_RP, GRP_TS_ALL), 필수
        
        Returns:
            허용된 S3 경로 목록 (예: ["사내내규/인사총무/", "사내내규/표준관리/"])
        """
        # group_code가 없으면 빈 리스트 반환 (접근 불가)
        if not group_code:
            return []
        
        if settings.use_mock_data:
            # Mock 데이터 사용
            if group_code not in MOCK_GROUP_CODES:
                return []
            
            group_info = MOCK_GROUP_CODES[group_code]
            allowed_paths = []
            
            kb_domains_str = group_info.get("kb_domains", "")
            if isinstance(kb_domains_str, str):
                kb_domains_list = [d.strip() for d in kb_domains_str.split(",") if d.strip()]
            else:
                kb_domains_list = kb_domains_str if isinstance(kb_domains_str, list) else []
            
            for kb_code in kb_domains_list:
                if kb_code in MOCK_KB_DOMAINS:
                    allowed_paths.append(MOCK_KB_DOMAINS[kb_code]["s3_path"])
            
            return allowed_paths
        else:
            # 데이터베이스에서 조회
            pool = await get_pool()
            async with pool.acquire() as conn:
                # group_code에 해당하는 kb_domains 조회
                group_row = await conn.fetchrow(
                    "SELECT kb_domains FROM group_codes WHERE code = $1",
                    group_code
                )
                
                if not group_row:
                    # group_code가 존재하지 않으면 빈 리스트 반환
                    return []
                
                kb_domains_str = group_row['kb_domains']
                kb_domains_list = [d.strip() for d in kb_domains_str.split(",") if d.strip()] if kb_domains_str else []
                
                if not kb_domains_list:
                    return []
                
                # kb_domains에 해당하는 s3_path 조회
                placeholders = ','.join([f'${i+1}' for i in range(len(kb_domains_list))])
                query = f"SELECT s3_path FROM kb_domains WHERE code IN ({placeholders})"
                rows = await conn.fetch(query, *kb_domains_list)
                
                return [row['s3_path'] for row in rows]
    
    def _extract_filename_from_s3_uri(self, s3_uri: str) -> str:
        """
        S3 URI에서 파일명 추출
        
        Args:
            s3_uri: S3 URI (예: "s3://bucket/사내내규/인사총무/선택적 복지제도 지침.pdf")
        
        Returns:
            파일명 (예: "선택적 복지제도 지침.pdf") 또는 경로의 마지막 부분
        """
        try:
            # S3 URI 파싱
            parsed = urlparse(s3_uri)
            # 경로 부분 추출 (예: "/사내내규/인사총무/선택적 복지제도 지침.pdf")
            path = parsed.path.lstrip('/')
            
            # 경로의 마지막 부분 추출 (파일명)
            if '/' in path:
                filename = path.split('/')[-1]
            else:
                filename = path
            
            # 파일 확장자 제거 (선택적)
            # filename = filename.rsplit('.', 1)[0] if '.' in filename else filename
            
            return filename if filename else s3_uri
        except Exception:
            return s3_uri
    
    async def _extract_kb_domain_from_s3_uri(self, s3_uri: str) -> Optional[str]:
        """
        S3 URI에서 KB Domain 코드 추출
        
        Args:
            s3_uri: S3 URI (예: "s3://bucket/사내내규/인사총무/doc.pdf")
        
        Returns:
            KB Domain 코드 (예: "IN_HR", "QLT_SPEC", "TS_OUT") 또는 None
        """
        try:
            # S3 URI 파싱
            parsed = urlparse(s3_uri)
            # 경로 부분 추출 (예: "/사내내규/인사총무/doc.pdf")
            path = parsed.path.lstrip('/')
            
            if settings.use_mock_data:
                # Mock 데이터 사용
                for kb_code, kb_info in MOCK_KB_DOMAINS.items():
                    s3_path = kb_info["s3_path"]
                    if path.startswith(s3_path):
                        return kb_code
            else:
                # 데이터베이스에서 조회
                pool = await get_pool()
                async with pool.acquire() as conn:
                    rows = await conn.fetch("SELECT code, s3_path FROM kb_domains ORDER BY code")
                    
                    for row in rows:
                        s3_path = row['s3_path']
                        if path.startswith(s3_path):
                            return row['code']
            
            return None
        except Exception:
            return None
    
    async def _filter_retrieval_results(
        self,
        retrieval_results: List[Dict[str, Any]],
        allowed_s3_paths: List[str]
    ) -> Dict[str, Any]:
        """
        검색 결과를 필터링하고 권한 체크
        
        Args:
            retrieval_results: 검색 결과 리스트
            allowed_s3_paths: 허용된 S3 경로 목록
        
        Returns:
            {
                "allowed": [...],  # 권한 있는 결과
                "blocked": [...],  # 권한 없는 결과
                "blocked_domains": ["QLT_SPEC", "QLT_LAW"],  # 차단된 Domain 목록
                "has_permission_violation": True/False
            }
        """
        allowed_results = []
        blocked_results = []
        blocked_domains = set()
        
        for result in retrieval_results:
            # S3 URI 추출
            s3_uri = None
            location = result.get("location", {})
            if "s3Location" in location:
                s3_uri = location["s3Location"].get("uri")
            
            if not s3_uri:
                # URI가 없으면 허용 (기본적으로 허용)
                allowed_results.append(result)
                continue
            
            # KB Domain 추출
            kb_domain = await self._extract_kb_domain_from_s3_uri(s3_uri)
            
            if kb_domain:
                # KB Domain의 s3_path 조회
                kb_s3_path = None
                if settings.use_mock_data:
                    if kb_domain in MOCK_KB_DOMAINS:
                        kb_s3_path = MOCK_KB_DOMAINS[kb_domain]["s3_path"]
                else:
                    # 데이터베이스에서 조회
                    pool = await get_pool()
                    async with pool.acquire() as conn:
                        kb_row = await conn.fetchrow(
                            "SELECT s3_path FROM kb_domains WHERE code = $1",
                            kb_domain
                        )
                        if kb_row:
                            kb_s3_path = kb_row['s3_path']
                
                # 허용된 경로인지 확인
                if kb_s3_path and kb_s3_path in allowed_s3_paths:
                    allowed_results.append(result)
                else:
                    blocked_results.append(result)
                    blocked_domains.add(kb_domain)
            else:
                # KB Domain을 추출할 수 없으면 경로 기반으로 확인
                path_match = any(s3_uri.endswith(path) or path in s3_uri for path in allowed_s3_paths)
                if path_match:
                    allowed_results.append(result)
                else:
                    blocked_results.append(result)
        
        return {
            "allowed": allowed_results,
            "blocked": blocked_results,
            "blocked_domains": list(blocked_domains),
            "has_permission_violation": len(blocked_results) > 0
        }
    
    async def _generate_permission_message(
        self,
        blocked_domains: List[str],
        group_code: Optional[str]
    ) -> str:
        """
        권한 제한 안내 메시지 생성
        
        Args:
            blocked_domains: 차단된 KB Domain 코드 목록
            group_code: Group Code
        
        Returns:
            권한 제한 안내 메시지
        """
        if not blocked_domains:
            return ""
        
        # 차단된 Domain 이름 수집
        blocked_names = []
        if settings.use_mock_data:
            for domain_code in blocked_domains:
                if domain_code in MOCK_KB_DOMAINS:
                    blocked_names.append(MOCK_KB_DOMAINS[domain_code]["name"])
        else:
            # 데이터베이스에서 조회
            if blocked_domains:
                pool = await get_pool()
                async with pool.acquire() as conn:
                    placeholders = ','.join([f'${i+1}' for i in range(len(blocked_domains))])
                    query = f"SELECT code, name FROM kb_domains WHERE code IN ({placeholders})"
                    rows = await conn.fetch(query, *blocked_domains)
                    blocked_names = [row['name'] for row in rows]
        
        # Group Code 정보
        group_info = ""
        if group_code:
            if settings.use_mock_data:
                if group_code in MOCK_GROUP_CODES:
                    kb_domains_str = MOCK_GROUP_CODES[group_code].get("kb_domains", "")
                    if isinstance(kb_domains_str, str):
                        allowed_domains = [d.strip() for d in kb_domains_str.split(",") if d.strip()]
                    else:
                        allowed_domains = kb_domains_str if isinstance(kb_domains_str, list) else []
                    allowed_names = [MOCK_KB_DOMAINS[d]["name"] for d in allowed_domains if d in MOCK_KB_DOMAINS]
                    group_info = f"\n\n현재 계정({group_code})은 다음 영역에만 접근 가능합니다:\n"
                    group_info += "\n".join([f"- {name}" for name in allowed_names])
            else:
                # 데이터베이스에서 조회
                pool = await get_pool()
                async with pool.acquire() as conn:
                    group_row = await conn.fetchrow(
                        "SELECT kb_domains FROM group_codes WHERE code = $1",
                        group_code
                    )
                    if group_row:
                        kb_domains_str = group_row['kb_domains']
                        allowed_domains = [d.strip() for d in kb_domains_str.split(",") if d.strip()] if kb_domains_str else []
                        
                        if allowed_domains:
                            placeholders = ','.join([f'${i+1}' for i in range(len(allowed_domains))])
                            query = f"SELECT name FROM kb_domains WHERE code IN ({placeholders})"
                            rows = await conn.fetch(query, *allowed_domains)
                            allowed_names = [row['name'] for row in rows]
                            group_info = f"\n\n현재 계정({group_code})은 다음 영역에만 접근 가능합니다:\n"
                            group_info += "\n".join([f"- {name}" for name in allowed_names])
        
        message = f"\n\n⚠️ 참고: 문의하신 내용 중 일부는 접근 권한이 필요한 영역입니다.\n"
        message += f"다음 영역의 정보는 현재 계정으로 접근할 수 없습니다:\n"
        message += "\n".join([f"- {name}" for name in blocked_names])
        message += group_info
        message += "\n\n해당 정보에 대한 접근이 필요하시면 관리자에게 권한 요청을 문의해주세요."
        
        return message
    
    def _enhance_query_with_prompt(self, query: str, user_name: Optional[str] = None, department: Optional[str] = None) -> str:
        """
        사용자 쿼리에 최소한의 프롬프트 지시사항을 추가하여 답변 형식을 유도
        
        Args:
            query: 원본 사용자 쿼리
            user_name: 사용자 이름
            department: 부서명
        
        Returns:
            프롬프트가 포함된 향상된 쿼리
        """
        user_prefix = f"{user_name}님" if user_name else "사용자"
        
        # 출처 형식을 명확히 지시 + 예시 포함 (간결하게 유지)
        prompt_instructions = f"""{user_prefix} 질문: {query}

답변 규칙:
1. {user_prefix}으로 시작
2. 출처는 다음 형식으로:

참고 문서:
- 「문서명」 (페이지 또는 코드)

예: 참고 문서:
- 「KS Q ISO 9000」 (27페이지)
- 「구매 규정」 (SH-P-100)

3. 자연스러운 대화체 사용"""
        
        return prompt_instructions
    
    async def _build_filtered_prompt(
        self,
        query: str,
        context: str,
        user_name: Optional[str] = None,
        department: Optional[str] = None,
        group_code: Optional[str] = None,
        permission_note: str = ""
    ) -> str:
        """
        필터링된 컨텍스트와 권한 정보를 포함한 프롬프트 생성
        
        Args:
            query: 사용자 쿼리
            context: 필터링된 컨텍스트
            user_name: 사용자 이름
            department: 부서명
            group_code: Group Code
            permission_note: 권한 제한 안내 메시지
        
        Returns:
            프롬프트 문자열
        """
        user_info = ""
        if user_name:
            user_info = f"\n사용자: {user_name}"
            if department:
                user_info += f" ({department})"
            user_info += "\n"
        
        user_name_placeholder = user_name if user_name else "[사용자명]"
        
        # Group Code 정보
        group_info = ""
        allowed_names_str = ""
        if group_code:
            if settings.use_mock_data:
                # Mock 데이터 사용
                if group_code in MOCK_GROUP_CODES:
                    kb_domains_str = MOCK_GROUP_CODES[group_code].get("kb_domains", "")
                    if isinstance(kb_domains_str, str):
                        allowed_domains = [d.strip() for d in kb_domains_str.split(",") if d.strip()]
                    else:
                        allowed_domains = kb_domains_str if isinstance(kb_domains_str, list) else []
                    allowed_names = [MOCK_KB_DOMAINS[d]["name"] for d in allowed_domains if d in MOCK_KB_DOMAINS]
                    allowed_names_str = ", ".join(allowed_names)
                    group_info = f"\n\n## 접근 권한 정보\n"
                    group_info += f"현재 계정({group_code})은 다음 영역에만 접근 가능합니다:\n"
                    group_info += "\n".join([f"- {name}" for name in allowed_names])
            else:
                # 데이터베이스에서 조회
                pool = await get_pool()
                async with pool.acquire() as conn:
                    group_row = await conn.fetchrow(
                        "SELECT kb_domains FROM group_codes WHERE code = $1",
                        group_code
                    )
                    if group_row:
                        kb_domains_str = group_row['kb_domains']
                        allowed_domains = [d.strip() for d in kb_domains_str.split(",") if d.strip()] if kb_domains_str else []
                        
                        if allowed_domains:
                            placeholders = ','.join([f'${i+1}' for i in range(len(allowed_domains))])
                            sql_query = f"SELECT name FROM kb_domains WHERE code IN ({placeholders})"
                            rows = await conn.fetch(sql_query, *allowed_domains)
                            allowed_names = [row['name'] for row in rows]
                            allowed_names_str = ", ".join(allowed_names)
                            group_info = f"\n\n## 접근 권한 정보\n"
                            group_info += f"현재 계정({group_code})은 다음 영역에만 접근 가능합니다:\n"
                            group_info += "\n".join([f"- {name}" for name in allowed_names])
        
        # 권한 검증 및 답변 규칙
        permission_validation_rules = ""
        has_group_code = False
        if group_code:
            if settings.use_mock_data:
                has_group_code = group_code in MOCK_GROUP_CODES
            else:
                pool = await get_pool()
                async with pool.acquire() as conn:
                    group_row = await conn.fetchrow(
                        "SELECT code FROM group_codes WHERE code = $1",
                        group_code
                    )
                    has_group_code = group_row is not None
        
        if permission_note or has_group_code:
            permission_validation_rules = f"""
## ⚠️ 접근 권한 검증 및 답변 규칙 (최우선 - 반드시 준수)

**1단계: 권한 경고 확인**
- 아래 "권한 제한 안내" 메시지가 있으면 → 즉시 "권한 없음 답변" 템플릿만 사용하고, 이후 단계를 생략하세요.
- 질문에 대한 실제 답변을 생성하지 마세요.

**2단계: 컨텍스트 문서 검증**
- 제공된 컨텍스트의 각 문서가 위 "접근 권한 정보"에 명시된 허용 영역에 속하는지 확인하세요.
- 문서 경로, 제목, 내용에서 다음 키워드가 보이면 허용 영역과 대조하세요:
  * "사내내규", "인사총무", "표준관리", "안전보건" → IN_HR, IN_STD, IN_SAFETY 영역
  * "품질", "시방서", "규격", "인증법규" → QLT_SPEC, QLT_LAW, QLT_STD 영역
  * "TS", "기술지원" → TS_OUT, TS_IN 영역
- 허용되지 않은 영역의 문서가 컨텍스트에 포함되어 있으면 → "권한 없음 답변" 템플릿을 사용하세요.

**3단계: 허용된 정보만 사용**
- 오직 위 "접근 권한 정보"에 명시된 영역({allowed_names_str})의 문서에서만 정보를 추출하세요.
- 다른 영역의 정보는 완전히 무시하고 답변에 포함하지 마세요.

**권한 없음 답변 템플릿 (반드시 이 형식만 사용)**:
"{user_name_placeholder}님, 죄송합니다. 문의하신 내용은 현재 계정으로 접근할 수 없는 영역입니다.
{permission_note if permission_note else '해당 정보에 대한 접근 권한이 필요합니다. 관리자에게 권한 요청을 문의해주세요.'}"

**중요**: 권한 경고가 있거나 컨텍스트에 권한 없는 문서가 포함되어 있으면, 질문에 대한 실제 답변을 생성하지 마세요. 위 템플릿만 사용하세요.
"""
        
        prompt = f"""당신은 삼화페인트 사내 임직원을 위한 지식 검색 어시스턴트입니다.
사내 문서, 규정, 기술 자료를 기반으로 업무 중 필요한 정보를 빠르고 정확하게 제공하는 것이 목적입니다.
{user_info}## 역할 및 원칙
- 사내 임직원(600-900명)의 영업 운영 지원을 위한 B2E(Business to Employee) 시스템
- 문서에 명시된 내용만 답변하며, 추측이나 개인 의견을 제시하지 않음
- 존댓말을 사용하며, "님" 호칭을 사용함 (예: 홍길동님)
- 답변은 간결하고 명확하게 (기본 3-5문장)
- 문서에 없는 내용은 "찾을 수 없음"을 명확히 표시
{group_info}
{permission_validation_rules}
## 답변 형식 (반드시 준수)

모든 답변은 다음 구조를 따라야 합니다:

1. **인사 및 사용자 호칭** (필수)
   - 반드시 "{user_name_placeholder}님," 으로 시작 (user_name이 제공된 경우)
   - user_name이 없으면 "안녕하세요," 또는 생략 가능
   - 예: "홍길동님, ..."

2. **핵심 답변** (2-3문장)
   - 질문에 대한 직접적인 답변
   - 명확하고 간결하게

3. **세부 내용** (필요시)
   - 목록이나 단계별로 구성
   - 명확한 구분 (번호, 불릿 포인트 등)

4. **출처 명시** (필수)
   - 형식: 참고 문서:
   - 각 문서를 별도 줄에 표시
   - 예: 참고 문서:
   - 「KS Q ISO 9000」 (27페이지)
   - 「구매 규정」 (SH-P-100)

5. **추가 안내** (권장)
   - 담당 부서/연락처 또는
   - 주의사항 또는
   - 다음 단계 안내

## 권한 제한 안내
{permission_note if permission_note else '(없음 - 권한 제한 없음)'}

## 표현 가이드

❌ **절대 사용 금지**:
- "검색 결과에서..."
- "확인할 수 있습니다"
- "데이터베이스에 따르면..."
- "찾을 수 있습니다"
- 기계적이고 건조한 보고서 스타일

✅ **권장 표현**:
- "{user_name_placeholder}님, ..." (user_name이 있는 경우)
- "...정보를 확인했습니다"
- "...말씀드립니다"
- "...내용은 다음과 같습니다"
- "...관련 정보입니다"

## 컨텍스트 활용
- 제공된 컨텍스트는 Knowledge Base에서 검색된 상위 관련 문서입니다
- **중요**: 위 "접근 권한 검증 및 답변 규칙"을 먼저 확인하고, 권한이 없는 경우 답변을 생성하지 마세요
- 여러 문서에서 일관된 정보 → 신뢰도 높음
- 문서 간 내용 충돌 → 최신 문서 우선 + 충돌 사실 명시
- 컨텍스트가 부족하거나 관련도가 낮으면 "찾을 수 없음"을 명확히 표시

---

<context>
{context}
</context>

사용자 질문: {query}

**답변 생성 전 확인사항**:
1. 위 "접근 권한 검증 및 답변 규칙"의 1단계부터 순서대로 확인하세요
2. 권한 경고가 있거나 컨텍스트에 권한 없는 문서가 포함되어 있으면, "권한 없음 답변 템플릿"만 사용하세요
3. 권한이 있는 경우에만 아래 형식으로 답변하세요:

**답변 형식 (권한이 있는 경우만)**:
1. "{user_name_placeholder}님," 으로 시작 (user_name이 제공된 경우, 필수)
2. 핵심 답변 2-3문장
3. 세부 정보 (필요시 목록 형태)
4. "참고 문서:" 형식으로 출처 명시 (각 문서를 별도 줄에, 허용된 영역의 문서만)
5. 추가 안내 (담당 부서, 주의사항 등)

"검색 결과에서..." 같은 기계적 표현은 절대 사용하지 마세요.
친근하지만 전문적인 어조로 답변해주세요.

답변:"""
        return prompt
    
    def _build_prompt_template(self, user_name: Optional[str] = None, department: Optional[str] = None) -> str:
        """
        사용자 정보를 포함한 프롬프트 템플릿 생성
        
        Args:
            user_name: 사용자 이름
            department: 부서명
        
        Returns:
            프롬프트 템플릿 문자열
        """
        # 사용자 정보 문자열 생성
        user_info = ""
        if user_name:
            user_info = f"\n사용자: {user_name}"
            if department:
                user_info += f" ({department})"
            user_info += "\n"
        
        # 사용자 호칭 부분 (템플릿에서 사용)
        user_name_placeholder = user_name if user_name else "[사용자명]"
        
        prompt = f"""당신은 삼화페인트 사내 임직원을 위한 지식 검색 어시스턴트입니다.
사내 문서, 규정, 기술 자료를 기반으로 업무 중 필요한 정보를 빠르고 정확하게 제공하는 것이 목적입니다.
{user_info}## 역할 및 원칙
- 사내 임직원(600-900명)의 영업 운영 지원을 위한 B2E(Business to Employee) 시스템
- 문서에 명시된 내용만 답변하며, 추측이나 개인 의견을 제시하지 않음
- 존댓말을 사용하며, "님" 호칭을 사용함 (예: 홍길동님)
- 답변은 간결하고 명확하게 (기본 3-5문장)
- 문서에 없는 내용은 "찾을 수 없음"을 명확히 표시

## 답변 형식 (반드시 준수)

모든 답변은 다음 구조를 따라야 합니다:

1. **인사 및 사용자 호칭** (필수)
   - 반드시 "{user_name_placeholder}님," 으로 시작 (user_name이 제공된 경우)
   - user_name이 없으면 "안녕하세요," 또는 생략 가능
   - 예: "홍길동님, ..."

2. **핵심 답변** (2-3문장)
   - 질문에 대한 직접적인 답변
   - 명확하고 간결하게

3. **세부 내용** (필요시)
   - 목록이나 단계별로 구성
   - 명확한 구분 (번호, 불릿 포인트 등)

4. **출처 명시** (필수)
   - 형식: 참고: 「문서명」 (코드 또는 날짜)
   - 예시: 참고: 「간판관리지침」 (SH-M-100M)
   - 예시: 참고: 「인사관리규정」 제15조 (2024.03.01)

5. **추가 안내** (권장)
   - 담당 부서/연락처 또는
   - 주의사항 또는
   - 다음 단계 안내

## 표현 가이드

❌ **절대 사용 금지**:
- "검색 결과에서..."
- "확인할 수 있습니다"
- "데이터베이스에 따르면..."
- "찾을 수 있습니다"
- 기계적이고 건조한 보고서 스타일

✅ **권장 표현**:
- "{user_name_placeholder}님, ..." (user_name이 있는 경우)
- "...정보를 확인했습니다"
- "...말씀드립니다"
- "...내용은 다음과 같습니다"
- "...관련 정보입니다"

## 톤앤매너
- 친근하지만 신뢰감 있는 어조
- 전문적이지만 이해하기 쉽게
- 임직원을 돕는 동료의 느낌
- 과도하게 격식적이지 않음

## 금지 사항
- ❌ 문서에 없는 내용 추측 ("아마도", "~것 같습니다" 등 모호한 표현 금지)
- ❌ 개인 의견 제시 ("제 생각에는...")
- ❌ 의사결정 대신 수행
- ❌ 개인정보 처리 (사번, 급여 등)
- ❌ 법률 자문 단정 ("법적으로 문제없습니다" 등)

## 컨텍스트 활용
- 제공된 컨텍스트는 Knowledge Base에서 검색된 상위 관련 문서입니다
- 여러 문서에서 일관된 정보 → 신뢰도 높음
- 문서 간 내용 충돌 → 최신 문서 우선 + 충돌 사실 명시
- 컨텍스트가 부족하거나 관련도가 낮으면 "찾을 수 없음"을 명확히 표시

## 정보를 찾을 수 없는 경우
다음 템플릿을 사용하세요:
```
죄송합니다. 해당 내용은 제가 참고할 수 있는 문서에서 찾을 수 없습니다.

다음 방법을 추천드립니다:
1. [관련 부서명] 담당자에게 문의
2. [시스템명]에서 직접 확인
3. 질문을 더 구체적으로 다시 작성해주세요
```

## 긴급/중요 사항
안전, 법규 관련 중요 사항은 ⚠️ 표시로 주의를 환기하고, 반드시 담당 부서 확인을 권장하세요.

## 답변 예시

### ❌ 나쁜 답변

"검색 결과에서 두 가지 제품 시방서를 확인할 수 있습니다. 첫 번째는..."

**문제점**: 
- 사용자 호칭 없음
- 기계적 표현 ("검색 결과에서...", "확인할 수 있습니다")
- 출처 명시 없음
- 추가 안내 없음

### ✅ 좋은 답변

"홍길동님, 간판 시방서 정보를 확인했습니다.

사내 표준으로 두 가지 유형이 관리되고 있습니다:

**1. 일반 간판 시방서**
주요 자재:
- 프레임: 알미늄 텐션 바 (백색열처리도장)
- 후렉스: LG 하이후렉스, SK 스카이후렉스 등
- 칼라시트: LG, 3M, MACTAC, GRAFITACK
- 전기: 옥외광고용 형광등, 전자식 안정기

**2. LED 입체채널 간판 시방서**
주요 자재:
- LED: 삼성전자 LME4-1.44W-W 모듈
- 전기: LS산전 누전차단기, LS전선
- 채널: 국산 알미늄(THK 1.0T)
- 도장: 삼화페인트 분체도장

참고: 「간판관리지침」 (SH-M-100M)

⚠️ 실제 시공 시에는 최신 규격을 반드시 확인하시기 바랍니다.

자세한 기술 지원: 기술지원팀 또는 품질관리팀"

**장점**: 
- 호칭 사용 ("홍길동님,")
- 친근한 톤
- 명확한 구조
- 출처 명시
- 추가 안내 포함

---

<context>
{{context}}
</context>

사용자 질문: {{input}}

중요: 위 정보를 바탕으로 답변할 때 반드시 다음 형식을 따르세요:

1. "{user_name_placeholder}님," 으로 시작 (user_name이 제공된 경우, 필수)
2. 핵심 답변 2-3문장
3. 세부 정보 (필요시 목록 형태)
4. "참고: 「문서명」" 형식으로 출처 명시 (필수)
5. 추가 안내 (담당 부서, 주의사항 등)

"검색 결과에서..." 같은 기계적 표현은 절대 사용하지 마세요.
친근하지만 전문적인 어조로 답변해주세요.

답변:"""
        return prompt

