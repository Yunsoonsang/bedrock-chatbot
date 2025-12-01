"""
유틸리티 함수들 (검증, 변환 등)
"""
import re
from typing import Optional


def validate_uuid(uuid_str: str) -> bool:
    """
    UUID 형식 검증
    
    Args:
        uuid_str: 검증할 UUID 문자열
    
    Returns:
        유효한 UUID 형식이면 True
    """
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    return bool(re.match(uuid_pattern, uuid_str.lower()))


def parse_kb_domains(kb_domains_str: str) -> list[str]:
    """
    콤마 구분 문자열을 리스트로 변환
    
    Args:
        kb_domains_str: 콤마 구분 문자열 (예: "IN_HR,IN_STD,QLT_SPEC")
    
    Returns:
        KB Domain 코드 리스트
    """
    if isinstance(kb_domains_str, str):
        return [d.strip() for d in kb_domains_str.split(",") if d.strip()]
    elif isinstance(kb_domains_str, list):
        return kb_domains_str
    else:
        return []


def format_kb_domains(kb_domains_list: list[str]) -> str:
    """
    리스트를 콤마 구분 문자열로 변환
    
    Args:
        kb_domains_list: KB Domain 코드 리스트
    
    Returns:
        콤마 구분 문자열
    """
    if isinstance(kb_domains_list, list):
        return ",".join([str(d).strip() for d in kb_domains_list if d])
    elif isinstance(kb_domains_list, str):
        return kb_domains_list
    else:
        return ""


