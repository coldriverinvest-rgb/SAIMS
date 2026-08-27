import json
import os
import html
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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
TEAMS_WEBHOOK_URL = os.getenv("TEAMS_WEBHOOK_URL", "")

OWN_COMPANIES = ["포스코퓨처엠"]
COMPETITORS = ["포스코홀딩스", "LG화학", "에코프로비엠", "엘앤에프"]
CUSTOMERS = ["LG에너지솔루션", "삼성SDI", "SK온", "현대차"]
COMPANIES = OWN_COMPANIES + COMPETITORS + CUSTOMERS
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
def fetch_dart_disclosures(
    corp_name: str,
    days: int = 7,
    api_key: str = "",
) -> pd.DataFrame:
    resolved_key = api_key or DART_API_KEY
    if not resolved_key:
        return empty_dart()
    try:
        dart = OpenDartReader(resolved_key)
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
            headers={"User-Agent": "Mozilla/5.0 FUTURE-M-RADAR/1.0"},
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
            group_type = "자사" if corp_name in OWN_COMPANIES else ("고객사" if corp_name in CUSTOMERS else "경쟁사")
            result.append({"title": title, "source": source, "time": time_value, "link": text(entry.get("link")), "summary": strip_html(entry.get("summary", "")), "corp_name": corp_name, "group_type": group_type})
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
    system_prompt = "당신은 배터리/소재 산업 전문 경영전략 수석 애널리스트입니다."
    user_prompt = f'''{group_type} 관련 공시/뉴스를 분석하세요.
경쟁사 CAPEX 증설·특허는 주의, 고객사 신규 수주·공급망 재편은 기회로 우선 분류하세요.
제목: {title}
본문: {text_value}
반드시 JSON만 반환하세요:
{{"summary_points":["핵심 사실 1","핵심 사실 2","핵심 사실 3"],"sentiment":"기회|주의|중립","priority":"HIGH|MID|LOW","strategic_implication":"경영진을 위한 한 줄 전략 제언"}}'''

    if GEMINI_API_KEY:
        try:
            schema = {
                "type": "OBJECT",
                "properties": {
                    "summary_points": {
                        "type": "ARRAY",
                        "items": {"type": "STRING"},
                        "minItems": 3,
                        "maxItems": 3,
                    },
                    "sentiment": {
                        "type": "STRING",
                        "enum": ["기회", "주의", "중립"],
                    },
                    "priority": {
                        "type": "STRING",
                        "enum": ["HIGH", "MID", "LOW"],
                    },
                    "strategic_implication": {"type": "STRING"},
                },
                "required": [
                    "summary_points",
                    "sentiment",
                    "priority",
                    "strategic_implication",
                ],
            }
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": GEMINI_API_KEY,
                },
                json={
                    "systemInstruction": {"parts": [{"text": system_prompt}]},
                    "contents": [{"parts": [{"text": user_prompt}]}],
                    "generationConfig": {
                        "temperature": 0.2,
                        "responseMimeType": "application/json",
                        "responseSchema": schema,
                    },
                },
                timeout=30,
            )
            response.raise_for_status()
            response_text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
            return validate_ai(json.loads(response_text))
        except Exception:
            pass

    if OPENAI_API_KEY:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            response = client.chat.completions.create(
                model="gpt-4o",
                temperature=0.2,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return validate_ai(json.loads(response.choices[0].message.content))
        except Exception:
            pass

    return default_ai()


def send_teams_alert(title: str, corp_name: str, ai_result: dict, source_url: str) -> bool:
    if not TEAMS_WEBHOOK_URL:
        return False
    try:
        r = validate_ai(ai_result)
        sentiment = r["sentiment"]
        header = {"주의": "🚨 주의", "기회": "💡 기회", "중립": "🟡 중립"}[sentiment]
        summary = "\n".join(f"• {x}" for x in r["summary_points"])
        content = {"type": "message", "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": {"$schema": "http://adaptivecards.io/schemas/adaptive-card.json", "type": "AdaptiveCard", "version": "1.4", "body": [{"type": "TextBlock", "text": f"{header} | FUTURE:M RADAR", "weight": "Bolder", "size": "Large", "wrap": True}, {"type": "TextBlock", "text": title, "weight": "Bolder", "wrap": True}, {"type": "FactSet", "facts": [{"title": "기업명", "value": corp_name}, {"title": "우선순위", "value": r["priority"]}, {"title": "감지시각", "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S")} ]}, {"type": "TextBlock", "text": "AI 3줄 요약", "weight": "Bolder"}, {"type": "TextBlock", "text": summary, "wrap": True}, {"type": "TextBlock", "text": "전략 시사점", "weight": "Bolder"}, {"type": "TextBlock", "text": r["strategic_implication"], "wrap": True}], "actions": [{"type": "Action.OpenUrl", "title": "📄 원문 바로가기", "url": source_url}] if source_url else []}}]}
        response = requests.post(TEAMS_WEBHOOK_URL, headers={"Content-Type": "application/json"}, json=content, timeout=15)
        response.raise_for_status()
        return True
    except Exception:
        return False


def badge(sentiment: str) -> str:
    return {"주의": "🔴 주의", "기회": "🟢 기회", "중립": "🟡 중립"}.get(sentiment, "🟡 중립")


def render_dart_link_table(dart_df: pd.DataFrame) -> None:
    rows = []
    for _, disclosure in dart_df.iterrows():
        receipt_date = html.escape(text(disclosure.get("rcept_dt")))
        company = html.escape(text(disclosure.get("corp_name")))
        report_name = html.escape(text(disclosure.get("report_nm")))
        source_url = html.escape(text(disclosure.get("url")), quote=True)
        report_cell = (
            f'<a href="{source_url}" target="_blank" rel="noopener noreferrer" '
            f'title="DART 원문 열기">{report_name}</a>'
            if source_url
            else report_name
        )
        rows.append(
            f"<tr><td>{receipt_date}</td><td>{company}</td><td>{report_cell}</td></tr>"
        )
    st.markdown(
        '<div class="dart-table-wrap"><table class="dart-table">'
        '<thead><tr><th>접수일</th><th>기업</th><th>보고서</th></tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table></div>',
        unsafe_allow_html=True,
    )


def quick_classify_news(item: dict) -> dict:
    content = f"{item.get('title', '')} {item.get('summary', '')}".lower()
    caution_words = ["증설", "capex", "특허", "점유율", "경쟁", "하향", "적자", "감축", "매각"]
    opportunity_words = ["수주", "공급계약", "협력", "공급망", "신규 공급", "파트너십", "양산"]
    if any(word in content for word in caution_words):
        sentiment, priority = "주의", "MID"
    elif any(word in content for word in opportunity_words):
        sentiment, priority = "기회", "MID"
    else:
        sentiment, priority = "중립", "LOW"
    return {
        "summary_points": [
            item.get("title", "뉴스 제목 확인 필요"),
            f"출처: {item.get('source', '출처 미상')}",
            "브리핑을 선택하면 Gemini가 심층 분석합니다.",
        ],
        "sentiment": sentiment,
        "priority": priority,
        "strategic_implication": "Gemini 심층 분석 대기 중입니다.",
    }


def render_ai(result: dict):
    result = validate_ai(result)
    st.markdown(f"**{badge(result['sentiment'])} · {result['priority']}**")
    for point in result["summary_points"]:
        st.markdown(f"- {point}")
    st.info(f"전략 시사점: {result['strategic_implication']}")


st.set_page_config(
    page_title="FUTURE:M RADAR",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: #f3f6fb; color: #172033; }
    .block-container { max-width: 100%; padding: .65rem 1.1rem .35rem; }
    [data-testid="stSidebar"] { background: #101d38; }
    [data-testid="stSidebar"] * { color: #f5f8ff; }
    [data-testid="stSidebar"] .stButton button { border: 0; background: #2f6bff; }
    [data-testid="stMetric"] {
        background: #fff; border: 1px solid #dfe6f1; border-radius: 12px;
        padding: .55rem .8rem; box-shadow: 0 2px 8px rgba(20,38,70,.05);
    }
    [data-testid="stMetricLabel"] { font-size: .78rem; color: #60708c; }
    [data-testid="stMetricValue"] { font-size: 1.65rem; color: #172033; }
    h1, h2, h3, h4 { color: #172033; }
    h3 { font-size: 1rem !important; margin: .15rem 0 .35rem !important; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #fff; border-color: #dfe6f1; border-radius: 12px;
    }
    .saims-header {
        display:flex; align-items:center; justify-content:space-between;
        background:linear-gradient(110deg,#12213f,#1c3970); color:#fff;
        border-radius:14px; padding:10px 16px; margin-bottom:8px;
        box-shadow:0 5px 18px rgba(16,33,65,.16);
    }
    .saims-brand { font-size:1.18rem; font-weight:800; letter-spacing:.02em; }
    .saims-sub { color:#b9c9ea; font-size:.76rem; margin-top:2px; }
    .saims-live { font-size:.76rem; color:#dce7ff; }
    .live-dot { color:#47dc91; margin-right:5px; }
    .panel-title { font-size:.93rem; font-weight:750; color:#1a2843; }
    .brief-card {
        background:#fff; border:1px solid #dfe6f1; border-radius:12px;
        padding:10px 13px; min-height:126px;
    }
    .brief-label { color:#64748b; font-size:.72rem; font-weight:700; text-transform:uppercase; }
    .brief-title { font-size:.92rem; font-weight:750; margin:4px 0 7px; }
    .brief-point { font-size:.78rem; margin:3px 0; color:#334155; }
    .brief-strategy { background:#eef4ff; color:#234584; border-radius:8px; padding:7px 9px; font-size:.78rem; }
    .footer-note { color:#738198; font-size:.67rem; text-align:right; margin-top:3px; }
    .stDataFrame { border-radius:10px; overflow:hidden; }
    .dart-table-wrap {
        height:190px; overflow:auto; border:1px solid #e1e7f0;
        border-radius:10px; margin:.35rem 0 .55rem; background:#fff;
    }
    .dart-table { width:100%; border-collapse:collapse; font-size:.78rem; }
    .dart-table th {
        position:sticky; top:0; z-index:1; text-align:left; padding:8px 10px;
        color:#64748b; background:#f5f7fb; border-bottom:1px solid #dfe6f1;
    }
    .dart-table td { padding:8px 10px; border-bottom:1px solid #edf1f6; color:#26344d; }
    .dart-table th:nth-child(1), .dart-table td:nth-child(1) { width:88px; white-space:nowrap; }
    .dart-table th:nth-child(2), .dart-table td:nth-child(2) { width:110px; white-space:nowrap; }
    .dart-table a { color:#2159c5; text-decoration:none; font-weight:650; }
    .dart-table a:hover { color:#123f99; text-decoration:underline; }
    div.stButton > button, div.stLinkButton > a { min-height:2rem; padding:.25rem .55rem; font-size:.76rem; }
    div[data-testid="stAlert"] { padding:.55rem .7rem; font-size:.78rem; }
    hr { margin:.35rem 0 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)
for key, default in {
    "dart": empty_dart(),
    "news": [],
    "ai": {},
    "selected": None,
    "updated": None,
    "dart_api_key": DART_API_KEY,
    "monitor_signature": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

st.sidebar.title("🔋 FUTURE:M RADAR")
st.sidebar.caption("Battery & Materials Intelligence")
companies = st.sidebar.multiselect("모니터링 풀", COMPANIES, default=COMPANIES)
current_signature = tuple(companies)
if st.session_state.monitor_signature is None:
    st.session_state.monitor_signature = current_signature
elif st.session_state.monitor_signature != current_signature:
    st.session_state.monitor_signature = current_signature
    st.session_state.dart = empty_dart()
    st.session_state.news = []
    st.session_state.ai = {}
    st.session_state.selected = None
    st.session_state.updated = None
    st.rerun()
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
            dart_jobs = {
                executor.submit(
                    fetch_dart_disclosures,
                    c,
                    7,
                    st.session_state.dart_api_key,
                ): c
                for c in companies
            }
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
        st.session_state.ai[key] = quick_classify_news(item)
    item = dict(item, key=key, ai=validate_ai(st.session_state.ai[key]))
    if sentiment_filter == "전체" or item["ai"]["sentiment"] == {"🔴 주의": "주의", "🟢 기회": "기회", "🟡 중립": "중립"}.get(sentiment_filter):
        news_items.append(item)

updated_text = st.session_state.updated or "미수집"
st.markdown(
    f"""
    <div class="saims-header">
      <div>
        <div class="saims-brand">FUTURE:M RADAR</div>
        <div class="saims-sub">SECONDARY BATTERY · MATERIALS · DISCLOSURE · NEWS</div>
      </div>
      <div class="saims-live"><span class="live-dot">●</span> LIVE &nbsp;|&nbsp; {updated_text}</div>
    </div>
    """,
    unsafe_allow_html=True,
)
today = datetime.now().strftime("%Y-%m-%d")
today_count = int(st.session_state.dart["rcept_dt"].str.startswith(today).sum()) if not st.session_state.dart.empty else 0
high_count = sum(x["ai"]["priority"] == "HIGH" or x["ai"]["sentiment"] == "주의" for x in news_items)
opportunity_count = sum(x["ai"]["sentiment"] == "기회" for x in news_items)
k1, k2, k3, k4 = st.columns(4)
k1.metric("오늘 수집 공시", today_count)
k2.metric("긴급 주의(High Risk)", high_count)
k3.metric("수주 기회(Opportunity)", opportunity_count)
k4.metric("수집 뉴스", len(news_items))

left, right = st.columns([1.05, 1.35], gap="medium")
with left:
    with st.container(border=True):
        st.markdown('<div class="panel-title">📋 실시간 DART 전자공시</div>', unsafe_allow_html=True)
        if st.session_state.dart.empty:
            st.info("DART API 키를 설정하면 최근 7일 공시가 이 영역에 표시됩니다.")
            st.dataframe(
                pd.DataFrame(columns=["접수일", "기업", "보고서"]),
                use_container_width=True, hide_index=True, height=190,
            )
        else:
            render_dart_link_table(st.session_state.dart)
            idx = st.selectbox(
                "분석 대상 공시", range(len(st.session_state.dart)),
                format_func=lambda i: f"{st.session_state.dart.iloc[i]['corp_name']} | {st.session_state.dart.iloc[i]['report_nm']}",
                label_visibility="collapsed",
            )
            row = st.session_state.dart.iloc[idx]
            dart_key = f"dart::{row['rcept_no']}"
            a, b = st.columns(2)
            if a.button("🧠 AI 분석", use_container_width=True):
                st.session_state.ai[dart_key] = analyze_content_with_llm(
                    row["report_nm"],
                    f"기업명: {row['corp_name']}\n접수일자: {row['rcept_dt']}\n접수번호: {row['rcept_no']}",
                    "자사" if row["corp_name"] in OWN_COMPANIES else ("고객사" if row["corp_name"] in CUSTOMERS else "경쟁사"),
                )
                st.session_state.selected = dart_key
                st.rerun()
            b.link_button("📄 원문", row["url"], use_container_width=True)

with right:
    with st.container(border=True):
        st.markdown('<div class="panel-title">📰 실시간 기업 뉴스 피드</div>', unsafe_allow_html=True)
        with st.container(height=300, border=False):
            if not news_items:
                st.info("조건에 맞는 뉴스가 없습니다.")
            for i, item in enumerate(news_items):
                c1, c2, c3 = st.columns([1.3, 6.2, 1.25], vertical_alignment="center")
                c1.markdown(f"**{badge(item['ai']['sentiment'])}**  \n`{item['corp_name']}`")
                c2.markdown(f"**{item['title']}**  \n<small>{item['source']} · {item['time']}</small>", unsafe_allow_html=True)
                if c3.button("브리핑", key=f"news_{i}", use_container_width=True):
                    with st.spinner("Gemini가 심층 분석 중입니다..."):
                        st.session_state.ai[item["key"]] = analyze_content_with_llm(
                            item["title"],
                            item["summary"],
                            item["group_type"],
                        )
                    st.session_state.selected = item["key"]
                    st.rerun()
                st.markdown("<hr>", unsafe_allow_html=True)

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

st.markdown('<div class="panel-title">🧠 AI 심층 브리핑 & 액션</div>', unsafe_allow_html=True)
if selected_result:
    selected_result = validate_ai(selected_result)
    brief_left, brief_mid, brief_right = st.columns([2.1, 4.9, 1.35], gap="small")
    with brief_left:
        st.markdown(
            f'<div class="brief-card"><div class="brief-label">Selected intelligence</div>'
            f'<div class="brief-title">{selected_company}</div>'
            f'<div class="brief-point">{badge(selected_result["sentiment"])} · {selected_result["priority"]}</div>'
            f'<div class="brief-point">{selected_title}</div></div>',
            unsafe_allow_html=True,
        )
    with brief_mid:
        points_html = "".join(f'<div class="brief-point">• {point}</div>' for point in selected_result["summary_points"])
        st.markdown(
            f'<div class="brief-card"><div class="brief-label">AI 3-line brief</div>{points_html}'
            f'<div class="brief-strategy">전략 제언 · {selected_result["strategic_implication"]}</div></div>',
            unsafe_allow_html=True,
        )
    with brief_right:
        with st.container(border=True):
            st.caption("EXECUTIVE ACTION")
            if selected_url:
                st.link_button("📄 원문 열기", selected_url, use_container_width=True)
            if st.button("🚀 Teams 발송", type="primary", use_container_width=True):
                if send_teams_alert(selected_title, selected_company, selected_result, selected_url):
                    st.success("발송 완료")
                else:
                    st.error("웹훅 설정 필요")
else:
    st.markdown(
        '<div class="brief-card"><div class="brief-label">Executive briefing</div>'
        '<div class="brief-title">뉴스의 ‘브리핑’ 또는 공시의 ‘AI 분석’을 선택하세요.</div>'
        '<div class="brief-point">선택한 인텔리전스의 핵심 사실 3개, 리스크/기회 등급, 경영진 전략 제언이 이 영역에 표시됩니다.</div>'
        '<div class="brief-strategy">OPENAI_API_KEY가 없으면 안전한 기본 분석 결과로 표시됩니다.</div></div>',
        unsafe_allow_html=True,
    )

st.markdown(
    f'<div class="footer-note">FUTURE:M RADAR v1.0 · 모니터링 {len(companies)}개사 · 마지막 갱신 {updated_text}</div>',
    unsafe_allow_html=True,
)
