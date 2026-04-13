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
      <main className="session-shell">
        <div className="rounded-[2rem] border border-rose-300/20 bg-rose-300/10 p-8 text-rose-100">
          <p className="text-sm uppercase tracking-[0.35em]">Report Locked</p>
          <h1 className="mt-4 text-3xl">当前还不能查看正式报告</h1>
          <p className="mt-4 max-w-2xl leading-7">{displayError}</p>
          <button
            type="button"
            className="mt-8 rounded-full border border-white/20 px-6 py-3 text-sm font-semibold text-white"
            onClick={() => router.push("/session")}
          >
            返回继续答题
          </button>
        </div>
      </main>
    );
  }

  if (!report) {
    return <main className="session-shell">正在生成 AI 报告...</main>;
  }

  const hasSubBars = Object.keys(report.sub_bars).length > 0;
  const hasModuleBars = Object.keys(report.module_bars).length > 0;
  const clusterMix = report.cluster_mix ?? [];

  return (
    <main className="session-shell space-y-8">
      <section className="grid gap-8 lg:grid-cols-[1.15fr_0.85fr]">
        <div className="rounded-[2.4rem] border border-white/10 bg-white/6 p-8 backdrop-blur-2xl">
          <p className="text-xs uppercase tracking-[0.4em] text-cyan-200/70">Report</p>
          <h1 className="mt-4 text-5xl leading-[0.96] text-white md:text-6xl">{report.narrative_label}</h1>
          {report.ai_aliases.length > 0 ? (
            <div className="mt-4 flex flex-wrap gap-3">
              {report.ai_aliases.map((alias) => (
                <span key={alias} className="rounded-full border border-white/10 bg-black/20 px-4 py-2 text-sm text-indigo-100">
                  {alias}
                </span>
              ))}
            </div>
          ) : null}
          <p className="mt-4 text-sm uppercase tracking-[0.32em] text-indigo-200/70">{report.cluster_name}</p>
          <p className="mt-8 max-w-3xl text-lg leading-8 text-slate-200">{report.ai_summary}</p>
          {warning ? <p className="mt-4 text-sm text-amber-200">{warning}</p> : null}
          <div className="mt-8 grid gap-4 md:grid-cols-2">
            <label className="rounded-[1.2rem] border border-white/10 bg-black/20 p-4 text-sm text-slate-200">
              <span className="text-xs uppercase tracking-[0.28em] text-slate-400">Projection Mode</span>
              <select
                className="mt-3 w-full rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-white outline-none"
                value={projectionMode}
                onChange={(event) => setProjectionMode(event.target.value as ProjectionMode)}
              >
                <option value="auto">自动投影</option>
                <option value="structure">结构轴投影</option>
                <option value="core">核心维度投影</option>
              </select>
            </label>
            <label className="rounded-[1.2rem] border border-white/10 bg-black/20 p-4 text-sm text-slate-200">
              <span className="text-xs uppercase tracking-[0.28em] text-slate-400">Naming Style</span>
              <select
                className="mt-3 w-full rounded-xl border border-white/10 bg-slate-950/80 px-3 py-2 text-white outline-none"
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
          <p className="mt-3 text-sm leading-6 text-slate-400">
            投影模式只改变可视化视角，不改变底层聚类结果；命名风格只改变 AI 的命名与总结风格，不改变分数和簇归属。
          </p>

          <div className="mt-8 flex flex-wrap gap-3">
            {report.structural_labels.map((item) => (
              <span
                key={item.dimension}
                className="rounded-full border border-white/10 bg-black/20 px-4 py-2 text-sm text-cyan-100"
              >
                {item.label} {item.score > 0 ? "偏高" : "偏低"}
              </span>
            ))}
          </div>

          <div className="mt-10 flex flex-wrap gap-4">
            {finalizedView ? (
              <>
                <button
                  type="button"
                  className="rounded-full bg-cyan-300 px-6 py-3 text-sm font-semibold text-slate-950"
                  onClick={handleCloseFinalReport}
                >
                  关闭最终报告
                </button>
                <button
                  type="button"
                  className="rounded-full border border-white/15 bg-white/6 px-6 py-3 text-sm font-semibold text-white"
                  onClick={() => void handleDelete()}
                >
                  删除这次会话
                </button>
              </>
            ) : (
              <>
                <button
                  type="button"
                  className="rounded-full bg-cyan-300 px-6 py-3 text-sm font-semibold text-slate-950"
                  onClick={() => router.push("/session")}
                >
                  继续答题细化画像
                </button>
                <button
                  type="button"
                  className="rounded-full border border-white/15 bg-white/6 px-6 py-3 text-sm font-semibold text-white"
                  onClick={() => void handleDelete()}
                >
                  结束并删除本次会话
                </button>
              </>
            )}
          </div>
        </div>

        <div className="grid gap-6">
          <div className="glass-card h-fit">
            <p className="label-mini">Confidence</p>
            <p className="metric-big">{map ? `${(map.confidence * 100).toFixed(1)}%` : "--"}</p>
            <p className="mt-2 text-sm text-cyan-200">聚类置信度 {(report.cluster_confidence * 100).toFixed(1)}%</p>
            <p className="mt-3 text-sm leading-6 text-slate-300">
              当前估计稳定度来自核心维度的不确定性收缩，答题越多，区间通常越窄。
            </p>
          </div>
          <div className="glass-card h-fit">
            <p className="label-mini">Cluster Mix</p>
            <h3 className="mt-3 text-2xl text-white">多簇归属</h3>
            <div className="mt-5 space-y-3">
              {clusterMix.map((item) => (
                <div key={item.cluster_index} className="rounded-[1.2rem] border border-white/10 bg-white/5 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm text-cyan-100">{item.cluster_name}</p>
                      <p className="mt-1 text-xs text-slate-400">{item.narrative_label}</p>
                    </div>
                    <p className="text-lg text-white">{(item.weight * 100).toFixed(1)}%</p>
                  </div>
                  <p className="mt-2 text-xs text-slate-400">距离 {item.distance.toFixed(2)}</p>
                </div>
              ))}
              {clusterMix.length === 0 ? <p className="text-sm text-slate-400">当前簇混合信息还在生成中。</p> : null}
            </div>
          </div>
          <div className="glass-card h-fit">
            <p className="label-mini">Trajectory Projection</p>
            <div className="mt-4 grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs uppercase tracking-[0.25em] text-slate-400">P1 Axis</p>
                <p className="mt-2 text-2xl text-white">{map?.point.x.toFixed(2) ?? "--"}</p>
                <p className="mt-1 text-xs text-slate-500">P1 投影轴</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-[0.25em] text-slate-400">P2 Axis</p>
                <p className="mt-2 text-2xl text-white">{map?.point.y.toFixed(2) ?? "--"}</p>
                <p className="mt-1 text-xs text-slate-500">P2 投影轴</p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="grid gap-8 xl:grid-cols-[1.1fr_0.9fr]">
        <RadarChart values={report.core_bars} />
        <MetricBars
          eyebrow="Sub Space"
          title={hasSubBars ? "已解锁细分维度" : "细分维度采样中"}
          metrics={report.sub_bars}
          emptyMessage="当前还没有采到足够的细分题样本，所以这里先不展示百分比条；继续答题后会更早进入 sub 探测。"
        />
      </section>

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

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="glass-card">
          <p className="label-mini">Salient Subdimensions</p>
          <h3 className="mt-3 text-2xl text-white">显著细分纤维</h3>
          <div className="mt-5 flex flex-wrap gap-3">
            {report.salient_subdimensions.length > 0 ? (
              report.salient_subdimensions.map((item) => (
                <span key={item} className="rounded-full border border-white/10 bg-white/6 px-4 py-2 text-sm text-white">
                  {item}
                </span>
              ))
            ) : (
              <span className="text-sm text-slate-400">继续答题后会逐渐显露。</span>
            )}
          </div>
        </div>
        <div className="glass-card">
          <p className="label-mini">Activated Modules</p>
          <h3 className="mt-3 text-2xl text-white">活跃情境模块</h3>
          <div className="mt-5 flex flex-wrap gap-3">
            {report.active_module_labels.length > 0 ? (
              report.active_module_labels.map((item) => (
                <span key={item} className="rounded-full border border-cyan-300/15 bg-cyan-300/10 px-4 py-2 text-sm text-cyan-100">
                  {item}
                </span>
              ))
            ) : (
              <span className="text-sm text-slate-400">当前还没有足够数据激活模块投影。</span>
            )}
          </div>
        </div>
      </section>

      <section className="grid gap-8 lg:grid-cols-2">
        <div className="rounded-[2rem] border border-white/10 bg-black/20 p-6 backdrop-blur-xl">
          <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/70">Sub Insights</p>
          <h3 className="mt-2 text-2xl text-white">细分参数与评价</h3>
          <div className="mt-6 space-y-4">
            {report.sub_insights.length > 0 ? (
              report.sub_insights.map((item) => (
                <div key={item.key} className="rounded-[1.4rem] border border-white/8 bg-white/[0.04] p-4">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="text-sm text-cyan-100">{item.label}</p>
                      <p className="mt-1 text-xs uppercase tracking-[0.25em] text-slate-400">{item.parent_label}</p>
                    </div>
                    <div className="text-right">
                      <p className="text-lg text-white">{item.percent.toFixed(1)}%</p>
                      <p className="text-xs text-slate-400">sigma {item.sigma.toFixed(2)}</p>
                    </div>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-slate-200">
                      {item.direction_label}
                    </span>
                    <span className="rounded-full border border-cyan-300/15 bg-cyan-300/10 px-3 py-1 text-cyan-100">
                      {item.strength_label}
                    </span>
                    <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-slate-200">
                      证据 {item.sample_count} 题
                    </span>
                    <span className="rounded-full border border-emerald-300/15 bg-emerald-300/10 px-3 py-1 text-emerald-100">
                      稳定度 {item.confidence_percent.toFixed(1)}% / {item.confidence_label}
                    </span>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-slate-200">{item.evaluation}</p>
                  <p className="mt-2 text-xs text-cyan-200/80">{item.metaphor}</p>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-400">当前这一轮还没采到足够细的 sub 题，继续作答会更快出现。</p>
            )}
          </div>
        </div>

        <div className="rounded-[2rem] border border-white/10 bg-black/20 p-6 backdrop-blur-xl">
          <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/70">Module Insights</p>
          <h3 className="mt-2 text-2xl text-white">情境模块参数</h3>
          <div className="mt-6 space-y-4">
            {report.module_insights.length > 0 ? (
              report.module_insights.map((item) => (
                <div key={item.key} className="rounded-[1.4rem] border border-cyan-300/10 bg-cyan-300/[0.05] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm text-white">{item.label}</p>
                    <p className="text-sm text-cyan-200">{item.percent.toFixed(1)}%</p>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <span className="rounded-full border border-cyan-300/15 bg-cyan-300/10 px-3 py-1 text-cyan-100">
                      {item.strength_label}
                    </span>
                    <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1 text-slate-200">
                      证据 {item.sample_count} 题
                    </span>
                    <span className="rounded-full border border-emerald-300/15 bg-emerald-300/10 px-3 py-1 text-emerald-100">
                      稳定度 {item.confidence_percent.toFixed(1)}% / {item.confidence_label}
                    </span>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-slate-200">{item.evaluation}</p>
                  <p className="mt-2 text-xs text-cyan-200/80">{item.metaphor}</p>
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-400">模块投影还比较淡，继续答题会更容易长出来。</p>
            )}
          </div>
        </div>
      </section>

      <section className="grid gap-8 lg:grid-cols-2">
        <MetricBars eyebrow="Core Bars" title="核心维度百分比条" metrics={report.core_bars} />
        <MetricBars
          eyebrow="Module Projection"
          title={hasModuleBars ? "情境投影画像" : "模块投影采样中"}
          metrics={report.module_bars}
          emptyMessage="模块采样还偏淡，继续答题后这里会出现更明确的模块百分比条。"
        />
      </section>
    </main>
  );
}
