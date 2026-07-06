import type { AnyRecord } from './types';
import { Panel } from './layout';
import { boolField, monitorProvider } from './utils';
import { clampPercent, formatMoney, formatRate, formatTime, maskBaseUrl, statusDotClass, statusLabel } from '../../shared/formatters';

export function ChannelsPanel({
  active,
  accounts,
  filter,
  expandedIds,
  loadingIds,
  onFilter,
  onToggleExpand,
  onProbe,
  onSyncKeys,
  onRelogin,
  onEditChannel,
  onDeleteChannel,
  onToggleMonitor,
  onEditKey,
  onSetDefault,
  onProbeModels,
  onPoolSchedule,
  onPoolPreview,
}: {
  active: boolean;
  accounts: AnyRecord[];
  filter: string;
  expandedIds: Set<number>;
  loadingIds: Set<number>;
  onFilter: (value: string) => void;
  onToggleExpand: (id: number) => void;
  onProbe: (id: number) => void;
  onSyncKeys: (id: number) => void;
  onRelogin: (channel: AnyRecord) => void;
  onEditChannel: (channel: AnyRecord) => void;
  onDeleteChannel: (channel: AnyRecord) => void;
  onToggleMonitor: (channel: AnyRecord) => void;
  onEditKey: (channel: AnyRecord) => void;
  onSetDefault: (id: number) => void;
  onProbeModels: (id: number) => void;
  onPoolSchedule: (id: number) => void;
  onPoolPreview: (id: number) => void;
}) {
  const visibleAccounts: AnyRecord[] = accounts
    .map((account: AnyRecord) => ({
      ...account,
      children: filter === "all" ? account.children || [] : (account.children || []).filter((child: AnyRecord) => child.status === filter),
    }))
    .filter((account) => filter === "all" || account.children.length);

  return (
    <Panel active={active} viewName="channels">
      <section className="toolbar actions-only" aria-label="渠道筛选">
        <div className="filters" role="group" aria-label="状态筛选">
          {[
            ["all", "全部"],
            ["healthy", "正常"],
            ["warning", "预警"],
            ["offline", "异常"],
            ["never", "未探测"],
          ].map(([value, label]) => (
            <button className={filter === value ? "filter-chip active" : "filter-chip"} key={value} type="button" onClick={() => onFilter(value)}>
              {label}
            </button>
          ))}
        </div>
      </section>
      <section className="channel-list" id="channelList" aria-label="渠道列表">
        {visibleAccounts.length ? (
          visibleAccounts.map((account) => (
            <AccountRow
              account={account}
              expanded={expandedIds.has(Number(account.id))}
              key={account.id}
              loading={loadingIds.has(Number(account.id))}
              loadingIds={loadingIds}
              onProbe={onProbe}
              onSyncKeys={onSyncKeys}
              onRelogin={onRelogin}
              onEditChannel={onEditChannel}
              onDeleteChannel={onDeleteChannel}
              onToggleExpand={onToggleExpand}
              onToggleMonitor={onToggleMonitor}
              onEditKey={onEditKey}
              onSetDefault={onSetDefault}
              onProbeModels={onProbeModels}
              onPoolSchedule={onPoolSchedule}
              onPoolPreview={onPoolPreview}
            />
          ))
        ) : (
          <div className="list-state">暂无账号或渠道</div>
        )}
      </section>
    </Panel>
  );
}

function AccountRow({
  account,
  expanded,
  loading,
  loadingIds,
  onProbe,
  onSyncKeys,
  onRelogin,
  onEditChannel,
  onDeleteChannel,
  onToggleExpand,
  onToggleMonitor,
  onEditKey,
  onSetDefault,
  onProbeModels,
  onPoolSchedule,
  onPoolPreview,
}: {
  account: AnyRecord;
  expanded: boolean;
  loading: boolean;
  loadingIds: Set<number>;
  onProbe: (id: number) => void;
  onSyncKeys: (id: number) => void;
  onRelogin: (channel: AnyRecord) => void;
  onEditChannel: (channel: AnyRecord) => void;
  onDeleteChannel: (channel: AnyRecord) => void;
  onToggleExpand: (id: number) => void;
  onToggleMonitor: (channel: AnyRecord) => void;
  onEditKey: (channel: AnyRecord) => void;
  onSetDefault: (id: number) => void;
  onProbeModels: (id: number) => void;
  onPoolSchedule: (id: number) => void;
  onPoolPreview: (id: number) => void;
}) {
  const id = Number(account.id);
  const children = account.children || [];
  const defaultChildId = account.default_child_id ?? account.defaultChildId;
  const monitoringCount = account.monitoring_count ?? account.monitoringCount ?? 0;
  const enabled = boolField(account, "is_enabled", "isEnabled");
  const percent = clampPercent(account.remaining_percent ?? account.remainingPercent ?? 0);
  const progressClass = account.status === "warning" ? "warning" : account.status === "offline" ? "danger" : "";
  return (
    <article className={`account-row ${expanded ? "is-expanded" : ""}`} data-id={id} onClick={() => onToggleExpand(id)}>
      <div className="channel-identity">
        <span className={`status-dot ${statusDotClass(account.status)}`}></span>
        <div>
          <h3>
            {account.name} {!enabled ? <span className="badge bad">已停调</span> : null}
          </h3>
          <code>{maskBaseUrl(account.base_url || account.baseUrl)}</code>
        </div>
      </div>
      <div className="channel-meta">
        <span>
          {account.platform} · {children.length} 个 Key · {monitoringCount} 个监控中
        </span>
        <span>默认 Key: {defaultChildId ? `#${defaultChildId}` : "未设置"}</span>
        <span>余额探测: {formatTime(account.last_checked_at || account.lastCheckedAt)}</span>
      </div>
      <div className="usage-block">
        <div className="usage-label">
          <span>{formatMoney(account.balance, account.unit)}</span>
          <small>阈值 {formatMoney(account.threshold, account.unit)}</small>
        </div>
        <div className={`progress-track ${progressClass}`}>
          <span style={{ width: `${percent}%` }}></span>
        </div>
      </div>
      <div className="row-actions" onClick={(event) => event.stopPropagation()}>
        <button className="ghost-button" type="button" disabled={loading} onClick={() => onProbe(id)}>
          <span className="icon icon-radar" aria-hidden="true"></span>
          {loading ? "查询中" : "余额"}
        </button>
        <button className="ghost-button" type="button" disabled={loading} onClick={() => onSyncKeys(id)}>
          <span className="icon icon-sync" aria-hidden="true"></span>
          {loading ? "同步中" : "同步 Key"}
        </button>
        {(account.platform === "sub2Api" || account.platform === "sub2api") ? (
          <button className="ghost-button" type="button" disabled={loading} onClick={() => onRelogin(account)}>
            重新登录
          </button>
        ) : null}
        <button className="ghost-button" type="button" onClick={() => onEditChannel(account)}>
          编辑
        </button>
        <button className="ghost-button danger" type="button" disabled={loading} onClick={() => onDeleteChannel(account)}>
          删除
        </button>
        <button className="ghost-button" type="button" aria-label={expanded ? "收起" : "展开"} onClick={() => onToggleExpand(id)}>
          {expanded ? "收起" : "展开"}
        </button>
      </div>
      {expanded ? (
        <div className="key-list" aria-label={`${account.name} Key 列表`} onClick={(event) => event.stopPropagation()}>
          {children.length ? (
            children.map((child: AnyRecord) => (
              <KeyRow
                channel={child}
                key={child.id}
                loading={loadingIds.has(Number(child.id))}
                onToggleMonitor={onToggleMonitor}
                onEditKey={onEditKey}
                onSetDefault={onSetDefault}
                onProbeModels={onProbeModels}
                onPoolSchedule={onPoolSchedule}
                onPoolPreview={onPoolPreview}
              />
            ))
          ) : (
            <span className="group-empty">暂无子 Key</span>
          )}
        </div>
      ) : null}
    </article>
  );
}

function KeyRow({
  channel,
  loading,
  onToggleMonitor,
  onEditKey,
  onSetDefault,
  onProbeModels,
  onPoolSchedule,
  onPoolPreview,
}: {
  channel: AnyRecord;
  loading: boolean;
  onToggleMonitor: (channel: AnyRecord) => void;
  onEditKey: (channel: AnyRecord) => void;
  onSetDefault: (id: number) => void;
  onProbeModels: (id: number) => void;
  onPoolSchedule: (id: number) => void;
  onPoolPreview: (id: number) => void;
}) {
  const id = Number(channel.id);
  const models = channel.monitor_models || channel.monitorModels || [];
  const provider = monitorProvider(channel.key_provider || channel.keyProvider || models[0], channel.platform);
  const monitoring = boolField(channel, "is_monitoring", "isMonitoring");
  const isDefault = boolField(channel, "is_default_key", "isDefaultKey");
  const enabled = boolField(channel, "is_enabled", "isEnabled");
  const poolIds = channel.pool_account_ids ?? channel.poolAccountIds ?? [];
  const hasPoolMapping = Array.isArray(poolIds) ? poolIds.length > 0 : String(poolIds || "").trim().length > 0;
  const monitorChecked = channel.monitor_last_checked_at || channel.monitorLastCheckedAt;
  const monitorError = channel.monitor_last_error || channel.monitorLastError;
  const disabledReason = channel.scheduling_disabled_reason || channel.schedulingDisabledReason;
  const lastLine = !enabled && disabledReason ? `停调原因: ${disabledReason}` : monitorError ? `监控错误: ${monitorError}` : monitorChecked ? `模型探测: ${formatTime(monitorChecked)}` : "尚未模型探测";
  return (
    <div className="key-row" data-id={id}>
      <div className="channel-identity">
        <span className={`status-dot ${statusDotClass(channel.status)}`} aria-label={statusLabel(channel.status)}></span>
        <div>
          <h3>
            {channel.name} {isDefault ? <span className="badge good">默认</span> : null}
            {!enabled ? <span className="badge bad">已停调</span> : null}
          </h3>
          <code>{channel.key_masked || channel.keyMasked || "未配置密钥"}</code>
        </div>
      </div>
      <div className="channel-meta">
        <span>
          分组: {channel.group_name || channel.groupName || "未选择分组"} · 倍率 {formatRate(channel.rate_multiplier ?? channel.rateMultiplier)}
        </span>
        <span>
          类型: {provider.label} · 模型: {models.join(", ") || "未配置"}
        </span>
        <span>{lastLine}</span>
        <PoolScheduleBadge account={channel} />
      </div>
      <div className="row-actions">
        <button className={`ghost-button ${monitoring ? "" : "is-muted"}`} type="button" onClick={() => onToggleMonitor(channel)}>
          <span className="icon icon-bell" aria-hidden="true"></span>
          {monitoring ? "停止监控" : "启动监控"}
        </button>
        <button className="ghost-button" type="button" onClick={() => onEditKey(channel)}>
          编辑
        </button>
        <button className={`ghost-button ${isDefault ? "is-muted" : ""}`} type="button" disabled={isDefault} onClick={() => onSetDefault(id)}>
          设为默认
        </button>
        <button className="ghost-button" type="button" disabled={loading} onClick={() => onProbeModels(id)}>
          <span className="icon icon-radar" aria-hidden="true"></span>
          {loading ? "探测中" : "模型探测"}
        </button>
        {hasPoolMapping ? (
          <>
            <button className="ghost-button" type="button" disabled={loading} onClick={() => onPoolPreview(id)}>
              号池预览
            </button>
            <button className="ghost-button" type="button" disabled={loading} onClick={() => onPoolSchedule(id)}>
              立即调度
            </button>
          </>
        ) : null}
      </div>
    </div>
  );
}

/** 只读展示某渠道的号池自动调度状态：期望态 + 最近原因 + 失败提示。 */
function PoolScheduleBadge({ account }: { account: AnyRecord }) {
  const accountIds = account.pool_account_ids ?? account.poolAccountIds ?? [];
  const ids: string[] = Array.isArray(accountIds)
    ? accountIds
    : String(accountIds || "")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
  if (!ids.length) return null;
  const desired = account.pool_desired_state ?? account.poolDesiredState;
  const pushed = account.pool_last_pushed_state ?? account.poolLastPushedState;
  const reason = account.pool_last_reason ?? account.poolLastReason;
  const error = account.pool_last_error ?? account.poolLastError;
  const state = pushed || desired;
  const stateLabel = state === "enabled" ? "已启用" : state === "disabled" ? "已禁用" : "待定";
  const stateClass = state === "enabled" ? "good" : state === "disabled" ? "warn" : "";
  return (
    <span className="pool-badge" title={reason || ""}>
      号池 {ids.length} 账号 · <span className={`badge ${stateClass}`}>{stateLabel}</span>
      {error ? <span className="badge bad">下发失败</span> : null}
    </span>
  );
}
