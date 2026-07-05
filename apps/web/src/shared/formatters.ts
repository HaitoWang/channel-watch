export function formatNumber(value: unknown) {
  const number = Number(value || 0);
  return number.toLocaleString("en-US", { maximumFractionDigits: 2 });
}

export function formatMoney(value: unknown, unit = "USD") {
  if (value == null || value === "") return unit === "USD" ? "$--" : "--";
  const prefix = unit === "USD" ? "$" : "";
  const suffix = unit === "USD" ? "" : ` ${unit}`;
  return `${prefix}${formatNumber(value)}${suffix}`;
}

export function formatRate(value: unknown) {
  if (value == null || value === "") return "未知";
  return `${formatNumber(value)}x`;
}

const commonCompoundSuffixes = new Set([
  "ac.uk",
  "co.jp",
  "co.uk",
  "com.au",
  "com.br",
  "com.cn",
  "com.hk",
  "com.mx",
  "com.sg",
  "com.tr",
  "gov.cn",
  "ne.jp",
  "net.au",
  "net.cn",
  "net.hk",
  "or.jp",
  "org.au",
  "org.cn",
  "org.hk",
  "org.uk",
]);

function domainSuffix(hostname: unknown) {
  const host = String(hostname || "").toLowerCase().replace(/^\[|\]$/g, "");
  if (!host || host === "localhost" || host.includes(":") || /^\d{1,3}(\.\d{1,3}){3}$/.test(host)) return "";
  const labels = host.split(".").filter(Boolean);
  if (!labels.length) return "";
  const compoundSuffix = labels.slice(-2).join(".");
  return commonCompoundSuffixes.has(compoundSuffix) ? compoundSuffix : labels[labels.length - 1];
}

export function maskBaseUrl(value: unknown) {
  const text = String(value ?? "").trim();
  if (!text) return "";
  const candidate = text.includes("://") ? text : `https://${text}`;
  try {
    const url = new URL(candidate);
    const suffix = domainSuffix(url.hostname);
    return suffix ? `${url.protocol}//*******.${suffix}` : `${url.protocol}//*****`;
  } catch {
    const match = text.match(/^(https?:\/\/)?([^/?#:]+)(?::\d+)?/i);
    const protocol = match?.[1] || "https://";
    const suffix = domainSuffix(match?.[2]);
    return suffix ? `${protocol}*******.${suffix}` : `${protocol}*****`;
  }
}

export function formatTime(value: unknown) {
  if (!value) return "未记录";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function relativeTime(value: unknown) {
  if (!value) return "--";
  const date = new Date(String(value));
  if (Number.isNaN(date.getTime())) return "--";
  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  return `${Math.round(minutes / 60)}h`;
}

export function clampPercent(value: unknown) {
  return Math.max(0, Math.min(100, Number(value || 0)));
}

export function statusLabel(status: unknown) {
  return (
    {
      healthy: "正常",
      warning: "预警",
      offline: "异常",
      never: "未探测",
      valid: "成功",
      invalid: "失败",
      acked: "已确认",
      critical: "严重",
    }[String(status)] || "未知"
  );
}

export function statusDotClass(status: unknown) {
  if (status === "healthy" || status === "valid") return "good";
  if (status === "warning" || status === "never") return "warn";
  return "bad";
}

export function statusBadgeClass(status: unknown) {
  if (["healthy", "valid", "acked"].includes(String(status))) return "good";
  if (["warning", "never"].includes(String(status))) return "warn";
  if (["offline", "invalid", "critical"].includes(String(status))) return "bad";
  return "";
}

export function severityClass(severity: unknown) {
  if (severity === "critical") return "bad";
  if (severity === "warning") return "warn";
  return "";
}

export function severityLabel(severity: unknown) {
  return severity === "critical" ? "严重" : severity === "warning" ? "预警" : "提示";
}

export function kindLabel(kind: unknown) {
  return (
    {
      balance: "余额",
      group: "倍率",
      alert: "告警",
      model: "模型",
    }[String(kind)] || "日志"
  );
}

export function logStatusLabel(status: unknown) {
  if (status === "valid") return "成功";
  if (status === "invalid") return "失败";
  if (status === "acked") return "已确认";
  return severityLabel(status);
}
