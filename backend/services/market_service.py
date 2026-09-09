"""Reference macro-market indicators for the executive ticker bar."""

from datetime import date, timedelta
import requests


def fetch_usd_krw() -> dict:
    """Return the latest USD/KRW reference rate and prior observation change."""
    start = (date.today() - timedelta(days=14)).isoformat()
    try:
        response = requests.get(
            "https://api.frankfurter.dev/v2/rates",
            params={"base": "USD", "quotes": "KRW", "from": start},
            headers={"User-Agent": "FUTURE-M-RADAR/2.1"},
            timeout=10,
        )
        response.raise_for_status()
        observations = sorted(response.json(), key=lambda item: item["date"])
        if not observations:
            return {}
        latest = observations[-1]
        previous = observations[-2] if len(observations) > 1 else None
        change_pct = None
        if previous and previous.get("rate"):
            change_pct = round((latest["rate"] / previous["rate"] - 1) * 100, 2)
        return {
            "pair": "USD/KRW",
            "rate": latest["rate"],
            "change_pct": change_pct,
            "date": latest["date"],
            "source": "Frankfurter reference rates",
        }
    except (requests.RequestException, ValueError, TypeError, KeyError):
        return {}
