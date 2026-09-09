export const signalColumns = [
  { key: 'orders', label: '수주·공급', tone: 'blue', words: /수주|공급계약|공급 계약|단일판매|계약체결|납품/i },
  { key: 'investment', label: '투자·CAPEX', tone: 'teal', words: /증설|신규시설|시설투자|양산|capex|투자/i },
  { key: 'technology', label: '기술·포트폴리오', tone: 'purple', words: /특허|전고체|lfp|미드니켈|실리콘|기술|상용화/i },
  { key: 'risk', label: '리스크 시그널', tone: 'red', words: /계약해지|계약 해지|적자|손실|소송|리콜|유상증자|채무보증|감산|권리락/i },
];
const riskLevel = { High: 3, Mid: 2, Low: 1 };
const asDate = (value = '') => /^\d{8}$/.test(value) ? `${value.slice(0,4)}-${value.slice(4,6)}-${value.slice(6,8)}` : value.slice(0, 10);
const extractAmount = (title = '') => title.match(/([\d,.]+)\s*억/)?.[1] ? `${title.match(/([\d,.]+)\s*억/)[1]}억` : title.match(/([\d,.]+)\s*조/)?.[1] ? `${title.match(/([\d,.]+)\s*조/)[1]}조` : null;
const riskName = title => /유상증자|권리락/.test(title) ? '유상증자' : /계약.?해지/.test(title) ? '계약 해지' : /채무보증/.test(title) ? '채무보증' : '리스크 점검';
const status = title => /해지|손실|적자|감산|유상증자/.test(title) ? '조정/주의' : /증설|시설투자|양산/.test(title) ? '진행 점검' : '신호 확인';

export function buildCompetitiveSignals(companies, data, now = new Date()) {
  const cutoff = now.getTime() - 30 * 86400000;
  const currentWeekStart = now.getTime() - 7 * 86400000;
  const previousWeekStart = now.getTime() - 14 * 86400000;
  const sources = [...(data?.disclosures || []).map(x => ({...x,kind:'DART 공시',title:x.report_nm || '',date:x.rcept_dt,link:x.url})), ...(data?.news || []).map(x => ({...x,kind:'뉴스',title:x.title || '',date:x.time,link:x.link}))];
  return companies.map(company => {
    const seen = new Set();
    const evidence = sources.filter(item => {
      if (item.corp_name !== company) return false;
      const stamp=Date.parse(asDate(item.date)), unique=`${item.kind}:${item.rcept_no || item.title.replace(/\s/g,'')}`;
      if (!Number.isFinite(stamp) || stamp < cutoff || stamp > now.getTime() || seen.has(unique)) return false;
      seen.add(unique); return true;
    }).map(item => {
      const signals=signalColumns.filter(column=>column.words.test(item.title)).map(column=>column.key);
      const amount=extractAmount(item.title), risk=signals.includes('risk') ? (/유상증자|계약.?해지|손실|적자/.test(item.title)?'High':'Mid') : 'Low';
      return {...item,date:asDate(item.date),timestamp:Date.parse(asDate(item.date)),signals,amount,risk,status:status(item.title)};
    });
    const currentEvidence=evidence.filter(item=>item.timestamp>=currentWeekStart);
    const previousEvidence=evidence.filter(item=>item.timestamp>=previousWeekStart&&item.timestamp<currentWeekStart);
    const cells=Object.fromEntries(signalColumns.map(column=>{
      const items=evidence.filter(item=>item.signals.includes(column.key));
      const primary=[...items].sort((a,b)=>riskLevel[b.risk]-riskLevel[a.risk])[0];
      const currentCount=currentEvidence.filter(item=>item.signals.includes(column.key)).length;
      const previousCount=previousEvidence.filter(item=>item.signals.includes(column.key)).length;
      const currentShare=currentEvidence.length?Math.round(currentCount/currentEvidence.length*100):0;
      const previousShare=previousEvidence.length?Math.round(previousCount/previousEvidence.length*100):0;
      const deltaPoints=currentEvidence.length&&previousEvidence.length?currentShare-previousShare:null;
      return [column.key,{items,primary,count:items.length,currentCount,previousCount,deltaPoints}];
    }));
    const classifiedEvidence=evidence.filter(item=>item.signals.length>0);
    const highRiskCount=classifiedEvidence.filter(item=>item.risk==='High').length;
    const issueCount=classifiedEvidence.length;
    const attention=highRiskCount>0||issueCount>=5
      ? {key:'check',label:'확인 필요',description:'고위험 또는 다수 이슈'}
      : issueCount>=3
        ? {key:'watch',label:'관찰 강화',description:'복수 이슈 지속 관찰'}
        : issueCount>=1
          ? {key:'normal',label:'일반 관찰',description:'일부 이슈 확인'}
          : {key:'none',label:'특이사항 없음',description:'분류 신호 없음'};
    return {company,evidence,cells,attention,issueCount,highRiskCount,evidenceCount:evidence.length};
  });
}

export function executiveBriefing(row) {
  const strongest=signalColumns.map(column=>({column,cell:row?.cells[column.key]})).filter(x=>x.cell?.primary).sort((a,b)=>(riskLevel[b.cell.primary.risk]-riskLevel[a.cell.primary.risk])||(b.cell.count-a.cell.count))[0];
  if (!row || !strongest) return ['금주 분류 가능한 핵심 이벤트가 없습니다.','현재 수집 표본에서는 별도 확인 신호가 없습니다.','공시·뉴스 수집 상태를 지속 점검하세요.'];
  const {column,cell}=strongest, event=cell.primary, label=event.amount?`${event.amount} 규모 신호`:`${event.kind} 기반 신호`;
  const effect=column.key==='risk'?'공급망·재무 안정성과 고객 대응 여력을 우선 점검해야 합니다.':column.key==='investment'?'경쟁사의 양산 타임라인과 고객사 확보 여부가 공급 경쟁을 바꿀 수 있습니다.':column.key==='orders'?'고객사·계약 기간이 확인되면 자사 수주 파이프라인과 비교가 필요합니다.':'소재 포트폴리오와 제품 로드맵의 중복·차별화 여부를 점검해야 합니다.';
  return [`핵심 이벤트: ${row.company} · ${event.title} (${label})`,`당사 영향도: ${effect}`,`대응 제언: ${event.status} 상태의 원문 근거와 후속 공시를 확인하세요.`];
}
export function issueSummary(row) {
  const strongest=signalColumns.map(column=>({column,cell:row?.cells[column.key]})).filter(item=>item.cell?.primary).sort((a,b)=>(riskLevel[b.cell.primary.risk]-riskLevel[a.cell.primary.risk])||(b.cell.count-a.cell.count))[0];
  if (!strongest) return { headline:'특이사항 없음', detail:'최근 30일 분류 신호 없음', columnKey:'risk' };
  const { column, cell }=strongest, event=cell.primary;
  const labels={orders:'수주·공급',investment:'투자·CAPEX',technology:'기술·포트폴리오',risk:'리스크'};
  const headline=column.key==='risk' ? `${riskName(event.title)} ${cell.count}건` : column.key==='technology' ? `${event.title.match(/LFP|전고체|실리콘|미드니켈/i)?.[0]||'기술'} 관련 ${cell.count}건` : `${labels[column.key]} ${event.amount||`${cell.count}건`}`;
  return { headline, detail:event.title, columnKey:column.key };
}
export function cellSummary(column, cell) {
  if (!cell?.primary) return {headline:'특이사항 없음',subline:'최근 30일 표본 기준',tags:[]};
  const item=cell.primary;
  if(column.key==='orders') return {headline:item.amount||`${cell.count}건 신호`,subline:'계약·고객사 확인',tags:['수주','고객사']};
  if(column.key==='investment') return {headline:item.amount||`${cell.count}건 신호`,subline:item.status,tags:['증설','CAPEX']};
  if(column.key==='technology') return {headline:item.title.match(/LFP|전고체|실리콘|미드니켈/i)?.[0]||'기술 신호',subline:`${cell.count}건 · 개발 진행`,tags:['기술']};
  return {headline:`${item.risk==='High'?'주의':'점검'} · ${riskName(item.title)}`,subline:`${cell.count}건 · ${item.risk}`,tags:[riskName(item.title)]};
}
