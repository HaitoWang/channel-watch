import type { AnyRecord } from './types';
import { Panel } from './layout';
import { formatTime, severityClass, severityLabel } from '../../shared/formatters';

export function AlertsPanel({
  active,
  events,
  openEvents,
  alertFilter,
  onFilter,
  onAck,
  onAckAll,
}: {
  active: boolean;
  events: AnyRecord[];
  openEvents: AnyRecord[];
  alertFilter: string;
  onFilter: (value: string) => void;
  onAck: (id: number) => void;
  onAckAll: () => void;
}) {
  let visible = events;
  if (alertFilter === "open") visible = events.filter((event) => !(event.is_ack ?? event.isAck));
  if (alertFilter === "ack") visible = events.filter((event) => event.is_ack ?? event.isAck);
  return (
    <Panel active={active} viewName="alerts">
      <section className="toolbar actions-only" aria-label="告警筛选">
        <div className="filters" role="group" aria-label="告警状态筛选">
          {[
            ["open", "未确认"],
            ["all", "全部"],
            ["ack", "已确认"],
          ].map(([value, label]) => (
            <button className={alertFilter === value ? "filter-chip active" : "filter-chip"} key={value} type="button" onClick={() => onFilter(value)}>
              {label}
            </button>
          ))}
          <button className="ghost-button" type="button" disabled={!openEvents.length} onClick={onAckAll}>
            <span className="icon icon-check" aria-hidden="true"></span>
            全部确认
          </button>
        </div>
      </section>
      <section className="panel-list" id="alertList" aria-label="告警列表">
        {visible.length ? (
          visible.map((event) => {
            const isAck = event.is_ack ?? event.isAck;
            return (
              <article className={`alert-row ${isAck ? "is-ack" : ""}`} key={event.id}>
                <div className="alert-copy">
                  <h3>{event.title}</h3>
                  <p>{event.message}</p>
                  <div className="alert-meta">
                    <span className={`badge ${severityClass(event.severity)}`}>{severityLabel(event.severity)}</span>
                    <span className="badge">{event.channel_name || event.channelName || "系统"}</span>
                    <span className="badge">{formatTime(event.created_at || event.createdAt)}</span>
                    <span className={`badge ${isAck ? "good" : "warn"}`}>{isAck ? "已确认" : "未确认"}</span>
                  </div>
                </div>
                <div className="row-actions">
                  {isAck ? (
                    <button className="ghost-button is-muted" type="button" disabled>
                      <span className="icon icon-check" aria-hidden="true"></span>已确认
                    </button>
                  ) : (
                    <button className="ghost-button" type="button" onClick={() => onAck(Number(event.id))}>
                      <span className="icon icon-check" aria-hidden="true"></span>确认
                    </button>
                  )}
                </div>
              </article>
            );
          })
        ) : (
          <div className="list-state">{alertFilter === "open" ? "当前没有未确认告警" : "没有告警记录"}</div>
        )}
      </section>
    </Panel>
  );
}
