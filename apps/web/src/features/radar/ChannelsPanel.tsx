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
  onEditChannel,
  onDeleteChannel,
  onToggleMonitor,
  onEditKey,
  onSetDefault,
  onProbeModels,
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
  onEditChannel: (channel: AnyRecord) => void;
  onDeleteChannel: (channel: AnyRecord) => void;
  onToggleMonitor: (channel: AnyRecord) => void;
  onEditKey: (channel: AnyRecord) => void;
  onSetDefault: (id: number) => void;
  onProbeModels: (id: number) => void;
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
              onEditChannel={onEditChannel}
              onDeleteChannel={onDeleteChannel}
              onToggleExpand={onToggleExpand}
              onToggleMonitor={onToggleMonitor}
              onEditKey={onEditKey}
              onSetDefault={onSetDefault}
              onProbeModels={onProbeModels}
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
  onEditChannel,
  onDeleteChannel,
  onToggleExpand,
  onToggleMonitor,
  onEditKey,
  onSetDefault,
  onProbeModels,
}: {
  account: AnyRecord;
  expanded: boolean;
  loading: boolean;
  loadingIds: Set<number>;
  onProbe: (id: number) => void;
  onSyncKeys: (id: number) => void;
  onEditChannel: (channel: AnyRecord) => void;
  onDeleteChannel: (channel: AnyRecord) => void;
  onToggleExpand: (id: number) => void;
  onToggleMonitor: (channel: AnyRecord) => void;
  onEditKey: (channel: AnyRecord) => void;
  onSetDefault: (id: number) => void;
  onProbeModels: (id: number) => void;
}) {
  const id = Number(account.id);
  const children = account.children || [];
  const defaultChildId = account.default_child_id ?? account.defaultChildId;
  const monitoringCount = account.monitoring_count ?? account.monitoringCount ?? 0;
  const percent = clampPercent(account.remaining_percent ?? account.remainingPercent ?? 0);
  const progressClass = account.status === "warning" ? "warning" : account.status === "offline" ? "danger" : "";
  return (
    <article className={`account-row ${expanded ? "is-expanded" : ""}`} data-id={id} onClick={() => onToggleExpand(id)}>
      <div className="channel-identity">
        <span className={`status-dot ${statusDotClass(account.status)}`}></span>
        <div>
          <h3>{account.name}</h3>
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
}: {
  channel: AnyRecord;
  loading: boolean;
  onToggleMonitor: (channel: AnyRecord) => void;
  onEditKey: (channel: AnyRecord) => void;
  onSetDefault: (id: number) => void;
  onProbeModels: (id: number) => void;
}) {
  const id = Number(channel.id);
  const models = channel.monitor_models || channel.monitorModels || [];
  const provider = monitorProvider(channel.key_provider || channel.keyProvider || models[0], channel.platform);
  const monitoring = boolField(channel, "is_monitoring", "isMonitoring");
  const isDefault = boolField(channel, "is_default_key", "isDefaultKey");
  const monitorChecked = channel.monitor_last_checked_at || channel.monitorLastCheckedAt;
  const monitorError = channel.monitor_last_error || channel.monitorLastError;
  const lastLine = monitorError ? `监控错误: ${monitorError}` : monitorChecked ? `模型探测: ${formatTime(monitorChecked)}` : "尚未模型探测";
  return (
    <div className="key-row" data-id={id}>
      <div className="channel-identity">
        <span className={`status-dot ${statusDotClass(channel.status)}`} aria-label={statusLabel(channel.status)}></span>
        <div>
          <h3>
            {channel.name} {isDefault ? <span className="badge good">默认</span> : null}
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
      </div>
    </div>
  );
}
