import { useEffect, useMemo, useState } from 'react';
import { api } from './api';
import { buildCompetitiveSignals, executiveBriefing as companyBriefing } from './competitiveSignals.mjs';
import ExecutiveSummaryPanel from './ExecutiveSummaryPanel';
import SignalMatrix from './SignalMatrix';
import SignalDetailDrawer from './SignalDetailDrawer';
import './intelligence-scores.css';
import './executive-briefing.css';

const coreCompanies = ['포스코퓨처엠', '에코프로비엠', '엘앤에프', 'LG화학'];

function sourceKeyword(item, type) {
  const raw = String(item.report_nm || item.title || item.name || '').replace(/\s+/g, ' ').trim();
  const topic = (raw.split(/[·:—–-]/)[0] || raw).replace(/^(주요\s*)?(공시|뉴스)\s*/i, '').trim();
  const short = topic.length > 18 ? `${topic.slice(0, 18)}…` : topic;
  return `${type} · ${short || '원문'}`;
}

function localBriefing(rows) {
  const priorityRow = [...rows].sort((a, b) => b.highRiskCount - a.highRiskCount || b.issueCount - a.issueCount)[0];
  const lines = companyBriefing(priorityRow);
  const sourceIds = priorityRow?.evidence.map(item => item.source_id).filter(Boolean).slice(0, 3) || [];
  return {
    headline: priorityRow ? `${priorityRow.company}의 최근 주요 신호를 우선 점검해야 합니다.` : '수집된 근거 데이터를 점검하고 있습니다.',
    market_status: 'AI 종합 브리핑 API 연결 전에도 최근 30일 공시·뉴스 분류 결과를 기준으로 표시합니다.',
    key_takeaways: lines.map((point, index) => ({ point, source_ids: sourceIds[index] ? [sourceIds[index]] : sourceIds.slice(0, 1) })),
    signal_analysis: [],
    recommended_actions: [
      { priority: 'IMMEDIATE', target_department: '사업전략', action_title: '수주·투자 영향 등급 확정', action_description: '금주 경영회의에서 핵심 신호가 당사 수주와 투자계획에 미치는 영향을 상·중·하로 판정하고 담당 임원을 지정합니다.', rationales: sourceIds },
      { priority: 'SHORT_TERM', target_department: '구매/원료', action_title: '메탈 가격 손익 민감도 재산정', action_description: '리튬·니켈 등 가격 변동과 판가 반영 시차를 기준으로 원가 및 재고 손익 시나리오를 이번 주 안에 비교합니다.', rationales: sourceIds },
      { priority: 'MONITORING', target_department: '생산기획', action_title: '가동률·납기 재보고 기준 설정', action_description: '고객 일정이나 물량 변동이 가동률과 납기에 영향을 주는 경우 경영진에게 재보고할 기준을 설정합니다.', rationales: sourceIds },
    ],
  };
}

export default function IntelligenceScores({ data, companies, selectedCompany, onSelect, loading }) {
  const [scope, setScope] = useState('core');
  const [selection, setSelection] = useState(null);
  const [briefing, setBriefing] = useState(null);
  const [briefingLoading, setBriefingLoading] = useState(false);
  const [briefingError, setBriefingError] = useState('');
  const [materialSources, setMaterialSources] = useState([]);
  const rows = useMemo(() => buildCompetitiveSignals(companies, data), [companies, data]);
  const sourceLabels = useMemo(() => {
    const labels = {};
    (data.disclosures || []).forEach(item => { if (item.source_id) labels[item.source_id] = sourceKeyword(item, '공시'); });
    (data.news || []).forEach(item => { if (item.source_id) labels[item.source_id] = sourceKeyword(item, '뉴스'); });
    materialSources.forEach(item => { labels[`KOMIS-${String(item.id).toUpperCase()}`] = `KOMIS · ${item.name} 가격`; });
    return labels;
  }, [data, materialSources]);
  const activeCompany = rows.some(row => row.company === selectedCompany) ? selectedCompany : '포스코퓨처엠';
  const visibleRows = scope === 'core' ? rows.filter(row => coreCompanies.includes(row.company)) : rows;
  const companyKey = companies.join(',');

  useEffect(() => {
    if (loading || !companies.length) return undefined;
    let active = true;
    setBriefingLoading(true);
    setBriefingError('');
    Promise.allSettled([api.executiveBriefing(companies), api.materials()])
      .then(([briefingResult, materialsResult]) => {
        if (!active) return;
        if (briefingResult.status === 'fulfilled') setBriefing(briefingResult.value);
        else {
          setBriefing(localBriefing(rows));
          setBriefingError('');
        }
        if (materialsResult.status === 'fulfilled') setMaterialSources(materialsResult.value.items || []);
      })
      .finally(() => { if (active) setBriefingLoading(false); });
    return () => { active = false; };
  }, [loading, companyKey, data]);

  const selectCompany = company => {
    onSelect(company);
    setSelection(null);
  };
  const openSource = sourceId => {
    for (const row of rows) {
      const source = row.evidence.find(item => item.source_id === sourceId);
      if (!source) continue;
      onSelect(row.company);
      if (source.signals[0]) setSelection({ row, columnKey: source.signals[0], sourceId });
      else setSelection({ sourceOnly: source });
      return;
    }
    const collectedSource = [...(data.disclosures || []), ...(data.news || [])].find(item => item.source_id === sourceId);
    if (collectedSource) {
      setSelection({ sourceOnly: {
        ...collectedSource,
        kind: collectedSource.rcept_no ? 'DART 공시' : '뉴스',
        title: collectedSource.report_nm || collectedSource.title,
        date: collectedSource.rcept_dt || collectedSource.time,
        link: collectedSource.url || collectedSource.link,
        raw_content: collectedSource.text || collectedSource.summary || collectedSource.report_nm || collectedSource.title || '',
      } });
      return;
    }
    const material = materialSources.find(item => `KOMIS-${String(item.id).toUpperCase()}` === sourceId);
    if (material) {
      const sourceOnly = {
        source_id: sourceId,
        kind: 'KOMIS',
        title: `${material.name} 공개 가격`,
        date: material.date,
        link: material.source,
        raw_content: `품목 ${material.name}; 가격 ${material.price} ${material.unit}; 전일 대비 ${material.change_pct}%; 가격 기준일 ${material.date}; 가격 규격 ${material.grade}`,
      };
      setSelection({ sourceOnly });
    }
  };

  if (loading) return <section className="competitive-page" aria-busy="true"><div className="competitive-loading">경쟁사 신호를 분석하고 있습니다…</div></section>;
  return <section className="competitive-page">
    <header className="competitive-page__title"><div><span>STRATEGY INTELLIGENCE</span><h1>경쟁사 신호 히트맵</h1><p>수집 원문, 위험도 변화와 실행 권고안을 하나의 근거 흐름으로 비교합니다.</p></div><div className="scope-toggle"><button className={scope === 'core' ? 'active' : ''} onClick={() => setScope('core')}>핵심 4개사</button><button className={scope === 'all' ? 'active' : ''} onClick={() => setScope('all')}>모니터링 전체</button></div></header>
    <ExecutiveSummaryPanel briefing={briefing} loading={briefingLoading} error={briefingError} onSourceSelect={openSource} sourceLabels={sourceLabels} />
    <SignalMatrix rows={visibleRows} selectedCompany={activeCompany} onSelect={selectCompany} onCellSelect={(row, columnKey) => { onSelect(row.company); setSelection({ row, columnKey }); }} />
    <SignalDetailDrawer selection={selection} onClose={() => setSelection(null)} />
  </section>;
}
