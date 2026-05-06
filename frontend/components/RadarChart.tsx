type RadarChartProps = {
  values: Record<string, number>;
};

const SIZE = 360;
const CENTER = SIZE / 2;
const RADIUS = 128;

function polarToCartesian(index: number, total: number, value: number) {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
  const scaledRadius = (value / 100) * RADIUS;
  return {
    x: CENTER + scaledRadius * Math.cos(angle),
    y: CENTER + scaledRadius * Math.sin(angle),
  };
}

export function RadarChart({ values }: RadarChartProps) {
  const entries = Object.entries(values).slice(0, 10);
  const polygonPoints = entries
    .map(([, value], index) => {
      const point = polarToCartesian(index, entries.length, value);
      return `${point.x},${point.y}`;
    })
    .join(" ");

  return (
    <div className="panel p-5 md:p-6">
      <div className="mb-4 flex items-end justify-between gap-3">
        <div>
          <p className="label-mini">Core Space</p>
          <h3 className="mt-1.5 text-xl text-[color:var(--ink-strong)]">核心相空间雷达图</h3>
        </div>
        <p className="max-w-[14rem] text-right text-[0.72rem] leading-5 text-[color:var(--ink-muted)]">
          越靠外代表当前估计越接近该维度的高侧，图形会随着答题继续收缩和偏转。
        </p>
      </div>
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="mx-auto h-[320px] w-full max-w-[360px]"
      >
        {[25, 50, 75, 100].map((ring) => (
          <circle
            key={ring}
            cx={CENTER}
            cy={CENTER}
            r={(ring / 100) * RADIUS}
            fill="none"
            stroke="rgba(26,24,22,0.08)"
            strokeDasharray="3 6"
          />
        ))}
        {entries.map(([label], index) => {
          const axis = polarToCartesian(index, entries.length, 100);
          return (
            <g key={label}>
              <line
                x1={CENTER}
                y1={CENTER}
                x2={axis.x}
                y2={axis.y}
                stroke="rgba(26,24,22,0.10)"
              />
              <text
                x={CENTER + (axis.x - CENTER) * 1.14}
                y={CENTER + (axis.y - CENTER) * 1.14}
                fill="rgba(44,42,39,0.85)"
                fontSize="11"
                textAnchor="middle"
              >
                {label}
              </text>
            </g>
          );
        })}
        <polygon
          points={polygonPoints}
          fill="rgba(47,111,94,0.16)"
          stroke="rgba(47,111,94,0.85)"
          strokeWidth="1.6"
        />
      </svg>
    </div>
  );
}
