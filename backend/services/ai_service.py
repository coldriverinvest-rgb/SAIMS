import json, requests
from openai import OpenAI
from langsmith import traceable
from backend.config import GEMINI_API_KEY, GEMINI_MODEL, OPENAI_API_KEY

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
