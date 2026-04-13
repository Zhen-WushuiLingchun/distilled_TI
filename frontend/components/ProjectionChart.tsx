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
    <div className="rounded-[2rem] border border-white/10 bg-black/20 p-6 backdrop-blur-xl">
      <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/70">Cluster Map</p>
      <h3 className="mt-2 text-2xl text-white">聚类轨迹投影图</h3>
      <div className="mt-6 overflow-hidden rounded-[1.4rem] border border-white/8 bg-[#08111f] p-4">
        <svg viewBox="0 0 320 240" className="h-[260px] w-full">
          <defs>
            <radialGradient id="clusterGlow" cx="50%" cy="50%" r="50%">
              <stop offset="0%" stopColor="rgba(103,232,249,0.95)" />
              <stop offset="100%" stopColor="rgba(99,102,241,0.25)" />
            </radialGradient>
          </defs>
          <line x1="20" y1="120" x2="300" y2="120" stroke="rgba(255,255,255,0.12)" strokeDasharray="4 8" />
          <line x1="160" y1="20" x2="160" y2="220" stroke="rgba(255,255,255,0.12)" strokeDasharray="4 8" />
          <text x="288" y="112" fill="rgba(148,163,184,0.75)" fontSize="11">P1+</text>
          <text x="166" y="28" fill="rgba(148,163,184,0.75)" fontSize="11">P2+</text>
          {clusterRegions.map((region, index) => (
            <g key={`${region.cluster_name}-${index}`}>
              <ellipse
                cx={toCanvasX(region.x)}
                cy={toCanvasY(region.y)}
                rx={Math.max(14, region.rx * 24)}
                ry={Math.max(10, region.ry * 24)}
                transform={`rotate(${region.angle} ${toCanvasX(region.x)} ${toCanvasY(region.y)})`}
                fill="rgba(250,204,21,0.07)"
                stroke="rgba(250,204,21,0.24)"
                strokeWidth="1.2"
              />
            </g>
          ))}
          {trajectoryPath ? (
            <path
              d={trajectoryPath}
              fill="none"
              stroke="rgba(165,180,252,0.55)"
              strokeWidth="1.6"
              strokeDasharray="5 4"
            />
          ) : null}
          {answerPoints.map((point, index) => (
            <g key={`${point.label ?? "answer"}-${index}`}>
              <circle
                cx={toCanvasX(point.x)}
                cy={toCanvasY(point.y)}
                r="3"
                fill="rgba(103,232,249,0.45)"
              />
              <title>{point.label ?? `answer-${index + 1}`}</title>
            </g>
          ))}
          {clusterCenters.map((point, index) => (
            <g key={`${point.label ?? "cluster"}-${index}`}>
              <circle
                cx={toCanvasX(point.x)}
                cy={toCanvasY(point.y)}
                r="5"
                fill="rgba(250,204,21,0.8)"
              />
              <text
                x={toCanvasX(point.x) + 8}
                y={toCanvasY(point.y) - 8}
                fill="rgba(250,204,21,0.92)"
                fontSize="11"
              >
                {point.label ?? `簇 ${index + 1}`}
              </text>
            </g>
          ))}
          <circle cx={cx} cy={cy} r={radius} fill="url(#clusterGlow)" />
          <circle cx={cx} cy={cy} r="4" fill="rgba(255,255,255,0.95)" />
        </svg>
      </div>
      <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-300">
        <span className="rounded-full border border-white/10 px-3 py-1">当前点 {clusterName ?? "未定簇"}</span>
        <span className="rounded-full border border-cyan-300/20 px-3 py-1">青点: 题目/选择向量</span>
        <span className="rounded-full border border-indigo-300/20 px-3 py-1">虚线: 作答轨迹</span>
        <span className="rounded-full border border-amber-300/20 px-3 py-1">黄点: 聚类中心</span>
        <span className="rounded-full border border-amber-300/20 px-3 py-1">淡黄椭圆: 簇包络</span>
      </div>
      <p className="mt-4 text-sm leading-6 text-slate-300">
        这张图来自高维特征向量压缩后的二维投影，P1/P2 不是原始人格轴；椭圆表示簇在投影平面里的近似包络，而不是硬边界。
      </p>
    </div>
  );
}
