from datetime import datetime
from urllib.parse import quote
import re, feedparser, requests
from backend.config import CUSTOMERS, OWN_COMPANIES

def strip_html(value: str) -> str:
    return " ".join(re.sub(r"<[^>]+>"," ",value or "").replace("&nbsp;"," ").split())

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
        response = requests.get(f"https://news.google.com/rss/search?q={quote(corp_name)}&hl=ko&gl=KR&ceid=KR:ko",headers={"User-Agent":"Mozilla/5.0 FUTURE-M-RADAR/2.0"},timeout=8)
        response.raise_for_status(); feed = feedparser.parse(response.content); result=[]
        for entry in feed.entries[:max_items]:
            title = str(entry.get("title") or "제목 없음"); source="출처 미상"
            if " - " in title: title, source = title.rsplit(" - ",1)
            published=entry.get("published_parsed"); time_value=datetime(*published[:6]).strftime("%Y-%m-%d %H:%M") if published else str(entry.get("published") or "시간 미상")
            group="자사" if corp_name in OWN_COMPANIES else "고객사" if corp_name in CUSTOMERS else "경쟁사"
            item={"title":title,"source":source,"time":time_value,"link":str(entry.get("link") or ""),"summary":strip_html(str(entry.get("summary") or "")),"corp_name":corp_name,"group_type":group}
            item["ai"]=classify(item); result.append(item)
        return result
    except Exception: return []
