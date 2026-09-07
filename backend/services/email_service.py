"""SMTP email delivery for important disclosure alerts."""
import html
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr

from backend.config import SMTP_FROM_EMAIL, SMTP_FROM_NAME, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USERNAME, SMTP_USE_SSL, SMTP_USE_TLS
from backend.services.ai_service import validate_result


def get_email_status() -> dict:
    configured = bool(SMTP_HOST and SMTP_PORT and SMTP_FROM_EMAIL)
    return {"configured": configured, "from_email": SMTP_FROM_EMAIL if configured else "", "security": "SSL" if SMTP_USE_SSL else "STARTTLS" if SMTP_USE_TLS else "NONE"}


def _content(title, corp_name, ai_result, source_url):
    result = validate_result(ai_result)
    summary_text = "\n".join(f"- {point}" for point in result["summary_points"])
    plain = f"[FUTURE:M RADAR] 중요 공시 알림\n\n기업: {corp_name}\n공시: {title}\n우선순위: {result['priority']}\n감지시각: {datetime.now():%Y-%m-%d %H:%M:%S}\n\nAI 핵심 요약\n{summary_text}\n\n전략 시사점\n{result['strategic_implication']}"
    if source_url:
        plain += f"\n\n공시 원문: {source_url}"
    points = "".join(f"<li>{html.escape(point)}</li>" for point in result["summary_points"])
    link = f'<p><a href="{html.escape(source_url, quote=True)}" style="display:inline-block;padding:11px 16px;border-radius:8px;background:#276fea;color:#fff;text-decoration:none;font-weight:700">DART 공시 원문 확인</a></p>' if source_url else ""
    body = f'''<div style="max-width:680px;margin:auto;font-family:Arial,'Noto Sans KR',sans-serif;color:#172b45"><div style="padding:22px 26px;border-radius:14px 14px 0 0;background:#0d2b54;color:#fff"><small style="color:#69ded0;letter-spacing:2px">DISCLOSURE INTELLIGENCE</small><h2 style="margin:8px 0">중요 공시 알림</h2></div><div style="padding:25px;border:1px solid #d8e3ef"><p><b>{html.escape(corp_name)}</b> · {html.escape(title)}</p><p style="color:#647b92">우선순위 {html.escape(result['priority'])} · {datetime.now():%Y-%m-%d %H:%M:%S}</p><h3>AI 핵심 요약</h3><ol>{points}</ol><div style="margin:20px 0;padding:14px;border-left:3px solid #35b8aa;background:#eff9f7"><b>전략 시사점</b><p>{html.escape(result['strategic_implication'])}</p></div>{link}</div></div>'''
    return result, plain, body


def send_email_alert(title, corp_name, ai_result, source_url, recipient_email):
    if not recipient_email or not get_email_status()["configured"]:
        return False
    result, plain, body = _content(title, corp_name, ai_result, source_url)
    message = EmailMessage()
    message["Subject"] = f"[{result['priority']}] {corp_name} 중요 공시 · {title}"
    message["From"] = formataddr((SMTP_FROM_NAME, SMTP_FROM_EMAIL))
    message["To"] = recipient_email
    message.set_content(plain)
    message.add_alternative(body, subtype="html")
    context = ssl.create_default_context()
    if SMTP_USE_SSL:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=20, context=context) as server:
            if SMTP_USERNAME: server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)
    else:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.ehlo()
            if SMTP_USE_TLS:
                server.starttls(context=context); server.ehlo()
            if SMTP_USERNAME: server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.send_message(message)
    return True
