"""FUTURE:M RADAR backend configuration."""
import logging
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

# 서비스 계층의 예외를 조용히 삼키지 않도록 공용 로거 설정을 한 번만 적용합니다.
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

DART_API_KEY = os.getenv("DART_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME)
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "FUTURE:M RADAR")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() in {"1", "true", "yes", "on"}
SMTP_USE_SSL = os.getenv("SMTP_USE_SSL", "false").lower() in {"1", "true", "yes", "on"}
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
ALERT_POLL_SECONDS = max(60, int(os.getenv("ALERT_POLL_SECONDS", "300")))
ALERT_DATABASE_PATH = os.getenv("ALERT_DATABASE_PATH", str(ROOT_DIR / "data" / "saims_alerts.db"))
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "FUTURE-M-RADAR")
LANGSMITH_ENDPOINT = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")

# LangSmith decorators read their configuration from the environment. Keep
# tracing safely disabled until an API key is actually configured.
os.environ["LANGSMITH_PROJECT"] = LANGSMITH_PROJECT
os.environ["LANGSMITH_ENDPOINT"] = LANGSMITH_ENDPOINT
os.environ["LANGSMITH_TRACING"] = "true" if LANGSMITH_API_KEY else "false"

OWN_COMPANIES = ["포스코퓨처엠"]
COMPETITORS = ["포스코홀딩스", "LG화학", "에코프로비엠", "엘앤에프"]
CUSTOMERS = ["LG에너지솔루션", "삼성SDI", "SK온", "현대차"]
DEFAULT_COMPANIES = OWN_COMPANIES + COMPETITORS + CUSTOMERS
DART_COLUMNS = ["rcept_dt", "corp_name", "report_nm", "rcept_no", "url"]

# OpenDART 검색어와 실제 등록 법인명이 다른 경우의 매핑. 여러 서비스가 공유합니다.
# DART는 포스코홀딩스를 'POSCO홀딩스'(005490)로 등록하고 있어 한글 표기로는 조회되지 않습니다.
CORPORATE_NAME_ALIASES = {"현대차": "현대자동차", "SK온": "에스케이온", "포스코홀딩스": "POSCO홀딩스"}

# /api/intelligence 응답 캐시 수명(초). 0이면 매 요청마다 외부 소스를 다시 조회합니다.
INTELLIGENCE_CACHE_SECONDS = max(0, int(os.getenv("INTELLIGENCE_CACHE_SECONDS", "300")))
