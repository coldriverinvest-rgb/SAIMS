"""FUTURE:M RADAR backend configuration."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

DART_API_KEY = os.getenv("DART_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
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
