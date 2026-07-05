import type { AnyRecord } from './types';

export function field(item: AnyRecord, snake: string, camel?: string) {
  return item[snake] ?? item[camel || snake];
}

export function boolField(item: AnyRecord, snake: string, camel?: string) {
  return Boolean(field(item, snake, camel));
}

export function monitorProvider(model: unknown, platform?: unknown) {
  const normalized = String(model || "").toLowerCase();
  if (normalized.includes("anthropic") || normalized.includes("claude")) return { label: "Anthropic", className: "claude" };
  if (normalized.includes("gemini")) return { label: "Gemini", className: "gemini" };
  if (normalized.includes("gpt") || normalized.includes("o1") || normalized.includes("openai")) return { label: "OpenAI", className: "openai" };
  return { label: String(platform || "模型"), className: "generic" };
}

export function monitorStatusMeta(status: unknown) {
  if (status === "healthy") return { label: "正常", tone: "good" };
  if (status === "failed") return { label: "异常", tone: "bad" };
  if (status === "checking") return { label: "探测中", tone: "warn" };
  return { label: "等待", tone: "warn" };
}

export function monitorDisplayName(channel: AnyRecord) {
  const parentName = channel.parent_name || channel.parentName;
  const accountName = parentName || channel.name;
  const keyName = channel.key_name || channel.keyName || (parentName ? channel.name : "");
  if (accountName && keyName && accountName !== keyName) return `${accountName}-${keyName}`;
  return accountName || keyName || channel.name || "未命名 Key";
}

export function monitorPrimaryModel(models: string[], modelResults: AnyRecord[]) {
  const fromResult = modelResults.find((item) => item?.model)?.model;
  return fromResult || models[0] || "未配置模型";
}

export function monitorLatencyValue(channel: AnyRecord, modelResults: AnyRecord[], mode = "max") {
  const direct = channel.monitor_latency_ms ?? channel.monitorLatencyMs;
  const values = modelResults
    .map((item) => item.latency_ms ?? item.latencyMs)
    .map((value) => Number(value))
    .filter((value) => Number.isFinite(value));
  if (mode === "max" && direct != null && direct !== "") return Number(direct);
  if (!values.length) return null;
  return mode === "min" ? Math.min(...values) : Math.max(...values);
}

export function formatLatency(value: unknown) {
  const number = Number(value);
  return Number.isFinite(number) ? `${Math.round(number)}ms` : "--";
}

export function nextMonitorRefresh(channel: AnyRecord) {
  const checkedAt = channel.monitor_last_checked_at || channel.monitorLastCheckedAt;
  if (!checkedAt) return "等待首次";
  const checkedDate = new Date(checkedAt);
  if (Number.isNaN(checkedDate.getTime())) return "等待首次";
  const interval = Number(channel.monitor_interval_seconds ?? channel.monitorIntervalSeconds ?? 60);
  const remaining = Math.max(0, Math.round(interval - (Date.now() - checkedDate.getTime()) / 1000));
  return `${remaining}s 后刷新`;
}
