import type { ReactNode } from 'react';

export function Panel({ active, viewName, children, className = "view-panel" }: { active: boolean; viewName: string; children: ReactNode; className?: string }) {
  return (
    <section className={`${className} ${active ? "active" : ""}`} data-view-panel={viewName} aria-label={viewName}>
      {children}
    </section>
  );
}

export function MetricCard({ label, value, sub, tone = "" }: { label: string; value: ReactNode; sub?: ReactNode; tone?: string }) {
  return (
    <article className={`metric-card ${tone}`}>
      <span className="metric-label">{label}</span>
      <strong>{value}</strong>
      {sub ? <small>{sub}</small> : null}
    </article>
  );
}
