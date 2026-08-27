import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from urllib.parse import quote

import feedparser
import OpenDartReader
import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
DART_API_KEY = os.getenv("DART_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "")

COMPETITORS = ["포스코홀딩스", "LG화학", "에코프로비엠", "엘앤에프", "BASF"]
CUSTOMERS = ["LG에너지솔루션", "삼성SDI", "SK온", "GM", "현대차"]
COMPANIES = COMPETITORS + CUSTOMERS
DART_COLUMNS = ["rcept_dt", "corp_name", "report_nm", "rcept_no", "url"]


def empty_dart() -> pd.DataFrame:
    return pd.DataFrame(columns=DART_COLUMNS)


def text(value, default="") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value)


def normalize_dart(raw) -> pd.DataFrame:
    if raw is None or getattr(raw, "empty", True):
        return empty_dart()
    df = raw.copy().rename(columns={
        "접수일자": "rcept_dt", "접수일": "rcept_dt", "회사명": "corp_name",
        "보고서명": "report_nm", "접수번호": "rcept_no",
    })
    for col in DART_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    for col in DART_COLUMNS:
        df[col] = df[col].map(text)
    df["url"] = df.apply(
        lambda r: r["url"] or f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={r['rcept_no']}",
        axis=1,
    )
    return df[DART_COLUMNS].drop_duplicates("rcept_no").reset_index(drop=True)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_dart_disclosures(corp_name: str, days: int = 7) -> pd.DataFrame:
    if not DART_API_KEY:
        return empty_dart()
    try:
        dart = OpenDartReader(DART_API_KEY)
        today = datetime.now().date()
        start = today - timedelta(days=max(days - 1, 0))
        df = normalize_dart(dart.list(corp_name, start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")))
        today_rows = df["rcept_dt"].str.startswith(today.strftime("%Y-%m-%d")) if not df.empty else pd.Series(dtype=bool)
        if df.empty or not today_rows.any():
            start = today - timedelta(days=6)
            df = normalize_dart(dart.list(corp_name, start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")))
        return df.sort_values("rcept_dt", ascending=False).reset_index(drop=True) if not df.empty else empty_dart()
    except Exception:
        return empty_dart()


def strip_html(value: str) -> str:
    value = text(value).replace("<br>", " ").replace("<br/>", " ").replace("&nbsp;", " ")
    while "<" in value and ">" in value:
        a, b = value.find("<"), value.find(">")
        value = value[:a] + value[b + 1:]
    return " ".join(value.split())


@st.cache_data(ttl=300, show_spinner=False)
def fetch_company_news(corp_name: str, max_items: int = 5) -> list[dict]:
    try:
        url = f"https://news.google.com/rss/search?q={quote(corp_name)}&hl=ko&gl=KR&ceid=KR:ko"
        response = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0 SAIMS/1.0"},
            timeout=6,
        )
        response.raise_for_status()
        feed = feedparser.parse(response.content)
        result = []
        for entry in feed.entries[:max_items]:
            title = text(entry.get("title"), "제목 없음")
            source = text(entry.get("source", {}).get("title") if isinstance(entry.get("source"), dict) else "출처 미상", "출처 미상")
            if " - " in title:
                title, source_from_title = title.rsplit(" - ", 1)
                source = source or source_from_title
            p = entry.get("published_parsed")
            time_value = datetime(*p[:6]).strftime("%Y-%m-%d %H:%M") if p else text(entry.get("published"), "시간 미상")
            result.append({"title": title, "source": source, "time": time_value, "link": text(entry.get("link")), "summary": strip_html(entry.get("summary", "")), "corp_name": corp_name, "group_type": "고객사" if corp_name in CUSTOMERS else "경쟁사"})
        return result
    except Exception:
        return []


def default_ai() -> dict:
    return {"summary_points": ["AI 분석 결과가 없습니다.", "원문을 확인해 주세요.", "추가 검토가 필요합니다."], "sentiment": "중립", "priority": "LOW", "strategic_implication": "원문 확인 후 경영진 검토 안건으로 판단해 주세요."}


def validate_ai(result) -> dict:
    base = default_ai()
    if not isinstance(result, dict):
        return base
    points = result.get("summary_points", [])
    points = [text(x) for x in points] if isinstance(points, list) else []
    sentiment = text(result.get("sentiment"), "중립")
    priority = text(result.get("priority"), "LOW").upper()
    return {"summary_points": (points + base["summary_points"])[:3], "sentiment": sentiment if sentiment in ["기회", "주의", "중립"] else "중립", "priority": priority if priority in ["HIGH", "MID", "LOW"] else "LOW", "strategic_implication": text(result.get("strategic_implication"), base["strategic_implication"])}


def analyze_content_with_llm(title: str, text_value: str, group_type: str = "경쟁사") -> dict:
    if not OPENAI_API_KEY:
        return default_ai()
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        response = client.chat.completions.create(
            model="gpt-4o", temperature=0.2, response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": "당신은 배터리/소재 산업 전문 경영전략 수석 애널리스트입니다."},
                {"role": "user", "content": f'''{group_type} 관련 공시/뉴스를 분석하세요. 경쟁사 CAPEX 증설·특허는 주의, 고객사 신규 수주·공급망 재편은 기회로 우선 분류하세요. 제목: {title}\n본문: {text_value}\n반드시 JSON만 반환: {{"summary_points":["핵심 사실 1","핵심 사실 2","핵심 사실 3"],"sentiment":"기회|주의|중립","priority":"HIGH|MID|LOW","strategic_implication":"경영진을 위한 한 줄 전략 제언"}}'''}
            ],
        )
        return validate_ai(json.loads(response.choices[0].message.content))
    except Exception:
        return default_ai()


def send_teams_alert(title: str, corp_name: str, ai_result: dict, source_url: str) -> bool:
    if not TEAMS_WEBHOOK_URL:
        return False
    try:
        r = validate_ai(ai_result)
        sentiment = r["sentiment"]
        header = {"주의": "🚨 주의", "기회": "💡 기회", "중립": "🟡 중립"}[sentiment]
        summary = "\n".join(f"• {x}" for x in r["summary_points"])
        content = {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.4", "body": [{"type": "TextBlock", "text": f"{header} | SAIMS 경영기획 인텔리전스", "weight": "Bolder", "size": "Large", "wrap": True}, {"type": "TextBlock", "text": title, "weight": "Bolder", "wrap": True}, {"type": "FactSet", "facts": [{"title": "기업명", "value": corp_name}, {"title": "우선순위", "value": r["priority"]}, {"title": "감지시각", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S")} ]}, {"type": "TextBlock", "text": "AI 3줄 요약", "weight": "Bolder"}, {"type": "TextBlock", "text": summary, "wrap": True}, {"type": "TextBlock", "text": "전략 시사점", "weight": "Bolder"}, {"type": "TextBlock", "text": r["strategic_implication"], "wrap": True}], "actions": [{"type": "Action.OpenUrl", "title": "📄 원문 바로가기", "url": source_url}] if source_url else []}}]}
        response = requests.post(TEAMS_WEBHOOK_URL, headers={"Content-Type": "application/json"}, json=content, timeout=15)
        response.raise_for_status()
        return True
    except Exception:
        return False


def badge(sentiment: str) -> str:
    return {"주의": "🔴 주의", "기회": "🟢 기회", "중립": "🟡 중립"}.get(sentiment, "🟡 중립")


def render_ai(result: dict):
    result = validate_ai(result)
    st.markdown(f"**{badge(result['sentiment'])} · {result['priority']}**")
    for point in result["summary_points"]:
        st.markdown(f"- {point}")
    st.info(f"전략 시사점: {result['strategic_implication']}")


st.set_page_config(page_title="SAIMS 경영기획 인텔리전스", page_icon="🔋", layout="wide")
for key, default in {"dart": empty_dart(), "news": [], "ai": {}, "selected": None, "updated": None}.items():
    if key not in st.session_state:
        st.session_state[key] = default

st.sidebar.title("🔋 SAIMS")
companies = st.sidebar.multiselect("모니터링 풀", COMPANIES, default=COMPANIES)
sentiment_filter = st.sidebar.selectbox("감성 필터", ["전체", "🔴 주의", "🟢 기회", "🟡 중립"])
if st.sidebar.button("🔄 실시간 데이터 갱신", type="primary", use_container_width=True):
    st.cache_data.clear()
    st.session_state.dart = empty_dart()
    st.session_state.news = []
    st.session_state.ai = {}
    st.session_state.selected = None
    st.session_state.updated = None
    st.rerun()

if st.session_state.updated is None and companies:
    with st.spinner("공시와 뉴스를 수집하는 중입니다..."):
        dart_frames = []
        collected_news = []
        with ThreadPoolExecutor(max_workers=min(8, len(companies) * 2)) as executor:
            dart_jobs = {executor.submit(fetch_dart_disclosures, c): c for c in companies}
            news_jobs = {executor.submit(fetch_company_news, c): c for c in companies}
            for job in as_completed([*dart_jobs, *news_jobs]):
                try:
                    value = job.result()
                    if isinstance(value, pd.DataFrame):
                        dart_frames.append(value)
                    elif isinstance(value, list):
                        collected_news.extend(value)
                except Exception:
                    continue
        dart_frames = [x for x in dart_frames if not x.empty]
        st.session_state.dart = pd.concat(dart_frames, ignore_index=True).drop_duplicates("rcept_no") if dart_frames else empty_dart()
        st.session_state.news = collected_news
        st.session_state.updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

news_items = []
for item in st.session_state.news:
    key = f"news::{item['link'] or item['title']}"
    if key not in st.session_state.ai:
        st.session_state.ai[key] = analyze_content_with_llm(item["title"], item["summary"], item["group_type"])
    item = dict(item, key=key, ai=validate_ai(st.session_state.ai[key]))
    if sentiment_filter == "전체" or item["ai"]["sentiment"] == {"🔴 주의": "주의", "🟢 기회": "기회", "🟡 중립": "중립"}.get(sentiment_filter):
        news_items.append(item)

st.title("🔋 SAIMS 경영기획 인텔리전스")
today = datetime.now().strftime("%Y-%m-%d")
today_count = int(st.session_state.dart["rcept_dt"].str.startswith(today).sum()) if not st.session_state.dart.empty else 0
high_count = sum(x["ai"]["priority"] == "HIGH" or x["ai"]["sentiment"] == "주의" for x in news_items)
opportunity_count = sum(x["ai"]["sentiment"] == "기회" for x in news_items)
k1, k2, k3 = st.columns(3)
k1.metric("오늘 수집 공시", today_count)
k2.metric("긴급 주의(High Risk)", high_count)
k3.metric("수주 기회(Opportunity)", opportunity_count)

left, right = st.columns(2)
with left:
    st.subheader("📋 실시간 DART 전자공시")
    if st.session_state.dart.empty:
        st.info("조회된 공시가 없습니다.")
    else:
        display = st.session_state.dart.rename(columns={"rcept_dt": "접수일자", "corp_name": "기업명", "report_nm": "보고서명", "rcept_no": "접수번호"})
        st.dataframe(display[["접수일자", "기업명", "보고서명", "접수번호"]], use_container_width=True, hide_index=True, height=300)
        idx = st.selectbox("상세 분석 대상 선택", range(len(st.session_state.dart)), format_func=lambda i: f"{st.session_state.dart.iloc[i]['corp_name']} | {st.session_state.dart.iloc[i]['report_nm']}")
        row = st.session_state.dart.iloc[idx]
        dart_key = f"dart::{row['rcept_no']}"
        if st.button("🧠 선택 공시 AI 분석", use_container_width=True):
            st.session_state.ai[dart_key] = analyze_content_with_llm(row["report_nm"], f"기업명: {row['corp_name']}\n접수일자: {row['rcept_dt']}\n접수번호: {row['rcept_no']}", "고객사" if row["corp_name"] in CUSTOMERS else "경쟁사")
            st.session_state.selected = dart_key
        if dart_key in st.session_state.ai:
            render_ai(st.session_state.ai[dart_key])
            st.link_button("📄 DART 원문 열기", row["url"], use_container_width=True)

with right:
    st.subheader("📰 실시간 기업 뉴스 피드")
    if not news_items:
        st.info("조건에 맞는 뉴스가 없습니다.")
    for i, item in enumerate(news_items):
        with st.container(border=True):
            st.markdown(f"**{badge(item['ai']['sentiment'])} {item['corp_name']}**")
            st.markdown(f"**{item['title']}**")
            st.caption(f"{item['source']} · {item['time']}")
            a, b = st.columns(2)
            if a.button("AI 분석 보기", key=f"news_{i}", use_container_width=True):
                st.session_state.selected = item["key"]
            if item["link"]:
                b.link_button("원문", item["link"], use_container_width=True)

st.divider()
st.subheader("🧠 AI 심층 브리핑 & 액션")
selected = st.session_state.selected
selected_item = next((x for x in news_items if x["key"] == selected), None)
if selected_item:
    selected_title, selected_company, selected_url, selected_result = selected_item["title"], selected_item["corp_name"], selected_item["link"], selected_item["ai"]
elif selected and selected.startswith("dart::"):
    receipt = selected[6:]
    matches = st.session_state.dart[st.session_state.dart["rcept_no"] == receipt]
    if not matches.empty:
        row = matches.iloc[0]
        selected_title, selected_company, selected_url, selected_result = row["report_nm"], row["corp_name"], row["url"], st.session_state.ai[selected]
else:
    selected_title = selected_company = selected_url = ""
    selected_result = None

if selected_result:
    st.markdown(f"#### {selected_company} | {selected_title}")
    render_ai(selected_result)
    if st.button("🚀 MS Teams 채널로 브리핑 발송", type="primary", use_container_width=True):
        if send_teams_alert(selected_title, selected_company, selected_result, selected_url):
            st.success("MS Teams 채널로 브리핑을 발송했습니다.")
        else:
            st.error("발송 실패: TEAMS_WEBHOOK_URL 또는 웹훅 권한을 확인하세요.")
else:
    st.info("공시를 분석하거나 뉴스의 'AI 분석 보기'를 선택하세요.")

st.caption(f"최근 갱신: {st.session_state.updated or '미수집'}")
