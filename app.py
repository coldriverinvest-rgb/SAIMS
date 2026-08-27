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


def parse_amount(value) -> float | None:
    raw = text(value).replace(",", "").strip()
    if not raw or raw in {"-", "None", "nan"}:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def pick_account(statement: pd.DataFrame, account_ids: list[str], cumulative=False) -> tuple[float | None, float | None]:
    if statement is None or statement.empty:
        return None, None
    matched = statement[statement["account_id"].isin(account_ids)]
    if matched.empty:
        return None, None
    row = matched.iloc[0]
    current_field = "thstrm_add_amount" if cumulative and parse_amount(row.get("thstrm_add_amount")) is not None else "thstrm_amount"
    prior_field = "frmtrm_add_amount" if cumulative and parse_amount(row.get("frmtrm_add_amount")) is not None else "frmtrm_amount"
    return parse_amount(row.get(current_field)), parse_amount(row.get(prior_field))


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_customer_financials(corp_name: str, year: int, report_code: str, api_key: str = "") -> dict:
    resolved_key = api_key or DART_API_KEY
    if not resolved_key:
        return {}
    try:
        dart = OpenDartReader(resolved_key)
        statement = dart.finstate_all(corp_name, year, reprt_code=report_code, fs_div="CFS")
        if statement is None or statement.empty:
            return {}

        assets, prior_assets = pick_account(statement, ["ifrs-full_Assets", "ifrs_Assets"])
        liabilities, prior_liabilities = pick_account(statement, ["ifrs-full_Liabilities", "ifrs_Liabilities"])
        equity, prior_equity = pick_account(statement, ["ifrs-full_Equity", "ifrs_Equity"])
        current_assets, _ = pick_account(statement, ["ifrs-full_CurrentAssets", "ifrs_CurrentAssets"])
        current_liabilities, _ = pick_account(statement, ["ifrs-full_CurrentLiabilities", "ifrs_CurrentLiabilities"])
        revenue, prior_revenue = pick_account(
            statement,
            ["ifrs-full_Revenue", "ifrs_Revenue", "dart_Revenue"],
            cumulative=True,
        )
        operating_income, prior_operating_income = pick_account(
            statement,
            ["dart_OperatingIncomeLoss", "ifrs-full_ProfitLossFromOperatingActivities"],
            cumulative=True,
        )
        net_income, prior_net_income = pick_account(
            statement,
            ["ifrs-full_ProfitLoss", "ifrs_ProfitLoss"],
            cumulative=True,
        )
        receipt_no = text(statement.iloc[0].get("rcept_no"))
        return {
            "corp_name": corp_name,
            "year": year,
            "report_code": report_code,
            "receipt_no": receipt_no,
            "source_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt_no}" if receipt_no else "",
            "assets": assets,
            "liabilities": liabilities,
            "equity": equity,
            "current_assets": current_assets,
            "current_liabilities": current_liabilities,
            "revenue": revenue,
            "operating_income": operating_income,
            "net_income": net_income,
            "prior_assets": prior_assets,
            "prior_liabilities": prior_liabilities,
            "prior_equity": prior_equity,
            "prior_revenue": prior_revenue,
            "prior_operating_income": prior_operating_income,
            "prior_net_income": prior_net_income,
        }
    except Exception:
        return {}


@st.cache_data(ttl=3600, show_spinner=False)
def validate_listed_company(company_query: str, api_key: str = "") -> dict:
    resolved_key = api_key or DART_API_KEY
    query = company_query.strip()
    if not resolved_key or not query:
        return {"valid": False, "message": "기업명을 입력해 주세요."}
    try:
        dart = OpenDartReader(resolved_key)
        corp_codes = dart.corp_codes.copy()
        corp_codes["corp_name"] = corp_codes["corp_name"].fillna("").astype(str).str.strip()
        corp_codes["stock_code"] = corp_codes["stock_code"].fillna("").astype(str).str.strip()
        exact = corp_codes[
            corp_codes["corp_name"].eq(query)
            | corp_codes["stock_code"].eq(query.zfill(6) if query.isdigit() else query)
        ]
        listed = exact[exact["stock_code"].str.len().eq(6)]
        if not listed.empty:
            row = listed.iloc[0]
            return {
                "valid": True,
                "corp_name": text(row["corp_name"]),
                "stock_code": text(row["stock_code"]),
            }
        suggestions = corp_codes[
            corp_codes["corp_name"].str.contains(query, case=False, regex=False)
            & corp_codes["stock_code"].str.len().eq(6)
        ]["corp_name"].head(3).tolist()
        message = "정확한 상장기업명을 입력해 주세요."
        if suggestions:
            message += f" 검색 결과: {', '.join(suggestions)}"
        return {"valid": False, "message": message}
    except Exception:
        return {"valid": False, "message": "OpenDART에서 기업 정보를 확인하지 못했습니다."}


def safe_ratio(numerator, denominator) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator * 100


def format_krw(value) -> str:
    if value is None:
        return "N/A"
    sign = "-" if value < 0 else ""
    absolute = abs(value)
    if absolute >= 1_000_000_000_000:
        return f"{sign}{absolute / 1_000_000_000_000:,.2f}조"
    return f"{sign}{absolute / 100_000_000:,.0f}억"


def format_ratio(value) -> str:
    return "N/A" if value is None else f"{value:,.1f}%"


def growth_rate(current, prior) -> float | None:
    if current is None or prior in (None, 0):
        return None
    return (current - prior) / abs(prior) * 100


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
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] textarea {
        color: #172033 !important;
        -webkit-text-fill-color: #172033 !important;
        caret-color: #2f6bff !important;
    }
    [data-testid="stSidebar"] input::placeholder,
    [data-testid="stSidebar"] textarea::placeholder {
        color: #7b879c !important;
        -webkit-text-fill-color: #7b879c !important;
        opacity: 1 !important;
    }
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

    /* FUTURE:M RADAR — executive design system */
    :root {
        --radar-navy:#07142d; --radar-blue:#2365f5; --radar-cyan:#29c7c9;
        --radar-ink:#12203a; --radar-muted:#718096; --radar-line:#dce5f1;
        --radar-surface:rgba(255,255,255,.94);
    }
    [data-testid="stHeader"] {
        height:0 !important; min-height:0 !important; background:transparent !important;
    }
    [data-testid="stToolbar"], [data-testid="stDecoration"],
    [data-testid="stStatusWidget"], .stAppDeployButton, #MainMenu {
        display:none !important;
    }
    html, body, [class*="css"] { font-family:"Pretendard","Inter","Segoe UI",sans-serif; }
    .stApp {
        background:
            radial-gradient(circle at 84% 2%, rgba(35,101,245,.10), transparent 25rem),
            radial-gradient(circle at 12% 96%, rgba(41,199,201,.08), transparent 24rem),
            #f4f7fb;
    }
    .block-container { padding:.35rem 1.25rem .4rem; }
    [data-testid="stSidebar"] {
        background:
            radial-gradient(circle at 15% 4%, rgba(41,199,201,.16), transparent 14rem),
            linear-gradient(165deg,#0c1d3d 0%,#07142d 72%,#091a36 100%);
        border-right:1px solid rgba(128,164,220,.16);
        box-shadow:12px 0 32px rgba(7,20,45,.10);
    }
    [data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top:.7rem; }
    .side-brand { padding:.45rem .15rem .9rem; border-bottom:1px solid rgba(177,203,242,.14); margin-bottom:.8rem; }
    .side-brand-top { display:flex; align-items:center; gap:.6rem; }
    .side-logo {
        width:31px; height:31px; display:grid; place-items:center; border-radius:10px;
        color:white; font-weight:900; background:linear-gradient(145deg,#2b72ff,#29c7c9);
        box-shadow:0 8px 22px rgba(35,101,245,.38);
    }
    .side-name { color:#fff; font-size:1.02rem; font-weight:850; letter-spacing:.04em; }
    .side-sub { color:#88a1c8; font-size:.68rem; margin:5px 0 0 42px; letter-spacing:.11em; }
    [data-testid="stSidebar"] label p,
    [data-testid="stSidebar"] .stCaption p { color:#9eb1cf !important; font-weight:650; letter-spacing:.02em; }
    [data-testid="stSidebar"] [data-testid="stRadio"] > div { gap:.35rem; }
    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        padding:.42rem .5rem; border:1px solid rgba(164,190,230,.12); border-radius:9px;
        background:rgba(255,255,255,.025); transition:.18s ease;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
        background:rgba(50,111,243,.16); border-color:rgba(80,139,255,.38);
    }
    [data-testid="stSidebar"] [data-baseweb="input"] > div,
    [data-testid="stSidebar"] [data-baseweb="select"] > div {
        background:#f9fbff !important; border:1px solid rgba(255,255,255,.3) !important;
        border-radius:11px !important; box-shadow:0 5px 16px rgba(0,0,0,.12);
    }
    [data-testid="stSidebar"] [data-baseweb="tag"] {
        background:linear-gradient(135deg,#245de0,#2d76ff) !important;
        border-radius:7px !important; border:1px solid rgba(255,255,255,.12) !important;
    }
    [data-testid="stSidebar"] [data-baseweb="tag"] * { color:#fff !important; }
    [data-testid="stSidebar"] .stButton button {
        min-height:2.25rem; border-radius:10px; color:#fff !important; font-weight:750;
        background:linear-gradient(135deg,#2462e9,#3479ff); border:1px solid rgba(255,255,255,.10);
        box-shadow:0 8px 20px rgba(35,101,245,.22); transition:.18s ease;
    }
    [data-testid="stSidebar"] .stButton button:hover {
        transform:translateY(-1px); box-shadow:0 11px 25px rgba(35,101,245,.34);
    }
    .saims-header {
        min-height:78px; position:relative; overflow:hidden; padding:13px 18px; margin-bottom:10px;
        background:
            radial-gradient(circle at 78% -40%,rgba(41,199,201,.33),transparent 17rem),
            linear-gradient(112deg,#0a1833 0%,#123469 62%,#164a80 100%);
        border:1px solid rgba(135,177,239,.22); border-radius:16px;
        box-shadow:0 12px 30px rgba(12,35,75,.18);
    }
    .saims-header:after {
        content:""; position:absolute; width:180px; height:180px; right:-55px; top:-92px;
        border:1px solid rgba(255,255,255,.13); border-radius:50%; box-shadow:0 0 0 24px rgba(255,255,255,.025);
    }
    .header-eyebrow { color:#55dadd; font-size:.64rem; font-weight:800; letter-spacing:.18em; margin-bottom:2px; }
    .saims-brand { color:#fff; font-size:1.34rem; font-weight:880; letter-spacing:.035em; }
    .saims-sub { color:#9fb5d9; font-size:.7rem; letter-spacing:.055em; }
    .header-status { display:flex; align-items:center; justify-content:flex-end; gap:.4rem; position:relative; z-index:1; }
    .status-chip {
        padding:5px 8px; color:#c8d8f3; font-size:.64rem; font-weight:750; letter-spacing:.03em;
        background:rgba(255,255,255,.075); border:1px solid rgba(190,214,249,.16); border-radius:999px;
        backdrop-filter:blur(8px);
    }
    .status-chip.ok { color:#91f1cc; }
    .updated-chip { color:#9fb5d9; font-size:.66rem; margin-left:.2rem; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background:var(--radar-surface); border:1px solid var(--radar-line); border-radius:14px;
        box-shadow:0 7px 22px rgba(28,53,91,.065); backdrop-filter:blur(10px);
    }
    .panel-title { color:var(--radar-ink); font-size:.92rem; font-weight:820; letter-spacing:-.01em; }
    [data-testid="stMetric"] {
        background:linear-gradient(160deg,#fff,#f8fbff); border:1px solid var(--radar-line);
        border-radius:13px; padding:.62rem .75rem; box-shadow:0 7px 20px rgba(26,53,94,.07);
    }
    [data-testid="stMetricLabel"] p { color:#738198 !important; font-weight:700; font-size:.72rem; }
    [data-testid="stMetricValue"] { color:#142441; font-weight:820; letter-spacing:-.035em; }
    .brief-card {
        background:linear-gradient(155deg,#fff,#f8fbff); border:1px solid var(--radar-line);
        border-radius:13px; box-shadow:0 7px 20px rgba(26,53,94,.065);
    }
    .brief-label { color:#2c6dec; letter-spacing:.11em; }
    .brief-strategy { background:linear-gradient(100deg,#edf4ff,#eefcfb); color:#194d80; border:1px solid #d9e8f8; }
    .dart-table-wrap { border-color:var(--radar-line); box-shadow:inset 0 1px 0 #fff; }
    .dart-table th { background:#f1f5fb; color:#687995; font-size:.69rem; letter-spacing:.03em; }
    .dart-table tr:hover td { background:#f5f9ff; }
    .dart-table a { color:#2163df; }
    div.stButton > button, div.stLinkButton > a { border-radius:9px; font-weight:700; transition:.16s ease; }
    div.stButton > button:hover, div.stLinkButton > a:hover { transform:translateY(-1px); }
    div[data-testid="stAlert"] { border-radius:10px; border-width:1px; }
    ::-webkit-scrollbar { width:7px; height:7px; }
    ::-webkit-scrollbar-track { background:transparent; }
    ::-webkit-scrollbar-thumb { background:#b7c5d8; border-radius:999px; }
    ::-webkit-scrollbar-thumb:hover { background:#8fa3bf; }
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
    "custom_companies": [],
    "company_add_message": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

st.sidebar.markdown(
    '<div class="side-brand"><div class="side-brand-top"><div class="side-logo">M</div>'
    '<div class="side-name">FUTURE:M RADAR</div></div>'
    '<div class="side-sub">MATERIALS INTELLIGENCE</div></div>',
    unsafe_allow_html=True,
)
analysis_category = st.sidebar.radio(
    "분석 카테고리",
    ["📡 산업 인텔리전스", "📊 기업 재무분석"],
)
st.sidebar.caption("상장기업 추가")
company_to_add = st.sidebar.text_input(
    "기업명 또는 종목코드",
    placeholder="예: 롯데에너지머티리얼즈",
    label_visibility="collapsed",
)
if st.sidebar.button("＋ 모니터링 기업 추가", width="stretch"):
    validation = validate_listed_company(company_to_add, st.session_state.dart_api_key)
    if validation.get("valid"):
        canonical_name = validation["corp_name"]
        if canonical_name not in COMPANIES and canonical_name not in st.session_state.custom_companies:
            st.session_state.custom_companies.append(canonical_name)
        selected_pool = list(st.session_state.get("monitoring_pool", COMPANIES))
        if canonical_name not in selected_pool:
            selected_pool.append(canonical_name)
        st.session_state.monitoring_pool = selected_pool
        st.session_state.company_add_message = (
            "success",
            f"{canonical_name}({validation['stock_code']}) 추가 완료",
        )
        st.session_state.dart = empty_dart()
        st.session_state.news = []
        st.session_state.ai = {}
        st.session_state.selected = None
        st.session_state.updated = None
        st.rerun()
    else:
        st.session_state.company_add_message = ("error", validation["message"])
        st.rerun()

if st.session_state.company_add_message:
    message_type, message_text = st.session_state.company_add_message
    if message_type == "success":
        st.sidebar.success(message_text)
    else:
        st.sidebar.error(message_text)

company_options = list(dict.fromkeys(COMPANIES + st.session_state.custom_companies))
if "monitoring_pool" not in st.session_state:
    st.session_state.monitoring_pool = company_options
companies = st.sidebar.multiselect(
    "모니터링 풀",
    company_options,
    key="monitoring_pool",
)
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
if st.sidebar.button("🔄 실시간 데이터 갱신", type="primary", width="stretch"):
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
dart_chip = "DART CONNECTED" if st.session_state.dart_api_key else "DART OFFLINE"
gemini_chip = "GEMINI READY" if GEMINI_API_KEY else "AI OFFLINE"
st.markdown(
    f"""
    <div class="saims-header">
      <div>
        <div class="header-eyebrow">POSCO FUTURE M · EXECUTIVE INTELLIGENCE</div>
        <div class="saims-brand">FUTURE:M RADAR</div>
        <div class="saims-sub">BATTERY MATERIALS · DISCLOSURE · NEWS · FINANCIAL SIGNALS</div>
      </div>
      <div class="header-status">
        <span class="status-chip ok">● {dart_chip}</span>
        <span class="status-chip ok">● {gemini_chip}</span>
        <span class="updated-chip">{updated_text}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
if analysis_category == "📊 기업 재무분석":
    report_options = {
        "1분기보고서": "11013",
        "반기보고서": "11012",
        "3분기보고서": "11014",
        "사업보고서": "11011",
    }
    control1, control2, control3 = st.columns([1.4, 1, 1.4])
    finance_company = control1.selectbox("분석 기업", companies or company_options)
    current_year = datetime.now().year
    finance_year = control2.selectbox("사업연도", list(range(current_year, current_year - 5, -1)))
    report_label = control3.selectbox("보고서", list(report_options.keys()), index=1)
    with st.spinner("DART 연결재무제표를 불러오는 중입니다..."):
        financials = fetch_customer_financials(
            finance_company,
            finance_year,
            report_options[report_label],
            st.session_state.dart_api_key,
        )

    if not financials:
        st.warning(f"{finance_company}의 {finance_year}년 {report_label} 연결재무제표가 없습니다. 비상장사·해외기업이거나 아직 보고서가 제출되지 않았을 수 있습니다.")
    else:
        debt_ratio = safe_ratio(financials["liabilities"], financials["equity"])
        current_ratio = safe_ratio(financials["current_assets"], financials["current_liabilities"])
        equity_ratio = safe_ratio(financials["equity"], financials["assets"])
        operating_margin = safe_ratio(financials["operating_income"], financials["revenue"])
        net_margin = safe_ratio(financials["net_income"], financials["revenue"])
        roa = safe_ratio(financials["net_income"], financials["assets"])

        st.markdown(f"### {finance_company} · {finance_year} {report_label} 연결기준")
        result_cols = st.columns(5)
        result_cols[0].metric("매출액", format_krw(financials["revenue"]), format_ratio(growth_rate(financials["revenue"], financials["prior_revenue"])))
        result_cols[1].metric("영업이익", format_krw(financials["operating_income"]), format_ratio(growth_rate(financials["operating_income"], financials["prior_operating_income"])))
        result_cols[2].metric("당기순이익", format_krw(financials["net_income"]), format_ratio(growth_rate(financials["net_income"], financials["prior_net_income"])))
        result_cols[3].metric("자산총계", format_krw(financials["assets"]))
        result_cols[4].metric("부채총계", format_krw(financials["liabilities"]))

        health_col, profit_col = st.columns(2, gap="medium")
        with health_col:
            with st.container(border=True):
                st.markdown("#### 🛡️ 재무 건전성")
                h1, h2, h3 = st.columns(3)
                h1.metric("부채비율", format_ratio(debt_ratio))
                h2.metric("유동비율", format_ratio(current_ratio))
                h3.metric("자기자본비율", format_ratio(equity_ratio))
                health_status = "안정" if debt_ratio is not None and debt_ratio < 150 and current_ratio is not None and current_ratio >= 100 else "점검 필요"
                st.info(f"건전성 진단: **{health_status}** · 부채비율과 단기 지급능력을 연결 재무상태표 기준으로 평가했습니다.")
        with profit_col:
            with st.container(border=True):
                st.markdown("#### 📈 수익성")
                p1, p2, p3 = st.columns(3)
                p1.metric("영업이익률", format_ratio(operating_margin))
                p2.metric("순이익률", format_ratio(net_margin))
                p3.metric("ROA", format_ratio(roa))
                profit_status = "양호" if operating_margin is not None and operating_margin > 5 and net_margin is not None and net_margin > 0 else "개선 필요"
                st.info(f"수익성 진단: **{profit_status}** · 선택 보고서의 누적 손익과 기말 자산을 기준으로 계산했습니다.")

        detail_rows = pd.DataFrame(
            [
                ["유동자산", format_krw(financials["current_assets"])],
                ["유동부채", format_krw(financials["current_liabilities"])],
                ["자본총계", format_krw(financials["equity"])],
                ["전기 매출액", format_krw(financials["prior_revenue"])],
                ["전기 영업이익", format_krw(financials["prior_operating_income"])],
                ["전기 순이익", format_krw(financials["prior_net_income"])],
            ],
            columns=["항목", "금액"],
        )
        detail_col, source_col = st.columns([4, 1])
        detail_col.dataframe(detail_rows, hide_index=True, width="stretch", height=150)
        if financials["source_url"]:
            source_col.link_button("📄 DART 원문", financials["source_url"], width="stretch")
        source_col.caption("단위: 원\n연결재무제표 기준")

    st.markdown(
        f'<div class="footer-note">FUTURE:M RADAR · 기업 재무분석 · 마지막 조회 {datetime.now().strftime("%Y-%m-%d %H:%M")}</div>',
        unsafe_allow_html=True,
    )
    st.stop()

left, right = st.columns([1.05, 1.35], gap="medium")
with left:
    with st.container(border=True):
        st.markdown('<div class="panel-title">📋 실시간 DART 전자공시</div>', unsafe_allow_html=True)
        if st.session_state.dart.empty:
            st.info("DART API 키를 설정하면 최근 7일 공시가 이 영역에 표시됩니다.")
            st.dataframe(
                pd.DataFrame(columns=["접수일", "기업", "보고서"]),
                width="stretch", hide_index=True, height=190,
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
            if a.button("🧠 AI 분석", width="stretch"):
                st.session_state.ai[dart_key] = analyze_content_with_llm(
                    row["report_nm"],
                    f"기업명: {row['corp_name']}\n접수일자: {row['rcept_dt']}\n접수번호: {row['rcept_no']}",
                    "자사" if row["corp_name"] in OWN_COMPANIES else ("고객사" if row["corp_name"] in CUSTOMERS else "경쟁사"),
                )
                st.session_state.selected = dart_key
                st.rerun()
            b.link_button("📄 원문", row["url"], width="stretch")

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
                if c3.button("브리핑", key=f"news_{i}", width="stretch"):
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
                st.link_button("📄 원문 열기", selected_url, width="stretch")
            if st.button("🚀 Teams 발송", type="primary", width="stretch"):
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
