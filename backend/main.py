from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from backend.config import DART_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY
from backend.schemas import AnalyzeRequest, TelegramRequest
from backend.services.ai_service import analyze
from backend.services.dart_service import fetch_disclosures, validate_company
from backend.services.disclosure_text_service import fetch_disclosure_text
from backend.services.finance_service import fetch_financials
from backend.services.news_service import fetch_news
from backend.services.stock_service import fetch_stock_analysis
from backend.services.telegram_service import send_alert

app=FastAPI(title="FUTURE:M RADAR API",version="2.0.0")
app.add_middleware(CORSMiddleware,allow_origins=["http://localhost:5173","http://127.0.0.1:5173"],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])

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

@app.get("/api/intelligence")
def intelligence(companies: str=Query(...,min_length=1)):
    company_list=list(dict.fromkeys(x.strip() for x in companies.split(",") if x.strip()))[:20]; disclosures=[]; news=[]
    with ThreadPoolExecutor(max_workers=min(10,max(2,len(company_list)*2))) as executor:
        jobs={}
        for company in company_list:
            jobs[executor.submit(fetch_disclosures,company)]="dart"; jobs[executor.submit(fetch_news,company)]="news"
        for future in as_completed(jobs):
            try: (disclosures if jobs[future]=="dart" else news).extend(future.result())
            except Exception: continue
    disclosures.sort(key=lambda x:x.get("rcept_dt",""),reverse=True); news.sort(key=lambda x:x.get("time",""),reverse=True)
    return {"disclosures":disclosures,"news":news,"daily_briefing":build_daily_briefing(disclosures,news)}

@app.get("/api/companies/validate")
def company_validate(name: str):
    result=validate_company(name)
    if not result.get("valid"): raise HTTPException(status_code=404,detail=result.get("message"))
    return result

@app.get("/api/financials/{corp_name}")
def financials(corp_name: str, year: int | None = None, report_code: str | None = None):
    if report_code is not None and report_code not in {"11013", "11012", "11014", "11011"}:
        raise HTTPException(status_code=400, detail="지원하지 않는 보고서 구분입니다.")
    result=fetch_financials(corp_name, year, report_code)
    if not result: raise HTTPException(status_code=404,detail="선택한 연도와 기간의 연결 재무제표를 찾지 못했습니다.")
    return result

@app.get("/api/financials/{corp_name}/history")
def financial_history(corp_name: str, report_code: str = "11011", end_year: int | None = None, years: int = 5):
    if report_code not in {"11013", "11012", "11014", "11011"}:
        raise HTTPException(status_code=400, detail="지원하지 않는 보고서 구분입니다.")
    target_end = end_year or datetime.now().year
    target_years = list(range(target_end - min(max(years, 1), 7) + 1, target_end + 1))
    results = []
    with ThreadPoolExecutor(max_workers=min(5, len(target_years))) as executor:
        jobs = {executor.submit(fetch_financials, corp_name, year, report_code): year for year in target_years}
        for future in as_completed(jobs):
            try:
                item = future.result()
                if item: results.append(item)
            except Exception: continue
    return {"corp_name": corp_name, "report_code": report_code, "items": sorted(results, key=lambda item: item["year"])}

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
