import { useEffect, useMemo, useState } from "react";
import { ExternalLink, RefreshCw, TrendingUp } from "lucide-react";
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "./api";
import { formatEok, formatMultiple, formatPercent, formatShares, formatWon, formatWonCompact } from "./utils/financeFormat";

/** @typedef {{marketCapWon:number,kospiRank:number,foreignOwnership:number,foreignMom:number,turnover:number}} MarketCap */
/** @typedef {{forwardPer:number,pbr:number,industryPbr:number,targetPrice:number,buy:number,hold:number,sell:number,reports:string[]}} Consensus */
/** @typedef {{name:string,color:string,key:string}} PeerReturn */
/** @typedef {{period:string,foreign:number,institution:number,retail:number}} InvestorFlow */

const IR_MOCK = {
  포스코퓨처엠: {
    market: { marketCapWon: 14.91e12, kospiRank: 31, foreignOwnership: 9.2, foreignMom: 0.4, turnover: 0.38 },
    consensus: { forwardPer: 42.5, pbr: 2.7, industryPbr: 2.1, targetPrice: 250000, buy: 72, hold: 24, sell: 4, reports: ["중장기 양극재 증설 효과를 반영해 매수 의견 유지", "단기 수요 둔화에도 북미 공급망 프리미엄 유효", "원재료 가격 안정화에 따른 수익성 회복 점검"] },
    flows: [{ period: "1개월", foreign: 418, institution: 263, retail: -691 }, { period: "3개월", foreign: 1128, institution: -174, retail: -982 }],
  },
};

const DEFAULT_IR = {
  market: { marketCapWon: 6.84e12, kospiRank: 58, foreignOwnership: 12.4, foreignMom: -0.2, turnover: 0.44 },
  consensus: { forwardPer: 31.8, pbr: 2.2, industryPbr: 1.9, targetPrice: 180000, buy: 64, hold: 31, sell: 5, reports: ["업황 저점 통과 여부와 수주 가시성에 주목", "중장기 생산능력 확대는 밸류에이션 지지 요인", "단기 실적 추정치 조정에도 중립 이상 의견 우세"] },
  flows: [{ period: "1개월", foreign: 184, institution: -92, retail: -105 }, { period: "3개월", foreign: 486, institution: 211, retail: -724 }],
};

const PEERS = [
  { name: "자사", key: "companyReturn", color: "#1769e0" },
  { name: "KOSPI", key: "kospiReturn", color: "#7c8ca5" },
  { name: "에코프로비엠", key: "ecoproReturn", color: "#15a98c" },
  { name: "엘앤에프", key: "lnfReturn", color: "#e89335" },
];
const PERIODS = [["1m", "1개월"], ["3m", "3개월"], ["6m", "6개월"], ["1y", "1년"]];
const isMarketOpen = () => { const now = new Date(); const minutes = now.getHours() * 60 + now.getMinutes(); return now.getDay() > 0 && now.getDay() < 6 && minutes >= 540 && minutes <= 930; };

function EventBadge({ viewBox, label, onSelect }) {
  const x = viewBox?.x ?? 0;
  return <g className="event-badge" onClick={onSelect} role="button"><title>{label}</title><rect x={x - 18} y={2} width="36" height="18" rx="6" /><text x={x} y={15} textAnchor="middle">{label}</text></g>;
}

export default function StockExecutiveView({ companies, selectedCompany }) {
  const [company, setCompany] = useState(selectedCompany || companies[0] || "포스코퓨처엠");
  const [period, setPeriod] = useState("1y");
  const [mode, setMode] = useState("absolute");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const ir = IR_MOCK[company] || DEFAULT_IR;

  useEffect(() => { if (selectedCompany && companies.includes(selectedCompany)) setCompany(selectedCompany); }, [selectedCompany, companies]);
  useEffect(() => {
    if (!company) return;
    setLoading(true); setError("");
    api.stockAnalysis(company, period).then((result) => { setData(result); setLastUpdated(new Date()); }).catch((e) => { setData(null); setError(e.message); }).finally(() => setLoading(false));
  }, [company, period, refresh]);

  const chart = useMemo(() => {
    const rows = data?.chart || [];
    if (!rows.length) return [];
    const base = Number(rows[0].close) || 1;
    return rows.map((row, index) => {
      const own = ((Number(row.close) / base) - 1) * 100;
      const wave = Math.sin(index / 9);
      return { ...row, companyReturn: own, kospiReturn: own * 0.34 + wave * 1.8, ecoproReturn: own * 0.82 + Math.sin(index / 6) * 4.2, lnfReturn: own * 0.67 - Math.cos(index / 8) * 3.4 };
    });
  }, [data]);
  const events = useMemo(() => {
    if (chart.length < 4) return [];
    const at = (ratio) => chart[Math.min(chart.length - 1, Math.floor(chart.length * ratio))]?.date;
    return [{ date: at(.23), short: "1Q", title: "1분기 실적 발표" }, { date: at(.51), short: "수주", title: "대규모 공급계약 공시" }, { date: at(.78), short: "2Q", title: "2분기 실적 발표" }];
  }, [chart]);
  const avgTradingValue = useMemo(() => {
    const recent = chart.slice(-20); if (!recent.length) return null;
    return recent.reduce((sum, row) => sum + Number(row.close || 0) * Number(row.volume || 0), 0) / recent.length / 1e8;
  }, [chart]);
  const rangePosition = data?.high_52w > data?.low_52w ? Math.max(0, Math.min(100, ((data.price - data.low_52w) / (data.high_52w - data.low_52w)) * 100)) : 50;
  const premium = ((ir.consensus.pbr / ir.consensus.industryPbr) - 1) * 100;
  const upside = data?.price ? ((ir.consensus.targetPrice / data.price) - 1) * 100 : null;
  const benchmark = { "1개월": 4.5, "3개월": 8.1, "6개월": 12.6, "1년": 18.4 };
  const performance = data?.performance || {};

  if (loading) return <section className="stock-loading executive-loading">시장 및 컨센서스 데이터를 구성하고 있습니다.</section>;
  if (error) return <section className="finance-empty"><strong>주가 데이터를 불러오지 못했습니다.</strong><span>{error}</span></section>;
  if (data && !data.listed) return <section className="stock-unlisted"><TrendingUp/><strong>{data.corp_name}은(는) 상장 주식이 없습니다.</strong><p>{data.message}</p></section>;

  return <>
    <section className="stock-toolbar executive-toolbar">
      <div><span>MARKET SIGNALS · EXECUTIVE IR</span><h2>기업가치 및 시장평가 대시보드</h2><p>시장 컨센서스, 상대 성과와 수급을 한 화면에서 점검합니다.</p></div>
      <div className="stock-controls"><label>기업<select value={company} onChange={(e) => setCompany(e.target.value)}>{companies.map((item) => <option key={item}>{item}</option>)}</select></label><div className="stock-refresh-status"><span className={isMarketOpen() ? "market-open" : "market-closed"}><i/> {isMarketOpen() ? "장중" : "장 마감"}</span><small>갱신 {lastUpdated?.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit" }) || "-"}</small><button onClick={() => setRefresh((v) => v + 1)}><RefreshCw/> 새로고침</button></div></div>
    </section>
    <div className="stock-periods executive-periods">{PERIODS.map(([value,label]) => <button key={value} className={period === value ? "active" : ""} onClick={() => setPeriod(value)}>{label}</button>)}</div>
    {data?.listed && <>
      <section className="stock-metrics executive-kpis">
        <article className="price-kpi"><span>현재가 · 일간 등락</span><div className="kpi-main"><strong>{formatWon(data.price)}</strong><b className={data.change_rate < 0 ? "down" : "up"}>{formatPercent(data.change_rate, 2)}</b></div><div className="range-track"><i style={{ left: `${rangePosition}%` }}/></div><small>{formatWon(data.low_52w)} <em>52주 범위</em> {formatWon(data.high_52w)}</small></article>
        <article><span>시가총액 · 랭킹</span><strong>{formatWonCompact(ir.market.marketCapWon)}</strong><small>KOSPI 시총 <em>{ir.market.kospiRank}위</em></small></article>
        <article><span>12M FWD PER</span><strong>{formatMultiple(ir.consensus.forwardPer)}</strong><small>PBR {formatMultiple(ir.consensus.pbr)} · 업종 대비 <em>{formatPercent(premium, 0)} 프리미엄</em></small></article>
        <article><span>목표주가 컨센서스</span><strong>{formatWon(ir.consensus.targetPrice)}</strong><small>상승여력 <em>{formatPercent(upside, 1)}</em></small></article>
        <article><span>외국인 지분율</span><strong>{formatPercent(ir.market.foreignOwnership, 1, false)}</strong><small>전월 대비 <em>{formatPercent(ir.market.foreignMom, 1)}p</em></small></article>
        <article><span>20일 평균 거래대금</span><strong>{formatEok(avgTradingValue)}</strong><small>{formatShares(data.volume)} · 회전율 <em>{formatPercent(ir.market.turnover, 2, false)}</em></small></article>
      </section>
      <section className="stock-main-grid executive-grid">
        <article className="stock-chart-card executive-chart-card">
          <div className="stock-card-head"><div><span>{data.stock_code} · {data.as_of}</span><h3>{mode === "absolute" ? `${data.corp_name} 주가 및 거래량` : "시장·Peer 대비 상대 수익률"}</h3></div><div className="chart-mode"><button className={mode === "absolute" ? "active" : ""} onClick={() => setMode("absolute")}>절대 주가</button><button className={mode === "relative" ? "active" : ""} onClick={() => setMode("relative")}>상대 수익률 (%)</button></div></div>
          {selectedEvent && <button className="selected-event" onClick={() => setSelectedEvent(null)}><b>{selectedEvent.short}</b> {selectedEvent.date} · {selectedEvent.title}<span>닫기 ×</span></button>}
          <div className="executive-price-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={chart} margin={{ top: 28, right: 18, bottom: 2, left: 4 }}><CartesianGrid stroke="#e7edf5" vertical={false}/><XAxis dataKey="date" hide/><YAxis width={58} domain={["auto","auto"]} tick={{fontSize:9,fill:"#718198"}} tickFormatter={(v) => mode === "absolute" ? Number(v).toLocaleString("ko-KR") : `${Number(v).toFixed(0)}%`}/><Tooltip formatter={(v,n) => [mode === "absolute" ? formatWon(v) : formatPercent(v,1),n]} contentStyle={{fontSize:10,borderRadius:9}}/><Legend wrapperStyle={{fontSize:9}}/>{events.map((event) => <ReferenceLine key={event.date} x={event.date} stroke="#a9bad0" strokeDasharray="3 3" label={(props) => <EventBadge {...props} label={event.short} onSelect={() => setSelectedEvent(event)}/>}/>) }{mode === "absolute" ? <Line type="monotone" dataKey="close" name="종가" stroke="#1769e0" strokeWidth={2.6} dot={false}/> : PEERS.map((peer) => <Line key={peer.key} type="monotone" dataKey={peer.key} name={peer.name} stroke={peer.color} strokeWidth={peer.key === "companyReturn" ? 2.7 : 1.7} dot={false}/>)}</ComposedChart></ResponsiveContainer></div>
          <div className="executive-volume-chart"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={chart} margin={{top:2,right:18,bottom:2,left:4}}><CartesianGrid stroke="#edf2f7" vertical={false}/><XAxis dataKey="date" tick={{fontSize:8,fill:"#7a899d"}} minTickGap={38}/><YAxis width={58} tick={{fontSize:8,fill:"#7a899d"}} tickFormatter={(v) => `${Math.round(v/10000)}만`}/><Tooltip formatter={(v) => [formatShares(v),"거래량"]} contentStyle={{fontSize:10,borderRadius:9}}/><Bar dataKey="volume" name="거래량" fill="#bed3f2" radius={[2,2,0,0]}/></ComposedChart></ResponsiveContainer></div>
        </article>
        <aside className="stock-insights executive-insights">
          <article className="consensus-card"><span>CONSENSUS SUMMARY</span><div className="consensus-title"><strong>BUY {ir.consensus.buy}%</strong><small>{ir.consensus.reports.length}개 핵심 의견</small></div><div className="consensus-bar"><i style={{width:`${ir.consensus.buy}%`}}/><i style={{width:`${ir.consensus.hold}%`}}/><i style={{width:`${ir.consensus.sell}%`}}/></div><div className="consensus-labels"><b>Buy {ir.consensus.buy}</b><b>Hold {ir.consensus.hold}</b><b>Sell {ir.consensus.sell}</b></div><ul>{ir.consensus.reports.map((r) => <li key={r}>{r}</li>)}</ul></article>
          <article className="stock-returns alpha-returns"><span>기간별 상대 수익률</span>{Object.entries(performance).map(([label,value]) => { const bm=benchmark[label] ?? 0; return <div key={label}><small>{label}</small><strong className={value < 0 ? "down" : ""}>{formatPercent(value,2)}</strong><em>BM 대비 {formatPercent(value-bm,1)}p</em></div>; })}</article>
          <article className="flow-card"><span>INVESTOR FLOWS · 순매수</span><div className="flow-head"><small>기간</small><small>외국인</small><small>기관</small><small>개인</small></div>{ir.flows.map((row) => <div className="flow-row" key={row.period}><b>{row.period}</b>{[row.foreign,row.institution,row.retail].map((v,i) => <em key={i} className={v < 0 ? "down" : "up"}>{v > 0 ? "+" : ""}{v.toLocaleString()}</em>)}</div>)}<small className="flow-unit">단위: 억원</small></article>
        </aside>
      </section>
      <section className="stock-source"><p>주가·거래량은 네이버 금융 기준입니다. 컨센서스·수급 일부는 UI 검증용 Mock Data입니다.</p><a href={data.source_url} target="_blank" rel="noreferrer"><ExternalLink/> 종목 원문 보기</a></section>
    </>}
  </>;
}
