import type { FormEvent } from 'react';

import type { AnyRecord } from './types';
import { Panel } from './layout';
import { formatTime } from '../../shared/formatters';

export function SettingsPanel({
  active,
  settings,
  draft,
  message,
  onDraft,
  onSubmit,
  onTest,
}: {
  active: boolean;
  settings: AnyRecord;
  draft: AnyRecord;
  message: string;
  onDraft: (patch: AnyRecord) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onTest: () => void;
}) {
  const enabled = Boolean(settings.notification_enabled ?? settings.notificationEnabled);
  const channel = draft.notification_channel || "pushplus";
  const pushplusConfigured = Boolean(settings.pushplus_configured ?? settings.pushplusConfigured);
  const pushplusMasked = settings.pushplus_token_masked || settings.pushplusTokenMasked;
  const serverchanConfigured = Boolean(settings.serverchan_configured ?? settings.serverchanConfigured);
  const serverchanMasked = settings.serverchan_send_key_masked || settings.serverchanSendKeyMasked;
  const qqbotConfigured = Boolean(settings.qqbot_configured ?? settings.qqbotConfigured);
  const qqbotSecretMasked = settings.qqbot_secret_masked || settings.qqbotSecretMasked || settings.qqbot_client_secret_masked || settings.qqbotClientSecretMasked;
  const qqbotTargetMasked = settings.qqbot_target_id_masked || settings.qqbotTargetIdMasked;
  const qqbotTargetLabel = settings.qqbot_target_label || settings.qqbotTargetLabel || "QQBot";
  const qqbotTargetType = draft.qqbot_target_type || "subscribers";
  const qqbotSubscriberCount = Number(settings.qqbot_subscriber_count ?? settings.qqbotSubscriberCount ?? 0);
  const qqbotLastTargetMasked = settings.qqbot_last_target_id_masked || settings.qqbotLastTargetIdMasked;
  const qqbotLastEventType = settings.qqbot_last_event_type || settings.qqbotLastEventType;
  const qqbotLastEventAt = settings.qqbot_last_event_at || settings.qqbotLastEventAt;
  const qqbotGatewayStatus = settings.qqbot_gateway_status || settings.qqbotGatewayStatus || "stopped";
  const qqbotGatewayLastConnectedAt = settings.qqbot_gateway_last_connected_at || settings.qqbotGatewayLastConnectedAt;
  const qqbotGatewayLastError = settings.qqbot_gateway_last_error || settings.qqbotGatewayLastError;
  const qqbotGatewayStatusLabel =
    qqbotGatewayStatus === "connected"
      ? "已连接"
      : qqbotGatewayStatus === "connecting"
        ? "连接中"
        : qqbotGatewayStatus === "disabled"
          ? "未配置"
          : qqbotGatewayStatus === "error"
            ? "连接异常"
            : "未连接";
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
    <Panel active={active} viewName="settings">
      <section className="settings-panel" aria-label="通知设置">
        <header className="settings-head">
          <div>
            <h2>通知通道</h2>
            <p>多通道告警推送</p>
          </div>
          <div className="settings-status" id="settingsStatus">
            <span className={`badge ${enabled ? "good" : "warn"}`}>{enabled ? "已启用" : "未启用"}</span>
            <span className="badge">{channelLabel}</span>
            <span className="badge">{credentialStatus}</span>
          </div>
        </header>
        <form id="settingsForm" className="channel-form settings-form" onSubmit={onSubmit}>
          <label className="check-row span-2">
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
          <div></div>
          <div className="settings-channel span-2" id="pushplusSettings" hidden={channel !== "pushplus"}>
            <div className="settings-subhead">
              <strong>pushplus</strong>
            </div>
            <label>
              <span>Token</span>
              <input
                name="pushplus_token"
                type="password"
                autoComplete="off"
                placeholder={pushplusConfigured ? `已配置: ${pushplusMasked}` : "填写 pushplus token"}
                value={draft.pushplus_token || ""}
                onChange={(event) => onDraft({ pushplus_token: event.target.value })}
              />
            </label>
            <label>
              <span>发送通道</span>
              <select name="pushplus_channel" value={draft.pushplus_channel || "wechat"} onChange={(event) => onDraft({ pushplus_channel: event.target.value })}>
                <option value="wechat">wechat</option>
                <option value="webhook">webhook</option>
                <option value="cp">企业微信</option>
                <option value="mail">邮件</option>
                <option value="sms">短信</option>
                <option value="call">语音</option>
                <option value="app">App</option>
              </select>
            </label>
            <label>
              <span>消息模板</span>
              <select name="pushplus_template" value={draft.pushplus_template || "markdown"} onChange={(event) => onDraft({ pushplus_template: event.target.value })}>
                <option value="markdown">markdown</option>
                <option value="html">html</option>
                <option value="txt">txt</option>
                <option value="json">json</option>
              </select>
            </label>
            <label className="check-row">
              <input
                name="clear_pushplus_token"
                type="checkbox"
                checked={Boolean(draft.clear_pushplus_token)}
                onChange={(event) => onDraft({ clear_pushplus_token: event.target.checked })}
              />
              <span>清空当前 Token</span>
            </label>
          </div>
          <div className="settings-channel span-2" id="serverchanSettings" hidden={channel !== "serverchan"}>
            <div className="settings-subhead">
              <strong>Server酱</strong>
            </div>
            <label>
              <span>SendKey</span>
              <input
                name="serverchan_send_key"
                type="password"
                autoComplete="off"
                placeholder={serverchanConfigured ? `已配置: ${serverchanMasked}` : "填写 Server酱 SendKey"}
                value={draft.serverchan_send_key || ""}
                onChange={(event) => onDraft({ serverchan_send_key: event.target.value })}
              />
            </label>
            <label className="check-row">
              <input
                name="clear_serverchan_send_key"
                type="checkbox"
                checked={Boolean(draft.clear_serverchan_send_key)}
                onChange={(event) => onDraft({ clear_serverchan_send_key: event.target.checked })}
              />
              <span>清空当前 SendKey</span>
            </label>
          </div>
          <div className="settings-channel span-2" id="qqbotSettings" hidden={channel !== "qqbot"}>
            <div className="settings-subhead">
              <strong>QQBot</strong>
            </div>
            <label>
              <span>AppID</span>
              <input
                name="qqbot_app_id"
                autoComplete="off"
                placeholder="填写 QQBot AppID"
                value={draft.qqbot_app_id || ""}
                onChange={(event) => onDraft({ qqbot_app_id: event.target.value })}
              />
            </label>
            <label>
              <span>Secret</span>
              <input
                name="qqbot_secret"
                type="password"
                autoComplete="off"
                placeholder={qqbotSecretMasked ? `已配置: ${qqbotSecretMasked}` : "填写 Secret"}
                value={draft.qqbot_secret || ""}
                onChange={(event) => onDraft({ qqbot_secret: event.target.value })}
              />
            </label>
            <label>
              <span>目标类型</span>
              <select name="qqbot_target_type" value={qqbotTargetType} onChange={(event) => onDraft({ qqbot_target_type: event.target.value })}>
                <option value="subscribers">自动订阅列表</option>
                <option value="group">QQ群</option>
                <option value="user">QQ单聊</option>
                <option value="channel">频道子频道</option>
                <option value="guild_dm">频道私信</option>
              </select>
            </label>
            {qqbotTargetType === "subscribers" ? (
              <label>
                <span>订阅对象</span>
                <input name="qqbot_subscriber_count" readOnly value={`${qqbotSubscriberCount} 个`} />
              </label>
            ) : (
              <label>
                <span>目标 ID</span>
                <input
                  name="qqbot_target_id"
                  autoComplete="off"
                  placeholder={qqbotTargetMasked ? `已配置: ${qqbotTargetMasked}` : "填写 openid / group_openid / channel_id"}
                  value={draft.qqbot_target_id || ""}
                  onChange={(event) => onDraft({ qqbot_target_id: event.target.value })}
                />
              </label>
            )}
            <label>
              <span>连接方式</span>
              <input name="qqbot_transport" readOnly value="WebSocket 长连接" />
            </label>
            <label>
              <span>连接状态</span>
              <input name="qqbot_gateway_status" readOnly value={qqbotGatewayStatusLabel} />
            </label>
            <label>
              <span>测试指令</span>
              <input name="qqbot_test_command" readOnly value="测试" />
            </label>
            <label className="check-row">
              <input
                name="clear_qqbot_secret"
                type="checkbox"
                checked={Boolean(draft.clear_qqbot_secret)}
                onChange={(event) => onDraft({ clear_qqbot_secret: event.target.checked })}
              />
              <span>清空当前 Secret</span>
            </label>
            {(qqbotGatewayStatus || qqbotGatewayLastConnectedAt || qqbotGatewayLastError || qqbotLastTargetMasked || qqbotLastEventType) && (
              <div className="settings-hints">
                <span className={`badge ${qqbotGatewayStatus === "connected" ? "good" : qqbotGatewayStatus === "error" ? "bad" : ""}`}>{qqbotGatewayStatusLabel}</span>
                {qqbotGatewayLastConnectedAt && <span className="badge">{formatTime(qqbotGatewayLastConnectedAt)}</span>}
                {qqbotLastEventType && <span className="badge">{qqbotLastEventType}</span>}
                {qqbotLastTargetMasked && <span className="badge">{qqbotLastTargetMasked}</span>}
                {qqbotLastEventAt && <span className="badge">{formatTime(qqbotLastEventAt)}</span>}
                {qqbotGatewayLastError && <span className="badge bad">{qqbotGatewayLastError}</span>}
              </div>
            )}
          </div>
          <div className="settings-subhead span-2">
            <strong>触发事件</strong>
          </div>
          <label className="check-row">
            <input
              name="notify_low_balance"
              type="checkbox"
              checked={Boolean(draft.notify_low_balance)}
              onChange={(event) => onDraft({ notify_low_balance: event.target.checked })}
            />
            <span>余额低于阈值</span>
          </label>
          <label className="check-row">
            <input
              name="notify_rate_change"
              type="checkbox"
              checked={Boolean(draft.notify_rate_change)}
              onChange={(event) => onDraft({ notify_rate_change: event.target.checked })}
            />
            <span>倍率变化</span>
          </label>
          <label className="check-row">
            <input
              name="notify_model_failure"
              type="checkbox"
              checked={Boolean(draft.notify_model_failure)}
              onChange={(event) => onDraft({ notify_model_failure: event.target.checked })}
            />
            <span>模型监控失败</span>
          </label>
          <div className="modal-actions span-2">
            <span id="settingsMessage">{message}</span>
            <button className="ghost-button" type="button" onClick={onTest}>
              <span className="icon icon-bell" aria-hidden="true"></span>
              测试当前通道
            </button>
            <button className="primary-button" type="submit">
              保存设置
            </button>
          </div>
        </form>
      </section>
    </Panel>
  );
}
