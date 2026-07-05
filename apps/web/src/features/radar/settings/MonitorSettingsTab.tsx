import type { AnyRecord } from "../types";
import { qqbotStatusLabel } from "./monitorStatus";
import { PushplusFields } from "./PushplusFields";
import { QqbotFields } from "./QqbotFields";
import { ServerchanFields } from "./ServerchanFields";

/** "渠道监控配置" tab: notification channel + trigger events. */
export function MonitorSettingsTab({
  settings,
  draft,
  onDraft,
}: {
  settings: AnyRecord;
  draft: AnyRecord;
  onDraft: (patch: AnyRecord) => void;
}) {
  const enabled = Boolean(settings.notification_enabled ?? settings.notificationEnabled);
  const channel = draft.notification_channel || "pushplus";
  const pushplusConfigured = Boolean(settings.pushplus_configured ?? settings.pushplusConfigured);
  const pushplusMasked = settings.pushplus_token_masked || settings.pushplusTokenMasked;
  const serverchanConfigured = Boolean(settings.serverchan_configured ?? settings.serverchanConfigured);
  const serverchanMasked = settings.serverchan_send_key_masked || settings.serverchanSendKeyMasked;
  const qqbotConfigured = Boolean(settings.qqbot_configured ?? settings.qqbotConfigured);
  const qqbotTargetMasked = settings.qqbot_target_id_masked || settings.qqbotTargetIdMasked;
  const qqbotTargetLabel = settings.qqbot_target_label || settings.qqbotTargetLabel || "QQBot";
  const qqbotTargetType = draft.qqbot_target_type || "subscribers";
  const qqbotSubscriberCount = Number(settings.qqbot_subscriber_count ?? settings.qqbotSubscriberCount ?? 0);
  const qqbotGatewayStatus = settings.qqbot_gateway_status || settings.qqbotGatewayStatus || "stopped";
  const qqbotGatewayStatusLabel = qqbotStatusLabel(qqbotGatewayStatus);
  const channelLabel = channel === "serverchan" ? "Server酱" : channel === "qqbot" ? "QQBot" : "pushplus";
  const credentialStatus =
    channel === "serverchan"
      ? serverchanConfigured
        ? `SendKey ${serverchanMasked}`
        : "SendKey 未配置"
      : channel === "qqbot"
        ? qqbotConfigured
          ? qqbotTargetType === "subscribers"
            ? `WebSocket ${qqbotGatewayStatusLabel} · 订阅 ${qqbotSubscriberCount} 个`
            : `WebSocket ${qqbotGatewayStatusLabel} · ${qqbotTargetLabel} ${qqbotTargetMasked || "已配置"}`
          : "QQBot 未配置"
      : pushplusConfigured
        ? `Token ${pushplusMasked}`
        : "Token 未配置";

  return (
    <>
      <section className="settings-card span-2">
        <header className="settings-card-head">
          <div>
            <h3>通知通道</h3>
            <p>{credentialStatus}</p>
          </div>
          <div className="settings-status">
            <span className={`badge ${enabled ? "good" : "warn"}`}>{enabled ? "已启用" : "未启用"}</span>
            <span className="badge">{channelLabel}</span>
          </div>
        </header>
        <div className="settings-grid">
          <label className="settings-toggle-row span-2">
            <input
              name="notification_enabled"
              type="checkbox"
              checked={Boolean(draft.notification_enabled)}
              onChange={(event) => onDraft({ notification_enabled: event.target.checked })}
            />
            <span>启用通知</span>
          </label>
          <label>
            <span>通知通道</span>
            <select name="notification_channel" value={channel} onChange={(event) => onDraft({ notification_channel: event.target.value })}>
              <option value="pushplus">pushplus</option>
              <option value="serverchan">Server酱</option>
              <option value="qqbot">QQBot</option>
            </select>
          </label>
        </div>

        <PushplusFields channel={channel} settings={settings} draft={draft} onDraft={onDraft} />
        <ServerchanFields channel={channel} settings={settings} draft={draft} onDraft={onDraft} />
        <QqbotFields channel={channel} settings={settings} draft={draft} onDraft={onDraft} />
      </section>

      <section className="settings-card settings-events span-2">
        <header className="settings-card-head">
          <div>
            <h3>触发事件</h3>
            <p>通知发送范围</p>
          </div>
        </header>
        <div className="settings-event-grid">
          <label className="settings-toggle-row">
            <input
              name="notify_low_balance"
              type="checkbox"
              checked={Boolean(draft.notify_low_balance)}
              onChange={(event) => onDraft({ notify_low_balance: event.target.checked })}
            />
            <span>余额低于阈值</span>
          </label>
          <label className="settings-toggle-row">
            <input
              name="notify_rate_change"
              type="checkbox"
              checked={Boolean(draft.notify_rate_change)}
              onChange={(event) => onDraft({ notify_rate_change: event.target.checked })}
            />
            <span>倍率变化</span>
          </label>
          <label className="settings-toggle-row">
            <input
              name="notify_model_failure"
              type="checkbox"
              checked={Boolean(draft.notify_model_failure)}
              onChange={(event) => onDraft({ notify_model_failure: event.target.checked })}
            />
            <span>模型监控失败</span>
          </label>
        </div>
      </section>
    </>
  );
}
