export const dimensions = [
  {key:'orders', label:'수주·공급', words:/수주|공급계약|공급 계약|단일판매.*체결/i},
  {key:'investment', label:'투자·증설', words:/증설|신규시설|시설투자|양산|capex/i},
  {key:'technology', label:'기술·특허', words:/특허|전고체|신기술|기술개발|기술 개발|상용화/i},
  {key:'risk', label:'위험 신호', words:/계약해지|계약 해지|적자|손실|소송|리콜|유상증자|채무보증|감산/i},
];

export function scoreCompanies(companies, data, now = new Date()) {
  const cutoff = now.getTime() - 30 * 86400000;
  return companies.map(company => {
    const seen = new Set();
    const sources = [...(data.disclosures || []).map(x => ({...x, kind:'공시', title:x.report_nm, date:x.rcept_dt, link:x.url})), ...(data.news || []).map(x => ({...x, kind:'뉴스', date:x.time}))];
    const evidence = sources.filter(x => {
      if (x.corp_name !== company) return false;
      const date = /^\d{8}$/.test(x.date || '') ? `${x.date.slice(0,4)}-${x.date.slice(4,6)}-${x.date.slice(6,8)}` : x.date;
      const stamp = Date.parse(date);
      if (!Number.isFinite(stamp) || stamp < cutoff || stamp > now.getTime()) return false;
      const key = x.kind === '공시' ? x.rcept_no : x.title.replace(/\s/g,'');
      if (seen.has(key)) return false;
      seen.add(key); return true;
    }).map(x => ({...x, signals:dimensions.filter(d => d.words.test(x.title || '')).map(d => d.key)}));
    const counts = Object.fromEntries(dimensions.map(d => [d.key, evidence.filter(e => e.signals.includes(d.key)).length]));
    const values = Object.fromEntries(dimensions.map(d => [d.key, evidence.length ? Math.round(100 * counts[d.key] / evidence.length) : null]));
    // Composite measures attention required, not investment merit or creditworthiness.
    const score = evidence.length ? Math.round(.2*values.orders + .2*values.investment + .15*values.technology + .45*values.risk) : null;
    return {company, evidence, counts, values, score};
  });
}
