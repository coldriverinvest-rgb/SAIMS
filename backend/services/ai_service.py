import hashlib
import json
import re

import requests
from openai import OpenAI
from langsmith import traceable
from backend.config import GEMINI_API_KEY, GEMINI_MODEL, OPENAI_API_KEY
from backend.schemas import DeepDiveRequest, DeepDiveResponse, ExecutiveBriefingResponse

GROUNDING_FAILURE = "제공된 데이터에서 확인할 수 없습니다"


def make_source_id(source: dict, index: int = 0) -> str:
    """Return a stable, human-readable identifier shared by API and UI."""
    existing = str(source.get("source_id") or "").strip()
    if existing:
        return existing
    source_type = str(source.get("source_type") or source.get("kind") or "SOURCE").upper()
    prefix = "DART" if "DART" in source_type or source.get("rcept_no") else "KOMIS" if "KOMIS" in source_type else "NEWS"
    identity = str(source.get("rcept_no") or source.get("link") or source.get("url") or source.get("title") or index)
    if prefix == "DART" and source.get("rcept_no"):
        suffix = re.sub(r"[^0-9A-Za-z_-]", "", str(source["rcept_no"]))
    elif prefix == "KOMIS" and source.get("material"):
        suffix = re.sub(r"[^0-9A-Za-z_-]", "", str(source["material"]).upper())
    else:
        suffix = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:10].upper()
    return f"{prefix}-{suffix or index + 1}"


def assign_source_ids(raw_data_sources: list) -> list[dict]:
    prepared = []
    for index, source in enumerate(raw_data_sources or []):
        if not isinstance(source, dict):
            source = {"content": str(source)}
        clean = dict(source)
        clean["source_id"] = make_source_id(clean, index)
        prepared.append(clean)
    return prepared


def _model_dump(model):
    return model.model_dump() if hasattr(model, "model_dump") else model.dict()


def _model_schema(model):
    return model.model_json_schema() if hasattr(model, "model_json_schema") else model.schema()


def _gemini_schema(model):
    """Inline Pydantic $refs because generateContent responseSchema rejects them."""
    schema = _model_schema(model)
    definitions = schema.get("$defs", schema.get("definitions", {}))

    def expand(node):
        if isinstance(node, list):
            return [expand(item) for item in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:
            name = node["$ref"].split("/")[-1]
            resolved = expand(definitions.get(name, {}))
            return {**resolved, **{key: expand(value) for key, value in node.items() if key != "$ref"}}
        return {
            key: expand(value)
            for key, value in node.items()
            if key not in {"$defs", "definitions", "title", "default", "additionalProperties"}
        }

    return expand(schema)


def _validate_model(model, payload):
    return model.model_validate(payload) if hasattr(model, "model_validate") else model.parse_obj(payload)


def _source_context(sources: list[dict], limit: int = 70000) -> str:
    blocks, used = [], 0
    for source in sources:
        payload = {
            "source_id": source["source_id"],
            "source_type": source.get("source_type") or source.get("kind") or "unknown",
            "title": source.get("title") or source.get("name") or "제목 없음",
            "date": source.get("date") or source.get("rcept_dt") or "",
            "company": source.get("company") or source.get("corp_name") or "",
            "content": source.get("content") or source.get("raw_content") or source.get("summary") or source.get("text") or "",
            "figures": source.get("figures") or {},
        }
        block = json.dumps(payload, ensure_ascii=False, default=str)
        if used + len(block) > limit:
            break
        blocks.append(block)
        used += len(block)
    return "\n".join(blocks)


def _fallback_briefing(sources: list[dict]) -> ExecutiveBriefingResponse:
    source_ids = [source["source_id"] for source in sources]
    takeaways = []
    for source in sources[:3]:
        title = str(source.get("title") or source.get("name") or "수집 데이터")
        takeaways.append({"point": f"{title} 원문 신호가 수집되었습니다. 세부 영향은 근거 원문 확인이 필요합니다.", "source_ids": [source["source_id"]]})
    while len(takeaways) < 3:
        takeaways.append({"point": "추가로 확인 가능한 근거 데이터가 없습니다.", "source_ids": []})
    primary_ids = source_ids[:3]
    return ExecutiveBriefingResponse(
        headline=f"현재 수집 근거 {len(sources)}건을 기준으로 주요 신호를 점검해야 합니다.",
        market_status="AI 연결이 없거나 응답 검증에 실패하여 수집 원문 기준 브리핑을 표시합니다.",
        key_takeaways=takeaways,
        signal_analysis=[{
            "category": "데이터 검증",
            "issue_name": "수집 원문 교차 확인",
            "severity": "MONITORING",
            "impact_analysis": "수집된 제목만으로 사업 영향을 단정할 수 없어 담당 부서의 원문 검증이 필요합니다.",
            "source_ids": primary_ids,
        }],
        recommended_actions=[
            {"priority": "IMMEDIATE", "target_department": "사업전략", "action_title": "수주·투자 영향 등급 확정", "action_description": "금주 경영회의에서 상위 신호가 당사 수주와 투자계획에 미치는 영향을 상·중·하로 판정하고 담당 임원을 지정합니다.", "rationales": primary_ids},
            {"priority": "SHORT_TERM", "target_department": "구매/원료", "action_title": "메탈 가격 손익 민감도 점검", "action_description": "리튬·니켈 등 가격 변동의 구매단가 및 판가 반영 시차를 확인하고 원가 민감도 시나리오를 비교합니다.", "rationales": ([sid for sid in source_ids if sid.startswith("KOMIS-")][:3] or primary_ids)},
            {"priority": "MONITORING", "target_department": "생산기획", "action_title": "생산계획 재보고 기준 설정", "action_description": "고객 일정·물량 변화가 가동률과 납기에 영향을 주는 경우 경영진에게 재보고할 기준을 설정합니다.", "rationales": primary_ids},
        ],
    )


def _parse_openai(model, system: str, prompt: str):
    client = OpenAI(api_key=OPENAI_API_KEY)
    parse = getattr(client.chat.completions, "parse", None)
    if parse is None:
        parse = client.beta.chat.completions.parse
    response = parse(
        model="gpt-4o-2024-08-06",
        temperature=0.1,
        response_format=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": prompt}],
    )
    message = response.choices[0].message
    if getattr(message, "parsed", None):
        return message.parsed
    raise ValueError(getattr(message, "refusal", None) or "Structured response was empty")


def _parse_gemini(model, system: str, prompt: str):
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",
        headers={"Content-Type": "application/json", "x-goog-api-key": GEMINI_API_KEY},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
                "responseSchema": _gemini_schema(model),
            },
        },
        timeout=45,
    )
    response.raise_for_status()
    payload = json.loads(response.json()["candidates"][0]["content"]["parts"][0]["text"])
    return _validate_model(model, payload)

def default_result():
    return {"summary_points":["핵심 사실과 즉시 사업 영향을 확인해 주세요.","고객·경쟁사 및 배터리 소재 밸류체인 파급 효과를 점검해 주세요.","포스코퓨처엠의 영업·투자·기술 대응 과제로 검토해 주세요."],"sentiment":"중립","priority":"LOW","strategic_implication":"원문 확인 후 포스코퓨처엠 사업계획 반영 여부를 경영진 검토 안건으로 판단해 주세요.","business_impact":"고객 수요와 경쟁 구도, 소재 공급망에 미치는 영향을 함께 점검해야 합니다.","keyword_tags":[],"key_figures":[]}

def validate_result(result):
    base=default_result()
    if not isinstance(result,dict): return base
    points=[str(x) for x in result.get("summary_points",[]) if x]
    sentiment=result.get("sentiment","중립"); priority=str(result.get("priority","LOW")).upper()
    tags=result.get("keyword_tags",[])
    figures=result.get("key_figures",[])
    clean_figures=[]
    if isinstance(figures,list):
        for figure in figures[:6]:
            if isinstance(figure,dict) and figure.get("label") and figure.get("value"):
                clean_figures.append({"label":str(figure["label"]),"value":str(figure["value"])})
    return {"summary_points":(points+base["summary_points"])[:3],"sentiment":sentiment if sentiment in {"기회","주의","중립"} else "중립","priority":priority if priority in {"HIGH","MID","LOW"} else "LOW","strategic_implication":str(result.get("strategic_implication") or base["strategic_implication"]),"business_impact":str(result.get("business_impact") or base["business_impact"]),"keyword_tags":[str(tag) for tag in tags][:6] if isinstance(tags,list) else [],"key_figures":clean_figures}

@traceable(name="FUTURE:M RADAR AI Analysis", run_type="chain")
def analyze(title: str, text: str, group_type: str):
    system="당신은 배터리/소재 산업 전문 경영전략 수석 애널리스트입니다."
    prompt=f'''{group_type} 관련 공시/뉴스를 분석하세요. 경쟁사 CAPEX 증설·특허는 주의, 고객사 신규 수주·공급망 재편은 기회로 우선 분류하세요.
제목: {title}
본문: {text}

summary_points 세 문장은 단순 출처나 분석 대기 문구가 아니라 각각 독립적인 경영 임플리케이션이어야 합니다.
1번: 핵심 사실과 포스코퓨처엠에 미치는 즉시 사업 영향
2번: 고객·경쟁사 및 배터리 소재 밸류체인 관점의 시사점
3번: 포스코퓨처엠이 취해야 할 구체적인 영업·투자·기술 대응 방향
근거가 부족하면 단정하지 말고 '확인 필요' 항목을 구체적으로 명시하세요.
임원·주요주주 특정증권 소유상황보고서라면 반드시 원문 표에서 보고자/변동 주체, 취득·처분 구분, 이번 변동 주식 수, 변동 후 보유 주식 수, 변동 전후 지분율을 찾아 요약하세요. 숫자는 쉼표와 단위를 포함해 정확히 쓰고, 원문에 없는 값은 추정하지 마세요.
key_figures에는 경영진이 바로 확인해야 할 구체적인 계약금액·투자금액·주식 수·지분율·CAPEX·기간 등 원문 수치를 최대 6개 넣으세요.

JSON만 반환하세요: {{"summary_points":["핵심 사실과 즉시 사업 영향","밸류체인 시사점","포스코퓨처엠 대응 방향"],"sentiment":"기회|주의|중립","priority":"HIGH|MID|LOW","strategic_implication":"경영진을 위한 한 줄 전략 제언","business_impact":"자사 및 밸류체인 관점의 사업적 영향","keyword_tags":["키워드1","키워드2","키워드3"],"key_figures":[{{"label":"변동 주체","value":"홍길동"}},{{"label":"취득 주식 수","value":"10,000주"}}]}}'''
    if GEMINI_API_KEY:
        try:
            response=requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent",headers={"Content-Type":"application/json","x-goog-api-key":GEMINI_API_KEY},json={"systemInstruction":{"parts":[{"text":system}]},"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.2,"responseMimeType":"application/json"}},timeout=35)
            response.raise_for_status(); return validate_result(json.loads(response.json()["candidates"][0]["content"]["parts"][0]["text"]))
        except Exception: pass
    if OPENAI_API_KEY:
        try:
            client=OpenAI(api_key=OPENAI_API_KEY); response=client.chat.completions.create(model="gpt-4o",temperature=0.2,response_format={"type":"json_object"},messages=[{"role":"system","content":system},{"role":"user","content":prompt}])
            return validate_result(json.loads(response.choices[0].message.content))
        except Exception: pass
    return default_result()


@traceable(name="FUTURE:M RADAR Executive Briefing", run_type="chain")
def generate_executive_briefing(raw_data_sources: list) -> ExecutiveBriefingResponse:
    sources = assign_source_ids(raw_data_sources)
    if not sources:
        return _fallback_briefing([])
    allowed_ids = {source["source_id"] for source in sources}
    system = """당신은 배터리 소재·공급망 전문 C-Level 전략 애널리스트입니다.
Zero-Hallucination 원칙을 최우선으로 적용하세요. 제공된 CONTEXT 밖의 사실·원인·수치·전망을 추론하거나 날조하지 마세요.
모든 핵심 주장과 수치에는 CONTEXT에 존재하는 source_id를 연결하세요. 근거가 부족하면 '제공된 데이터에서 확인할 수 없습니다'라고 명시하세요.
단순 사실 나열이 아니라 당사 밸류체인 영향과 구매/원료, 사업전략, 생산기획 등 담당 부서의 구체적 대응으로 연결하세요.
recommended_actions는 최소 3개이며 priority는 IMMEDIATE, SHORT_TERM, MONITORING 중 하나만 사용하세요.
각 action_title은 '검토/확인' 같은 추상 표현 대신 경영진이 내려야 할 결정을 쓰세요.
각 action_description에는 의사결정 시점, 판단 대상, 확인할 경영지표(수주·원가·판가 시차·가동률·CAPEX 등)를 근거 범위 안에서 구체적으로 포함하세요.
반드시 지정된 JSON Schema에 맞는 한국어 응답만 반환하세요."""
    prompt = f"""아래 근거 데이터만 사용해 경영진 브리핑을 작성하세요.

[CONTEXT]
{_source_context(sources)}

[작성 기준]
- headline: 가장 중요한 변화와 경영 의미를 한 문장으로 작성
- market_status: 확인된 사실의 방향성과 데이터 한계를 함께 작성
- key_takeaways: 각 항목마다 1개 이상의 source_id 연결
- signal_analysis: 심각도와 당사 밸류체인 영향 작성, 각 항목에 source_id 연결
- recommended_actions: 최소 3개, rationales에는 판단 근거가 된 source_id만 기재
- CONTEXT에 없는 수치, 기업 관계, 인과관계는 작성 금지"""
    result = None
    for provider in ("gemini", "openai"):
        try:
            if provider == "gemini" and GEMINI_API_KEY:
                result = _parse_gemini(ExecutiveBriefingResponse, system, prompt)
            elif provider == "openai" and OPENAI_API_KEY:
                result = _parse_openai(ExecutiveBriefingResponse, system, prompt)
            if result:
                break
        except Exception:
            continue
    if not result:
        return _fallback_briefing(sources)

    payload = _model_dump(result)
    for item in payload.get("key_takeaways", []) + payload.get("signal_analysis", []):
        item["source_ids"] = [sid for sid in item.get("source_ids", []) if sid in allowed_ids]
    for item in payload.get("recommended_actions", []):
        item["rationales"] = [sid for sid in item.get("rationales", []) if sid in allowed_ids]
    if any(not item.get("source_ids") for item in payload.get("key_takeaways", [])):
        return _fallback_briefing(sources)
    if any(not item.get("source_ids") for item in payload.get("signal_analysis", [])):
        return _fallback_briefing(sources)
    if len(payload.get("recommended_actions", [])) < 3:
        fallback_actions = _model_dump(_fallback_briefing(sources))["recommended_actions"]
        payload["recommended_actions"] = (payload.get("recommended_actions", []) + fallback_actions)[:3]
    try:
        return _validate_model(ExecutiveBriefingResponse, payload)
    except Exception:
        return _fallback_briefing(sources)


@traceable(name="FUTURE:M RADAR Signal Deep Dive", run_type="chain")
def deep_dive_signal(request: DeepDiveRequest) -> DeepDiveResponse:
    raw_content = request.raw_content.strip()
    question = request.question.strip()
    if not raw_content or not question:
        return DeepDiveResponse(answer=f"{GROUNDING_FAILURE}.", citations=[])
    system = f"""당신은 배터리 소재·공급망 원문 검증 분석가입니다.
오직 SOURCE_ID={request.signal_id}의 RAW_CONTENT만 근거로 답하세요.
원문 밖의 지식, 추정, 일반론을 추가하지 마세요. 질문의 답이 원문에 없으면 정확히 '{GROUNDING_FAILURE}'라고 답하세요.
수치·날짜·조항을 언급할 때는 원문의 해당 문구를 citations에 짧게 직접 인용하세요.
반드시 지정된 JSON Schema에 맞는 한국어 응답만 반환하세요."""
    prompt = f"""신호 제목: {request.signal_title}
사용자 질문: {question}

[RAW_CONTENT]
{raw_content[:60000]}

answer에는 결론과 근거를 간결히 작성하고 citations에는 원문에서 직접 확인되는 조항 번호·수치·문구만 넣으세요."""
    result = None
    for provider in ("gemini", "openai"):
        try:
            if provider == "gemini" and GEMINI_API_KEY:
                result = _parse_gemini(DeepDiveResponse, system, prompt)
            elif provider == "openai" and OPENAI_API_KEY:
                result = _parse_openai(DeepDiveResponse, system, prompt)
            if result:
                break
        except Exception:
            continue
    if not result:
        excerpt = " ".join(raw_content.split())[:240]
        return DeepDiveResponse(
            answer=f"AI 분석 연결을 사용할 수 없어 원문 발췌만 제공합니다. 질문의 답은 {GROUNDING_FAILURE}.",
            citations=[f"[{request.signal_id}] {excerpt}"] if excerpt else [],
        )
    payload = _model_dump(result)
    normalized_raw = " ".join(raw_content.split())
    valid_citations = []
    for citation in payload.get("citations", []):
        clean = " ".join(str(citation).strip().strip('"“”').split())[:500]
        without_source = re.sub(r"^\[[^\]]+\]\s*", "", clean)
        if len(without_source) >= 4 and without_source in normalized_raw:
            valid_citations.append(f"[{request.signal_id}] {without_source}")
    payload["citations"] = valid_citations[:8]
    if not payload["citations"] and GROUNDING_FAILURE not in str(payload.get("answer", "")):
        payload["answer"] = f"{GROUNDING_FAILURE}."
    try:
        return _validate_model(DeepDiveResponse, payload)
    except Exception:
        return DeepDiveResponse(answer=f"{GROUNDING_FAILURE}.", citations=[])
