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


def signal(price: float, ma20: float | None, ma60: float | None, rsi: float | None):
    if rsi is not None and rsi >= 70:
        return {"label": "과열 주의", "tone": "risk", "description": "RSI가 과매수 구간에 진입했습니다. 단기 변동성 확대 가능성을 점검하세요."}
    if rsi is not None and rsi <= 30:
        return {"label": "낙폭 과대", "tone": "opportunity", "description": "RSI가 과매도 구간입니다. 실적·수급 확인 후 반등 가능성을 검토하세요."}
    if ma20 and ma60 and price > ma20 > ma60:
        return {"label": "상승 추세", "tone": "opportunity", "description": "주가가 단기·중기 이동평균을 상회합니다. 추세 지속 여부와 거래량을 확인하세요."}
    if ma20 and ma60 and price < ma20 < ma60:
        return {"label": "하락 추세", "tone": "risk", "description": "주가가 단기·중기 이동평균을 하회합니다. 실적 모멘텀과 지지 구간을 점검하세요."}
    return {"label": "중립 구간", "tone": "neutral", "description": "이동평균과 모멘텀 신호가 혼재합니다. 방향성 확인 전까지 수급 변화를 관찰하세요."}


def fetch_stock_analysis(corp_name: str, period: str = "1y") -> dict:
    stock_code = resolve_stock_code(corp_name)
    if not stock_code:
        return {"listed": False, "corp_name": corp_name, "message": "비상장 기업이거나 주식 종목코드를 확인할 수 없습니다."}
    try:
        response = requests.get(
            "https://fchart.stock.naver.com/sise.nhn",
            params={"symbol": stock_code, "timeframe": "day", "count": 320, "requestType": 0},
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
        if len(rows) < 2:
            return {}
        closes = [row["close"] for row in rows]
        for index, row in enumerate(rows):
            row["ma20"] = moving_average(closes, 20, index)
            row["ma60"] = moving_average(closes, 60, index)
            row["ma120"] = moving_average(closes, 120, index)
        latest, previous = rows[-1], rows[-2]
        returns = [closes[index] / closes[index - 1] - 1 for index in range(1, len(closes)) if closes[index - 1]]
        volatility = round(stdev(returns[-252:]) * sqrt(252) * 100, 1) if len(returns) > 2 else None
        rsi = calculate_rsi(closes)
        period_count = PERIOD_POINTS.get(period, PERIOD_POINTS["1y"])
        chart = rows[-period_count:]
        year_rows = rows[-260:]
        average_volume = round(sum(row["volume"] for row in rows[-20:]) / min(20, len(rows)))
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
            "rsi14": rsi, "volatility": volatility,
            "ma20": latest["ma20"], "ma60": latest["ma60"], "ma120": latest["ma120"],
            "performance": performance,
            "signal": signal(latest["close"], latest["ma20"], latest["ma60"], rsi),
            "chart": chart,
            "source_url": f"https://finance.naver.com/item/main.naver?code={stock_code}",
        }
    except Exception:
        return {}
