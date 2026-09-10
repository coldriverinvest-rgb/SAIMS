import logging
from datetime import datetime
import pandas as pd
from backend.config import CORPORATE_NAME_ALIASES
from backend.services.dart_client import get_dart
from backend.services.dart_service import safe_text

logger = logging.getLogger(__name__)

def amount(value):
    try:
        raw=safe_text(value).replace(",","").strip(); return float(raw) if raw and raw not in {"-","None","nan"} else None
    except (TypeError,ValueError): return None

def pick(frame: pd.DataFrame, ids: list[str], cumulative=False):
    matched=frame[frame["account_id"].isin(ids)]
    if matched.empty: return None
    row=matched.iloc[0]; field="thstrm_add_amount" if cumulative and amount(row.get("thstrm_add_amount")) is not None else "thstrm_amount"
    return amount(row.get(field))

def ratio(a,b): return None if a is None or b in (None,0) else a/b*100
def format_krw(value):
    if value is None: return "N/A"
    sign="-" if value<0 else ""; absolute=abs(value)
    return f"{sign}{absolute/1_000_000_000_000:,.2f}조" if absolute>=1_000_000_000_000 else f"{sign}{absolute/100_000_000:,.0f}억"
def format_ratio(value): return "N/A" if value is None else f"{value:,.1f}%"
def to_eok(value): return None if value is None else round(value / 100_000_000, 1)

REPORT_LABELS = {"11013": "1분기", "11012": "반기", "11014": "3분기", "11011": "사업보고서(연간)"}
QUARTERLY_CODES = ("11013", "11012", "11014", "11011")
QUARTER_LABELS = {"11013": "Q1", "11012": "Q2", "11014": "Q3", "11011": "Q4"}

STATEMENT_LABELS = {"CFS": "연결", "OFS": "별도"}

def quarterly_periods(end_year: int, end_report_code: str, count: int = 8) -> list[tuple[int, str]]:
    end_index = end_year * 4 + QUARTERLY_CODES.index(end_report_code)
    start_index = end_index - max(1, count) + 1
    return [(index // 4, QUARTERLY_CODES[index % 4]) for index in range(start_index, end_index + 1)]

def normalize_quarterly_history(items: list[dict]) -> list[dict]:
    """Convert DART year-to-date income/cashflow values into standalone quarters."""
    ordered = sorted(items, key=lambda item: (item["year"], QUARTERLY_CODES.index(item["report_code"])))
    flow_fields = ("revenue", "operating_income", "net_income", "operating_cf", "investing_cf", "financing_cf")
    cumulative_by_year: dict[int, dict[str, float | None]] = {}
    result = []
    for source in ordered:
        item = dict(source)
        year, code = item["year"], item["report_code"]
        previous = cumulative_by_year.setdefault(year, {})
        for field in flow_fields:
            cumulative = item.get(field)
            prior = previous.get(field)
            if cumulative is not None and prior is not None:
                item[field] = round(cumulative - prior, 1)
            previous[field] = cumulative
        item["operating_margin"] = ratio(item.get("operating_income"), item.get("revenue"))
        item["net_margin"] = ratio(item.get("net_income"), item.get("revenue"))
        item["current_ratio"] = ratio(item.get("current_assets"), item.get("current_liabilities"))
        item["net_debt_ratio"] = ratio(item.get("net_debt"), item.get("equity"))
        item["quarter_label"] = f"{year} {QUARTER_LABELS[code]}"
        result.append(item)
    return result

def fetch_financials(corp_name: str, year: int | None = None, report_code: str | None = None, fs_div: str = "CFS"):
    dart = get_dart()
    if dart is None: return {}
    dart_name = CORPORATE_NAME_ALIASES.get(corp_name, corp_name)
    statement=None; selected=None; now=datetime.now().year
    if year is not None and report_code in REPORT_LABELS:
        candidates = [(year, report_code, REPORT_LABELS[report_code])]
    else:
        candidates = [(now,"11012","반기"),(now,"11013","1분기"),(now-1,"11011","사업보고서(연간)"),(now-1,"11014","3분기")]
    for target_year,code,label in candidates:
        try:
            candidate=dart.finstate_all(dart_name,target_year,reprt_code=code,fs_div=fs_div)
            if candidate is not None and not candidate.empty: statement,selected=candidate,(target_year,label,code); break
        except Exception:
            logger.debug("재무제표 조회 실패: %s %s %s", dart_name, target_year, code, exc_info=True)
            continue
    if statement is None:
        logger.warning("재무제표를 찾지 못함: %s (fs_div=%s)", dart_name, fs_div)
        return {}
    revenue=pick(statement,["ifrs-full_Revenue","ifrs_Revenue","dart_Revenue"],True); operating=pick(statement,["dart_OperatingIncomeLoss","ifrs-full_ProfitLossFromOperatingActivities"],True); net=pick(statement,["ifrs-full_ProfitLoss","ifrs_ProfitLoss"],True)
    assets=pick(statement,["ifrs-full_Assets","ifrs_Assets"]); liabilities=pick(statement,["ifrs-full_Liabilities","ifrs_Liabilities"]); equity=pick(statement,["ifrs-full_Equity","ifrs_Equity"])
    current_assets=pick(statement,["ifrs-full_CurrentAssets","ifrs_CurrentAssets"]); current_liabilities=pick(statement,["ifrs-full_CurrentLiabilities","ifrs_CurrentLiabilities"])
    short_borrowings=pick(statement,["ifrs-full_ShorttermBorrowings","ifrs_ShorttermBorrowings","dart_ShortTermBorrowings"]); long_borrowings=pick(statement,["ifrs-full_LongtermBorrowings","ifrs_LongtermBorrowings","dart_LongTermBorrowings"])
    borrowings=sum(value for value in (short_borrowings,long_borrowings) if value is not None) if short_borrowings is not None or long_borrowings is not None else None
    operating_cf=pick(statement,["ifrs-full_CashFlowsFromUsedInOperatingActivities","ifrs_CashFlowsFromUsedInOperatingActivities"],True); investing_cf=pick(statement,["ifrs-full_CashFlowsFromUsedInInvestingActivities","ifrs_CashFlowsFromUsedInInvestingActivities"],True); financing_cf=pick(statement,["ifrs-full_CashFlowsFromUsedInFinancingActivities","ifrs_CashFlowsFromUsedInFinancingActivities"],True); cash=pick(statement,["ifrs-full_CashAndCashEquivalents","ifrs_CashAndCashEquivalents"])
    net_debt=borrowings-cash if borrowings is not None and cash is not None else None
    receipt=safe_text(statement.iloc[0].get("rcept_no")); debt_ratio=ratio(liabilities,equity); current_ratio=ratio(current_assets,current_liabilities); net_debt_ratio=ratio(net_debt,equity); operating_margin=ratio(operating,revenue); net_margin=ratio(net,revenue); roe=ratio(net,equity); roa=ratio(net,assets)
    return {
        "corp_name": corp_name,
        "fs_div": fs_div,
        "statement_type": STATEMENT_LABELS[fs_div],
        "source_corp_name": dart_name,
        "year": selected[0],
        "report_code": selected[2],
        "report_label": selected[1],
        "period_label": f"{selected[0]}년 {selected[1]}",
        "revenue": to_eok(revenue), "operating_income": to_eok(operating), "net_income": to_eok(net),
        "assets": to_eok(assets), "liabilities": to_eok(liabilities), "equity": to_eok(equity), "current_assets": to_eok(current_assets), "current_liabilities": to_eok(current_liabilities), "borrowings": to_eok(borrowings), "net_debt": to_eok(net_debt),
        "operating_cf": to_eok(operating_cf), "investing_cf": to_eok(investing_cf),
        "financing_cf": to_eok(financing_cf), "cash": to_eok(cash),
        "debt_ratio": debt_ratio, "current_ratio": current_ratio, "net_debt_ratio": net_debt_ratio, "operating_margin": operating_margin, "net_margin": net_margin, "roe": roe, "roa": roa,
        "revenue_display": format_krw(revenue), "operating_income_display": format_krw(operating),
        "net_income_display": format_krw(net), "assets_display": format_krw(assets),
        "liabilities_display": format_krw(liabilities), "equity_display": format_krw(equity),
        "operating_cf_display": format_krw(operating_cf), "investing_cf_display": format_krw(investing_cf),
        "financing_cf_display": format_krw(financing_cf), "cash_display": format_krw(cash),
        "debt_ratio_display": format_ratio(debt_ratio), "current_ratio_display": format_ratio(current_ratio), "net_debt_ratio_display": format_ratio(net_debt_ratio), "operating_margin_display": format_ratio(operating_margin),
        "net_margin_display": format_ratio(net_margin), "roe_display": format_ratio(roe), "roa_display": format_ratio(roa),
        "source_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={receipt}" if receipt else "",
    }
