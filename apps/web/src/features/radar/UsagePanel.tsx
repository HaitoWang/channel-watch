import type { AnyRecord } from './types';
import { MetricCard, Panel } from './layout';
import { clampPercent, formatMoney, formatNumber, formatTime, statusBadgeClass, statusLabel } from '../../shared/formatters';

export function UsagePanel({ active, usage, onProbe }: { active: boolean; usage: AnyRecord; onProbe: (id: number) => void }) {
  const summary = usage.summary || {};
  const rows = usage.channels || [];
  return (
    <Panel active={active} viewName="usage">
      <section className="usage-summary metrics-grid" aria-label="消耗摘要">
        <MetricCard label="累计消耗" value={formatMoney(summary.used_total ?? summary.usedTotal)} />
        <MetricCard label="剩余额度" value={formatMoney(summary.balance_total ?? summary.balanceTotal)} />
        <MetricCard label="低余额渠道" value={summary.low_count ?? summary.lowCount ?? 0} tone="danger" />
        <MetricCard label="平均消耗率" value={`${formatNumber(summary.burn_rate ?? summary.burnRate ?? 0)}%`} />
      </section>
      <section className="usage-list" id="usageList" aria-label="消耗列表">
        {rows.length ? (
          rows.map((item: AnyRecord) => {
            const usedPercent = clampPercent(item.used_percent ?? item.usedPercent ?? 0);
            const tone = item.is_low || item.isLow ? "danger" : usedPercent > 85 ? "warning" : "";
            const channelId = Number(item.channel_id || item.channelId || item.id);
            return (
              <article className="usage-row" key={item.channel_id || item.channelId || item.id || item.name}>
                <div>
                  <h3>{item.name}</h3>
                  <div className="usage-meta">
                    <span className="badge">{item.platform}</span>
                    <span className={`badge ${statusBadgeClass(item.status)}`}>{statusLabel(item.status)}</span>
                    <span className="badge">{formatTime(item.last_checked_at || item.lastCheckedAt)}</span>
                  </div>
                </div>
                <div className="usage-numbers">
                  <strong>{formatMoney(item.used, item.unit)}</strong>
                  <span className="badge">累计消耗</span>
                </div>
                <div className="usage-block">
                  <div className="usage-label">
                    <span>剩余 {formatMoney(item.balance, item.unit)}</span>
                    <small>总额 {formatMoney(item.quota_total ?? item.quotaTotal, item.unit)}</small>
                  </div>
                  <div className={`progress-track ${tone}`}>
                    <span style={{ width: `${usedPercent}%` }}></span>
                  </div>
                </div>
                <div className="row-actions">
                  <button className="ghost-button" type="button" onClick={() => onProbe(channelId)}>
                    <span className="icon icon-radar" aria-hidden="true"></span>
                    刷新
                  </button>
                </div>
              </article>
            );
          })
        ) : (
          <div className="list-state">暂无消耗数据</div>
        )}
      </section>
    </Panel>
  );
}
