# FUTURE:M RADAR

POSCO퓨처엠을 중심으로 경쟁사·고객사의 공시, 뉴스, 재무정보를 모니터링하고 AI 브리핑을 제공하는 분리형 웹 애플리케이션입니다.

## 기술 구조

- Frontend: React, Vite, Lucide React
- Backend: FastAPI, OpenDartReader, feedparser, Gemini/OpenAI, pandas
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8001`
- API 문서: `http://localhost:8001/docs`

```text
FUTURE_M_RADAR/
├─ frontend/
│  ├─ src/
│  │  ├─ App.jsx          # 화면 및 사용자 흐름
│  │  ├─ api.js           # 백엔드 API 연결
│  │  └─ styles.css       # 디자인 시스템
│  ├─ package.json
│  └─ vite.config.js
├─ backend/
│  ├─ services/
│  │  ├─ dart_service.py
│  │  ├─ news_service.py
│  │  ├─ finance_service.py
│  │  ├─ ai_service.py
│  │  └─ telegram_service.py
│  ├─ config.py
│  ├─ schemas.py
│  └─ main.py             # FastAPI 진입점
├─ .env
├─ .env.example
└─ requirements.txt
```

## 설치

Backend:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Frontend:

```powershell
cd frontend
npm install
```

## 환경변수

`.env.example`을 `.env`로 복사한 뒤 API 키를 입력합니다.

```env
DART_API_KEY=
GEMINI_API_KEY=
GEMINI_MODEL=gemini-flash-lite-latest
OPENAI_API_KEY=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=FUTURE-M-RADAR
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
```

`LANGSMITH_API_KEY`를 입력하면 AI 분석 요청·응답, 실행시간 및 오류가
`FUTURE-M-RADAR` 프로젝트에 자동으로 기록됩니다. 키가 비어 있으면 추적은
자동으로 비활성화됩니다.

## 실행

터미널 1 — Backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8001
```

터미널 2 — Frontend:

```powershell
cd frontend
npm run dev
```

브라우저에서 `http://localhost:5173`을 엽니다.

## 빌드

```powershell
cd frontend
npm run build
```

빌드 결과는 `frontend/dist`에 생성됩니다.
