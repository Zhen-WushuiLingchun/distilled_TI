type MetricBarsProps = {
  title: string;
  eyebrow: string;
  metrics: Record<string, number>;
  emptyMessage?: string;
};

export function MetricBars({ title, eyebrow, metrics, emptyMessage }: MetricBarsProps) {
  const entries = Object.entries(metrics);

  return (
    <section className="rounded-[2rem] border border-white/10 bg-black/20 p-6 backdrop-blur-xl">
      <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/70">{eyebrow}</p>
      <h3 className="mt-2 text-2xl text-white">{title}</h3>
      <div className="mt-6 space-y-4">
        {entries.length === 0 ? (
          <p className="text-sm text-slate-400">{emptyMessage ?? "当前阶段还没有足够数据解锁这部分。"}</p>
        ) : (
          entries.map(([label, value]) => (
            <div key={label}>
              <div className="mb-2 flex items-center justify-between gap-4 text-sm text-slate-200">
                <span>{label}</span>
                <span className="text-cyan-200">{value.toFixed(1)}%</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-white/8">
                <div
                  className="h-full rounded-full bg-gradient-to-r from-cyan-300 via-sky-400 to-indigo-400"
                  style={{ width: `${value}%` }}
                />
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
