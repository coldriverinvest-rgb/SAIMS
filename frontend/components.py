"""재사용 가능한 Streamlit 화면 컴포넌트."""

import html

import pandas as pd
import streamlit as st


def safe_text(value, default="") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value)


def badge(sentiment: str) -> str:
    return {"주의": "🔴 주의", "기회": "🟢 기회", "중립": "🟡 중립"}.get(sentiment, "🟡 중립")


def render_dart_link_table(dart_df: pd.DataFrame) -> None:
    rows = []
    for _, disclosure in dart_df.iterrows():
        receipt_date = html.escape(safe_text(disclosure.get("rcept_dt")))
        company = html.escape(safe_text(disclosure.get("corp_name")))
        report_name = html.escape(safe_text(disclosure.get("report_nm")))
        source_url = html.escape(safe_text(disclosure.get("url")), quote=True)
        report_cell = (
            f'<a href="{source_url}" target="_blank" rel="noopener noreferrer" '
            f'title="DART 원문 열기">{report_name}</a>'
            if source_url else report_name
        )
        rows.append(f"<tr><td>{receipt_date}</td><td>{company}</td><td>{report_cell}</td></tr>")
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


def render_ai(result: dict) -> None:
    sentiment = safe_text(result.get("sentiment"), "중립")
    priority = safe_text(result.get("priority"), "LOW")
    st.markdown(f"**{badge(sentiment)} · {priority}**")
    for point in result.get("summary_points", [])[:3]:
        st.markdown(f"- {point}")
    st.info(f"전략 시사점: {result.get('strategic_implication', '')}")
