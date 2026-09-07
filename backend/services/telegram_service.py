from datetime import datetime
import html, requests
from backend.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from backend.services.ai_service import validate_result

def send_alert(title,corp_name,ai_result,source_url,chat_id: str | None = None):
    target_chat_id = chat_id or TELEGRAM_CHAT_ID
    if not TELEGRAM_BOT_TOKEN or not target_chat_id: return False
    result=validate_result(ai_result); header={"주의":"🚨 주의","기회":"💡 기회","중립":"🟡 중립"}[result["sentiment"]]; summary="\n".join(f"• {html.escape(x)}" for x in result["summary_points"]); link=f'\n\n<a href="{html.escape(source_url,quote=True)}">📄 원문 바로가기</a>' if source_url else ""
    message=f"<b>{header} | FUTURE:M RADAR</b>\n\n<b>{html.escape(title)}</b>\n기업: {html.escape(corp_name)}\n우선순위: <b>{result['priority']}</b>\n감지시각: {datetime.now():%Y-%m-%d %H:%M:%S}\n\n<b>AI 핵심 요약</b>\n{summary}\n\n<b>전략 시사점</b>\n{html.escape(result['strategic_implication'])}{link}"
    response=requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",json={"chat_id":target_chat_id,"text":message[:4096],"parse_mode":"HTML","link_preview_options":{"is_disabled":True}},timeout=15); response.raise_for_status(); return bool(response.json().get("ok"))

def get_bot_status() -> dict:
    if not TELEGRAM_BOT_TOKEN:
        return {"configured": False, "connected": False, "username": ""}
    try:
        response = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe", timeout=10)
        response.raise_for_status()
        payload = response.json()
        user = payload.get("result", {})
        return {"configured": True, "connected": bool(payload.get("ok")), "username": user.get("username", "")}
    except Exception:
        return {"configured": True, "connected": False, "username": ""}

def get_recent_chats() -> list[dict]:
    if not TELEGRAM_BOT_TOKEN:
        return []
    response = requests.get(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates", timeout=12)
    response.raise_for_status()
    chats = {}
    for update in response.json().get("result", []):
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        display_name = " ".join(filter(None, [chat.get("first_name"), chat.get("last_name")])).strip()
        chats[str(chat_id)] = {"chat_id": str(chat_id), "name": display_name or chat.get("title") or chat.get("username") or str(chat_id), "username": chat.get("username", ""), "type": chat.get("type", "")}
    return list(chats.values())
