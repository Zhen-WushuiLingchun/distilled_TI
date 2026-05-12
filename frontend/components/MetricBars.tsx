type MetricBarsProps = {
  title: string;
  eyebrow: string;
  metrics: Record<string, number>;
  emptyMessage?: string;
};

export function MetricBars({ title, eyebrow, metrics, emptyMessage }: MetricBarsProps) {
  const entries = Object.entries(metrics);

  return (
    <section className="panel p-5 md:p-6">
      <p className="label-mini">{eyebrow}</p>
      <h3 className="mt-1.5 text-xl text-[color:var(--ink-strong)]">{title}</h3>
      <div className="mt-5 space-y-3.5">
        {entries.length === 0 ? (
          <p className="surface-sunken p-3.5 text-sm text-[color:var(--ink-muted)]">
            {emptyMessage ?? "当前阶段还没有足够数据解锁这部分。"}
          </p>
        ) : (
          entries.map(([label, value]) => (
            <div key={label}>
              <div className="mb-1.5 flex items-center justify-between gap-3 text-sm">
                <span className="text-[color:var(--ink-strong)]">{label}</span>
                <span className="num text-[color:var(--accent-ink)]">{value.toFixed(1)}%</span>
              </div>
              <div className="bar-track">
                <div className="bar-fill" style={{ width: `${value}%` }} />
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
