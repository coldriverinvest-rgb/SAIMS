import { cellSummary, issueSummary, signalColumns } from './competitiveSignals.mjs';
import './attention-status.css';
import './signal-matrix-summary.css';

function DeltaBadge({ value = 0, risk = false }) {
  if (value == null) return <span className="signal-delta is-flat">전주 비교 데이터 없음</span>;
  if (!value) return <span className="signal-delta is-flat">전주 대비 0pt</span>;
  const rising = value > 0;
  const state = risk ? (rising ? '위험' : '안정') : (rising ? '증가' : '감소');
  return <span className={`signal-delta ${rising ? 'is-up' : 'is-down'} ${risk && rising ? 'is-risk' : ''}`}>
    {rising ? '+' : ''}{value}pt {rising ? '▲' : '▼'} ({state})
  </span>;
}

export default function SignalMatrix({ rows, selectedCompany, onSelect, onCellSelect }) {
  return <section className="signal-matrix">
    <header className="signal-matrix__meta">
      <span>COMPETITIVE LANDSCAPE / 최근 30일</span>
      <small>셀 클릭 → 전략 분석 및 원문 근거</small>
    </header>
    <p className="signal-matrix__scroll-guide">좌우로 밀어 전체 신호를 확인하세요 →</p>
    <div className="signal-matrix__scroll" tabIndex="0" aria-label="경쟁사 신호 표, 작은 화면에서는 좌우 스크롤">
      <table>
        <thead><tr><th>기업</th>{signalColumns.map(column => <th key={column.key}>{column.label}</th>)}<th className="issue-summary-heading">주요 이슈 요약</th><th>모니터링 상태</th></tr></thead>
        <tbody>{rows.map(row => {
          const issue = issueSummary(row);
          return <tr className={row.company === selectedCompany ? 'is-selected' : ''} key={row.company}>
            <th><button onClick={() => onSelect(row.company)}>{row.company}</button><small>근거 {row.evidenceCount}건</small></th>
            {signalColumns.map(column => {
              const cell = row.cells[column.key];
              const summary = cellSummary(column, cell);
              const surging = column.key === 'risk' && cell.deltaPoints >= 15;
              return <td key={column.key}>
                <button className={`signal-cell signal-cell--${column.tone} ${!cell.primary ? 'is-empty' : ''} ${surging ? 'is-surging' : ''}`} onClick={() => onCellSelect(row, column.key)}>
                  <b>{summary.headline}</b><small>{summary.subline}</small>
                  <DeltaBadge value={cell.deltaPoints} risk={column.key === 'risk'} />
                  <span>{summary.tags.map(tag => <i key={tag}>[{tag}]</i>)}</span>
                </button>
              </td>;
            })}
            <td className="issue-summary-cell"><button className={`issue-summary issue-summary--${row.attention.key}`} onClick={() => onCellSelect(row, issue.columnKey)}><b>{issue.headline}</b><small title={issue.detail}>{issue.detail}</small></button></td>
            <td><button className={`attention-chip ${row.attention.key}`} onClick={() => onSelect(row.company)}><strong>{row.attention.label}</strong><small>{row.issueCount ? `주요 이슈 ${row.issueCount}건` : '분류 신호 없음'}</small></button></td>
          </tr>;
        })}</tbody>
      </table>
    </div>
    <footer><span className="legend-check">확인 필요</span><span className="legend-watch">관찰 강화</span><span className="legend-normal">일반 관찰</span><span className="legend-none">특이사항 없음</span><em>위험 신호가 전주 대비 15pt 이상 상승하면 테두리로 강조합니다.</em></footer>
    <details className="attention-guide"><summary>모니터링 상태 구분 기준 보기 <span>＋</span></summary><div><article><b>확인 필요</b><p>고위험 신호가 1건 이상이거나 분류된 주요 이슈가 5건 이상인 경우</p></article><article><b>관찰 강화</b><p>분류된 주요 이슈가 3~4건인 경우</p></article><article><b>일반 관찰</b><p>분류된 주요 이슈가 1~2건인 경우</p></article><article><b>특이사항 없음</b><p>최근 30일 수집 표본에서 분류된 주요 이슈가 없는 경우</p></article><small>※ 변화폭은 최근 7일과 직전 7일의 해당 신호 비중 차이(%p)이며, 투자 판단 점수가 아닙니다.</small></div></details>
  </section>;
}
