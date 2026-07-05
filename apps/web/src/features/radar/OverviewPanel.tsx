import type { AnyRecord } from './types';
import { MetricCard, Panel } from './layout';
import { formatMoney, formatRate, formatTime, relativeTime, severityClass, severityLabel } from '../../shared/formatters';

export function OverviewPanel({ active, radar, onAck }: { active: boolean; radar: AnyRecord; onAck: (id: number) => void }) {
  const overview = radar.overview || {};
  const events = (radar.events || []) as AnyRecord[];
  const total = overview.total_channels ?? overview.totalChannels ?? 0;
  const healthy = overview.healthy_channels ?? overview.healthyChannels ?? 0;
  const warning = overview.warning_channels ?? overview.warningChannels ?? 0;
  const offline = overview.offline_channels ?? overview.offlineChannels ?? 0;
  const openEvents = overview.open_events ?? overview.openEvents ?? radar.events.length;
  const balanceTotal = overview.balance_total ?? overview.balanceTotal;
  const usedTotal = overview.used_total ?? overview.usedTotal;
  const lanes = [
    ["正常", healthy, "good"],
    ["预警", warning, "warn"],
    ["异常", offline, "bad"],
    ["未探测", Math.max(0, Number(total) - Number(healthy) - Number(warning) - Number(offline)), ""],
  ] as const;
  return (
    <Panel active={active} viewName="overview">
      <section className="metrics-grid" aria-label="监控摘要">
        <MetricCard label="在线渠道" value={`${healthy}/${total}`} sub={`${warning} 个预警 · ${offline} 个异常`} />
        <MetricCard label="风险告警" value={openEvents} sub="未确认事件" tone="danger" />
        <MetricCard label="当前余额合计" value={formatMoney(balanceTotal)} sub={`累计消耗 ${formatMoney(usedTotal)}`} />
        <MetricCard label="最近成功探测" value={relativeTime(overview.last_success_at || overview.lastSuccessAt)} sub="后端 API 已接入" />
      </section>
      <section className="event-dock" id="eventDock" aria-label="雷达告警">
        {events.slice(0, 3).map((event) => (
          <article className="event-item" key={event.id}>
            <div className="event-copy">
              <strong>{event.title}</strong>
              <span>{event.message}</span>
            </div>
            <button type="button" onClick={() => onAck(Number(event.id))}>
              确认
            </button>
          </article>
        ))}
      </section>
      <section className="summary-board" id="overviewBoard" aria-label="运行概览">
        <article className="summary-panel">
          <h3>运行状态</h3>
          <div className="status-stack">
            {lanes.map(([label, count, tone]) => {
              const percent = Number(total) ? Math.round((Number(count) / Number(total)) * 100) : 0;
              return (
                <div className="status-lane" key={label}>
                  <span>{label}</span>
                  <div className={`mini-track ${tone}`}>
                    <span style={{ width: `${percent}%` }}></span>
                  </div>
                  <strong>{count}</strong>
                </div>
              );
            })}
          </div>
          <div className="summary-stats">
            <div className="summary-stat">
              <span>平均倍率</span>
              <strong>{formatRate(overview.average_rate ?? overview.averageRate)}</strong>
            </div>
            <div className="summary-stat">
              <span>低余额渠道</span>
              <strong>{overview.low_balance_channels ?? overview.lowBalanceChannels ?? 0}</strong>
            </div>
          </div>
        </article>
        <article className="summary-panel">
          <h3>风险队列</h3>
          <div className="status-stack">
            {events.slice(0, 4).length ? (
              events.slice(0, 4).map((event) => (
                <div key={event.id}>
                  <h4>{event.title}</h4>
                  <p className="log-copy">{event.message}</p>
                  <div className="alert-meta">
                    <span className={`badge ${severityClass(event.severity)}`}>{severityLabel(event.severity)}</span>
                    <span className="badge">{formatTime(event.created_at || event.createdAt)}</span>
                  </div>
                </div>
              ))
            ) : (
              <div className="list-state">当前没有未确认告警</div>
            )}
          </div>
        </article>
      </section>
    </Panel>
  );
}
