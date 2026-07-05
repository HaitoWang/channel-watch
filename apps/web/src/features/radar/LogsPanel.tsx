import { useMemo } from 'react';

import type { AnyRecord } from './types';
import { Panel } from './layout';
import { formatTime, kindLabel, logStatusLabel, statusBadgeClass } from '../../shared/formatters';

export function LogsPanel({
  active,
  history,
  events,
  logKind,
  onLogKind,
}: {
  active: boolean;
  history: AnyRecord[];
  events: AnyRecord[];
  logKind: string;
  onLogKind: (value: string) => void;
}) {
  const items = useMemo(() => {
    const historyItems = history.map((item) => ({
      source: "history",
      kind: item.kind,
      title: `${item.channel_name || item.channelName || "未知渠道"} ${kindLabel(item.kind)}`,
      message: item.summary || "",
      status: item.status,
      createdAt: item.created_at || item.createdAt,
      channel: item.channel_name || item.channelName,
      platform: item.platform,
    }));
    const alertItems = events.map((event) => ({
      source: "event",
      kind: "alert",
      title: event.title,
      message: event.message,
      status: event.is_ack || event.isAck ? "acked" : event.severity,
      createdAt: event.created_at || event.createdAt,
      channel: event.channel_name || event.channelName,
      platform: event.platform,
    }));
    return [...historyItems, ...alertItems]
      .filter((item) => logKind === "all" || item.kind === logKind)
      .sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime())
      .slice(0, 120);
  }, [events, history, logKind]);

  return (
    <Panel active={active} viewName="logs">
      <section className="toolbar actions-only" aria-label="日志筛选">
        <label className="select-filter">
          <span>类型</span>
          <select value={logKind} onChange={(event) => onLogKind(event.target.value)}>
            <option value="all">全部</option>
            <option value="balance">余额</option>
            <option value="group">倍率</option>
            <option value="alert">告警</option>
          </select>
        </label>
      </section>
      <section className="log-list" id="logList" aria-label="日志列表">
        {items.length ? (
          items.map((item, index) => (
            <article className="log-row" key={`${item.source}-${item.createdAt}-${index}`}>
              <span className="log-kind">{kindLabel(item.kind)}</span>
              <div className="log-copy">
                <strong>{item.title}</strong>
                <p>{item.message}</p>
                <div className="log-meta">
                  <span className={`badge ${statusBadgeClass(item.status)}`}>{logStatusLabel(item.status)}</span>
                  <span className="badge">{item.platform || "系统"}</span>
                  <span className="badge">{item.channel || "全局"}</span>
                </div>
              </div>
              <span className="badge">{formatTime(item.createdAt)}</span>
            </article>
          ))
        ) : (
          <div className="list-state">暂无日志记录</div>
        )}
      </section>
    </Panel>
  );
}
