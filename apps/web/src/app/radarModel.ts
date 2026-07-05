export type ViewName = "overview" | "channels" | "monitor" | "alerts" | "rates" | "usage" | "logs" | "settings";
export type AnyRecord = Record<string, any>;

export type RadarState = {
  channels: AnyRecord[];
  accounts: AnyRecord[];
  events: AnyRecord[];
  allEvents: AnyRecord[];
  history: AnyRecord[];
  usage: AnyRecord;
  rates: AnyRecord;
  monitor: AnyRecord;
  settings: AnyRecord;
  overview: AnyRecord;
};

export const viewMeta: Record<ViewName, { title: string; subtitle: string }> = {
  overview: { title: "渠道雷达", subtitle: "newApi / sub2Api 状态概览" },
  channels: { title: "渠道管理", subtitle: "Base URL、凭证、阈值和探测状态" },
  monitor: { title: "监控室", subtitle: "已启动监控的 Key 和模型探测结果" },
  alerts: { title: "告警中心", subtitle: "余额阈值、探测失败和倍率变化" },
  rates: { title: "分组倍率", subtitle: "分组、模型范围和有效倍率" },
  usage: { title: "消耗分析", subtitle: "余额、消耗和低余额风险" },
  logs: { title: "探测日志", subtitle: "余额、倍率和告警时间线" },
  settings: { title: "通知设置", subtitle: "pushplus / Server酱 / QQBot 通知" },
};

export const MONITOR_REFRESH_MS = 5000;
export const CHANNEL_REFRESH_MS = 30000;

export const initialRadarState: RadarState = {
  channels: [],
  accounts: [],
  events: [],
  allEvents: [],
  history: [],
  usage: { summary: {}, channels: [], history: [] },
  rates: { summary: {}, channels: [], history: [] },
  monitor: { summary: {}, channels: [] },
  settings: {},
  overview: {},
};

export function initialView(): ViewName {
  const hash = window.location.hash.slice(1) as ViewName;
  return viewMeta[hash] ? hash : "overview";
}

export function field(item: AnyRecord, snake: string, camel?: string) {
  return item[snake] ?? item[camel || snake];
}

export function boolField(item: AnyRecord, snake: string, camel?: string) {
  return Boolean(field(item, snake, camel));
}

export function providerDefaultModels(provider: string | null | undefined) {
  if (provider === "openai") return ["gpt-5.5"];
  if (provider === "anthropic") return ["claude-sonnet-4-5"];
  return ["gpt-5.5", "claude-sonnet-4-5"];
}

export function splitModels(value: string) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function isDefaultModelList(value: string) {
  const normalized = splitModels(value).join(",");
  return ["", "gpt-5.5", "claude-sonnet-4-5", "gpt-5.5,claude-sonnet-4-5"].includes(normalized);
}

export function settingsFromBackend(settings: AnyRecord) {
  return {
    notification_enabled: Boolean(settings.notification_enabled ?? settings.notificationEnabled),
    notification_channel: settings.notification_channel || settings.notificationChannel || "pushplus",
    pushplus_channel: settings.pushplus_channel || settings.pushplusChannel || "wechat",
    pushplus_template: settings.pushplus_template || settings.pushplusTemplate || "markdown",
    qqbot_app_id: settings.qqbot_app_id || settings.qqbotAppId || "",
    qqbot_target_type: settings.qqbot_target_type || settings.qqbotTargetType || "subscribers",
    qqbot_target_id: settings.qqbot_target_id || settings.qqbotTargetId || "",
    notify_low_balance: settings.notify_low_balance ?? settings.notifyLowBalance ?? true,
    notify_rate_change: settings.notify_rate_change ?? settings.notifyRateChange ?? true,
    notify_model_failure: settings.notify_model_failure ?? settings.notifyModelFailure ?? true,
    pushplus_token: "",
    serverchan_send_key: "",
    qqbot_secret: "",
    clear_pushplus_token: false,
    clear_serverchan_send_key: false,
    clear_qqbot_secret: false,
  };
}

export function settingsPayloadFromDraft(draft: AnyRecord) {
  const payload = { ...draft };
  const pushplusToken = String(payload.pushplus_token || "").trim();
  const serverchanSendKey = String(payload.serverchan_send_key || "").trim();
  const qqbotSecret = String(payload.qqbot_secret || "").trim();
  if (pushplusToken) payload.pushplus_token = pushplusToken;
  else delete payload.pushplus_token;
  if (serverchanSendKey) payload.serverchan_send_key = serverchanSendKey;
  else delete payload.serverchan_send_key;
  if (qqbotSecret) payload.qqbot_secret = qqbotSecret;
  else delete payload.qqbot_secret;
  payload.qqbot_app_id = String(payload.qqbot_app_id || "").trim();
  payload.qqbot_target_id = String(payload.qqbot_target_id || "").trim();
  if ((payload.qqbot_target_type || "subscribers") === "subscribers") payload.qqbot_target_id = "";
  return payload;
}
