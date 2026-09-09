import { useEffect, useMemo, useState } from 'react';
import { ExternalLink, LoaderCircle, Send, X } from 'lucide-react';
import { api } from './api';
import { cellSummary, signalColumns } from './competitiveSignals.mjs';

export default function SignalDetailDrawer({ selection, onClose }) {
  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setQuestion('');
    setAnswer(null);
    setError('');
  }, [selection]);

  const context = useMemo(() => {
    if (!selection) return null;
    if (selection.sourceOnly) {
      const source = selection.sourceOnly;
      return {
        row: { company: '원자재 시장', evidence: [source] },
        column: { key: 'source', label: source.kind === 'KOMIS' ? 'KOMIS 가격 근거' : '수집 원문 근거' },
        cell: { items: [source], primary: source },
        source,
        analysis: `${source.title}의 공개 가격·기준일·규격만을 근거로 표시합니다. 가격 변화의 원인이나 향후 방향은 제공된 데이터만으로 단정하지 않습니다.`,
      };
    }
    const { row, columnKey, sourceId } = selection;
    const column = signalColumns.find(item => item.key === columnKey) || signalColumns[3];
    const cell = row.cells[column.key];
    const summary = cellSummary(column, cell);
    const source = sourceId ? row.evidence.find(item => item.source_id === sourceId) : cell.primary;
    const analysis = cell.primary
      ? `${row.company}의 ${column.label} 신호는 ${summary.headline}로 분류됩니다. ${column.key === 'risk' ? '재무·운영 리스크의 실제 규모 및 지속 여부를 원문에서 우선 확인하세요.' : '고객사, 투자 집행 시점 및 사업화 일정이 확인되면 자사 계획과 비교해야 합니다.'}`
      : `${row.company}에 대해 최근 30일 수집 표본에서 ${column.label} 관련 특이사항이 분류되지 않았습니다. 데이터 부재가 아니라 수집 범위 내 미탐지일 수 있습니다.`;
    return { row, column, cell, source, analysis };
  }, [selection]);

  if (!selection || !context) return null;
  const { row, column, cell, source, analysis } = context;
  const rawContent = source?.raw_content || source?.text || source?.summary || source?.title || '';

  const submitQuestion = async event => {
    event.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError('');
    setAnswer(null);
    try {
      setAnswer(await api.deepDive({
        signal_id: source?.source_id || `${row.company}-${column.key}`,
        signal_title: source?.title || `${row.company} ${column.label}`,
        raw_content: rawContent,
        question: question.trim(),
      }));
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  return <div className="signal-drawer-backdrop" role="presentation" onMouseDown={onClose}>
    <section className="signal-drawer" role="dialog" aria-modal="true" aria-label="전략 신호 상세" onMouseDown={event => event.stopPropagation()}>
      <button className="drawer-close" onClick={onClose} aria-label="상세 닫기"><X /></button>
      <span>STRATEGIC SIGNAL DETAIL</span>
      <h2>{row.company} · {column.label}</h2>
      <div className="drawer-summary"><b>AI 전략 영향도 분석</b><p>{analysis}</p></div>
      <h3>연계 공시·뉴스 원문</h3>
      {cell.items.length ? <div className="drawer-links">{cell.items.map((item, index) => <a className={item.source_id === source?.source_id ? 'is-grounding-source' : ''} key={`${item.link}-${index}`} href={item.link} target="_blank" rel="noreferrer"><span>{item.kind}</span><strong>{item.title}</strong><small>{item.date}</small><ExternalLink /></a>)}</div> : <p className="drawer-empty">연계된 근거가 없습니다.</p>}
      <section className="drawer-deep-dive">
        <div><span>GROUNDED Q&amp;A</span><h3>선택 원문에 질문하기</h3><p>{source ? `[${source.source_id}] ${source.title}` : '분석할 원문을 먼저 선택해 주세요.'}</p></div>
        <form onSubmit={submitQuestion}>
          <input value={question} onChange={event => setQuestion(event.target.value)} placeholder="예: 투자 금액과 집행 시점은 언제인가요?" aria-label="원문 심층 질문" disabled={!source || loading} />
          <button type="submit" disabled={!source || !question.trim() || loading}>{loading ? <LoaderCircle className="is-spinning" /> : <Send />} {loading ? '분석 중' : '질문'}</button>
        </form>
        {!source ? <p className="drawer-qa-hint">위 원문 목록에서 근거를 선택하거나 브리핑의 근거 태그를 클릭하세요.</p> : null}
        {error ? <p className="drawer-qa-error">{error}</p> : null}
        {answer ? <article className="drawer-answer"><strong>근거 기반 답변</strong><p>{answer.answer}</p>{answer.citations?.length ? <ul>{answer.citations.map((citation, index) => <li key={`${citation}-${index}`}>{citation}</li>)}</ul> : <small>직접 인용 가능한 근거가 없습니다.</small>}</article> : null}
      </section>
    </section>
  </div>;
}
