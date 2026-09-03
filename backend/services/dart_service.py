from datetime import datetime, timedelta
import OpenDartReader
import pandas as pd
from backend.config import DART_API_KEY, DART_COLUMNS

MAJOR_DISCLOSURE_TERMS = ("단일판매·공급계약체결", "단일판매ㆍ공급계약체결", "신규시설투자", "타법인주식및출자증권취득결정", "유상증자")
CORPORATE_NAME_ALIASES = {"SK온": "에스케이온"}

def safe_text(value, default="") -> str:
    if value is None: return default
    try:
        if pd.isna(value): return default
    except Exception: pass
    return str(value)

def normalize(raw) -> pd.DataFrame:
    if raw is None or getattr(raw, "empty", True): return pd.DataFrame(columns=DART_COLUMNS)
    frame = raw.copy().rename(columns={"접수일자":"rcept_dt","접수일":"rcept_dt","회사명":"corp_name","보고서명":"report_nm","접수번호":"rcept_no"})
    for column in DART_COLUMNS:
        if column not in frame.columns: frame[column] = ""
        frame[column] = frame[column].map(safe_text)
    frame["url"] = frame.apply(lambda row: row["url"] or f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={row['rcept_no']}", axis=1)
    return frame[DART_COLUMNS].drop_duplicates("rcept_no")

def fetch_disclosures(corp_name: str, days: int = 30) -> list[dict]:
    if not DART_API_KEY: return []
    try:
        dart_name = CORPORATE_NAME_ALIASES.get(corp_name, corp_name)
        dart, today = OpenDartReader(DART_API_KEY), datetime.now().date()
        start = today - timedelta(days=max(days - 1, 0))
        frame = normalize(dart.list(dart_name, start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")))
        if frame.empty:
            frame = normalize(dart.list(dart_name, (today - timedelta(days=29)).strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")))
        records = frame.sort_values("rcept_dt", ascending=False).to_dict("records") if not frame.empty else []
        for record in records:
            record["corp_name"] = corp_name
            record["is_major"] = any(term in record["report_nm"].replace(" ", "") for term in MAJOR_DISCLOSURE_TERMS)
            record["major_label"] = "주요" if record["is_major"] else ""
        return records
    except Exception: return []

def validate_company(query: str) -> dict:
    if not DART_API_KEY or not query.strip(): return {"valid":False,"message":"기업명을 입력해 주세요."}
    try:
        codes = OpenDartReader(DART_API_KEY).corp_codes.copy()
        codes["corp_name"] = codes["corp_name"].fillna("").astype(str).str.strip()
        codes["stock_code"] = codes["stock_code"].fillna("").astype(str).str.strip()
        value = query.strip(); stock = value.zfill(6) if value.isdigit() else value
        exact = codes[(codes["corp_name"] == value) | (codes["stock_code"] == stock)]
        listed = exact[exact["stock_code"].str.len() == 6]
        if not listed.empty:
            row = listed.iloc[0]; return {"valid":True,"corp_name":safe_text(row["corp_name"]),"stock_code":safe_text(row["stock_code"])}
        suggestions = codes[codes["corp_name"].str.contains(value,case=False,regex=False) & (codes["stock_code"].str.len()==6)]["corp_name"].head(3).tolist()
        return {"valid":False,"message":"정확한 상장기업명을 입력해 주세요." + (f" 검색 결과: {', '.join(suggestions)}" if suggestions else "")}
    except Exception: return {"valid":False,"message":"OpenDART에서 기업 정보를 확인하지 못했습니다."}
