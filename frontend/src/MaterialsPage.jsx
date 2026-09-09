import {useEffect, useRef, useState} from 'react';
import {ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid} from 'recharts';
import {api} from './api';
import './materials.css';

export default function MaterialsPage() {
  const [data,setData]=useState(null), [error,setError]=useState(''), [busy,setBusy]=useState(false);
  const [selected,setSelected]=useState('lithium'), [days,setDays]=useState(30);
  const [news,setNews]=useState([]), [newsBusy,setNewsBusy]=useState(false), [newsError,setNewsError]=useState('');
  const pending=useRef(false);
  const refresh=async()=>{
    if(pending.current)return;
    pending.current=true;setBusy(true);
    try {const r=await fetch(`${import.meta.env.VITE_API_BASE_URL || '/api'}/materials`); if(!r.ok)throw new Error('가격 조회 실패'); setData(await r.json());setError('');}
    catch {setError('가격을 불러오지 못했습니다. 새로고침해 주세요.');}
    finally{pending.current=false;setBusy(false);}
  };
  useEffect(()=>{refresh();const timer=setInterval(()=>{if(!document.hidden)refresh();},10000);return()=>clearInterval(timer);},[]);
  useEffect(()=>{
    let active=true;setNewsBusy(true);setNewsError('');
    api.materialNews(selected).then(result=>{if(active)setNews(result.items||[]);}).catch(()=>{if(active){setNews([]);setNewsError('관련 뉴스를 불러오지 못했습니다.');}}).finally(()=>{if(active)setNewsBusy(false);});
    return()=>{active=false;};
  },[selected]);
  const item=data?.items.find(x=>x.id===selected);
  const cutoff=new Date();cutoff.setDate(cutoff.getDate()-days);
  const points=(item?.history || []).filter(x=>new Date(x.date)>=cutoff);
  return <section className="materials-widget">
    <header><div><span>BATTERY MATERIALS / PRICE MONITOR</span><h3>원자재 가격 동향</h3><p>KOMIS 공개 시세 · 서버가 1시간마다 자동 수집 · 실시간 체결가 아님</p></div><button disabled={busy} onClick={refresh}>{busy?'조회 중…':'↻ 저장 가격 새로고침'}</button></header>
    {(error || data?.error) && <p role="status">{error || data.error}</p>}
    {!data && <p>{busy?'KOMIS 수집 가격을 확인하고 있습니다.':'데이터 대기 중'}</p>}
    <p role="status">{data?.collecting ? '백엔드 수집 진행 중…' : data?.checked_at ? `최근 수집 시도 ${new Date(data.checked_at).toLocaleString('ko-KR')}` : '서버 시작 후 첫 수집 대기 중'}</p><div className="material-cards">{data?.items.map(m=><button key={m.id} className={selected===m.id?'selected':''} onClick={()=>setSelected(m.id)}><span>{m.name}</span><strong>{m.price===null?'—':m.price.toLocaleString('en-US',{maximumFractionDigits:2})}</strong><small>{m.price===null?'공개 데이터 미연결':m.unit}</small><b className={m.change_pct>0?'up':'down'}>{m.change_pct===null?'가격 확인 필요':`${m.change_pct>0?'+':''}${m.change_pct.toFixed(2)}%`}</b><small>{m.date?`가격 기준 ${m.date}`:'KOMIS 공개 시세 미확인'}</small></button>)}</div>
    <p>품목별 통화·중량 단위와 가격 규격을 확인하세요. 아래 기간은 확보된 이력 범위 내에서 표시됩니다.</p>
    <section className="material-news">
      <div className="material-news-head"><div><span>MINERAL MARKET INTELLIGENCE</span><h3>{item?.name || '원자재'} 광물시장 주요 뉴스</h3><p>배터리 일반 뉴스는 제외하고 광산·채굴·제련·생산·재고·수출입·가격 이슈만 선별합니다.</p></div><small>{newsBusy?'뉴스 추출 중…':`${news.length}건`}</small></div>
      {newsError&&<div className="material-news-empty">{newsError}</div>}
      {!newsError&&!newsBusy&&news.length===0&&<div className="material-news-empty">선택한 원자재의 주요 뉴스가 없습니다.</div>}
      <div className="material-news-grid">{news.map((article,index)=><article key={`${article.link}-${index}`}>
        <div><span className={`metal-signal ${article.tone}`}>{article.signal}</span><time>{article.time}</time></div>
        <h4>{article.title}</h4>
        <p>{article.summary||'기사 원문에서 세부 내용을 확인하세요.'}</p>
        <footer><span>{article.source}</span>{article.link&&<a href={article.link} target="_blank" rel="noreferrer">원문 보기 ↗</a>}</footer>
      </article>)}</div>
    </section>
    {item && <div className="material-detail"><div className="material-chart-head"><div><strong>{item.name} · 공개 가격 추이</strong><p>{item.grade} / {item.unit}</p></div><div>{[30,90,180,365].map(d=><button key={d} className={days===d?'selected':''} onClick={()=>setDays(d)}>{d===365?'1년':`${d}일`}</button>)}</div></div>
      {points.length>=2?<ResponsiveContainer width="100%" height={330}><LineChart data={points} margin={{top:10,right:20,bottom:5,left:15}}><CartesianGrid stroke="#e5edf5" vertical={false}/><XAxis dataKey="date" tick={{fontSize:10}}/><YAxis domain={['auto','auto']} tick={{fontSize:10}}/><Tooltip formatter={v=>[`${Number(v).toLocaleString()} ${item.unit}`,item.name]}/><Line dataKey="price" stroke="#288b9d" strokeWidth={2} dot={{r:3}} connectNulls={false}/></LineChart></ResponsiveContainer>:<div className="material-empty">{item.price===null?'이 규격의 공개 가격을 조회하지 못했습니다. 원문에서 확인해 주세요.':`첫 공표 가격을 저장했습니다 (${item.date}). 다른 기준일 가격이 쌓이면 추이 그래프가 표시됩니다.`}</div>}
      <footer><span>{item.collected_at?`최근 수집 ${new Date(item.collected_at).toLocaleString('ko-KR')}`:'수집 이력 없음'} · 등락률은 직전 공표 가격 대비</span><a href={item.source} target="_blank" rel="noreferrer">KOMIS 출처 확인 ↗</a></footer></div>}
  </section>;
}
