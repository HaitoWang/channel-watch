import type { FormEvent } from 'react';

import type { AnyRecord } from './types';
import { monitorDisplayName } from './utils';

export function ChannelModal({
  channelModal,
  message,
  onClose,
  onSubmit,
}: {
  channelModal: { mode: "create" } | { mode: "edit"; channel: AnyRecord };
  message: string;
  onClose: () => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  const channel = channelModal.mode === "edit" ? channelModal.channel : {};
  const isEdit = channelModal.mode === "edit";
  const apiKeyMasked = channel.api_key_masked || channel.apiKeyMasked || channel.key_masked || channel.keyMasked;
  const accessTokenHint = channel.has_access_token || channel.hasAccessToken ? "已配置，留空则不修改" : "账号同步/余额查询使用";
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
            <input name="base_url" required placeholder="https://api.example.com" autoComplete="off" defaultValue={channel.base_url || channel.baseUrl || ""} />
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
            <input name="refresh_token" type="password" placeholder={isEdit ? "留空则不修改" : "sub2Api 自动刷新登录"} autoComplete="off" />
          </label>
          <label>
            <span>账号邮箱</span>
            <input name="email" type="email" placeholder="sub2Api 登录邮箱" autoComplete="off" defaultValue={channel.email || ""} />
          </label>
          <label>
            <span>登录密码</span>
            <input name="password" type="password" placeholder={isEdit ? "留空则不修改" : "sub2Api 登录密码"} autoComplete="off" />
          </label>
          <label>
            <span>userId</span>
            <input name="user_id" placeholder="newApi 必填" autoComplete="off" defaultValue={channel.user_id || channel.userId || ""} />
          </label>
          <label>
            <span>预警阈值</span>
            <input name="threshold" type="number" step="0.01" defaultValue={channel.threshold ?? "10"} min="0" />
          </label>
          <label>
            <span>分组 ID</span>
            <input name="group_id" placeholder="可选" autoComplete="off" defaultValue={channel.group_id || channel.groupId || ""} />
          </label>
          <label>
            <span>模型范围</span>
            <input name="model_scope" defaultValue={channel.model_scope || channel.modelScope || "All models"} autoComplete="off" />
          </label>
          <label className="span-2">
            <span>登录校验 Token</span>
            <input name="turnstile_token" type="password" placeholder={isEdit ? "重新登录时可填" : "sub2Api 登录校验可选"} autoComplete="off" />
          </label>
          <label className="check-row span-2">
            <input name="is_demo" type="checkbox" defaultChecked={Boolean(channel.is_demo ?? channel.isDemo)} />
            <span>演示探测</span>
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
