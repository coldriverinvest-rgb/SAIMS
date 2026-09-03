import re
from html.parser import HTMLParser

import OpenDartReader
import requests

from backend.config import DART_API_KEY


class DisclosureHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data):
        if self.skip_depth:
            return
        value = re.sub(r"\s+", " ", data).strip()
        if value:
            self.parts.append(value)


DISCLOSURE_KEYWORDS = (
    "성명", "보고자", "임원", "주요주주", "소유주식", "보유주식", "특정증권",
    "주식수", "증감", "변동", "취득", "매수", "처분", "매도", "지분율", "소유비율",
)


def focus_relevant_text(text: str, limit: int = 30000) -> str:
    if len(text) <= limit:
        return text
    excerpts = [text[:4000]]
    lowered = text.lower()
    used_ranges = []
    for keyword in DISCLOSURE_KEYWORDS:
        start = 0
        while True:
            index = lowered.find(keyword.lower(), start)
            if index < 0:
                break
            left, right = max(0, index - 700), min(len(text), index + 1400)
            if not any(left < used_right and right > used_left for used_left, used_right in used_ranges):
                excerpts.append(text[left:right])
                used_ranges.append((left, right))
            start = index + len(keyword)
            if sum(len(item) for item in excerpts) >= limit:
                return "\n---\n".join(excerpts)[:limit]
    return "\n---\n".join(excerpts)[:limit]


def fetch_disclosure_text(rcept_no: str) -> str:
    if not DART_API_KEY or not rcept_no:
        return ""
    html = ""
    try:
        html = OpenDartReader(DART_API_KEY).document(rcept_no)
    except Exception:
        html = ""
    if not html:
        try:
            page = requests.get(
                "https://dart.fss.or.kr/dsaf001/main.do",
                params={"rcpNo": rcept_no},
                headers={"User-Agent": "Mozilla/5.0 FUTURE-M-RADAR/2.0"},
                timeout=12,
            )
            page.raise_for_status()
            sections = []
            for block in page.text.split("var node1 = {};")[1:]:
                values = {}
                for key in ("dcmNo", "eleId", "offset", "length", "dtd"):
                    match = re.search(rf"node1\['{key}'\]\s*=\s*\"([^\"]*)\"", block)
                    if match:
                        values[key] = match.group(1)
                if len(values) != 5:
                    continue
                viewer = requests.get(
                    "https://dart.fss.or.kr/report/viewer.do",
                    params={"rcpNo": rcept_no, **values},
                    headers={"User-Agent": "Mozilla/5.0 FUTURE-M-RADAR/2.0"},
                    timeout=12,
                )
                if viewer.ok and viewer.content:
                    # DART's current report viewer serves section HTML as UTF-8,
                    # even when older response metadata suggests a Korean legacy charset.
                    sections.append(viewer.content.decode("utf-8", errors="replace"))
                if len(sections) >= 12:
                    break
            html = "\n".join(sections)
        except Exception:
            html = ""
    if not html:
        return ""
    try:
        parser = DisclosureHTMLParser()
        parser.feed(str(html))
        text = "\n".join(parser.parts)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return focus_relevant_text(text)
    except Exception:
        return ""
