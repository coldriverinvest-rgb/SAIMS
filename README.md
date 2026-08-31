# FUTURE:M RADAR

POSCO퓨처엠을 중심으로 경쟁사·고객사의 공시, 뉴스, 재무정보를 모니터링하고 AI 브리핑을 제공하는 Streamlit 대시보드입니다.

## 주요 기능

- OpenDART 최근 공시 조회 및 원문 링크
- Google News RSS 기반 기업 뉴스 모니터링
- Gemini/OpenAI 기반 뉴스·공시 분석
- 기업별 재무 건전성·수익성 분석
- 모니터링 기업 추가 및 감성 필터
- Telegram 브리핑 발송
- 한 화면에서 확인 가능한 대시보드 UI

## 프로젝트 구조

```text
SAIMS/
├─ app.py                    # Streamlit 실행 진입점
├─ backend/
│  ├─ __init__.py
│  └─ config.py              # API 환경변수 및 기본 기업 목록
├─ frontend/
│  ├─ __init__.py
│  └─ components.py          # 화면용 재사용 컴포넌트
├─ .env.example              # 환경변수 예시
├─ requirements.txt          # Python 패키지 목록
└─ PRD.md                    # 제품 요구사항 문서
```

## 설치

Python 3.10 이상을 권장합니다.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 환경변수 설정

`.env.example`을 복사하여 `.env`를 만들고 실제 키를 입력합니다.

```powershell
Copy-Item .env.example .env
```

필수·선택 환경변수:

```env
DART_API_KEY=OpenDART_API_KEY
GEMINI_API_KEY=Gemini_API_KEY
GEMINI_MODEL=gemini-flash-lite-latest
OPENAI_API_KEY=OpenAI_API_KEY
TELEGRAM_BOT_TOKEN=Telegram_Bot_Token
TELEGRAM_CHAT_ID=Telegram_Chat_ID
```

`.env` 파일은 Git에 커밋하지 않습니다.

## 실행

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

브라우저에서 다음 주소를 엽니다.

```text
http://localhost:8501
```

## 사용 순서

1. 사이드바에서 모니터링 기업을 확인하거나 상장기업을 추가합니다.
2. `실시간 데이터 갱신`을 클릭합니다.
3. DART 공시 또는 뉴스 원문을 선택합니다.
4. AI 분석 결과와 전략 시사점을 확인합니다.
5. 필요한 경우 Telegram으로 브리핑을 발송합니다.

## 주의사항

- DART 기업명이 OpenDART 등록명과 다르면 공시가 조회되지 않을 수 있습니다.
- Gemini·OpenAI·Telegram 기능은 해당 API 키와 설정이 있을 때 활성화됩니다.
- API 호출 결과가 없거나 오류가 발생하면 대시보드는 빈 결과 또는 안내 메시지를 표시합니다.
