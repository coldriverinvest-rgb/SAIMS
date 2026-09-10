import asyncio
import hmac
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from backend.config import ADMIN_PASSWORD, ALERT_POLL_SECONDS, DART_API_KEY, GEMINI_API_KEY, INTELLIGENCE_CACHE_SECONDS, OPENAI_API_KEY
from backend.schemas import AnalyzeRequest, RecipientCreate, RecipientUpdate, TelegramRequest
from backend.services.cache import TTLCache
from backend.services.alert_monitor import alert_monitor_loop, scan_important_disclosures
from backend.services.ai_service import analyze
from backend.services.dart_service import fetch_disclosures, validate_company
from backend.services.disclosure_text_service import fetch_disclosure_text
from backend.services.finance_service import fetch_financials, normalize_quarterly_history, quarterly_periods
from backend.services.news_service import fetch_news
from backend.services.stock_service import fetch_stock_analysis
from backend.services.komis_service import material_prices, material_monitor_loop
from backend.services.recipient_service import add_recipient, delete_recipient, initialize_database, list_recipients, update_recipient
from backend.services.telegram_service import get_bot_status, get_recent_chats, send_alert
from backend.services.email_service import get_email_status, send_email_alert

@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    monitor_task = asyncio.create_task(alert_monitor_loop())
    material_task = asyncio.create_task(material_monitor_loop())
    yield
    material_task.cancel()
    try:
        await material_task
    except asyncio.CancelledError:
        pass
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass

app=FastAPI(title="FUTURE:M RADAR API",version="2.1.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

@app.get('/api/materials')
def materials():
    return material_prices()

def build_daily_briefing(disclosures: list[dict], news: list[dict]) -> list[str]:
    signals = []
    for index, item in enumerate(disclosures):
        signals.append({"score": (100 if item.get("is_major") else 58) - index * 0.01, "corp": item.get("corp_name", "기업 미상"), "key": f"dart:{item.get('rcept_no')}", "text": f"{'주요 공시' if item.get('is_major') else '공시 신호'}: {item.get('corp_name')} · {item.get('report_nm')} — 계약·투자 규모와 배터리 소재 밸류체인 영향을 확인하세요."})
    type_scores = {"opportunity": 92, "risk": 88, "investment": 82, "technology": 76, "neutral": 55}
    implications = {"opportunity": "수주 가능성과 공급망 수요 영향을 검토하세요.", "risk": "경쟁 대응 및 실적 리스크를 점검하세요.", "investment": "CAPEX 일정과 소재 수요 증가 가능성을 확인하세요.", "technology": "기술 경쟁력과 특허·제품 로드맵 영향을 검토하세요.", "neutral": "시장·밸류체인 영향을 확인하세요."}
    for index, item in enumerate(news):
        ai = item.get("ai", {})
        strategy_type = ai.get("strategy_type", "neutral")
        strategy_tag = ai.get("strategy_tag", "시장/일반")
        signals.append({"score": type_scores.get(strategy_type, 55) - index * 0.01, "corp": item.get("corp_name", "기업 미상"), "key": f"news:{item.get('link') or item.get('title')}", "text": f"{strategy_tag}: {item.get('corp_name')} · {item.get('title')} — {implications.get(strategy_type, implications['neutral'])}"})
    ranked = sorted(signals, key=lambda signal: signal["score"], reverse=True)
    selected, seen_keys, seen_corps = [], set(), set()
    for prefer_new_company in (True, False):
        for signal in ranked:
            if signal["key"] in seen_keys or (prefer_new_company and signal["corp"] in seen_corps): continue
            selected.append(signal["text"]); seen_keys.add(signal["key"]); seen_corps.add(signal["corp"])
            if len(selected) == 3: return selected
    return selected or ["수집된 주요 공시·뉴스가 없습니다. 실시간 데이터 갱신 상태를 확인하세요."]

@app.get("/api/status")
def status(): return {"dart":bool(DART_API_KEY),"ai":bool(GEMINI_API_KEY or OPENAI_API_KEY)}

def require_admin(x_admin_password: str = Header(default="")) -> None:
    if not ADMIN_PASSWORD:
        raise HTTPException(status_code=503, detail="ADMIN_PASSWORD를 .env에 먼저 설정해 주세요.")
    if not hmac.compare_digest(x_admin_password, ADMIN_PASSWORD):
        raise HTTPException(status_code=401, detail="관리자 비밀번호가 올바르지 않습니다.")

@app.get("/api/admin/status", dependencies=[Depends(require_admin)])
def admin_status():
    return {"authenticated": True, "telegram": get_bot_status(), "email": get_email_status(), "poll_seconds": ALERT_POLL_SECONDS}

@app.get("/api/admin/telegram/chats", dependencies=[Depends(require_admin)])
def admin_telegram_chats():
    try:
        return {"items": get_recent_chats()}
    except Exception as error:
        raise HTTPException(status_code=502, detail="Telegram 대화 목록을 불러오지 못했습니다. Bot Token과 webhook 설정을 확인해 주세요.") from error

@app.get("/api/admin/recipients", dependencies=[Depends(require_admin)])
def admin_recipients():
    return {"items": list_recipients()}

@app.post("/api/admin/recipients", dependencies=[Depends(require_admin)])
def admin_add_recipient(payload: RecipientCreate):
    try:
        return add_recipient(payload.name, payload.chat_id, payload.email, payload.telegram_enabled, payload.email_enabled)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="이미 등록된 Telegram Chat ID 또는 이메일입니다.") from error

@app.patch("/api/admin/recipients/{recipient_id}", dependencies=[Depends(require_admin)])
def admin_update_recipient(recipient_id: int, payload: RecipientUpdate):
    try:
        item = update_recipient(recipient_id, payload.name, payload.enabled, payload.chat_id, payload.email, payload.telegram_enabled, payload.email_enabled)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="이미 등록된 Telegram Chat ID 또는 이메일입니다.") from error
    if not item:
        raise HTTPException(status_code=404, detail="수신자를 찾지 못했습니다.")
    return item

@app.delete("/api/admin/recipients/{recipient_id}", dependencies=[Depends(require_admin)])
def admin_delete_recipient(recipient_id: int):
    if not delete_recipient(recipient_id):
        raise HTTPException(status_code=404, detail="수신자를 찾지 못했습니다.")
    return {"success": True}

@app.post("/api/admin/recipients/{recipient_id}/test", dependencies=[Depends(require_admin)])
def admin_test_recipient(recipient_id: int):
    recipient = next((item for item in list_recipients() if item["id"] == recipient_id), None)
    if not recipient:
        raise HTTPException(status_code=404, detail="수신자를 찾지 못했습니다.")
    result = {
        "summary_points": ["중요 공시 자동 알림 연결 테스트입니다.", "활성화된 Telegram·이메일 채널로 자동 발송됩니다.", "관리자 페이지에서 채널별 수신 여부를 관리할 수 있습니다."],
        "sentiment": "중립", "priority": "LOW", "strategic_implication": "FUTURE:M RADAR 알림 채널 연결이 정상인지 확인해 주세요.",
    }
    channels, failures = [], []
    if recipient.get("telegram_enabled") and recipient.get("chat_id"):
        try:
            if send_alert("자동 알림 테스트", "FUTURE:M RADAR", result, "", recipient["chat_id"]): channels.append("telegram")
            else: failures.append("Telegram 설정 필요")
        except Exception: failures.append("Telegram 발송 실패")
    if recipient.get("email_enabled") and recipient.get("email"):
        try:
            if send_email_alert("자동 알림 테스트", "FUTURE:M RADAR", result, "", recipient["email"]): channels.append("email")
            else: failures.append("SMTP 설정 필요")
        except Exception: failures.append("이메일 발송 실패")
    if not channels: raise HTTPException(status_code=503, detail=" / ".join(failures) or "활성화된 알림 채널이 없습니다.")
    return {"success": True, "channels": channels, "failures": failures}

@app.post("/api/admin/alerts/scan", dependencies=[Depends(require_admin)])
def admin_scan_alerts():
    return scan_important_disclosures()

_intelligence_cache = TTLCache(INTELLIGENCE_CACHE_SECONDS)

@app.get("/api/intelligence")
def intelligence(companies: str=Query(...,min_length=1), refresh: bool=False):
    company_list=list(dict.fromkeys(x.strip() for x in companies.split(",") if x.strip()))[:20]
    cache_key=",".join(sorted(company_list))
    if not refresh:
        cached=_intelligence_cache.get(cache_key)
        if cached is not None:
            return cached
    disclosures=[]; news=[]
    with ThreadPoolExecutor(max_workers=min(10,max(2,len(company_list)*2))) as executor:
        jobs={}
        for company in company_list:
            jobs[executor.submit(fetch_disclosures,company)]="dart"; jobs[executor.submit(fetch_news,company)]="news"
        for future in as_completed(jobs):
            try: (disclosures if jobs[future]=="dart" else news).extend(future.result())
            except Exception: continue
    disclosures.sort(key=lambda x:x.get("rcept_dt",""),reverse=True); news.sort(key=lambda x:x.get("time",""),reverse=True)
    payload={"disclosures":disclosures,"news":news,"daily_briefing":build_daily_briefing(disclosures,news)}
    _intelligence_cache.set(cache_key,payload)
    return payload

@app.get("/api/companies/validate")
def company_validate(name: str):
    result=validate_company(name)
    if not result.get("valid"): raise HTTPException(status_code=404,detail=result.get("message"))
    return result

@app.get("/api/financials/{corp_name}")
def financials(corp_name: str, year: int | None = None, report_code: str | None = None, fs_div: str = "CFS"):
    if report_code is not None and report_code not in {"11013", "11012", "11014", "11011"}:
        raise HTTPException(status_code=400, detail="지원하지 않는 보고서 구분입니다.")
    if fs_div not in {"CFS", "OFS"}:
        raise HTTPException(status_code=400, detail="지원하지 않는 재무제표 구분입니다.")
    result=fetch_financials(corp_name, year, report_code, fs_div)
    if not result: raise HTTPException(status_code=404,detail=f"선택한 연도와 기간의 {'연결' if fs_div == 'CFS' else '별도'} 재무제표를 찾지 못했습니다.")
    return result

@app.get("/api/financials/{corp_name}/history")
def financial_history(corp_name: str, report_code: str = "11011", end_year: int | None = None, quarters: int = 8, years: int = 6, frequency: str = "quarter", fs_div: str = "CFS"):
    if report_code not in {"11013", "11012", "11014", "11011"}:
        raise HTTPException(status_code=400, detail="지원하지 않는 보고서 구분입니다.")
    if fs_div not in {"CFS", "OFS"}:
        raise HTTPException(status_code=400, detail="지원하지 않는 재무제표 구분입니다.")
    if frequency not in {"quarter", "annual"}:
        raise HTTPException(status_code=400, detail="지원하지 않는 추이 기준입니다.")
    target_end = end_year or datetime.now().year
    target_periods = quarterly_periods(target_end, report_code, min(max(quarters, 4), 12)) if frequency == "quarter" else [(year, "11011") for year in range(target_end - min(max(years, 2), 7) + 1, target_end + 1)]
    results = []
    with ThreadPoolExecutor(max_workers=min(8, len(target_periods))) as executor:
        jobs = {executor.submit(fetch_financials, corp_name, year, code, fs_div): (year, code) for year, code in target_periods}
        for future in as_completed(jobs):
            try:
                item = future.result()
                if item: results.append(item)
            except Exception: continue
    items = normalize_quarterly_history(results) if frequency == "quarter" else sorted(results, key=lambda item: item["year"])
    if frequency == "annual":
        items = [{**item, "quarter_label": f"{item['year']} 연간"} for item in items]
    return {"corp_name": corp_name, "report_code": report_code, "fs_div": fs_div, "frequency": frequency, "items": items}

@app.get("/api/stocks/{corp_name}")
def stock_analysis(corp_name: str, period: str = "1y"):
    if period not in {"1m", "3m", "6m", "1y"}:
        raise HTTPException(status_code=400, detail="지원하지 않는 주가 조회 기간입니다.")
    result = fetch_stock_analysis(corp_name, period)
    if not result:
        raise HTTPException(status_code=502, detail="주가 데이터를 불러오지 못했습니다.")
    return result

@app.post("/api/analyze")
def analyze_content(payload: AnalyzeRequest):
    disclosure_text = fetch_disclosure_text(payload.rcept_no) if payload.rcept_no else ""
    source_text = payload.text
    if disclosure_text:
        source_text = f"{source_text}\n\n[DART 공시 원문 본문]\n{disclosure_text}"
    return analyze(payload.title, source_text, payload.group_type)

@app.post("/api/telegram")
def telegram(payload: TelegramRequest):
    try:
        if not send_alert(payload.title,payload.corp_name,payload.ai_result.model_dump(),payload.source_url): raise HTTPException(status_code=503,detail="Telegram 설정을 확인해 주세요.")
        return {"success":True}
    except HTTPException: raise
    except Exception as error: raise HTTPException(status_code=502,detail="Telegram 발송에 실패했습니다.") from error
