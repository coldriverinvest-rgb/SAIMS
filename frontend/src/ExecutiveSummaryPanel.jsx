const ISSUE = {
  headline: '에코프로비엠 대규모 유상증자 단행에 따른 증설 경쟁 및 양극재 수급 영향 점검',
  takeaways: [
    { type: 'FACT', text: '에코프로비엠 유상증자 권리락 발생 및 시설자금 조달 공시', sources: ['DART 26.09.08'] },
    { type: 'INDUSTRY IMPACT', text: '북미·유럽 설비 CAPEX 격차 확대 및 Peer 주도 증설 경쟁 심화', sources: ['조선비즈'] },
    { type: 'INTERNAL IMPACT', text: '당사 NCM·하이니켈 수주 파이프라인 방어 및 차입·투자 여력 대비 필요', sources: ['내부 전략 분석'] },
  ],
  metrics: [
    { label: '조달 규모', value: '1.2조 원', detail: '시설 8,000억 · 운영 4,000억', tone: 'money' },
    { label: '예상 신주 발행비율', value: '15.4%', detail: '기존 주주 가치 희석', tone: 'dilution' },
    { label: '시그널 위험도', value: 'HIGH RISK', detail: 'Peer CAPEX 격차', tone: 'risk' },
    { label: '당사 연계 영향도', value: '사업전략', detail: '수주 파이프라인 대응', tone: 'impact' },
  ],
};

export default function ExecutiveSummaryPanel({ loading, error }) {
  return <aside className="executive-panel executive-print-area executive-panel--compact" aria-busy={loading}>
    <div className="executive-panel__head"><span>AI EXECUTIVE BRIEFING</span></div>
    {loading ? <p className="briefing-state">경쟁사 공시와 시장 영향을 분석하고 있습니다…</p> : error ? <p className="briefing-state is-error">{error}</p> : <>
      <div className="executive-impact-grid">
        <section className="briefing-core">
          <div className="briefing-hero"><small>HEADLINE</small><strong>{ISSUE.headline}</strong></div>
          <div className="executive-takeaways">{ISSUE.takeaways.map((item, index) => <article key={item.type}><b>0{index + 1}</b><div><span>{item.type}</span><p>{item.text}</p><footer>{item.sources.map(source => <em key={source}>{source}</em>)}</footer></div></article>)}</div>
        </section>
        <section className="impact-summary"><div>{ISSUE.metrics.map(item => <article className={item.tone} key={item.label}><small>{item.label}</small><strong>{item.value}</strong><p>{item.detail}</p></article>)}</div></section>
      </div>
    </>}
  </aside>;
}
