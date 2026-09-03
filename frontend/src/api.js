const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || `요청 실패 (${response.status})`);
  }
  return response.json();
}

export const api = {
  status: () => request("/status"),
  intelligence: (companies) => request(`/intelligence?companies=${encodeURIComponent(companies.join(","))}`),
  financials: (company, year, reportCode) => request(`/financials/${encodeURIComponent(company)}?year=${year}&report_code=${reportCode}`),
  financialHistory: (company, endYear, reportCode) => request(`/financials/${encodeURIComponent(company)}/history?end_year=${endYear}&report_code=${reportCode}&years=6`),
  stockAnalysis: (company, period) => request(`/stocks/${encodeURIComponent(company)}?period=${period}`),
  analyze: (payload) => request("/analyze", { method: "POST", body: JSON.stringify(payload) }),
  telegram: (payload) => request("/telegram", { method: "POST", body: JSON.stringify(payload) }),
  validateCompany: (name) => request(`/companies/validate?name=${encodeURIComponent(name)}`),
};
