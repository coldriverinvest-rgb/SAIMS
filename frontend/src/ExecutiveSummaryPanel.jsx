import { useState } from 'react';

const priorityLabel = { IMMEDIATE: '즉시', SHORT_TERM: '단기', MONITORING: '모니터링' };

function executiveGuide(item) {
  if (item.target_department.includes('구매') || item.target_department.includes('원료')) return {
    decision: '메탈 가격 변동을 구매단가·판가에 언제 반영할지 확정',
    metrics: '메탈 가격 변동률 · 판가 반영 시차 · 재고 노출액 · 원가 민감도',
  };
  if (item.target_department.includes('생산')) return {
    decision: '수요·고객 일정 변화에 따른 생산계획 조정 여부 결정',
    metrics: '가동률 · 고객 납기 · 생산계획 변경 폭 · 적정 재고일수',
  };
  return {
    decision: '당사 수주·투자계획에 미치는 영향과 담당 임원을 확정',
    metrics: '예상 수주 영향 · 경쟁사 양산 시점 · 고객 일정 · CAPEX 변경 필요액',
  };
}

function SourceChips({ ids = [], labels = {}, onSelect, activeSource }) {
  if (!ids.length) return <small className="source-empty">근거 미연결</small>;
  return <span className="source-chips">{ids.map(id => <button className={id === activeSource ? 'is-active' : ''} key={id} type="button" title={`근거 ID: ${id}`} onClick={() => onSelect?.(id)}>{labels[id] || '근거 문서'}</button>)}</span>;
}

export default function ExecutiveSummaryPanel({ briefing, loading, error, onSourceSelect, sourceLabels }) {
  const [activeSource, setActiveSource] = useState('');
  const selectSource = id => { setActiveSource(id); onSourceSelect?.(id); };
  return <aside className="executive-panel executive-print-area" aria-busy={loading}>
    <div className="executive-panel__head">
      <span>AI EXECUTIVE BRIEFING</span>
    </div>
    {loading ? <p className="briefing-state">수집 원문을 근거로 경영 브리핑을 생성하고 있습니다…</p> : error ? <p className="briefing-state is-error">{error}</p> : briefing ? <>
      <div className="briefing-hero"><small>HEADLINE</small><strong>{briefing.headline}</strong><p>{briefing.market_status}</p></div>
      <section className="executive-brief"><h3>KEY TAKEAWAYS</h3>{briefing.key_takeaways.map((item, index) => <article key={`${item.point}-${index}`}><b>0{index + 1}</b><div><p>{item.point}</p><SourceChips ids={item.source_ids} labels={sourceLabels} onSelect={selectSource} activeSource={activeSource} /></div></article>)}</section>
      <section className="recommended-actions"><div className="recommended-actions__title"><div><h3>STRATEGIC ACTIONS</h3><strong>경영진 의사결정 포인트</strong></div><p>무엇을 결정하고 어떤 숫자를 확인할지 우선순위별로 정리했습니다.</p></div><div>{briefing.recommended_actions.map((item, index) => { const guide = executiveGuide(item); return <article key={`${item.action_title}-${index}`}><header><span className={`priority-badge ${item.priority.toLowerCase()}`}>{priorityLabel[item.priority] || item.priority}</span><small>담당 · {item.target_department}</small></header><strong>{item.action_title}</strong><p className="action-rationale">{item.action_description}</p><dl className="executive-checklist"><div><dt>결정할 것</dt><dd>{guide.decision}</dd></div><div><dt>회의 확인 지표</dt><dd>{guide.metrics}</dd></div></dl><SourceChips ids={item.rationales} labels={sourceLabels} onSelect={selectSource} activeSource={activeSource} /></article>; })}</div></section>
    </> : <p className="briefing-state">브리핑 데이터가 없습니다.</p>}
  </aside>;
}
