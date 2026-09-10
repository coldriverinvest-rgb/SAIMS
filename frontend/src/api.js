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
  intelligence: (companies, { signal, force = false } = {}) =>
    request(
      `/intelligence?companies=${encodeURIComponent(companies.join(","))}${force ? "&refresh=true" : ""}`,
      { signal },
    ),
  financials: (company, year, reportCode, statementType) => request(`/financials/${encodeURIComponent(company)}?year=${year}&report_code=${reportCode}&fs_div=${statementType}`),
  financialHistory: (company, endYear, reportCode, statementType, frequency) => request(`/financials/${encodeURIComponent(company)}/history?end_year=${endYear}&report_code=${reportCode}&fs_div=${statementType}&frequency=${frequency}&quarters=9&years=7`),
  stockAnalysis: (company, period) => request(`/stocks/${encodeURIComponent(company)}?period=${period}`),
  materials: () => request("/materials"),
  materialNews: async () => ({ items: [] }),
  analyze: (payload) => request("/analyze", { method: "POST", body: JSON.stringify(payload) }),
  telegram: (payload) => request("/telegram", { method: "POST", body: JSON.stringify(payload) }),
  validateCompany: (name) => request(`/companies/validate?name=${encodeURIComponent(name)}`),
  adminStatus: (password) => request("/admin/status", { headers: { "Content-Type": "application/json", "X-Admin-Password": password } }),
  adminRecipients: (password) => request("/admin/recipients", { headers: { "Content-Type": "application/json", "X-Admin-Password": password } }),
  addRecipient: (password, payload) => request("/admin/recipients", { method: "POST", headers: { "Content-Type": "application/json", "X-Admin-Password": password }, body: JSON.stringify(payload) }),
  updateRecipient: (password, id, payload) => request(`/admin/recipients/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json", "X-Admin-Password": password }, body: JSON.stringify(payload) }),
  deleteRecipient: (password, id) => request(`/admin/recipients/${id}`, { method: "DELETE", headers: { "Content-Type": "application/json", "X-Admin-Password": password } }),
  testRecipient: (password, id) => request(`/admin/recipients/${id}/test`, { method: "POST", headers: { "Content-Type": "application/json", "X-Admin-Password": password } }),
  scanAlerts: (password) => request("/admin/alerts/scan", { method: "POST", headers: { "Content-Type": "application/json", "X-Admin-Password": password } }),
  telegramChats: (password) => request("/admin/telegram/chats", { headers: { "Content-Type": "application/json", "X-Admin-Password": password } }),
};
