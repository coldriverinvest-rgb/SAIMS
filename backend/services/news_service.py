import logging
from datetime import datetime
from urllib.parse import quote
import re, feedparser, requests
from backend.config import CUSTOMERS, OWN_COMPANIES

logger = logging.getLogger(__name__)

BATTERY_NEWS_TERMS = (
    "이차전지", "2차전지", "배터리", "양극재", "음극재", "전해질", "분리막",
    "리튬", "니켈", "코발트", "전고체", "lfp", "ncm", "ess", "전기차",
    "battery", "cathode", "anode",
)

# 조사·접속어와 회사명은 기사 군집화에 도움이 되지 않아 제거합니다.
NEWS_STOPWORDS = {
    "관련", "시장", "전략", "강화", "통해", "위한", "대한", "이번", "이후", "확대", "추진",
    "진출", "공략", "선정", "전망", "주목", "가능", "배터리", "소재", "기업", "업계",
    "로", "은", "는", "이", "가", "과", "와", "의", "및", "에", "도", "더",
}
THEME_KEYWORDS = (
    "휴머노이드", "로봇", "전고체", "하이니켈", "미드니켈", "양극재", "음극재",
    "리튬인산철", "lfp", "실리콘", "ess", "전기차", "유상증자", "시설투자", "증설",
)

def strip_html(value: str) -> str:
    return " ".join(re.sub(r"<[^>]+>"," ",value or "").replace("&nbsp;"," ").split())

def _topic_words(title: str, corp_name: str) -> set[str]:
    normalized = re.sub(r"[^0-9a-zA-Z가-힣]+", " ", (title or "").lower())
    company = re.sub(r"[^0-9a-zA-Z가-힣]", "", (corp_name or "").lower())
    words = set()
    for word in normalized.split():
        compact = re.sub(r"[^0-9a-zA-Z가-힣]", "", word)
        if len(compact) < 2 or compact in NEWS_STOPWORDS or compact == company:
            continue
        words.add(compact)
    return words

def _theme_words(title: str) -> set[str]:
    normalized = (title or "").lower().replace(" ", "")
    return {keyword for keyword in THEME_KEYWORDS if keyword in normalized}

def deduplicate_news(items: list[dict]) -> list[dict]:
    """Keep one representative for syndicated/rewritten coverage of the same event."""
    kept: list[dict] = []
    fingerprints: list[tuple[set[str], set[str]]] = []
    for item in items:
        words = _topic_words(item.get("title", ""), item.get("corp_name", ""))
        themes = _theme_words(item.get("title", ""))
        duplicate = False
        for existing, (existing_words, existing_themes) in zip(kept, fingerprints):
            if existing.get("corp_name") != item.get("corp_name"):
                continue
            overlap = len(words & existing_words)
            similarity = overlap / max(len(words | existing_words), 1)
            # Core topic keywords 3개 이상이 겹치거나, 제목 단어의 절반 이상이 겹치면 동일 이슈로 판단합니다.
            if len(themes & existing_themes) >= 2 or (overlap >= 3 and (similarity >= 0.38 or overlap >= min(len(words), len(existing_words)))):
                duplicate = True
                break
        if not duplicate:
            kept.append(item)
            fingerprints.append((words, themes))
    return kept

def classify(item: dict) -> dict:
    content = f"{item.get('title','')} {item.get('summary','')}".lower()
    rules = [
        ("호재/수주", "opportunity", "기회", ["수주", "공급계약", "협력", "공급망", "신규 공급", "파트너십"]),
        ("증설/투자", "investment", "중립", ["증설", "capex", "시설투자", "투자", "양산"]),
        ("경쟁/리스크", "risk", "주의", ["점유율", "경쟁", "하향", "적자", "감축", "매각", "리콜"]),
        ("기술/특허", "technology", "중립", ["특허", "기술", "전고체", "lpf", "lFP", "공정"]),
    ]
    label, tag_type, sentiment = "시장/일반", "neutral", "중립"
    for candidate_label, candidate_type, candidate_sentiment, words in rules:
        if any(word.lower() in content for word in words):
            label, tag_type, sentiment = candidate_label, candidate_type, candidate_sentiment
            break
    implications = {
        "opportunity": "고객사의 수주 확대가 양극재·음극재 수요로 연결되는 시점과 규모를 확인해야 합니다.",
        "investment": "경쟁사 CAPEX와 가동 시점을 자사 증설·판매 계획과 비교해 공급 과잉 및 점유율 영향을 점검해야 합니다.",
        "risk": "가격·점유율·수익성 압력을 경쟁 대응 시나리오와 고객 협상 전략에 반영해야 합니다.",
        "technology": "특허·기술 로드맵 변화가 차세대 소재 개발 우선순위와 고객 인증 일정에 미치는 영향을 검토해야 합니다.",
        "neutral": "시장 변화가 고객 수요와 배터리 소재 사업에 미치는 구체적 영향을 추가 확인해야 합니다.",
    }
    value_chain_implication = implications[tag_type]
    return {
        "summary_points": [
            f"핵심 신호: {item['title']}",
            f"밸류체인 시사점: {value_chain_implication}",
            "자사 대응: 관련 고객·경쟁사 후속 동향을 추적하고 포스코퓨처엠의 영업·투자·기술 계획 반영 여부를 검토해야 합니다.",
        ],
        "sentiment": sentiment,
        "priority": "MID" if sentiment != "중립" else "LOW",
        "strategic_implication": value_chain_implication,
        "strategy_tag": label,
        "strategy_type": tag_type,
    }

def fetch_news(corp_name: str, max_items: int = 5) -> list[dict]:
    try:
        battery_query = f'{corp_name} (이차전지 OR 배터리 OR 양극재 OR 음극재 OR 전고체 OR LFP OR ESS OR 전기차)'
        response = requests.get(f"https://news.google.com/rss/search?q={quote(battery_query)}&hl=ko&gl=KR&ceid=KR:ko",headers={"User-Agent":"Mozilla/5.0 FUTURE-M-RADAR/2.0"},timeout=8)
        response.raise_for_status(); feed = feedparser.parse(response.content); result=[]
        for entry in feed.entries[:max(max_items * 6, 30)]:
            title = str(entry.get("title") or "제목 없음"); source="출처 미상"
            if " - " in title: title, source = title.rsplit(" - ",1)
            summary = strip_html(str(entry.get("summary") or ""))
            if not any(term in f"{title} {summary}".lower() for term in BATTERY_NEWS_TERMS):
                continue
            published=entry.get("published_parsed"); time_value=datetime(*published[:6]).strftime("%Y-%m-%d %H:%M") if published else str(entry.get("published") or "시간 미상")
            group="자사" if corp_name in OWN_COMPANIES else "고객사" if corp_name in CUSTOMERS else "경쟁사"
            item={"title":title,"source":source,"time":time_value,"link":str(entry.get("link") or ""),"summary":summary,"corp_name":corp_name,"group_type":group}
            item["ai"]=classify(item); result.append(item)
            if len(result) >= max_items:
                break
        return deduplicate_news(result)[:max_items]
    except Exception:
        logger.warning("뉴스 수집 실패: %s", corp_name, exc_info=True)
        return []
