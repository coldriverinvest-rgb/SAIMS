"""환경변수와 모니터링 대상 설정."""

import os

from dotenv import load_dotenv

load_dotenv()

DART_API_KEY = os.getenv("DART_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

OWN_COMPANIES = ["포스코퓨처엠"]
COMPETITORS = ["포스코홀딩스", "LG화학", "에코프로비엠", "엘앤에프"]
CUSTOMERS = ["LG에너지솔루션", "삼성SDI", "SK온", "현대차"]
COMPANIES = OWN_COMPANIES + COMPETITORS + CUSTOMERS
DART_COLUMNS = ["rcept_dt", "corp_name", "report_nm", "rcept_no", "url"]
