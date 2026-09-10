export const formatWon = (value) =>
  value == null ? "-" : `${Math.trunc(Number(value)).toLocaleString("ko-KR")}원`;

export const formatWonCompact = (value) => {
  if (value == null) return "-";
  const amount = Number(value);
  if (Math.abs(amount) >= 1e12) return `${(amount / 1e12).toFixed(2)}조원`;
  if (Math.abs(amount) >= 1e8) return `${Math.trunc(amount / 1e8).toLocaleString("ko-KR")}억원`;
  return formatWon(amount);
};

export const formatEok = (value, digits = 0) =>
  value == null ? "-" : `${Number(value).toLocaleString("ko-KR", { maximumFractionDigits: digits })}억원`;

export const formatPercent = (value, digits = 1, sign = true) =>
  value == null ? "-" : `${sign && Number(value) > 0 ? "+" : ""}${Number(value).toFixed(digits)}%`;

export const formatMultiple = (value) =>
  value == null ? "-" : `${Number(value).toFixed(1)}x`;

export const formatShares = (value) => {
  if (value == null) return "-";
  if (value >= 1e6) return `${(value / 1e6).toFixed(1)}백만주`;
  if (value >= 1e4) return `${(value / 1e4).toFixed(1)}만주`;
  return `${Math.trunc(value).toLocaleString("ko-KR")}주`;
};
