import type { AnyRecord } from './types';
import { Panel } from './layout';
import { formatRate, formatTime, logStatusLabel } from '../../shared/formatters';
import { formatLatency, monitorDisplayName, monitorLatencyValue, monitorPrimaryModel, monitorProvider, monitorStatusMeta, nextMonitorRefresh } from './utils';

export function MonitorPanel({
  active,
  channels,
  history,
  loadingIds,
  onProbeModels,
  onOpenLog,
  onEditKey,
  onToggleMonitor,
}: {
  active: boolean;
  channels: AnyRecord[];
  history: AnyRecord[];
  loadingIds: Set<number>;
  onProbeModels: (id: number) => void;
  onOpenLog: (channel: AnyRecord) => void;
  onEditKey: (channel: AnyRecord) => void;
  onToggleMonitor: (channel: AnyRecord) => void;
}) {
  const sortedChannels = [...channels].sort((left, right) => {
    const leftRate = Number(left.rate_multiplier ?? left.rateMultiplier ?? Number.POSITIVE_INFINITY);
    const rightRate = Number(right.rate_multiplier ?? right.rateMultiplier ?? Number.POSITIVE_INFINITY);
    return leftRate - rightRate;
  });
  return (
    <Panel active={active} viewName="monitor">
      <section className="rate-grid monitor-grid" id="monitorList" aria-label="监控卡片">
        {sortedChannels.length ? (
          sortedChannels.map((channel) => {
            const monitorHistory = channel.monitor_history ?? channel.monitorHistory;
            const channelHistory = Array.isArray(monitorHistory)
              ? monitorHistory
              : history.filter((item) => Number(item.channel_id ?? item.channelId) === Number(channel.id) && item.kind === "model").slice(0, 60);
            return (
              <MonitorCard
                channel={channel}
                history={channelHistory}
                key={channel.id}
                loading={loadingIds.has(Number(channel.id))}
                onProbeModels={onProbeModels}
                onOpenLog={onOpenLog}
                onEditKey={onEditKey}
                onToggleMonitor={onToggleMonitor}
              />
            );
          })
        ) : (
          <div className="list-state">暂无启动监控的 Key</div>
        )}
      </section>
    </Panel>
  );
}

function MonitorCard({
  channel,
  history,
  loading,
  onProbeModels,
  onOpenLog,
  onEditKey,
  onToggleMonitor,
}: {
  channel: AnyRecord;
  history: AnyRecord[];
  loading: boolean;
  onProbeModels: (id: number) => void;
  onOpenLog: (channel: AnyRecord) => void;
  onEditKey: (channel: AnyRecord) => void;
  onToggleMonitor: (channel: AnyRecord) => void;
}) {
  const models = channel.monitor_models || channel.monitorModels || [];
  const result = channel.monitor_result || channel.monitorResult || {};
  const modelResults = Array.isArray(result.models) ? result.models : [];
  const status = channel.monitor_status || channel.monitorStatus || "idle";
  const statusMeta = monitorStatusMeta(status);
  const primaryModel = monitorPrimaryModel(models, modelResults);
  const provider = monitorProvider(channel.key_provider || channel.keyProvider || primaryModel, channel.platform);
  const latency = monitorLatencyValue(channel, modelResults, "max");
  const endpointPing = monitorLatencyValue(channel, modelResults, "min");
  return (
    <article className={`monitor-card is-${statusMeta.tone}`}>
      <header className="monitor-head">
        <div className="monitor-service">
          <span className={`monitor-logo ${provider.className}`}>
            <span className="icon icon-radar" aria-hidden="true"></span>
          </span>
          <div className="monitor-title">
            <h3>{monitorDisplayName(channel)}</h3>
            <div className="monitor-service-meta">
              <span className={`monitor-provider ${provider.className}`}>{provider.label}</span>
              <span>{primaryModel}</span>
            </div>
          </div>
        </div>
        <span className={`monitor-status ${statusMeta.tone}`}>{statusMeta.label}</span>
      </header>
      <div className="monitor-metrics">
        <div className="monitor-metric">
          <span>对话延迟</span>
          <strong>{formatLatency(latency)}</strong>
        </div>
        <div className="monitor-metric">
          <span>端点 PING</span>
          <strong>{formatLatency(endpointPing)}</strong>
        </div>
        <div className="monitor-metric accent">
          <span>当前倍率</span>
          <strong>{formatRate(channel.rate_multiplier ?? channel.rateMultiplier)}</strong>
        </div>
      </div>
      <div className="monitor-availability">
        <div>
          <span>可用性 · 7 天</span>
        </div>
        <strong>{monitorAvailability(history)}</strong>
      </div>
      <div className="monitor-history">
        <div className="monitor-history-meta">
          <span>近 {history.length} 次记录</span>
          <span>{nextMonitorRefresh(channel)}</span>
        </div>
        <div className="monitor-bars" aria-hidden="true">
          {monitorTrendBars(history)}
        </div>
        <div className="monitor-history-axis">
          <span>PAST</span>
          <span>NOW</span>
        </div>
      </div>
      <div className="row-actions monitor-actions">
        <button className="ghost-button" type="button" disabled={loading} onClick={() => onProbeModels(Number(channel.id))}>
          <span className="icon icon-radar" aria-hidden="true"></span>探测
        </button>
        <button className="ghost-button" type="button" onClick={() => onOpenLog(channel)}>
          日志
        </button>
        <button className="ghost-button" type="button" onClick={() => onEditKey(channel)}>
          编辑
        </button>
        <button className="ghost-button is-muted" type="button" onClick={() => onToggleMonitor(channel)}>
          停止
        </button>
      </div>
    </article>
  );
}

function monitorAvailability(entries: AnyRecord[]) {
  if (!entries.length) return "--";
  const success = entries.filter((item) => item.status === "valid").length;
  const percent = (success / entries.length) * 100;
  return `${percent >= 99.995 ? "100" : percent.toFixed(2)}%`;
}

function monitorTrendBars(entries: AnyRecord[]) {
  const chronological = [...entries].reverse();
  const padding = Math.max(0, 60 - chronological.length);
  const items = [...Array(padding).fill(null), ...chronological].slice(-60);
  return items.map((item, index) => {
    const tone = !item ? "pending" : item.status === "valid" ? "good" : item.status === "invalid" ? "bad" : "warn";
    const title = item ? `${logStatusLabel(item.status)} · ${formatTime(item.created_at || item.createdAt)}` : "等待记录";
    return <span className={`monitor-bar ${tone}`} key={`${item?.id || "pending"}-${index}`} title={title}></span>;
  });
}
