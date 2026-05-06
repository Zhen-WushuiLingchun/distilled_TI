type ProjectionChartProps = {
  x: number;
  y: number;
  confidence: number;
  clusterName?: string;
  answerPoints?: Array<{ x: number; y: number; label?: string | null }>;
  trajectoryPoints?: Array<{ x: number; y: number; label?: string | null }>;
  clusterCenters?: Array<{ x: number; y: number; label?: string | null }>;
  clusterRegions?: Array<{ x: number; y: number; rx: number; ry: number; angle: number; cluster_name: string }>;
};

function toCanvasX(x: number) {
  return 160 + x * 34;
}

function toCanvasY(y: number) {
  return 120 - y * 34;
}

export function ProjectionChart({
  x,
  y,
  confidence,
  clusterName,
  answerPoints = [],
  trajectoryPoints = [],
  clusterCenters = [],
  clusterRegions = [],
}: ProjectionChartProps) {
  const cx = 160 + x * 34;
  const cy = 120 - y * 34;
  const radius = 10 + confidence * 10;
  const trajectoryPath = trajectoryPoints
    .map((point, index) => `${index === 0 ? "M" : "L"} ${toCanvasX(point.x)} ${toCanvasY(point.y)}`)
    .join(" ");

  return (
    <div className="panel p-5 md:p-6">
      <p className="label-mini">Cluster Map</p>
      <h3 className="mt-1.5 text-xl text-[color:var(--ink-strong)]">聚类轨迹投影图</h3>
      <div className="surface-sunken mt-5 overflow-hidden p-3">
        <svg viewBox="0 0 320 240" className="h-[260px] w-full">
          <defs>
            <radialGradient id="clusterGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="rgba(47,111,94,0.85)" />
              <stop offset="100%" stopColor="rgba(47,111,94,0.05)" />
            </radialGradient>
          </defs>
          <line x1="20" y1="120" x2="300" y2="120" stroke="rgba(26,24,22,0.10)" strokeDasharray="3 6" />
          <line x1="160" y1="20" x2="160" y2="220" stroke="rgba(26,24,22,0.10)" strokeDasharray="3 6" />
          <text x="288" y="112" fill="rgba(107,102,96,0.9)" fontSize="11">P1+</text>
          <text x="166" y="28" fill="rgba(107,102,96,0.9)" fontSize="11">P2+</text>
          {clusterRegions.map((region, index) => (
            <g key={`${region.cluster_name}-${index}`}>
              <ellipse
                cx={toCanvasX(region.x)}
                cy={toCanvasY(region.y)}
                rx={Math.max(14, region.rx * 24)}
                ry={Math.max(10, region.ry * 24)}
                transform={`rotate(${region.angle} ${toCanvasX(region.x)} ${toCanvasY(region.y)})`}
                fill="rgba(184,128,31,0.06)"
                stroke="rgba(184,128,31,0.32)"
                strokeWidth="1"
              />
            </g>
          ))}
          {trajectoryPath ? (
            <path
              d={trajectoryPath}
              fill="none"
              stroke="rgba(47,111,94,0.55)"
              strokeWidth="1.4"
              strokeDasharray="4 4"
            />
          ) : null}
          {answerPoints.map((point, index) => (
            <g key={`${point.label ?? "answer"}-${index}`}>
              <circle
                cx={toCanvasX(point.x)}
                cy={toCanvasY(point.y)}
                r="3"
                fill="rgba(47,111,94,0.55)"
              />
              <title>{point.label ?? `answer-${index + 1}`}</title>
            </g>
          ))}
          {clusterCenters.map((point, index) => (
            <g key={`${point.label ?? "cluster"}-${index}`}>
              <circle
                cx={toCanvasX(point.x)}
                cy={toCanvasY(point.y)}
                r="4.5"
                fill="rgba(184,128,31,0.9)"
              />
              <text
                x={toCanvasX(point.x) + 8}
                y={toCanvasY(point.y) - 8}
                fill="rgba(107,74,20,0.95)"
                fontSize="11"
              >
                {point.label ?? `簇 ${index + 1}`}
              </text>
            </g>
          ))}
          <circle cx={cx} cy={cy} r={radius} fill="url(#clusterGlow)" />
          <circle cx={cx} cy={cy} r="3.5" fill="#1a1816" />
        </svg>
      </div>
      <div className="mt-3.5 flex flex-wrap gap-1.5">
        <span className="chip">当前点 {clusterName ?? "未定簇"}</span>
        <span className="chip chip-accent">青点：题目/选择向量</span>
        <span className="chip">虚线：作答轨迹</span>
        <span className="chip chip-warn">黄点：聚类中心</span>
        <span className="chip chip-warn">淡黄椭圆：簇包络</span>
      </div>
      <p className="mt-3.5 text-[0.82rem] leading-6 text-[color:var(--ink-muted)]">
        这张图来自高维特征向量压缩后的二维投影，P1/P2 不是原始人格轴；椭圆表示簇在投影平面里的近似包络，而不是硬边界。
      </p>
    </div>
  );
}
