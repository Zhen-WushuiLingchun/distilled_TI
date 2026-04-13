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
    <div className="relative overflow-hidden rounded-[2rem] border border-white/10 bg-white/5 p-6 shadow-[0_30px_120px_rgba(22,22,54,0.35)] backdrop-blur-xl">
      <div className="mb-4 flex items-end justify-between">
        <div>
          <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/70">
            Core Space
          </p>
          <h3 className="mt-2 text-2xl text-white">核心相空间雷达图</h3>
        </div>
        <p className="max-w-40 text-right text-xs leading-5 text-slate-300">
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
            stroke="rgba(255,255,255,0.12)"
            strokeDasharray="3 8"
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
                stroke="rgba(255,255,255,0.15)"
              />
              <text
                x={CENTER + (axis.x - CENTER) * 1.14}
                y={CENTER + (axis.y - CENTER) * 1.14}
                fill="rgba(226,232,240,0.9)"
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
          fill="rgba(96,165,250,0.18)"
          stroke="rgba(125,211,252,0.95)"
          strokeWidth="2"
        />
      </svg>
    </div>
  );
}
