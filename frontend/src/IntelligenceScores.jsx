import { useMemo, useState } from 'react';
import { buildCompetitiveSignals } from './competitiveSignals.mjs';
import SignalMatrix from './SignalMatrix';
import SignalDetailDrawer from './SignalDetailDrawer';
import './intelligence-scores.css';

const coreCompanies=['포스코퓨처엠','에코프로비엠','엘앤에프','LG화학'];
export default function IntelligenceScores({data,companies,selectedCompany,onSelect,loading}) {
  const [scope,setScope]=useState('core'); const [selection,setSelection]=useState(null);
  const rows=useMemo(()=>buildCompetitiveSignals(companies,data),[companies,data]);
  const activeCompany=rows.some(row=>row.company===selectedCompany)?selectedCompany:'포스코퓨처엠';
  const visibleRows=scope==='core'?rows.filter(row=>coreCompanies.includes(row.company)):rows;
  const selectCompany=company=>{onSelect(company);setSelection(null);};
  if(loading)return <section className="competitive-page" aria-busy="true"><div className="competitive-loading">경쟁사 신호를 분석하고 있습니다…</div></section>;
  return <section className="competitive-page"><header className="competitive-page__title"><div><span>STRATEGY INTELLIGENCE</span><h1>경쟁사 신호 히트맵</h1><p>단순 수집 건수 대신 사업 영향도와 원문 근거를 중심으로 비교합니다.</p></div><div className="scope-toggle"><button className={scope==='core'?'active':''} onClick={()=>setScope('core')}>핵심 4개사</button><button className={scope==='all'?'active':''} onClick={()=>setScope('all')}>모니터링 전체</button></div></header><SignalMatrix rows={visibleRows} selectedCompany={activeCompany} onSelect={selectCompany} onCellSelect={(row,columnKey)=>{onSelect(row.company);setSelection({row,columnKey});}}/><SignalDetailDrawer selection={selection} onClose={()=>setSelection(null)}/></section>;
}
