import logging
from datetime import datetime
from urllib.parse import quote

import feedparser
import requests

from backend.services.news_service import strip_html

logger = logging.getLogger(__name__)

MATERIALS = {
    "lithium": ("리튬", ("리튬", "lithium")),
    "nickel": ("니켈", ("니켈", "nickel")),
    "cobalt": ("코발트", ("코발트", "cobalt")),
    "manganese": ("망간", ("망간", "manganese")),
}
MARKET_TERMS = (
    "광산", "채굴", "제련", "생산", "공급", "수요", "재고", "수출", "수입",
    "가격", "시세", "감산", "증산", "정광", "원광", "톤", "mining", "mine",
    "refining", "production", "supply", "demand", "inventory", "price",
)


def _classify(text: str) -> tuple[str, str]:
    lowered = text.lower()
    if any(word in lowered for word in ("차질", "규제", "금지", "감산", "급등", "부족", "리스크")):
        return "공급 리스크", "risk"
    if any(word in lowered for word in ("상승", "반등", "강세", "인상")):
        return "가격 상승", "positive"
    if any(word in lowered for word in ("하락", "약세", "과잉", "감소")):
        return "가격 하락", "neutral"
    return "수급 동향", "neutral"


def fetch_material_news(material_id: str, max_items: int = 6) -> list[dict]:
    if material_id not in MATERIALS:
        raise ValueError("지원하지 않는 원자재입니다.")
    name, aliases = MATERIALS[material_id]
    query = f'{name} (광산 OR 채굴 OR 제련 OR 생산 OR 공급 OR 재고 OR 수출 OR 가격)'
    try:
        response = requests.get(
            f"https://news.google.com/rss/search?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko",
            headers={"User-Agent": "Mozilla/5.0 FUTURE-M-RADAR/2.0"},
            timeout=8,
        )
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        items: list[dict] = []
        seen: set[str] = set()
        for entry in feed.entries[:60]:
            raw_title = str(entry.get("title") or "")
            title, source = (raw_title.rsplit(" - ", 1) if " - " in raw_title else (raw_title, "출처 미상"))
            summary = strip_html(str(entry.get("summary") or ""))
            content = f"{title} {summary}".lower()
            if not any(alias in content for alias in aliases) or not any(term in content for term in MARKET_TERMS):
                continue
            fingerprint = "".join(ch for ch in title.lower() if ch.isalnum())[:70]
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            published = entry.get("published_parsed")
            time_value = datetime(*published[:6]).strftime("%Y-%m-%d %H:%M") if published else str(entry.get("published") or "시간 미상")
            signal, tone = _classify(content)
            items.append({
                "title": title,
                "source": source,
                "time": time_value,
                "link": str(entry.get("link") or ""),
                "summary": summary,
                "signal": signal,
                "tone": tone,
            })
            if len(items) >= max_items:
                break
        return items
    except Exception:
        logger.warning("원자재 뉴스 수집 실패: %s", material_id, exc_info=True)
        return []
