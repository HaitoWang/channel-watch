import type { AnyRecord } from './types';
import { Panel } from './layout';
import { formatTime, statusBadgeClass, statusLabel } from '../../shared/formatters';

export function RatesPanel({
  active,
  channels,
  loadingIds,
  syncingRates,
  onSyncAll,
  onProbe,
}: {
  active: boolean;
  channels: AnyRecord[];
  loadingIds: Set<number>;
  syncingRates: boolean;
  onSyncAll: () => void;
  onProbe: (id: number) => void;
}) {
  return (
    <Panel active={active} viewName="rates">
      <section className="toolbar actions-only" aria-label="倍率工具">
        <div className="filters" role="group" aria-label="倍率操作">
          <button className="ghost-button" type="button" disabled={syncingRates || !channels.length} onClick={onSyncAll}>
            <span className="icon icon-sync" aria-hidden="true"></span>
            {syncingRates ? "同步中" : "同步全部"}
          </button>
        </div>
      </section>
      <section className="rate-grid" id="rateList" aria-label="倍率列表">
        {channels.length ? (
          channels.map((channel) => {
            const id = Number(channel.id);
            const loading = loadingIds.has(id);
            const rate = channel.rate_multiplier ?? channel.rateMultiplier;
            const latest = channel.last_rate_probe || channel.lastRateProbe;
            return (
              <article className="rate-row" key={channel.id}>
                <div>
                  <h3>{channel.name}</h3>
                  <div className="rate-meta">
                    <span className="badge">{channel.platform}</span>
                    <span className="badge">{channel.model_scope || channel.modelScope || "All models"}</span>
                    <span className={`badge ${statusBadgeClass(channel.status)}`}>{statusLabel(channel.status)}</span>
                  </div>
                </div>
                <div className="rate-value">
                  {rate == null ? "未知" : rate}
                  <small>{rate == null ? "" : "x"}</small>
                </div>
                <div className="rate-meta">
                  <span>分组: {channel.group_name || channel.groupName || channel.group_id || channel.groupId || "未选择"}</span>
                  <span>最近同步: {latest ? formatTime(latest.created_at || latest.createdAt) : "暂无"}</span>
                  <span>{latest?.summary || "等待倍率探测"}</span>
                </div>
                <div className="row-actions">
                  <button className="ghost-button" type="button" disabled={loading} onClick={() => onProbe(id)}>
                    <span className="icon icon-sync" aria-hidden="true"></span>
                    {loading ? "同步中" : "同步"}
                  </button>
                </div>
              </article>
            );
          })
        ) : (
          <div className="list-state">暂无渠道可同步倍率</div>
        )}
      </section>
    </Panel>
  );
}
