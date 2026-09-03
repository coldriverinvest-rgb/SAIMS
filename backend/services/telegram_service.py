from datetime import datetime
import html, requests
from backend.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from backend.services.ai_service import validate_result

def send_alert(title,corp_name,ai_result,source_url):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID: return False
    result=validate_result(ai_result); header={"주의":"🚨 주의","기회":"💡 기회","중립":"🟡 중립"}[result["sentiment"]]; summary="\n".join(f"• {html.escape(x)}" for x in result["summary_points"]); link=f'\n\n<a href="{html.escape(source_url,quote=True)}">📄 원문 바로가기</a>' if source_url else ""
    message=f"<b>{header} | FUTURE:M RADAR</b>\n\n<b>{html.escape(title)}</b>\n기업: {html.escape(corp_name)}\n우선순위: <b>{result['priority']}</b>\n감지시각: {datetime.now():%Y-%m-%d %H:%M:%S}\n\n<b>AI 핵심 요약</b>\n{summary}\n\n<b>전략 시사점</b>\n{html.escape(result['strategic_implication'])}{link}"
    response=requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",json={"chat_id":TELEGRAM_CHAT_ID,"text":message[:4096],"parse_mode":"HTML","link_preview_options":{"is_disabled":True}},timeout=15); response.raise_for_status(); return bool(response.json().get("ok"))
