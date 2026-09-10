"""Shared OpenDartReader instance.

OpenDartReader() 생성 시 매번 회사 코드 테이블을 역직렬화하므로,
서비스마다 새로 만들지 않고 프로세스에서 한 번만 만들어 재사용합니다.
객체의 조회 메서드는 요청 기반이라 스레드 풀에서 함께 써도 안전합니다.
"""
from functools import lru_cache

import OpenDartReader

from backend.config import DART_API_KEY


@lru_cache(maxsize=1)
def get_dart() -> "OpenDartReader | None":
    if not DART_API_KEY:
        return None
    return OpenDartReader(DART_API_KEY)
