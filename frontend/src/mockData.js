/** API 미연결 디자인 검토·컴포넌트 테스트용 Mock Data */
export const mockIntelligence = {
  disclosures: [
    { rcept_dt: "2026-08-31", corp_name: "LG에너지솔루션", report_nm: "단일판매ㆍ공급계약체결", rcept_no: "20260831000001", url: "https://dart.fss.or.kr", is_major: true, major_label: "주요" },
    { rcept_dt: "2026-08-31", corp_name: "포스코퓨처엠", report_nm: "신규시설투자등", rcept_no: "20260831000002", url: "https://dart.fss.or.kr", is_major: true, major_label: "주요" },
  ],
  news: [
    { title: "삼성SDI, 글로벌 고객사와 LFP 배터리 공급 협력", source: "산업뉴스", time: "2026-08-31 08:10", link: "https://news.google.com", summary: "공급망 협력 관련 뉴스 요약", corp_name: "삼성SDI", group_type: "고객사", ai: { sentiment: "기회", priority: "MID", strategy_tag: "호재/수주", strategy_type: "opportunity" } },
    { title: "경쟁사 양극재 생산능력 증설 계획 발표", source: "배터리데일리", time: "2026-08-31 07:30", link: "https://news.google.com", summary: "증설 투자 관련 뉴스 요약", corp_name: "에코프로비엠", group_type: "경쟁사", ai: { sentiment: "중립", priority: "MID", strategy_tag: "증설/투자", strategy_type: "investment" } },
  ],
  daily_briefing: [
    "주요 공시: 고객사 공급계약 및 신규시설투자 공시를 우선 확인하세요.",
    "기회 신호: LFP 공급망 협력이 소재 수요에 미치는 영향을 점검하세요.",
    "경쟁사 증설 일정과 자사 CAPEX·고객 대응 전략을 비교 검토하세요.",
  ],
};
