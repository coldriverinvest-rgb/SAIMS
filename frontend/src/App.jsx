import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  BarChart3,
  BatteryCharging,
  BellRing,
  Building2,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  FileText,
  Newspaper,
  Plus,
  RefreshCw,
  Send,
  Sparkles,
  Tag,
  TrendingUp,
  X,
} from "lucide-react";
import { api } from "./api";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  LabelList,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const COMPANY_GROUPS = {
  "자사/그룹": ["포스코퓨처엠", "포스코홀딩스"],
  경쟁사: ["에코프로비엠", "엘앤에프", "LG화학"],
  고객사: ["LG에너지솔루션", "삼성SDI", "SK온", "현대차"],
};
const DEFAULT_COMPANIES = Object.values(COMPANY_GROUPS).flat();
const EMPTY_AI = {
  summary_points: [],
  sentiment: "중립",
  priority: "LOW",
  strategic_implication: "분석할 공시 또는 뉴스를 선택하세요.",
  business_impact: "",
  keyword_tags: [],
  key_figures: [],
};
const tagClass = (item) => item.ai?.strategy_type || "neutral";

function Skeleton({ rows = 4 }) {
  return (
    <div className="skeleton-list">
      {Array.from({ length: rows }, (_, i) => (
        <div className="skeleton-row" key={i}>
          <i />
          <div>
            <b />
            <em />
          </div>
          <span />
        </div>
      ))}
    </div>
  );
}

function Sidebar({
  collapsed,
  setCollapsed,
  view,
  setView,
  companies,
  setCompanies,
  selectedCompany,
  setSelectedCompany,
  onRefresh,
  loading,
}) {
  const [newCompany, setNewCompany] = useState("");
  const addCompany = async () => {
    const value = newCompany.trim();
    if (!value || companies.includes(value)) return;
    try {
      const result = await api.validateCompany(value);
      setCompanies((items) => [...items, result.corp_name]);
      setNewCompany("");
    } catch (error) {
      alert(error.message);
    }
  };
  return (
    <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
      <button
        className="collapse-button"
        onClick={() => setCollapsed(!collapsed)}
        aria-label="사이드바 전환"
      >
        {collapsed ? <ChevronRight /> : <ChevronLeft />}
      </button>
      <div className="brand">
        <span className="brand-icon">
          <BatteryCharging />
        </span>
        <div>
          <strong>FUTURE:M RADAR</strong>
          <small>BATTERY MATERIALS INTELLIGENCE</small>
        </div>
      </div>
      {!collapsed && (
        <>
          <p className="side-label">분석 카테고리</p>
          <nav>
            <button
              className={view === "intel" ? "active" : ""}
              onClick={() => setView("intel")}
            >
              <Activity /> 산업 인텔리전스
            </button>
            <button
              className={view === "finance" ? "active" : ""}
              onClick={() => setView("finance")}
            >
              <BarChart3 /> 기업 재무분석
            </button>
            <button
              className={view === "stocks" ? "active" : ""}
              onClick={() => setView("stocks")}
            >
              <TrendingUp /> 주가 분석
            </button>
          </nav>
          <p className="side-label">모니터링 풀</p>
          <div className="company-tabs">
            <button
              className={!selectedCompany ? "selected" : ""}
              onClick={() => setSelectedCompany("")}
            >
              전체
            </button>
            {Object.keys(COMPANY_GROUPS).map((group) => (
              <button
                key={group}
                className="group-tab"
                onClick={() => setSelectedCompany("")}
              >
                {group}
              </button>
            ))}
          </div>
          {Object.entries(COMPANY_GROUPS).map(([group, items]) => (
            <div className="company-group" key={group}>
              <span>{group}</span>
              <div className="company-pool">
                {items
                  .filter((company) => companies.includes(company))
                  .map((company) => (
                    <button
                      className={
                        selectedCompany === company
                          ? "company-chip selected"
                          : "company-chip"
                      }
                      key={company}
                      onClick={() =>
                        setSelectedCompany(
                          selectedCompany === company ? "" : company,
                        )
                      }
                    >
                      {company}
                      <X
                        onClick={(event) => {
                          event.stopPropagation();
                          setCompanies(
                            companies.filter((item) => item !== company),
                          );
                          if (selectedCompany === company)
                            setSelectedCompany("");
                        }}
                      />
                    </button>
                  ))}
              </div>
            </div>
          ))}
          {companies.filter((company) => !DEFAULT_COMPANIES.includes(company))
            .length > 0 && (
            <div className="company-group">
              <span>추가 기업</span>
              <div className="company-pool">
                {companies
                  .filter((company) => !DEFAULT_COMPANIES.includes(company))
                  .map((company) => (
                    <button
                      className={
                        selectedCompany === company
                          ? "company-chip selected"
                          : "company-chip"
                      }
                      key={company}
                      onClick={() =>
                        setSelectedCompany(
                          selectedCompany === company ? "" : company,
                        )
                      }
                    >
                      {company}
                      <X
                        onClick={(event) => {
                          event.stopPropagation();
                          setCompanies(
                            companies.filter((item) => item !== company),
                          );
                        }}
                      />
                    </button>
                  ))}
              </div>
            </div>
          )}
          <p className="side-label">상장기업 추가</p>
          <input
            value={newCompany}
            onChange={(e) => setNewCompany(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addCompany()}
            placeholder="예: 롯데에너지머티리얼즈"
          />
          <button className="add-button" onClick={addCompany}>
            <Plus /> 모니터링 기업 추가
          </button>
          <button
            className="refresh-button"
            onClick={onRefresh}
            disabled={loading}
          >
            <RefreshCw className={loading ? "spin" : ""} />{" "}
            {loading ? "데이터 수집 중" : "실시간 데이터 갱신"}
          </button>
        </>
      )}
    </aside>
  );
}

function Header({ status }) {
  return (
    <header className="top-header">
      <div>
        <span className="eyebrow">EXECUTIVE INTELLIGENCE PLATFORM</span>
        <h1>FUTURE:M RADAR</h1>
        <p>BATTERY MATERIALS · DISCLOSURE · NEWS · FINANCIAL SIGNALS</p>
      </div>
      <div className="status-row">
        <span className={status.dart ? "ready" : "offline"}>
          ● DART {status.dart ? "CONNECTED" : "OFFLINE"}
        </span>
        <span className={status.ai ? "ready" : "offline"}>
          ● AI {status.ai ? "READY" : "OFFLINE"}
        </span>
        <small>{new Date().toLocaleString("ko-KR")}</small>
      </div>
    </header>
  );
}

function DailyBriefing({ lines, loading }) {
  return (
    <section className="daily-brief">
      <div className="daily-mark">
        <Sparkles />
        <span>
          AI DAILY
          <br />
          EXECUTIVE BRIEFING
        </span>
      </div>
      <div className="daily-lines">
        {loading ? (
          <Skeleton rows={3} />
        ) : (
          (lines.length
            ? lines
            : ["실시간 데이터 갱신 후 오늘의 핵심 신호를 제공합니다."]
          ).map((line, index) => (
            <p key={index}>
              <b>0{index + 1}</b>
              {line}
            </p>
          ))
        )}
      </div>
    </section>
  );
}

function DisclosurePanel({ items, loading, onAnalyze }) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>
          <FileText /> 실시간 DART 전자공시
        </h2>
        <span>최근 30일</span>
      </div>
      <div className="table-scroll">
        {loading ? (
          <Skeleton />
        ) : (
          <table>
            <thead>
              <tr>
                <th>접수일</th>
                <th>기업</th>
                <th>보고서</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {items.length ? (
                items.map((item) => (
                  <tr key={item.rcept_no}>
                    <td>{item.rcept_dt}</td>
                    <td>{item.corp_name}</td>
                    <td>
                      <div className="report-cell">
                        {item.is_major && (
                          <span className="major-badge">주요</span>
                        )}
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noreferrer"
                          title={item.report_nm}
                        >
                          {item.report_nm}
                        </a>
                      </div>
                    </td>
                    <td>
                      <button
                        className="text-button"
                        onClick={() =>
                          onAnalyze({
                            ...item,
                            type: "disclosure",
                            title: item.report_nm,
                            link: item.url,
                            text: `${item.corp_name} ${item.rcept_dt} ${item.report_nm}`,
                          })
                        }
                      >
                        AI 분석
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan="4" className="empty">
                    필터 조건에 맞는 공시가 없습니다.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

function NewsPanel({ items, loading, onSelect }) {
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>
          <Newspaper /> 실시간 기업 뉴스 피드
        </h2>
        <span>Latest signals</span>
      </div>
      <div className="news-scroll">
        {loading ? (
          <Skeleton />
        ) : items.length ? (
          items.map((item, index) => (
            <article className="news-row" key={`${item.link}-${index}`}>
              <div className={`strategy-tag ${tagClass(item)}`}>
                <Tag />
                <strong>{item.ai?.strategy_tag || "시장/일반"}</strong>
                <small>{item.corp_name}</small>
              </div>
              <div className="news-copy">
                <strong>{item.title}</strong>
                <small>
                  {item.source} · {item.time}
                </small>
              </div>
              <div className="row-actions">
                <a href={item.link} target="_blank" rel="noreferrer">
                  <ExternalLink /> 원문
                </a>
                <button
                  onClick={() =>
                    onSelect({ ...item, type: "news", text: item.summary })
                  }
                >
                  브리핑
                </button>
              </div>
            </article>
          ))
        ) : (
          <div className="empty">필터 조건에 맞는 뉴스가 없습니다.</div>
        )}
      </div>
    </section>
  );
}

function AnalysisModal({ item, result, loading, onClose }) {
  if (!item) return null;
  const isNews = item.type === "news";
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="analysis-modal"
        role="dialog"
        aria-modal="true"
        onMouseDown={(e) => e.stopPropagation()}
      >
        <button className="modal-close" onClick={onClose} aria-label="팝업 닫기">
          <X />
        </button>
        <span className="modal-kicker">
          {isNews ? "NEWS INTELLIGENCE" : "DISCLOSURE INTELLIGENCE"}
        </span>
        <h2>{item.title}</h2>
        <div className="modal-meta">
          <span>{item.corp_name}</span>
          {isNews && <span>{item.source}</span>}
          <span>{item.rcept_dt || item.time}</span>
          {item.is_major && <b>주요 공시</b>}
        </div>
        {loading ? (
          <Skeleton rows={3} />
        ) : (
          <>
            <section>
              <h3>원문 핵심 요약</h3>
              {result.summary_points.map((point, i) => (
                <p className="modal-point" key={i}>
                  <b>0{i + 1}</b>
                  {point}
                </p>
              ))}
            </section>
            {result.key_figures?.length > 0 && (
              <section>
                <h3>핵심 수치</h3>
                <div className="key-figures">
                  {result.key_figures.map((figure, index) => (
                    <article key={`${figure.label}-${index}`}>
                      <span>{figure.label}</span>
                      <strong>{figure.value}</strong>
                    </article>
                  ))}
                </div>
              </section>
            )}
            <section>
              <h3>사업적 영향 분석</h3>
              <p className="impact-copy">
                {result.business_impact || result.strategic_implication}
              </p>
            </section>
            <section>
              <h3>관련 키워드</h3>
              <div className="keyword-tags">
                {(result.keyword_tags?.length
                  ? result.keyword_tags
                  : [item.corp_name, isNews ? "뉴스" : "공시", "밸류체인"]
                ).map((tag) => (
                  <span key={tag}>#{tag}</span>
                ))}
              </div>
            </section>
          </>
        )}
        <a
          className="modal-source"
          href={item.link || item.url}
          target="_blank"
          rel="noreferrer"
        >
          <ExternalLink /> {isNews ? "뉴스 원문 열기" : "DART 원문 열기"}
        </a>
      </section>
    </div>
  );
}

function Briefing({ selected, selectedCompany, result, onSend, loading }) {
  return (
    <section className="briefing">
      <div className="brief-head">
        <div>
          <span>AI DEEP BRIEFING</span>
          <h2>
            {selected?.title ||
              (selectedCompany
                ? `${selectedCompany} 분석 대상을 선택하세요`
                : "분석 대상을 선택하세요")}
          </h2>
        </div>
      </div>
      <div className="brief-body">
        <div className="brief-status">
          <span className={`pill ${result.sentiment}`}>{result.sentiment}</span>
          <strong>{result.priority}</strong>
          <small>{selected?.corp_name || selectedCompany || "기업 미선택"}</small>
        </div>
        <div className="points">
          {loading ? (
            <p className="muted">AI가 핵심 영향과 대응 방향을 분석하고 있습니다.</p>
          ) : result.summary_points.length ? (
            result.summary_points.map((point, i) => (
              <p key={i}>
                <b>0{i + 1}</b>
                {point}
              </p>
            ))
          ) : (
            <p className="muted">뉴스 또는 공시의 브리핑 버튼을 선택하세요.</p>
          )}
          <div className="strategy">
            <span>STRATEGIC IMPLICATION</span>
            {result.strategic_implication}
          </div>
        </div>
        <div className="brief-actions">
          {selected?.link && (
            <a href={selected.link} target="_blank" rel="noreferrer">
              <ExternalLink /> 원문 열기
            </a>
          )}
          <button onClick={onSend} disabled={!selected}>
            <Send /> Telegram 발송
          </button>
        </div>
      </div>
    </section>
  );
}

function FinancialView({ companies, selectedCompany }) {
  const currentYear = new Date().getFullYear();
  const currentMonth = new Date().getMonth() + 1;
  const defaultYear = currentMonth < 5 ? currentYear - 1 : currentYear;
  const defaultReport =
    currentMonth >= 11
      ? "11014"
      : currentMonth >= 8
        ? "11012"
        : currentMonth >= 5
          ? "11013"
          : "11011";
  const years = Array.from({ length: 7 }, (_, index) => currentYear - index);
  const periods = [
    { value: "11013", label: "1분기" },
    { value: "11012", label: "반기" },
    { value: "11014", label: "3분기" },
    { value: "11011", label: "사업보고서(연간)" },
  ];
  const [company, setCompany] = useState(companies[0] || "포스코퓨처엠");
  const [year, setYear] = useState(defaultYear);
  const [reportCode, setReportCode] = useState(defaultReport);
  const [activeStatement, setActiveStatement] = useState("income");
  const [data, setData] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (selectedCompany && companies.includes(selectedCompany)) {
      setCompany(selectedCompany);
    }
  }, [selectedCompany, companies]);
  useEffect(() => {
    if (!company) return;
    setLoading(true);
    setError("");
    Promise.all([
      api.financials(company, year, reportCode),
      api.financialHistory(company, year, reportCode),
    ])
      .then(([current, historical]) => {
        setData(current);
        setHistory(historical.items || []);
      })
      .catch((requestError) => {
        setData(null);
        setHistory([]);
        setError(requestError.message);
      })
      .finally(() => setLoading(false));
  }, [company, year, reportCode]);
  const metricSets = data
    ? {
        income: [
          ["매출액", data.revenue_display],
          ["영업이익", data.operating_income_display],
          ["당기순이익", data.net_income_display],
          ["영업이익률", data.operating_margin_display],
          ["순이익률", data.net_margin_display],
        ],
        balance: [
          ["자산총계", data.assets_display],
          ["부채총계", data.liabilities_display],
          ["자본총계", data.equity_display],
          ["부채비율", data.debt_ratio_display],
        ],
        cashflow: [
          ["영업활동 현금흐름", data.operating_cf_display],
          ["투자활동 현금흐름", data.investing_cf_display],
          ["재무활동 현금흐름", data.financing_cf_display],
          ["현금 및 현금성자산", data.cash_display],
        ],
      }
    : { income: [], balance: [], cashflow: [] };
  const chartDataWithGrowth = history.map((item, index) => {
    const previous = history[index - 1];
    const growth = (value, prior) =>
      value == null || prior == null || prior === 0
        ? null
        : Number((((value - prior) / Math.abs(prior)) * 100).toFixed(1));
    return {
      ...item,
      label: `${item.year}/${reportCode === "11011" ? "12" : reportCode === "11014" ? "09" : reportCode === "11012" ? "06" : "03"}`,
      revenue_growth: growth(item.revenue, previous?.revenue),
      operating_growth: growth(
        item.operating_income,
        previous?.operating_income,
      ),
      net_growth: growth(item.net_income, previous?.net_income),
    };
  });
  const chartData = chartDataWithGrowth.slice(-5);
  const tabs = [
    { id: "income", label: "포괄손익계산서" },
    { id: "balance", label: "재무상태표" },
    { id: "cashflow", label: "현금흐름표" },
  ];
  const compactNumber = (value) =>
    value == null ? "-" : `${Number(value).toLocaleString()}억`;
  const formatRateLabel = (value) =>
    value == null || Number.isNaN(Number(value))
      ? ""
      : `${Number(value).toFixed(1)}%`;
  const renderRateLabel =
    (fill, offsetY) =>
    ({ x, y, value }) => {
      const label = formatRateLabel(value);
      if (!label || x == null || y == null) return null;
      return (
        <text
          x={Number(x)}
          y={Number(y) + offsetY}
          textAnchor="middle"
          fill={fill}
          stroke="#ffffff"
          strokeWidth={3}
          paintOrder="stroke"
          fontSize={8.5}
          fontWeight={700}
        >
          {label}
        </text>
      );
    };
  return (
    <>
      <section className="finance-toolbar">
        <div>
          <span>FINANCIAL HEALTH</span>
          <h2>기업 재무 건전성 및 수익성</h2>
        </div>
        <div className="finance-selectors">
          <label>
            기업
            <select
              value={company}
              onChange={(event) => setCompany(event.target.value)}
            >
              {companies.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <label>
            사업연도
            <select
              value={year}
              onChange={(event) => setYear(Number(event.target.value))}
            >
              {years.map((item) => (
                <option key={item} value={item}>
                  {item}년
                </option>
              ))}
            </select>
          </label>
          <label>
            기간
            <select
              value={reportCode}
              onChange={(event) => setReportCode(event.target.value)}
            >
              {periods.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>
      <div className="statement-tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            className={activeStatement === tab.id ? "active" : ""}
            onClick={() => setActiveStatement(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {loading ? (
        <section className="finance-grid">
          <Skeleton rows={4} />
        </section>
      ) : error ? (
        <section className="finance-empty">
          <strong>선택한 기간의 재무제표가 없습니다.</strong>
          <span>{error}</span>
          <small>
            공시 제출 시점에 따라 최근 분기 자료가 아직 등록되지 않았을 수
            있습니다.
          </small>
        </section>
      ) : (
        <>
          <section className="finance-grid statement-metrics">
            {metricSets[activeStatement].map(([label, value]) => (
              <article key={label}>
                <span>{label}</span>
                <strong>{value || "-"}</strong>
              </article>
            ))}
          </section>
          <section className="financial-charts">
            <article>
              <h3>
                주요 재무 항목 <small>단위: 억원</small>
              </h3>
              <div className="chart-frame">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart
                    data={chartData}
                    margin={{ top: 30, right: 16, bottom: 2, left: 2 }}
                  >
                    <CartesianGrid stroke="#e6ebf2" vertical={false} />
                    <XAxis
                      dataKey="label"
                      tick={{ fontSize: 9, fill: "#708098" }}
                    />
                    <YAxis tick={{ fontSize: 9, fill: "#708098" }} width={52} />
                    <Tooltip
                      formatter={compactNumber}
                      contentStyle={{
                        fontSize: 10,
                        borderRadius: 8,
                        borderColor: "#d7e0ec",
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: 9 }} />
                    {activeStatement === "income" && (
                      <>
                        <Bar
                          dataKey="revenue"
                          name="매출액"
                          fill="#2475e8"
                          radius={[3, 3, 0, 0]}
                        />
                        <Bar
                          dataKey="operating_income"
                          name="영업이익"
                          fill="#ef765c"
                          radius={[3, 3, 0, 0]}
                        >
                          <LabelList
                            dataKey="operating_margin"
                            position="top"
                            offset={7}
                            formatter={formatRateLabel}
                            fill="#c9543d"
                            fontSize={9}
                            fontWeight={700}
                          />
                        </Bar>
                        <Bar
                          dataKey="net_income"
                          name="순이익"
                          fill="#75bd45"
                          radius={[3, 3, 0, 0]}
                        >
                          <LabelList
                            dataKey="net_margin"
                            position="top"
                            offset={7}
                            formatter={formatRateLabel}
                            fill="#4d912b"
                            fontSize={9}
                            fontWeight={700}
                          />
                        </Bar>
                      </>
                    )}
                    {activeStatement === "balance" && (
                      <>
                        <Bar dataKey="assets" name="자산" fill="#2475e8" />
                        <Bar dataKey="liabilities" name="부채" fill="#ef765c" />
                        <Bar dataKey="equity" name="자본" fill="#75bd45" />
                      </>
                    )}
                    {activeStatement === "cashflow" && (
                      <>
                        <Bar
                          dataKey="operating_cf"
                          name="영업CF"
                          fill="#2475e8"
                        />
                        <Bar
                          dataKey="investing_cf"
                          name="투자CF"
                          fill="#8a6de9"
                        />
                        <Bar
                          dataKey="financing_cf"
                          name="재무CF"
                          fill="#ef9b34"
                        />
                      </>
                    )}
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </article>
            <article>
              <h3>
                수익성·성장성 지표 <small>단위: %</small>
              </h3>
              <div className="chart-frame">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart
                    data={chartData}
                    margin={{ top: 32, right: 22, bottom: 12, left: 8 }}
                  >
                    <CartesianGrid stroke="#e6ebf2" vertical={false} />
                    <XAxis
                      dataKey="label"
                      tick={{ fontSize: 9, fill: "#708098" }}
                    />
                    <YAxis tick={{ fontSize: 9, fill: "#708098" }} width={42} />
                    <Tooltip
                      formatter={(value) => (value == null ? "-" : `${value}%`)}
                      contentStyle={{
                        fontSize: 10,
                        borderRadius: 8,
                        borderColor: "#d7e0ec",
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: 9 }} />
                    {activeStatement === "income" ? (
                      <>
                        <Line
                          type="monotone"
                          dataKey="operating_margin"
                          name="영업이익률"
                          stroke="#ef765c"
                          strokeWidth={2}
                          dot={{ r: 3 }}
                        >
                          <LabelList
                            content={renderRateLabel("#c9543d", -20)}
                          />
                        </Line>
                        <Line
                          type="monotone"
                          dataKey="net_margin"
                          name="순이익률"
                          stroke="#8a6de9"
                          strokeWidth={2}
                          dot={{ r: 3 }}
                        >
                          <LabelList content={renderRateLabel("#7651cb", 15)} />
                        </Line>
                        <Line
                          type="monotone"
                          dataKey="revenue_growth"
                          name="매출성장률"
                          stroke="#2475e8"
                          strokeWidth={2}
                          dot={{ r: 3 }}
                        >
                          <LabelList content={renderRateLabel("#1e62cf", -9)} />
                        </Line>
                      </>
                    ) : activeStatement === "balance" ? (
                      <Line
                        type="monotone"
                        dataKey="debt_ratio"
                        name="부채비율"
                        stroke="#ef765c"
                        strokeWidth={2}
                        dot={{ r: 3 }}
                      >
                        <LabelList content={renderRateLabel("#c9543d", -10)} />
                      </Line>
                    ) : (
                      <>
                        <Line
                          type="monotone"
                          dataKey="operating_growth"
                          name="영업CF 연계 추이"
                          stroke="#2475e8"
                          strokeWidth={2}
                          dot={{ r: 3 }}
                        >
                          <LabelList
                            content={renderRateLabel("#1e62cf", -10)}
                          />
                        </Line>
                        <Line
                          type="monotone"
                          dataKey="net_growth"
                          name="순이익 성장률"
                          stroke="#75bd45"
                          strokeWidth={2}
                          dot={{ r: 3 }}
                        >
                          <LabelList content={renderRateLabel("#4d912b", 14)} />
                        </Line>
                      </>
                    )}
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </article>
          </section>
        </>
      )}
      {data && (
        <section className="panel finance-detail">
          <h2>
            <Building2 /> {data.corp_name} 연결 재무제표
          </h2>
          <p>
            {data.period_label} · OpenDART 기준 · 최근 {chartData.length}개년
            비교
            {data.source_corp_name && data.source_corp_name !== data.corp_name
              ? ` · ${data.source_corp_name} 연결 기준`
              : ""}
          </p>
          {data.source_url && (
            <a href={data.source_url} target="_blank" rel="noreferrer">
              <ExternalLink /> 공시 원문 확인
            </a>
          )}
        </section>
      )}
    </>
  );
}

function isKoreanMarketOpen() {
  const seoulNow = new Date(
    new Date().toLocaleString("en-US", { timeZone: "Asia/Seoul" }),
  );
  const day = seoulNow.getDay();
  const minutes = seoulNow.getHours() * 60 + seoulNow.getMinutes();
  return day >= 1 && day <= 5 && minutes >= 540 && minutes <= 930;
}

function StockComparison({ companies, selectedCompany, refreshNonce }) {
  const competitorOptions = useMemo(
    () => COMPANY_GROUPS["경쟁사"].filter((company) => companies.includes(company)),
    [companies],
  );
  const [selectedCompetitors, setSelectedCompetitors] = useState(() => {
    const stored = JSON.parse(localStorage.getItem("radar-stock-comparisons") || "null");
    return Array.isArray(stored) && stored.length
      ? stored
      : COMPANY_GROUPS["경쟁사"];
  });
  const [comparison, setComparison] = useState({ chart: [], series: [] });
  const [rawComparison, setRawComparison] = useState([]);
  const [startDate, setStartDate] = useState("");
  const [quickRange, setQuickRange] = useState("1y");
  const [dateRange, setDateRange] = useState({ min: "", max: "" });
  const [loading, setLoading] = useState(false);
  const colors = ["#174f9e", "#e56c57", "#39a982", "#8b6bd5"];
  useEffect(() => {
    setSelectedCompetitors((current) =>
      current.filter((company) => competitorOptions.includes(company)),
    );
  }, [competitorOptions]);
  useEffect(() => {
    if (
      selectedCompany &&
      competitorOptions.includes(selectedCompany)
    ) {
      setSelectedCompetitors((current) =>
        current.includes(selectedCompany) ? current : [...current, selectedCompany],
      );
    }
  }, [selectedCompany, competitorOptions]);
  useEffect(() => {
    localStorage.setItem(
      "radar-stock-comparisons",
      JSON.stringify(selectedCompetitors),
    );
  }, [selectedCompetitors]);
  useEffect(() => {
    const names = ["포스코퓨처엠", ...selectedCompetitors];
    setLoading(true);
    Promise.allSettled(names.map((name) => api.stockAnalysis(name, "1y")))
      .then((results) => {
        const valid = results
          .map((result, index) =>
            result.status === "fulfilled" && result.value.listed
              ? { name: names[index], data: result.value }
              : null,
          )
          .filter(Boolean);
        if (!valid.length) {
          setRawComparison([]);
          setComparison({ chart: [], series: [] });
          return;
        }
        setRawComparison(valid);
      })
      .finally(() => setLoading(false));
  }, [refreshNonce, selectedCompetitors]);
  useEffect(() => {
    if (!rawComparison.length) return;
    const availableDates = rawComparison[0].data.chart.map((point) => point.date);
    const min = availableDates[0] || "";
    const max = availableDates[availableDates.length - 1] || "";
    const quickRangePoints = { "10d": 10, "3m": 66, "6m": 132, "1y": 260 };
    const quickStart = quickRange !== "custom"
      ? availableDates[Math.max(0, availableDates.length - quickRangePoints[quickRange])]
      : startDate;
    const effectiveStart = !quickStart || quickStart < min || quickStart > max
      ? min
      : quickStart;
    setDateRange({ min, max });
    if (effectiveStart !== startDate) setStartDate(effectiveStart);
    const baseDates = availableDates.filter((date) => date >= effectiveStart);
    const series = rawComparison.map(({ name, data }, index) => {
          const filtered = data.chart.filter((point) => point.date >= effectiveStart);
          const first = filtered[0]?.close;
          const byDate = Object.fromEntries(
            filtered.map((point) => [
              point.date,
              first ? Number(((point.close / first) * 100).toFixed(2)) : null,
            ]),
          );
          const values = Object.values(byDate).filter((value) => value != null);
          return {
            name,
            color: colors[index % colors.length],
            byDate,
            returnRate: values.length
              ? Number((values[values.length - 1] - 100).toFixed(2))
              : null,
          };
        });
    setComparison({
      chart: baseDates.map((date) => {
        const row = { date };
        series.forEach((item) => {
          row[item.name] = item.byDate[date];
        });
        return row;
      }),
      series,
    });
  }, [rawComparison, startDate, quickRange]);
  const toggleCompetitor = (company) => {
    setSelectedCompetitors((current) =>
      current.includes(company)
        ? current.filter((item) => item !== company)
        : [...current, company],
    );
  };
  return (
    <section className="stock-comparison">
      <div className="comparison-head">
        <div>
          <span>PEER PERFORMANCE</span>
          <h3>포스코퓨처엠 vs 경쟁사 주가 비교</h3>
          <p>조회 시작일을 100으로 환산한 상대수익률 비교입니다.</p>
        </div>
        <div className="comparison-options">
          <label className="comparison-start">
            비교 시작일
            <input
              type="date"
              value={startDate}
              min={dateRange.min}
              max={dateRange.max}
              onChange={(event) => {
                setQuickRange("custom");
                setStartDate(event.target.value);
              }}
              disabled={!dateRange.min}
            />
          </label>
          <div className="comparison-quick-range">
            <small>빠른 기간</small>
            <div>
              {[
                ["10d", "10일"],
                ["3m", "3개월"],
                ["6m", "6개월"],
                ["1y", "1년"],
              ].map(([value, label]) => (
                <button
                  key={value}
                  className={quickRange === value ? "active" : ""}
                  onClick={() => setQuickRange(value)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div className="competitor-picker">
            <small>비교 경쟁사</small>
            <div>
              {competitorOptions.map((company) => (
                <button
                  key={company}
                  className={selectedCompetitors.includes(company) ? "active" : ""}
                  onClick={() => toggleCompetitor(company)}
                  aria-pressed={selectedCompetitors.includes(company)}
                >
                  {company}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
      {loading ? (
        <div className="comparison-loading"><Skeleton rows={3} /></div>
      ) : comparison.chart.length ? (
        <div className="comparison-grid">
          <div className="comparison-chart">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={comparison.chart} margin={{ top: 18, right: 18, bottom: 4, left: 2 }}>
                <CartesianGrid stroke="#e5ebf3" vertical={false} />
                <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#718198" }} minTickGap={35} />
                <YAxis tick={{ fontSize: 9, fill: "#718198" }} width={44} domain={["auto", "auto"]} tickFormatter={(value) => value.toFixed(0)} />
                <Tooltip formatter={(value, name) => [`${Number(value).toFixed(1)}`, name]} contentStyle={{ fontSize: 10, borderRadius: 9, borderColor: "#d7e0ec" }} />
                <Legend wrapperStyle={{ fontSize: 9 }} />
                {comparison.series.map((item) => (
                  <Line key={item.name} type="monotone" dataKey={item.name} stroke={item.color} strokeWidth={item.name === "포스코퓨처엠" ? 2.8 : 1.8} dot={false} connectNulls />
                ))}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          <div className="comparison-ranking">
            <span>기간 수익률 순위</span>
            {[...comparison.series]
              .sort((a, b) => (b.returnRate ?? -Infinity) - (a.returnRate ?? -Infinity))
              .map((item, index) => (
                <div key={item.name}>
                  <b>{index + 1}</b>
                  <i style={{ background: item.color }} />
                  <small>{item.name}</small>
                  <strong className={item.returnRate < 0 ? "down" : ""}>
                    {item.returnRate == null
                      ? "-"
                      : `${item.returnRate > 0 ? "+" : ""}${item.returnRate.toFixed(2)}%`}
                  </strong>
                </div>
              ))}
          </div>
        </div>
      ) : (
        <div className="comparison-empty">비교 가능한 주가 데이터가 없습니다.</div>
      )}
    </section>
  );
}

function StockView({ companies, selectedCompany }) {
  const [company, setCompany] = useState(selectedCompany || companies[0] || "포스코퓨처엠");
  const [period, setPeriod] = useState("1y");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refreshNonce, setRefreshNonce] = useState(0);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [marketOpen, setMarketOpen] = useState(isKoreanMarketOpen);
  const periods = [
    ["1m", "1개월"],
    ["3m", "3개월"],
    ["6m", "6개월"],
    ["1y", "1년"],
  ];
  const won = (value) =>
    value == null ? "-" : `${Number(value).toLocaleString("ko-KR")}원`;
  const percent = (value) =>
    value == null ? "-" : `${value > 0 ? "+" : ""}${Number(value).toFixed(2)}%`;
  const compactVolume = (value) => {
    if (value == null) return "-";
    if (value >= 1000000) return `${(value / 1000000).toFixed(1)}백만주`;
    if (value >= 10000) return `${(value / 10000).toFixed(1)}만주`;
    return `${Number(value).toLocaleString("ko-KR")}주`;
  };
  useEffect(() => {
    if (selectedCompany && companies.includes(selectedCompany)) {
      setCompany(selectedCompany);
    }
  }, [selectedCompany, companies]);
  useEffect(() => {
    if (!company) return;
    setLoading(true);
    setError("");
    api
      .stockAnalysis(company, period)
      .then((result) => {
        setData(result);
        setLastUpdated(new Date());
      })
      .catch((requestError) => {
        setData(null);
        setError(requestError.message);
      })
      .finally(() => setLoading(false));
  }, [company, period, refreshNonce]);
  useEffect(() => {
    const timer = window.setInterval(() => {
      const open = isKoreanMarketOpen();
      setMarketOpen(open);
      if (open) setRefreshNonce((value) => value + 1);
    }, 60000);
    return () => window.clearInterval(timer);
  }, []);
  const metrics = data?.listed
    ? [
        ["현재가", won(data.price), percent(data.change_rate)],
        ["52주 고가", won(data.high_52w), "연중 가격 상단"],
        ["52주 저가", won(data.low_52w), "연중 가격 하단"],
        ["거래량", compactVolume(data.volume), `20일 평균 ${compactVolume(data.average_volume_20d)}`],
        ["RSI(14)", data.rsi14 == null ? "-" : data.rsi14.toFixed(1), "70 과열 · 30 침체"],
        ["연환산 변동성", data.volatility == null ? "-" : `${data.volatility.toFixed(1)}%`, "최근 1년 일간 수익률"],
      ]
    : [];
  return (
    <>
      <section className="stock-toolbar">
        <div>
          <span>MARKET SIGNALS</span>
          <h2>기업 주가 분석</h2>
          <p>가격 추세·수익률·모멘텀을 함께 점검합니다.</p>
        </div>
        <div className="stock-controls">
          <label>
            기업
            <select value={company} onChange={(event) => setCompany(event.target.value)}>
              {companies.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </label>
          <div className="stock-refresh-status">
            <span className={marketOpen ? "market-open" : "market-closed"}>
              <i /> {marketOpen ? "장중 · 1분 자동갱신" : "장 마감"}
            </span>
            <small>
              마지막 갱신 {lastUpdated ? lastUpdated.toLocaleTimeString("ko-KR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "-"}
            </small>
            <button
              onClick={() => setRefreshNonce((value) => value + 1)}
              disabled={loading}
              aria-label="주가 데이터 수동 새로고침"
            >
              <RefreshCw className={loading ? "spin" : ""} /> 새로고침
            </button>
          </div>
        </div>
      </section>
      <div className="stock-periods" aria-label="주가 조회 기간">
        {periods.map(([value, label]) => (
          <button
            key={value}
            className={period === value ? "active" : ""}
            onClick={() => setPeriod(value)}
          >
            {label}
          </button>
        ))}
      </div>
      {loading ? (
        <section className="stock-loading"><Skeleton rows={5} /></section>
      ) : error ? (
        <section className="finance-empty">
          <strong>주가 데이터를 불러오지 못했습니다.</strong>
          <span>{error}</span>
        </section>
      ) : data && !data.listed ? (
        <section className="stock-unlisted">
          <TrendingUp />
          <strong>{data.corp_name}은(는) 상장 주식이 없습니다.</strong>
          <p>{data.message}</p>
          <small>SK온처럼 비상장 기업은 공시·뉴스·재무분석 기능을 이용해 주세요.</small>
        </section>
      ) : data?.listed ? (
        <>
          <section className="stock-metrics">
            {metrics.map(([label, value, detail]) => (
              <article key={label}>
                <span>{label}</span>
                <strong>{value}</strong>
                <small className={label === "현재가" && data.change_rate < 0 ? "down" : ""}>{detail}</small>
              </article>
            ))}
          </section>
          <section className="stock-main-grid">
            <article className="stock-chart-card">
              <div className="stock-card-head">
                <div>
                  <span>{data.stock_code}</span>
                  <h3>{data.corp_name} 주가 추이</h3>
                </div>
                <small>{data.as_of} 종가 기준</small>
              </div>
              <div className="stock-chart-frame">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={data.chart} margin={{ top: 16, right: 18, bottom: 4, left: 6 }}>
                    <CartesianGrid stroke="#e5ebf3" vertical={false} />
                    <XAxis dataKey="date" tick={{ fontSize: 9, fill: "#718198" }} minTickGap={35} />
                    <YAxis tick={{ fontSize: 9, fill: "#718198" }} width={58} domain={["auto", "auto"]} tickFormatter={(value) => Number(value).toLocaleString("ko-KR")} />
                    <Tooltip formatter={(value, name) => [won(value), name]} contentStyle={{ fontSize: 10, borderRadius: 9, borderColor: "#d7e0ec" }} />
                    <Legend wrapperStyle={{ fontSize: 9 }} />
                    <Line type="monotone" dataKey="close" name="종가" stroke="#2475e8" strokeWidth={2.4} dot={false} />
                    <Line type="monotone" dataKey="ma20" name="20일선" stroke="#34bfa3" strokeWidth={1.4} dot={false} connectNulls />
                    <Line type="monotone" dataKey="ma60" name="60일선" stroke="#f09a43" strokeWidth={1.4} dot={false} connectNulls />
                    <Line type="monotone" dataKey="ma120" name="120일선" stroke="#8c70d9" strokeWidth={1.2} dot={false} connectNulls />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </article>
            <aside className="stock-insights">
              <article className={`stock-signal ${data.signal.tone}`}>
                <span>TECHNICAL SIGNAL</span>
                <strong>{data.signal.label}</strong>
                <p>{data.signal.description}</p>
              </article>
              <article className="stock-returns">
                <span>기간 수익률</span>
                {Object.entries(data.performance).map(([label, value]) => (
                  <div key={label}>
                    <small>{label}</small>
                    <strong className={value < 0 ? "down" : ""}>{percent(value)}</strong>
                  </div>
                ))}
              </article>
              <article className="stock-averages">
                <span>이동평균 위치</span>
                <div><small>20일선</small><strong>{won(data.ma20)}</strong></div>
                <div><small>60일선</small><strong>{won(data.ma60)}</strong></div>
                <div><small>120일선</small><strong>{won(data.ma120)}</strong></div>
              </article>
            </aside>
          </section>
          <section className="stock-source">
            <p>시장 데이터는 네이버 금융 기준이며 투자 판단을 위한 참고 정보입니다.</p>
            <a href={data.source_url} target="_blank" rel="noreferrer"><ExternalLink /> 종목 원문 보기</a>
          </section>
        </>
      ) : null}
      <StockComparison
        companies={companies}
        selectedCompany={selectedCompany}
        refreshNonce={refreshNonce}
      />
    </>
  );
}

export default function App() {
  const [collapsed, setCollapsed] = useState(false);
  const [view, setView] = useState("intel");
  const [companies, setCompanies] = useState(
    () => {
      const stored = JSON.parse(localStorage.getItem("radar-companies") || "null");
      if (!Array.isArray(stored)) return DEFAULT_COMPANIES;
      return [
        "포스코퓨처엠",
        ...stored.filter((company) => company !== "포스코퓨처엠"),
      ];
    },
  );
  const [selectedCompany, setSelectedCompany] = useState("");
  const [status, setStatus] = useState({ dart: false, ai: false });
  const [data, setData] = useState({
    disclosures: [],
    news: [],
    daily_briefing: [],
  });
  const [selected, setSelected] = useState(null);
  const [aiResult, setAiResult] = useState(EMPTY_AI);
  const [loading, setLoading] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [briefingLoading, setBriefingLoading] = useState(false);
  useEffect(() => {
    localStorage.setItem("radar-companies", JSON.stringify(companies));
  }, [companies]);
  useEffect(() => {
    api
      .status()
      .then(setStatus)
      .catch(() => {});
  }, []);
  const refresh = async () => {
    setLoading(true);
    try {
      setData(await api.intelligence(companies));
    } catch (error) {
      alert(error.message);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    if (companies.length) refresh();
  }, [companies]);
  const filtered = useMemo(
    () => ({
      disclosures: selectedCompany
        ? data.disclosures.filter((x) => x.corp_name === selectedCompany)
        : data.disclosures,
      news: selectedCompany
        ? data.news.filter((x) => x.corp_name === selectedCompany)
        : data.news,
    }),
    [data, selectedCompany],
  );
  const analyze = async (item) => {
    setSelected(item);
    setModalLoading(true);
    try {
      const result = await api.analyze({
        title: item.title,
        text: item.text || item.summary || "",
        group_type: item.group_type || "경쟁사",
        rcept_no: item.rcept_no || null,
      });
      setAiResult(result);
    } catch (error) {
      alert(error.message);
      setAiResult(item.ai || EMPTY_AI);
    } finally {
      setModalLoading(false);
    }
  };
  const briefNews = async (item) => {
    setSelected(item);
    setAiResult(item.ai || EMPTY_AI);
    setBriefingLoading(true);
    try {
      const result = await api.analyze({
        title: item.title,
        text: `기업: ${item.corp_name}\n전략 태그: ${item.ai?.strategy_tag || "시장/일반"}\n기사 요약: ${item.summary || "요약 없음"}`,
        group_type: item.group_type || "경쟁사",
      });
      setAiResult(result);
    } catch (error) {
      setAiResult(item.ai || EMPTY_AI);
      alert(error.message);
    } finally {
      setBriefingLoading(false);
    }
  };
  const send = async () => {
    if (!selected) return;
    try {
      await api.telegram({
        title: selected.title,
        corp_name: selected.corp_name,
        ai_result: aiResult,
        source_url: selected.link || selected.url,
      });
      alert("Telegram으로 브리핑을 발송했습니다.");
    } catch (error) {
      alert(error.message);
    }
  };
  return (
    <div className="app-shell">
      <Sidebar
        {...{
          collapsed,
          setCollapsed,
          view,
          setView,
          companies,
          setCompanies,
          selectedCompany,
          setSelectedCompany,
          onRefresh: refresh,
          loading,
        }}
      />
      <main className={collapsed ? "wide" : ""}>
        <Header status={status} />
        {view === "intel" ? (
          <>
            <section className={`company-focus ${selectedCompany ? "active" : ""}`}>
              <div>
                <span>SELECTED COMPANY</span>
                <strong>{selectedCompany || "전체 모니터링 기업"}</strong>
              </div>
              <p>
                {selectedCompany
                  ? `${selectedCompany} 공시 ${filtered.disclosures.length}건 · 뉴스 ${filtered.news.length}건을 표시합니다.`
                  : `전체 공시 ${filtered.disclosures.length}건 · 뉴스 ${filtered.news.length}건을 표시합니다.`}
              </p>
              {selectedCompany && (
                <button onClick={() => setSelectedCompany("")}>전체 보기</button>
              )}
            </section>
            <DailyBriefing
              lines={data.daily_briefing || []}
              loading={loading}
            />
            <div className="filter-summary">
              {selectedCompany ? (
                <>
                  <span>{selectedCompany}</span> 관련 공시·뉴스만 표시 중{" "}
                  <button onClick={() => setSelectedCompany("")}>
                    필터 해제
                  </button>
                </>
              ) : (
                "모든 모니터링 기업의 인텔리전스를 표시합니다."
              )}
            </div>
            <div className="dual-grid">
              <DisclosurePanel
                items={filtered.disclosures}
                loading={loading}
                onAnalyze={analyze}
              />
              <NewsPanel
                items={filtered.news}
                loading={loading}
                onSelect={briefNews}
              />
            </div>
            <Briefing
              selected={selected}
              selectedCompany={selectedCompany}
              result={aiResult}
              onSend={send}
              loading={briefingLoading}
            />
            <AnalysisModal
              item={selected}
              result={aiResult}
              loading={
                selected?.type === "news" ? briefingLoading : modalLoading
              }
              onClose={() => setSelected(null)}
            />
          </>
        ) : view === "finance" ? (
          <FinancialView
            companies={companies}
            selectedCompany={selectedCompany}
          />
        ) : (
          <StockView
            companies={companies}
            selectedCompany={selectedCompany}
          />
        )}
      </main>
    </div>
  );
}
