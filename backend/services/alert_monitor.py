import asyncio
from datetime import datetime

from backend.config import ALERT_POLL_SECONDS, DEFAULT_COMPANIES
from backend.services.ai_service import analyze
from backend.services.dart_service import fetch_disclosures
from backend.services.disclosure_text_service import fetch_disclosure_text
from backend.services.recipient_service import list_recipients, mark_delivered, was_delivered
from backend.services.telegram_service import send_alert
from backend.services.email_service import send_email_alert


def scan_important_disclosures() -> dict:
    recipients = list_recipients(enabled_only=True)
    if not recipients:
        return {"found": 0, "sent": 0}
    today = datetime.now().strftime("%Y%m%d")
    disclosures = {}
    for company in DEFAULT_COMPANIES:
        for item in fetch_disclosures(company, days=2):
            if item.get("rcept_dt") == today and item.get("is_major"):
                disclosures[item["rcept_no"]] = item
    sent = telegram_sent = email_sent = 0
    for item in disclosures.values():
        pending = [recipient for recipient in recipients if
            (recipient.get("telegram_enabled") and recipient.get("chat_id") and not was_delivered(recipient["id"], item["rcept_no"], "telegram")) or
            (recipient.get("email_enabled") and recipient.get("email") and not was_delivered(recipient["id"], item["rcept_no"], "email"))]
        if not pending:
            continue
        original = fetch_disclosure_text(item["rcept_no"])
        result = analyze(item["report_nm"], original or item["report_nm"], "자동 중요 공시")
        for recipient in pending:
            if recipient.get("telegram_enabled") and recipient.get("chat_id") and not was_delivered(recipient["id"], item["rcept_no"], "telegram"):
                try:
                    if send_alert(item["report_nm"], item["corp_name"], result, item["url"], recipient["chat_id"]):
                        mark_delivered(recipient["id"], item["rcept_no"], "telegram"); telegram_sent += 1; sent += 1
                except Exception: pass
            if recipient.get("email_enabled") and recipient.get("email") and not was_delivered(recipient["id"], item["rcept_no"], "email"):
                try:
                    if send_email_alert(item["report_nm"], item["corp_name"], result, item["url"], recipient["email"]):
                        mark_delivered(recipient["id"], item["rcept_no"], "email"); email_sent += 1; sent += 1
                except Exception: pass
    return {"found": len(disclosures), "sent": sent, "telegram_sent": telegram_sent, "email_sent": email_sent}


async def alert_monitor_loop() -> None:
    while True:
        try:
            await asyncio.to_thread(scan_important_disclosures)
        except Exception:
            pass
        await asyncio.sleep(ALERT_POLL_SECONDS)
