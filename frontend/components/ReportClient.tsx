"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { MetricBars } from "@/components/MetricBars";
import { ProjectionChart } from "@/components/ProjectionChart";
import { RadarChart } from "@/components/RadarChart";
import {
  deleteSession,
  generateSessionReport,
  getSessionMap,
  type SessionMap,
  type SessionReport,
} from "@/lib/api";
import {
  clearActiveSessionAccess,
  clearFinalReportSnapshot,
  getActiveSessionAccess,
  getFinalReportSnapshot,
  getReportViewPreferences,
  saveReportViewPreferences,
  type NamingStyle,
  type ProjectionMode,
} from "@/lib/runtime-store";

type ReportClientProps = {
  sessionId?: string;
};

export function ReportClient({ sessionId }: ReportClientProps) {
  const router = useRouter();
  const snapshot = getFinalReportSnapshot<{
    mode?: string;
    sessionId: string;
    report: SessionReport;
    map: SessionMap;
  }>();
  const activeAccess = getActiveSessionAccess();
  const [report, setReport] = useState<SessionReport | null>(() => (!sessionId ? snapshot?.report ?? null : null));
  const [map, setMap] = useState<SessionMap | null>(() => (!sessionId ? snapshot?.map ?? null : null));
  const [error, setError] = useState("");
  const [warning, setWarning] = useState("");
  const [projectionMode, setProjectionMode] = useState<ProjectionMode>(() => getReportViewPreferences().projectionMode);
  const [namingStyle, setNamingStyle] = useState<NamingStyle>(() => getReportViewPreferences().namingStyle);
  const reportRef = useRef(report);
  const mapRef = useRef(map);
  const hasMatchingAccess = activeAccess && (!sessionId || activeAccess.session_id === sessionId);
  const resolvedAccess = hasMatchingAccess ? activeAccess : null;
  const finalizedView = !sessionId && snapshot?.mode === "finalized";
  const displayError =
    error ||
    (!resolvedAccess && !snapshot?.report
      ? "当前没有可读取的会话凭证。请从当前会话页或本地历史页进入报告。"
      : "");

  useEffect(() => {
    saveReportViewPreferences({ projectionMode, namingStyle });
  }, [projectionMode, namingStyle]);

  useEffect(() => {
    reportRef.current = report;
    mapRef.current = map;
  }, [report, map]);

  useEffect(() => {
    let cancelled = false;
    if (!resolvedAccess) return;
    const access = resolvedAccess;

    async function refreshReportOnly() {
      try {
        const reportPayload = await generateSessionReport(access, namingStyle);
        if (cancelled) return;
        setReport(reportPayload);
        setError("");
        setWarning("");
      } catch (reason) {
        if (cancelled) return;
        if (!reportRef.current) {
          setError(reason instanceof Error ? reason.message : "报告读取失败。");
        } else {
          setWarning("命名风格更新失败，已保留上一版报告文案。");
        }
      }
    }

    void refreshReportOnly();
    return () => {
      cancelled = true;
    };
  }, [resolvedAccess, namingStyle]);

  useEffect(() => {
    let cancelled = false;
    if (!resolvedAccess) return;
    const access = resolvedAccess;

    async function refreshMapOnly() {
      try {
        const mapPayload = await getSessionMap(access, projectionMode);
        if (cancelled) return;
        setMap(mapPayload);
        setError("");
        setWarning("");
      } catch (reason) {
        if (cancelled) return;
        if (!mapRef.current) {
          setError(reason instanceof Error ? reason.message : "地图读取失败。");
        } else {
          setWarning("投影模式更新失败，已保留上一版地图视图。");
        }
      }
    }

    void refreshMapOnly();
    return () => {
      cancelled = true;
    };
  }, [resolvedAccess, projectionMode]);

  async function handleDelete() {
    if (!resolvedAccess) return;
    await deleteSession(resolvedAccess);
    clearActiveSessionAccess();
    clearFinalReportSnapshot();
    router.push("/");
  }

  function handleCloseFinalReport() {
    clearFinalReportSnapshot();
    router.push("/");
  }

  if (displayError) {
    return (
      <main className="cockpit-shell">
        <div className="relative z-10 mx-auto max-w-3xl">
          <div className="panel border-[color:var(--danger)]/30 bg-[color:var(--danger-soft)]/55 p-7 md:p-9">
            <p className="label-mini">Report Locked</p>
            <h1 className="mt-3 text-3xl text-[color:var(--ink-strong)]">当前还不能查看正式报告</h1>
            <p className="mt-4 max-w-2xl leading-7 text-[color:var(--ink-body)]">{displayError}</p>
            <button
              type="button"
              className="btn btn-ghost mt-7"
              onClick={() => router.push("/session")}
            >
              返回继续答题
            </button>
          </div>
        </div>
      </main>
    );
  }

  if (!report) {
    return (
      <main className="cockpit-shell">
        <div className="relative z-10 mx-auto flex min-h-[60vh] max-w-2xl flex-col items-center justify-center text-center">
          <p className="eyebrow">Report</p>
          <h1 className="mt-4 text-3xl">正在生成 AI 报告</h1>
          <p className="mt-3 text-[color:var(--ink-muted)]">读取会话状态、聚类簇与命名…</p>
        </div>
      </main>
    );
  }

  const hasSubBars = Object.keys(report.sub_bars).length > 0;
  const hasModuleBars = Object.keys(report.module_bars).length > 0;
  const clusterMix = report.cluster_mix ?? [];

  return (
    <main className="cockpit-shell">
      <section className="relative z-10 mx-auto max-w-[1400px] space-y-6">
        {/* ============== HERO + CONFIDENCE ============== */}
        <section className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
          <div className="panel-paper fade-rise p-6 md:p-9">
            <div className="flex items-center gap-3">
              <span className="eyebrow">Report</span>
              <span className="hairline-strong h-px w-8" aria-hidden />
              <span className="eyebrow">{report.cluster_name}</span>
            </div>

            <h1 className="mt-4 text-[2.5rem] leading-[1.05] text-[color:var(--ink-strong)] md:text-[3.4rem]">
              {report.narrative_label}
            </h1>

            {report.ai_aliases.length > 0 ? (
              <div className="mt-4 flex flex-wrap gap-1.5">
                {report.ai_aliases.map((alias) => (
                  <span key={alias} className="chip chip-accent">{alias}</span>
                ))}
              </div>
            ) : null}

            <p className="mt-7 max-w-3xl text-[1rem] leading-7 text-[color:var(--ink-body)] md:text-[1.05rem] md:leading-8 measure-wide">
              {report.ai_summary}
            </p>

            {warning ? (
              <p className="mt-4 rounded-[var(--r-md)] border border-[color:var(--warn-soft)] bg-[color:var(--warn-soft)]/55 p-3 text-sm text-[color:var(--warn-ink)]">
                {warning}
              </p>
            ) : null}

            {report.support_risk_flags?.length ? (
              <div className="mt-6 rounded-[var(--r-lg)] border border-[color:var(--warn)]/20 bg-[color:var(--warn-soft)]/45 p-4">
                <p className="label-mini">Support Signals / Non Diagnostic</p>
                <h3 className="mt-1.5 text-lg text-[color:var(--ink-strong)]">AI 助手可复用的支持提示</h3>
                <p className="mt-2 text-sm leading-6 text-[color:var(--ink-muted)]">
                  这些信号只适合做产品内的暂停、追问、人工复核或安全支持提示，不是心理诊断结论。
                </p>
                <div className="mt-3 grid gap-2 md:grid-cols-2">
                  {report.support_risk_flags.map((flag) => (
                    <article key={flag.key} className="surface-sunken p-3">
                      <div className="flex items-center justify-between gap-3">
                        <strong className="text-sm text-[color:var(--ink-strong)]">{flag.label}</strong>
                        <span className="chip">{flag.severity}</span>
                      </div>
                      <p className="mt-2 text-xs leading-5 text-[color:var(--ink-muted)]">{flag.suggested_action}</p>
                      <p className="num mt-2 text-[0.68rem] text-[color:var(--ink-faint)]">{flag.evidence.join(" / ")}</p>
                    </article>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="mt-7 grid gap-3 md:grid-cols-2">
              <label className="surface-flat block p-3.5">
                <span className="label-mini">Projection Mode</span>
                <select
                  className="field mt-2"
                  value={projectionMode}
                  onChange={(event) => setProjectionMode(event.target.value as ProjectionMode)}
                >
                  <option value="auto">自动投影</option>
                  <option value="structure">结构轴投影</option>
                  <option value="core">核心维度投影</option>
                </select>
              </label>
              <label className="surface-flat block p-3.5">
                <span className="label-mini">Naming Style</span>
                <select
                  className="field mt-2"
                  value={namingStyle}
                  onChange={(event) => setNamingStyle(event.target.value as NamingStyle)}
                >
                  <option value="auto">自动</option>
                  <option value="object">物体 / 器件</option>
                  <option value="creature">生物 / 怪物</option>
                  <option value="role">职业 / 角色</option>
                  <option value="apparatus">抽象装置</option>
                </select>
              </label>
            </div>
            <p className="mt-2.5 text-[0.82rem] leading-6 text-[color:var(--ink-muted)]">
              投影模式只改变可视化视角，不改变底层聚类结果；命名风格只改变 AI 的命名与总结风格，不改变分数和簇归属。
            </p>

            {report.structural_labels.length > 0 ? (
              <div className="mt-7 flex flex-wrap gap-1.5">
                {report.structural_labels.map((item) => (
                  <span key={item.dimension} className="chip">
                    {item.label} {item.score > 0 ? "偏高" : "偏低"}
                  </span>
                ))}
              </div>
            ) : null}

            <div className="mt-8 flex flex-wrap gap-2.5">
              {finalizedView ? (
                <>
                  <button type="button" className="btn btn-primary" onClick={handleCloseFinalReport}>
                    关闭最终报告
                  </button>
                  <button type="button" className="btn btn-danger" onClick={() => void handleDelete()}>
                    删除这次会话
                  </button>
                </>
              ) : (
                <>
                  <button type="button" className="btn btn-primary" onClick={() => router.push("/session")}>
                    继续答题细化画像
                  </button>
                  <button type="button" className="btn btn-danger" onClick={() => void handleDelete()}>
                    结束并删除本次会话
                  </button>
                </>
              )}
            </div>
          </div>

          <div className="grid gap-5">
            <div className="panel fade-rise p-5 md:p-6" style={{ animationDelay: "60ms" }}>
              <p className="label-mini">Confidence</p>
              <p className="metric-big">
                {map ? `${(map.confidence * 100).toFixed(1)}%` : "—"}
              </p>
              <p className="num mt-2 text-sm text-[color:var(--accent-ink)]">
                聚类置信度 {(report.cluster_confidence * 100).toFixed(1)}%
              </p>
              <p className="mt-3 text-[0.85rem] leading-6 text-[color:var(--ink-muted)]">
                当前估计稳定度来自核心维度的不确定性收缩，答题越多，区间通常越窄。
              </p>
            </div>

            <div className="panel fade-rise p-5 md:p-6" style={{ animationDelay: "120ms" }}>
              <p className="label-mini">Cluster Mix</p>
              <h3 className="mt-1.5 text-xl text-[color:var(--ink-strong)]">多簇归属</h3>
              <div className="mt-4 space-y-2.5">
                {clusterMix.map((item) => (
                  <div key={item.cluster_index} className="surface-sunken p-3.5">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-[0.9rem] text-[color:var(--ink-strong)]">{item.cluster_name}</p>
                        <p className="mt-0.5 truncate text-[0.72rem] text-[color:var(--ink-faint)]">
                          {item.narrative_label}
                        </p>
                      </div>
                      <p className="num text-base text-[color:var(--ink-strong)]">{(item.weight * 100).toFixed(1)}%</p>
                    </div>
                    <p className="num mt-2 text-[0.7rem] text-[color:var(--ink-faint)]">距离 {item.distance.toFixed(2)}</p>
                  </div>
                ))}
                {clusterMix.length === 0 ? (
                  <p className="text-sm text-[color:var(--ink-muted)]">当前簇混合信息还在生成中。</p>
                ) : null}
              </div>
            </div>

            <div className="panel fade-rise p-5 md:p-6" style={{ animationDelay: "180ms" }}>
              <p className="label-mini">Trajectory Projection</p>
              <div className="mt-4 grid grid-cols-2 gap-3">
                <div className="surface-sunken p-3.5">
                  <p className="label-mini">P1 Axis</p>
                  <p className="num mt-1.5 text-2xl text-[color:var(--ink-strong)]">
                    {map?.point.x.toFixed(2) ?? "—"}
                  </p>
                  <p className="mt-0.5 text-[0.7rem] text-[color:var(--ink-faint)]">P1 投影轴</p>
                </div>
                <div className="surface-sunken p-3.5">
                  <p className="label-mini">P2 Axis</p>
                  <p className="num mt-1.5 text-2xl text-[color:var(--ink-strong)]">
                    {map?.point.y.toFixed(2) ?? "—"}
                  </p>
                  <p className="mt-0.5 text-[0.7rem] text-[color:var(--ink-faint)]">P2 投影轴</p>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ============== Radar + Sub Bars ============== */}
        <section className="grid gap-5 xl:grid-cols-[1.05fr_0.95fr]">
          <RadarChart values={report.core_bars} />
          <MetricBars
            eyebrow="Sub Space"
            title={hasSubBars ? "已解锁细分维度" : "细分维度采样中"}
            metrics={report.sub_bars}
            emptyMessage="当前还没有采到足够的细分题样本，所以这里先不展示百分比条；继续答题后会更早进入 sub 探测。"
          />
        </section>

        {/* ============== Projection chart ============== */}
        {map ? (
          <ProjectionChart
            x={map.point.x}
            y={map.point.y}
            confidence={map.confidence}
            clusterName={map.point.cluster_name ?? report.cluster_name}
            answerPoints={map.answer_points}
            trajectoryPoints={map.trajectory_points}
            clusterCenters={map.cluster_centers}
            clusterRegions={map.cluster_regions}
          />
        ) : null}

        {/* ============== Salient + Active modules ============== */}
        <section className="grid gap-5 lg:grid-cols-2">
          <div className="panel p-5 md:p-6">
            <p className="label-mini">Salient Subdimensions</p>
            <h3 className="mt-1.5 text-xl text-[color:var(--ink-strong)]">显著细分纤维</h3>
            <div className="mt-4 flex flex-wrap gap-1.5">
              {report.salient_subdimensions.length > 0 ? (
                report.salient_subdimensions.map((item) => (
                  <span key={item} className="chip">{item}</span>
                ))
              ) : (
                <span className="text-sm text-[color:var(--ink-muted)]">继续答题后会逐渐显露。</span>
              )}
            </div>
          </div>
          <div className="panel p-5 md:p-6">
            <p className="label-mini">Activated Modules</p>
            <h3 className="mt-1.5 text-xl text-[color:var(--ink-strong)]">活跃情境模块</h3>
            <div className="mt-4 flex flex-wrap gap-1.5">
              {report.active_module_labels.length > 0 ? (
                report.active_module_labels.map((item) => (
                  <span key={item} className="chip chip-accent">{item}</span>
                ))
              ) : (
                <span className="text-sm text-[color:var(--ink-muted)]">当前还没有足够数据激活模块投影。</span>
              )}
            </div>
          </div>
        </section>

        {/* ============== Sub / Module Insights ============== */}
        <section className="grid gap-5 lg:grid-cols-2">
          <div className="panel p-5 md:p-6">
            <p className="label-mini">Sub Insights</p>
            <h3 className="mt-1.5 text-xl text-[color:var(--ink-strong)]">细分参数与评价</h3>
            <div className="mt-5 space-y-3">
              {report.sub_insights.length > 0 ? (
                report.sub_insights.map((item) => (
                  <div key={item.key} className="surface-sunken p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-[0.92rem] text-[color:var(--ink-strong)]">{item.label}</p>
                        <p className="label-mini mt-0.5">{item.parent_label}</p>
                      </div>
                      <div className="text-right">
                        <p className="num text-lg text-[color:var(--ink-strong)]">{item.percent.toFixed(1)}%</p>
                        <p className="num text-[0.7rem] text-[color:var(--ink-faint)]">σ {item.sigma.toFixed(2)}</p>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      <span className="chip">{item.direction_label}</span>
                      <span className="chip chip-accent">{item.strength_label}</span>
                      <span className="chip">证据 {item.sample_count} 题</span>
                      <span className="chip chip-success">
                        稳定度 {item.confidence_percent.toFixed(1)}% / {item.confidence_label}
                      </span>
                    </div>
                    <p className="mt-3 text-[0.88rem] leading-6 text-[color:var(--ink-body)]">{item.evaluation}</p>
                    <p className="mt-1.5 text-[0.78rem] italic leading-5 text-[color:var(--accent-ink)]">{item.metaphor}</p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-[color:var(--ink-muted)]">
                  当前这一轮还没采到足够细的 sub 题，继续作答会更快出现。
                </p>
              )}
            </div>
          </div>

          <div className="panel p-5 md:p-6">
            <p className="label-mini">Module Insights</p>
            <h3 className="mt-1.5 text-xl text-[color:var(--ink-strong)]">情境模块参数</h3>
            <div className="mt-5 space-y-3">
              {report.module_insights.length > 0 ? (
                report.module_insights.map((item) => (
                  <div key={item.key} className="rounded-[var(--r-md)] border border-[color:var(--accent-soft)] bg-[color:var(--accent-soft)]/40 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-[0.92rem] text-[color:var(--ink-strong)]">{item.label}</p>
                      <p className="num text-[0.92rem] text-[color:var(--accent-ink)]">{item.percent.toFixed(1)}%</p>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      <span className="chip chip-accent">{item.strength_label}</span>
                      <span className="chip">证据 {item.sample_count} 题</span>
                      <span className="chip chip-success">
                        稳定度 {item.confidence_percent.toFixed(1)}% / {item.confidence_label}
                      </span>
                    </div>
                    <p className="mt-3 text-[0.88rem] leading-6 text-[color:var(--ink-body)]">{item.evaluation}</p>
                    <p className="mt-1.5 text-[0.78rem] italic leading-5 text-[color:var(--accent-ink)]">{item.metaphor}</p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-[color:var(--ink-muted)]">
                  模块投影还比较淡，继续答题会更容易长出来。
                </p>
              )}
            </div>
          </div>
        </section>

        {/* ============== Core / Module bars ============== */}
        <section className="grid gap-5 lg:grid-cols-2">
          <MetricBars eyebrow="Core Bars" title="核心维度百分比条" metrics={report.core_bars} />
          <MetricBars
            eyebrow="Module Projection"
            title={hasModuleBars ? "情境投影画像" : "模块投影采样中"}
            metrics={report.module_bars}
            emptyMessage="模块采样还偏淡，继续答题后这里会出现更明确的模块百分比条。"
          />
        </section>
      </section>
    </main>
  );
}
