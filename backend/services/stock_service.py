from functools import lru_cache
from math import sqrt
from statistics import stdev
from xml.etree import ElementTree

import OpenDartReader
import requests

from backend.config import DART_API_KEY


KNOWN_STOCK_CODES = {
    "포스코퓨처엠": "003670",
    "포스코홀딩스": "005490",
    "에코프로비엠": "247540",
    "엘앤에프": "066970",
    "LG화학": "051910",
    "LG에너지솔루션": "373220",
    "삼성SDI": "006400",
    "현대차": "005380",
}
CORPORATE_NAME_ALIASES = {"현대차": "현대자동차", "SK온": "에스케이온"}
PERIOD_POINTS = {"1m": 23, "3m": 66, "6m": 132, "1y": 260}
PEER_STOCK_CODES = ("247540", "066970", "051910")


def _number(value):
    try:
        return float(str(value).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def _fetch_price_rows(symbol: str, count: int = 420) -> list[dict]:
    response = requests.get(
        "https://fchart.stock.naver.com/sise.nhn",
        params={"symbol": symbol, "timeframe": "day", "count": count, "requestType": 0},
        headers={"User-Agent": "Mozilla/5.0 FUTURE-M-RADAR/2.0"},
        timeout=12,
    )
    response.raise_for_status()
    xml_text = response.content.decode("euc-kr", errors="replace")
    xml_text = xml_text.replace('encoding="EUC-KR"', 'encoding="UTF-8"')
    root = ElementTree.fromstring(xml_text)
    rows = []
    for node in root.findall(".//item"):
        fields = node.attrib.get("data", "").split("|")
        if len(fields) != 6:
            continue
        date, open_price, high, low, close, volume = fields
        rows.append({
            "date": f"{date[:4]}-{date[4:6]}-{date[6:]}",
            "open": float(open_price), "high": float(high), "low": float(low),
            "close": float(close), "volume": int(volume),
        })
    return rows


@lru_cache(maxsize=64)
def resolve_stock_code(corp_name: str) -> str:
    if corp_name in KNOWN_STOCK_CODES:
        return KNOWN_STOCK_CODES[corp_name]
    if not DART_API_KEY:
        return ""
    query = CORPORATE_NAME_ALIASES.get(corp_name, corp_name)
    try:
        codes = OpenDartReader(DART_API_KEY).corp_codes.copy()
        names = codes["corp_name"].fillna("").astype(str).str.strip()
        row = codes[names == query]
        if row.empty:
            return ""
        code = str(row.iloc[0].get("stock_code") or "").strip()
        return code.zfill(6) if code.isdigit() else ""
    except Exception:
        return ""


def moving_average(values: list[float], window: int, index: int):
    if index + 1 < window:
        return None
    subset = values[index - window + 1:index + 1]
    return round(sum(subset) / window, 2)


def rate(current: float, previous: float | None):
    if not previous:
        return None
    return round((current / previous - 1) * 100, 2)


def calculate_rsi(values: list[float], window: int = 14):
    if len(values) <= window:
        return None
    changes = [values[index] - values[index - 1] for index in range(len(values) - window, len(values))]
    gains = sum(max(change, 0) for change in changes) / window
    losses = sum(max(-change, 0) for change in changes) / window
    if losses == 0:
        return 100.0
    return round(100 - 100 / (1 + gains / losses), 1)


def signal(price: float, ma20: float | None, ma60: float | None, ma120: float | None, rsi: float | None):
    if rsi is not None and rsi >= 70:
        return {"label": "과열 주의", "tone": "risk", "description": "RSI가 과매수 구간에 진입했습니다. 단기 변동성 확대 가능성을 점검하세요."}
    if ma20 and ma120 and price < ma120 and price > ma20:
        return {"label": "단기 반등 · 장기 저항 테스트", "tone": "neutral", "description": f"120일 장기 저항선({ma120:,.0f}원)을 하회 중이나, 20일선({ma20:,.0f}원) 지지 기반의 단기 반등세입니다."}
    if ma20 and ma120 and price > ma120 and ma20 > ma120:
        return {"label": "중장기 상승 추세", "tone": "opportunity", "description": f"주가와 20일선이 120일선({ma120:,.0f}원)을 상회해 중장기 추세가 개선됐습니다. 거래량 동반 여부를 점검하세요."}
    if ma20 and ma120 and price < ma20 and price < ma120:
        return {"label": "중장기 약세", "tone": "risk", "description": f"주가가 20일선과 120일선({ma120:,.0f}원)을 모두 하회합니다. 수급 회복과 지지 구간 확인이 필요합니다."}
    if rsi is not None and rsi <= 30:
        return {"label": "낙폭 과대", "tone": "neutral", "description": "장기 추세 전환은 확인되지 않았으나 RSI 기준 과매도 구간으로 기술적 반등 가능성이 있습니다."}
    return {"label": "중립 구간", "tone": "neutral", "description": "이동평균과 모멘텀 신호가 혼재합니다. 방향성 확인 전까지 수급 변화를 관찰하세요."}


def fetch_stock_analysis(corp_name: str, period: str = "1y") -> dict:
    stock_code = resolve_stock_code(corp_name)
    if not stock_code:
        return {"listed": False, "corp_name": corp_name, "message": "비상장 기업이거나 주식 종목코드를 확인할 수 없습니다."}
    try:
        rows = _fetch_price_rows(stock_code)
        if len(rows) < 2:
            return {}
        closes = [row["close"] for row in rows]
        for index, row in enumerate(rows):
            row["ma20"] = moving_average(closes, 20, index)
            row["ma60"] = moving_average(closes, 60, index)
            row["ma120"] = moving_average(closes, 120, index)
            row["change_rate"] = rate(row["close"], rows[index - 1]["close"]) if index else None

        # Align market and peer closes to the company's trading dates. The UI
        # rebases them at the selected period's first visible date.
        kospi_by_date = {item["date"]: item["close"] for item in _fetch_price_rows("KOSPI")}
        peer_maps = [
            {item["date"]: item["close"] for item in _fetch_price_rows(code)}
            for code in PEER_STOCK_CODES if code != stock_code
        ]
        for row in rows:
            row["kospi"] = kospi_by_date.get(row["date"])
            row["peer_prices"] = [peer[row["date"]] for peer in peer_maps if row["date"] in peer]

        latest, previous = rows[-1], rows[-2]
        returns = [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes)) if closes[index - 1]]
        volatility = round(stdev(returns[-252:]) * sqrt(252) * 100, 1) if len(returns) > 2 else None
        rsi = calculate_rsi(closes)
        period_count = PERIOD_POINTS.get(period, PERIOD_POINTS["1y"])
        chart = rows[-period_count:]
        year_rows = rows[-260:]
        average_volume = round(sum(row["volume"] for row in rows[-20:]) / min(20, len(rows)))
        week_row = rows[-6] if len(rows) >= 6 else rows[0]
        day_volume_rate = rate(latest["volume"], previous["volume"])
        week_volume_rate = rate(latest["volume"], week_row["volume"])

        market_cap = foreign_rate = foreign_day_change = foreign_week_change = None
        try:
            polling = requests.get(
                f"https://polling.finance.naver.com/api/realtime/domestic/stock/{stock_code}",
                headers={"User-Agent": "Mozilla/5.0"}, timeout=8,
            ).json()
            stock_snapshot = (polling.get("datas") or [{}])[0]
            market_cap_raw = _number(stock_snapshot.get("marketValueFullRaw") or stock_snapshot.get("marketValueFull"))
            market_cap = round(market_cap_raw / 1_000_000_000_000, 2) if market_cap_raw else None

            integration = requests.get(
                f"https://m.stock.naver.com/api/stock/{stock_code}/integration",
                headers={"User-Agent": "Mozilla/5.0"}, timeout=8,
            ).json()
            info_by_code = {item.get("code"): item.get("value") for item in integration.get("totalInfos", [])}
            foreign_rate = _number(info_by_code.get("foreignRate"))
            trends = integration.get("dealTrendInfos") or []
            prior_foreign = _number(trends[0].get("foreignerHoldRatio")) if trends else None
            week_foreign = _number(trends[min(4, len(trends) - 1)].get("foreignerHoldRatio")) if trends else None
            foreign_day_change = round(foreign_rate - prior_foreign, 2) if foreign_rate is not None and prior_foreign is not None else None
            foreign_week_change = round(foreign_rate - week_foreign, 2) if foreign_rate is not None and week_foreign is not None else None
        except Exception:
            pass
        performance = {
            "1개월": rate(latest["close"], closes[-22] if len(closes) >= 22 else closes[0]),
            "3개월": rate(latest["close"], closes[-64] if len(closes) >= 64 else closes[0]),
            "6개월": rate(latest["close"], closes[-127] if len(closes) >= 127 else closes[0]),
            "1년": rate(latest["close"], closes[-253] if len(closes) >= 253 else closes[0]),
        }
        return {
            "listed": True, "corp_name": corp_name, "stock_code": stock_code,
            "as_of": latest["date"], "price": latest["close"],
            "change": latest["close"] - previous["close"],
            "change_rate": rate(latest["close"], previous["close"]),
            "high_52w": max(row["high"] for row in year_rows),
            "low_52w": min(row["low"] for row in year_rows),
            "volume": latest["volume"], "average_volume_20d": average_volume,
            "market_cap_trillion": market_cap, "foreign_rate": foreign_rate,
            "day_change_rate": rate(latest["close"], previous["close"]),
            "week_change_rate": rate(latest["close"], week_row["close"]),
            "volume_day_change_rate": day_volume_rate, "volume_week_change_rate": week_volume_rate,
            "foreign_day_change_pp": foreign_day_change, "foreign_week_change_pp": foreign_week_change,
            "rsi14": rsi, "volatility": volatility,
            "ma20": latest["ma20"], "ma60": latest["ma60"], "ma120": latest["ma120"],
            "performance": performance,
            "signal": signal(latest["close"], latest["ma20"], latest["ma60"], latest["ma120"], rsi),
            "chart": chart,
            "source_url": f"https://finance.naver.com/item/main.naver?code={stock_code}",
        }
    except Exception:
        return {}
