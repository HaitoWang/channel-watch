import type { FormEvent } from 'react';

import type { AnyRecord } from './types';
import { monitorDisplayName } from './utils';

export function ChannelModal({
  channelModal,
  settings,
  message,
  onClose,
  onSubmit,
}: {
  channelModal: { mode: "create" } | { mode: "edit"; channel: AnyRecord };
  settings: AnyRecord;
  message: string;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const channel = channelModal.mode === "edit" ? channelModal.channel : {};
  const isEdit = channelModal.mode === "edit";
  const sub2apiBaseUrl = settings.sub2api_base_url || settings.sub2apiBaseUrl || "";
  const sub2apiEmail = settings.sub2api_email || settings.sub2apiEmail || "";
  const sub2apiUserId = settings.sub2api_user_id || settings.sub2apiUserId || "";
  const sub2apiPasswordMasked = settings.sub2api_password_masked || settings.sub2apiPasswordMasked;
  const sub2apiAccessTokenMasked = settings.sub2api_access_token_masked || settings.sub2apiAccessTokenMasked;
  const sub2apiRefreshTokenMasked = settings.sub2api_refresh_token_masked || settings.sub2apiRefreshTokenMasked;
  const defaultRateStop = Boolean(settings.sub2api_disable_on_rate_multiplier_change ?? settings.sub2apiDisableOnRateMultiplierChange);
  const defaultModelStop = Boolean(settings.sub2api_disable_on_model_sync_failure ?? settings.sub2apiDisableOnModelSyncFailure);
  const apiKeyMasked = channel.api_key_masked || channel.apiKeyMasked || channel.key_masked || channel.keyMasked;
  const accessTokenHint =
    channel.has_access_token || channel.hasAccessToken
      ? "已配置，留空则不修改"
      : !isEdit && sub2apiAccessTokenMasked
        ? `设置已配置: ${sub2apiAccessTokenMasked}`
        : "账号同步/余额查询使用";
  const refreshTokenHint = isEdit
    ? "留空则不修改"
    : sub2apiRefreshTokenMasked
      ? `设置已配置: ${sub2apiRefreshTokenMasked}`
      : "sub2Api 自动刷新登录";
  const passwordHint = isEdit ? "留空则不修改" : sub2apiPasswordMasked ? `设置已配置: ${sub2apiPasswordMasked}` : "查余额/自动登录使用";
  return (
    <div className="modal-backdrop" id="channelModal" onMouseDown={(event) => event.currentTarget === event.target && onClose()}>
      <section className="modal-panel" role="dialog" aria-modal="true" aria-labelledby="channelModalTitle">
        <div className="modal-head">
          <h2 id="channelModalTitle">{isEdit ? "编辑渠道" : "新建渠道"}</h2>
          <button className="icon-button" type="button" aria-label="关闭" onClick={onClose}>
            ×
          </button>
        </div>
        <form id="channelForm" className="channel-form" onSubmit={onSubmit}>
          <label>
            <span>渠道名称</span>
            <input name="name" required placeholder="Production Router" autoComplete="off" defaultValue={channel.name || ""} />
          </label>
          <label>
            <span>平台</span>
            <select name="platform" required defaultValue={channel.platform || "sub2Api"}>
              <option value="sub2Api">sub2Api</option>
              <option value="newApi">newApi</option>
            </select>
          </label>
          <label className="span-2">
            <span>Base URL</span>
            <input
              name="base_url"
              placeholder={sub2apiBaseUrl ? `默认: ${sub2apiBaseUrl}；关联账号时可留空` : "https://api.example.com；关联账号时可留空"}
              autoComplete="off"
              defaultValue={channel.base_url || channel.baseUrl || (!isEdit ? sub2apiBaseUrl : "")}
            />
          </label>
          <label>
            <span>API Key</span>
            <input name="api_key" type="password" placeholder={isEdit && apiKeyMasked ? `已配置: ${apiKeyMasked}` : "手动添加单个 Key 时填写"} autoComplete="off" />
          </label>
          <label>
            <span>accessToken</span>
            <input name="access_token" type="password" placeholder={accessTokenHint} autoComplete="off" />
          </label>
          <label>
            <span>refreshToken</span>
            <input name="refresh_token" type="password" placeholder={refreshTokenHint} autoComplete="off" />
          </label>
          <label>
            <span>账号邮箱</span>
            <input name="email" type="email" placeholder="sub2Api 登录邮箱" autoComplete="off" defaultValue={channel.email || (!isEdit ? sub2apiEmail : "")} />
          </label>
          <label>
            <span>登录密码</span>
            <input name="password" type="password" placeholder={passwordHint} autoComplete="off" />
          </label>
          <label>
            <span>userId</span>
            <input name="user_id" placeholder="newApi 必填" autoComplete="off" defaultValue={channel.user_id || channel.userId || (!isEdit ? sub2apiUserId : "")} />
          </label>
          <label>
            <span>预警阈值</span>
            <input name="threshold" type="number" step="0.01" defaultValue={channel.threshold ?? "10"} min="0" />
          </label>
          {isEdit ? (
            <label>
              <span>分组 ID</span>
              <input name="group_id" placeholder="可选" autoComplete="off" defaultValue={channel.group_id || channel.groupId || ""} />
            </label>
          ) : null}
          <label>
            <span>模型范围</span>
            <input name="model_scope" defaultValue={channel.model_scope || channel.modelScope || "All models"} autoComplete="off" />
          </label>
          {isEdit ? (
            <label>
              <span>关联父账号 ID</span>
              <input name="source_channel_id" placeholder="可选，填父账号 ID 创建子 Key" autoComplete="off" defaultValue={channel.source_channel_id || channel.sourceChannelId || ""} />
            </label>
          ) : null}
          <label className="span-2">
            <span>登录校验 Token</span>
            <input name="turnstile_token" type="password" placeholder={isEdit ? "重新登录时可填" : "sub2Api 登录校验可选"} autoComplete="off" />
          </label>
          <label className="check-row">
            <input name="is_enabled" type="checkbox" defaultChecked={Boolean(channel.is_enabled ?? channel.isEnabled ?? true)} />
            <span>参与调度</span>
          </label>
          <label className="check-row span-2">
            <input name="is_demo" type="checkbox" defaultChecked={Boolean(channel.is_demo ?? channel.isDemo)} />
            <span>演示探测</span>
          </label>
          <label className="check-row">
            <input
              name="disable_on_rate_multiplier_change"
              type="checkbox"
              defaultChecked={isEdit ? Boolean(channel.disable_on_rate_multiplier_change ?? channel.disableOnRateMultiplierChange) : defaultRateStop}
            />
            <span>倍率变动停止调度</span>
          </label>
          <label className="check-row">
            <input
              name="disable_on_model_sync_failure"
              type="checkbox"
              defaultChecked={isEdit ? Boolean(channel.disable_on_model_sync_failure ?? channel.disableOnModelSyncFailure) : defaultModelStop}
            />
            <span>模型检测失败停止调度</span>
          </label>
          <div className="modal-actions span-2">
            <span id="formMessage">{message}</span>
            <button className="ghost-button" type="button" onClick={onClose}>
              取消
            </button>
            <button className="primary-button" type="submit">
              {isEdit ? "保存修改" : "保存并探测"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export function KeyModal({
  keyModal,
  message,
  onClose,
  onDraft,
  onSubmit,
}: {
  keyModal: { channel: AnyRecord; draft: AnyRecord; wasDefault: boolean };
  message: string;
  onClose: () => void;
  onDraft: (patch: AnyRecord) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const { channel, draft } = keyModal;
  const groupName = channel.group_name || channel.groupName || "未选择分组";
  const rate = channel.rate_multiplier ?? channel.rateMultiplier;
  return (
    <div className="modal-backdrop" id="keyModal" onMouseDown={(event) => event.currentTarget === event.target && onClose()}>
      <section className="modal-panel key-modal-panel" role="dialog" aria-modal="true" aria-labelledby="keyModalTitle">
        <div className="modal-head">
          <h2 id="keyModalTitle">编辑 Key</h2>
          <button className="icon-button" type="button" aria-label="关闭" onClick={onClose}>
            ×
          </button>
        </div>
        <form id="keyForm" className="channel-form key-form" onSubmit={onSubmit}>
          <input name="id" type="hidden" value={channel.id || ""} readOnly />
          <label className="span-2">
            <span>Key 名称</span>
            <input name="name" required placeholder="例如 GPT-PRO" autoComplete="off" value={draft.name || ""} onChange={(event) => onDraft({ name: event.target.value })} />
          </label>
          <label>
            <span>Key 类型</span>
            <select name="key_provider" value={draft.key_provider || ""} onChange={(event) => onDraft({ key_provider: event.target.value })}>
              <option value="">自动识别</option>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
            </select>
          </label>
          <label>
            <span>探测间隔</span>
            <input
              name="monitor_interval_seconds"
              type="number"
              min="15"
              step="1"
              value={draft.monitor_interval_seconds || 60}
              onChange={(event) => onDraft({ monitor_interval_seconds: event.target.value })}
            />
          </label>
          <label className="span-2">
            <span>监控模型</span>
            <input
              name="monitor_models"
              placeholder="多个模型用英文逗号分隔"
              autoComplete="off"
              value={draft.monitor_models || ""}
              onChange={(event) => onDraft({ monitor_models: event.target.value })}
            />
          </label>
          <label>
            <span>密钥</span>
            <input name="key_masked" value={channel.key_masked || channel.keyMasked || "未配置密钥"} disabled readOnly />
          </label>
          <label>
            <span>分组 / 倍率</span>
            <input name="key_context" value={`${groupName} / ${rate ?? "未知"}x`} disabled readOnly />
          </label>
          <label className="check-row">
            <input
              name="is_enabled"
              type="checkbox"
              checked={Boolean(draft.is_enabled)}
              onChange={(event) => onDraft({ is_enabled: event.target.checked })}
            />
            <span>参与调度</span>
          </label>
          <label className="check-row">
            <input
              name="is_monitoring"
              type="checkbox"
              checked={Boolean(draft.is_monitoring)}
              onChange={(event) => onDraft({ is_monitoring: event.target.checked })}
            />
            <span>启动监控</span>
          </label>
          <label className="check-row">
            <input
              name="is_default_key"
              type="checkbox"
              checked={Boolean(draft.is_default_key)}
              onChange={(event) => onDraft({ is_default_key: event.target.checked })}
            />
            <span>设为默认 Key</span>
          </label>
          <label className="check-row">
            <input
              name="disable_on_rate_multiplier_change"
              type="checkbox"
              checked={Boolean(draft.disable_on_rate_multiplier_change)}
              onChange={(event) => onDraft({ disable_on_rate_multiplier_change: event.target.checked })}
            />
            <span>倍率变动停止调度</span>
          </label>
          <label className="check-row">
            <input
              name="disable_on_model_sync_failure"
              type="checkbox"
              checked={Boolean(draft.disable_on_model_sync_failure)}
              onChange={(event) => onDraft({ disable_on_model_sync_failure: event.target.checked })}
            />
            <span>模型检测失败停止调度</span>
          </label>
          <div className="settings-divider span-2" role="separator">号池自动调度（根据本 Key 上游指标开关我方号池账号）</div>
          <label className="span-2">
            <span>映射号池账号 ID</span>
            <input
              name="pool_account_ids"
              placeholder="我方 sub2api account id，多个用逗号分隔，如 12,15,18"
              autoComplete="off"
              value={draft.pool_account_ids || ""}
              onChange={(event) => onDraft({ pool_account_ids: event.target.value })}
            />
          </label>
          <label>
            <span>倍率阈值（覆盖，选填）</span>
            <input
              name="pool_rate_threshold"
              type="number"
              step="0.0001"
              min="0"
              placeholder="留空=用卖价/毛利自动算"
              value={draft.pool_rate_threshold ?? ""}
              onChange={(event) => onDraft({ pool_rate_threshold: event.target.value })}
            />
          </label>
          <label>
            <span>卖价倍率（覆盖，选填）</span>
            <input
              name="pool_sell_rate"
              type="number"
              step="0.0001"
              min="0"
              placeholder="留空=用全局卖价"
              value={draft.pool_sell_rate ?? ""}
              onChange={(event) => onDraft({ pool_sell_rate: event.target.value })}
            />
          </label>
          <label>
            <span>目标毛利率 %（覆盖，选填）</span>
            <input
              name="pool_target_margin"
              type="number"
              step="1"
              min="0"
              placeholder="留空=用全局毛利率"
              value={draft.pool_target_margin ?? ""}
              onChange={(event) => onDraft({ pool_target_margin: event.target.value })}
            />
          </label>
          <label className="check-row">
            <input
              name="pool_auto_schedule"
              type="checkbox"
              checked={Boolean(draft.pool_auto_schedule)}
              onChange={(event) => onDraft({ pool_auto_schedule: event.target.checked })}
            />
            <span>参与号池自动调度</span>
          </label>
          <div className="modal-actions span-2">
            <span id="keyFormMessage">{message}</span>
            <button className="ghost-button" type="button" onClick={onClose}>
              取消
            </button>
            <button className="primary-button" type="submit">
              保存 Key
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

type MonitorLogRow = {
  title: string;
  status: string;
  detail: string;
  tone: string;
};

function monitorLogRows(channel: AnyRecord): MonitorLogRow[] {
  const result = channel.monitor_result || channel.monitorResult || {};
  const models = Array.isArray(result.models) ? result.models : [];
  const failures = Array.isArray(result.failures) ? result.failures : [];
  const rows: MonitorLogRow[] = models.map((item: AnyRecord) => ({
    title: String(item.model || "未配置模型"),
    status: item.ok === false ? "失败" : item.ok === true ? "成功" : "等待",
    detail: String(monitorLogDetail(item)),
    tone: item.ok === false ? "bad" : item.ok === true ? "good" : "warn",
  }));
  const lastError = channel.monitor_last_error || channel.monitorLastError;
  if (!rows.length && lastError) {
    rows.push({ title: "最近错误", status: "失败", detail: String(lastError), tone: "bad" });
  }
  failures.forEach((failure: unknown) => rows.push({ title: "失败详情", status: "失败", detail: String(failure), tone: "bad" }));
  return rows;
}

function monitorLogDetail(item: AnyRecord) {
  const latency = item.latency_ms ?? item.latencyMs;
  const protocol = item.protocol || "protocol";
  const probeSummary = latency === undefined || latency === null ? protocol : `${protocol} · ${latency}ms`;
  if (item.ok === false) return item.error || item.message || item.summary || probeSummary;
  if (item.ok === true) return probeSummary;
  return item.summary || probeSummary;
}

export function MonitorLogModal({ channel, message, onClose }: { channel: AnyRecord; message: string; onClose: () => void }) {
  const checkedAt = channel.monitor_last_checked_at || channel.monitorLastCheckedAt;
  const error = channel.monitor_last_error || channel.monitorLastError;
  const rows = monitorLogRows(channel);
  return (
    <div className="modal-backdrop" id="monitorLogModal" onMouseDown={(event) => event.currentTarget === event.target && onClose()}>
      <section className="modal-panel monitor-log-panel" role="dialog" aria-modal="true" aria-labelledby="monitorLogTitle">
        <div className="modal-head">
          <h2 id="monitorLogTitle">监控日志</h2>
          <button className="icon-button" type="button" aria-label="关闭" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="monitor-log-body" id="monitorLogBody">
          <div className="monitor-log-summary">
            <strong>{monitorDisplayName(channel)}</strong>
            <span>
              {channel.key_provider || channel.keyProvider || "自动识别"} · {checkedAt ? String(checkedAt) : "未探测"}
            </span>
          </div>
          {error ? (
            <div className="monitor-log-error">
              <strong>最近错误</strong>
              <p>{error}</p>
            </div>
          ) : (
            <div className="monitor-log-empty">暂无错误信息</div>
          )}
          <div className="monitor-log-list">
            {rows.length ? (
              rows.map((row, index) => (
                <article className={`monitor-log-row ${row.tone}`} key={`${row.title}-${index}`}>
                  <div>
                    <strong>{row.title}</strong>
                    <p>{row.detail || "--"}</p>
                  </div>
                  <span>{row.status}</span>
                </article>
              ))
            ) : (
              <div className="monitor-log-empty">暂无模型探测记录</div>
            )}
          </div>
        </div>
        <div className="modal-actions monitor-log-actions">
          <span id="monitorLogMessage">{message}</span>
          <button className="ghost-button" type="button" onClick={onClose}>
            关闭
          </button>
        </div>
      </section>
    </div>
  );
}
