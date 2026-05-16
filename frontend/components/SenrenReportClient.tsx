"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/api";

type ApiErrorPayload = {
  detail?: string;
};

type ClusterMix = {
  cluster_name: string;
  weight: number;
};

type ChoiceSummary = {
  location?: string;
  option_text?: string;
};

interface ReportData {
  session_id: string;
  question_count: number;
  current_route: string | null;
  route_analysis?: {
    route_name: string;
    description: string;
    key_traits: Record<string, string>;
  };
  cluster_name: string;
  narrative_label: string;
  cluster_confidence: number;
  cluster_mix: ClusterMix[];
  structural_labels: { dimension: string; label: string; score: number }[];
  core_bars: Record<string, number>;
  character_affinity: Record<string, number>;
  best_match_character: string;
  uncertainty_summary: {
    avg_sigma: number;
    stable_dimensions: number;
  };
  choice_summary: ChoiceSummary[];
  ai_summary?: string;
  ai_aliases?: string[];
}

export default function SenrenReportClient() {
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchReport();
  }, []);

  async function fetchReport() {
    const sid = sessionStorage.getItem("senren_session_id") || "";
    const secret = sessionStorage.getItem("senren_session_secret") || "";

    if (!sid || !secret) {
      setError("未找到活动会话。请先启动监视器。");
      setLoading(false);
      return;
    }

    try {
      const res = await fetch(`${API_BASE}/senren/monitor/${sid}/report`, {
        headers: { "X-Session-Secret": secret },
      });
      if (!res.ok) {
        const detail = (await res.json().catch(() => ({}))) as ApiErrorPayload;
        throw new Error(detail.detail || `需要至少8个选择才能生成报告`);
      }
      const data = await res.json();
      setReport(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "报告生成失败");
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-[calc(100vh-41px)] flex items-center justify-center">
        <p className="text-[var(--senren-ink-muted)] animate-pulse">生成人格报告...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-[calc(100vh-41px)] flex items-center justify-center px-4">
        <div className="text-center max-w-md">
          <p className="text-[var(--senren-sakura)] text-lg mb-4">{error}</p>
          <Link
            href="/senren/monitor"
            className="senren-choice-btn inline-block text-center"
          >
            返回仪表盘
          </Link>
        </div>
      </div>
    );
  }

  if (!report) return null;

  const affinitySorted = Object.entries(report.character_affinity).sort(
    ([, a], [, b]) => b - a
  );

  return (
    <div className="min-h-[calc(100vh-41px)] px-4 py-8 max-w-3xl mx-auto">
      {/* 卷轴式报告 */}
      <div className="senren-scroll fade-rise">
        {/* 报告头 */}
        <div className="text-center mb-8 pt-4">
          <p className="text-xs tracking-[0.2em] text-[#8b7355] mb-2">
            穗织镇 · 人格测绘所
          </p>
          <h1 className="text-2xl font-semibold text-[#2d1f3d] mb-1">
            {report.narrative_label || "人格测绘报告"}
          </h1>
          {report.ai_aliases && report.ai_aliases.length > 0 && (
            <p className="text-xs text-[#8b7355]">
              亦作: {report.ai_aliases.join(" · ")}
            </p>
          )}
        </div>

        {/* AI 解读 */}
        {report.ai_summary && (
          <div className="mb-8 p-4 bg-[#faf3e6] rounded border border-[#c9a96e20]">
            <p className="text-sm text-[#2d1f3d] leading-relaxed whitespace-pre-line">
              {report.ai_summary}
            </p>
          </div>
        )}

        {/* 核心维度 */}
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-[#2d1f3d] mb-4 border-b border-[#c9a96e30] pb-2">
            核心人格维度
          </h2>
          <div className="space-y-3">
            {Object.entries(report.core_bars).map(([label, value]) => (
              <div key={label} className="flex items-center gap-3">
                <span className="text-xs text-[#5a5665] w-24 shrink-0">{label}</span>
                <div className="flex-1 h-3 bg-[#e8e0d0] rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-1000"
                    style={{
                      width: `${value}%`,
                      background: value > 55
                        ? "linear-gradient(90deg, #c44b6b, #c9a96e)"
                        : "linear-gradient(90deg, #4a3785, #4a7a5a)",
                    }}
                  />
                </div>
                <span className="text-xs text-[#8b8694] w-12 text-right">{value}%</span>
              </div>
            ))}
          </div>
        </div>

        {/* 结构标签 */}
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-[#2d1f3d] mb-3 border-b border-[#c9a96e30] pb-2">
            最显著特征
          </h2>
          <div className="flex flex-wrap gap-2">
            {report.structural_labels.map((label) => (
              <span
                key={label.dimension}
                className="px-3 py-1 rounded-full text-xs bg-[#c9a96e15] text-[#2d1f3d] border border-[#c9a96e30]"
              >
                {label.label}: {label.score > 0 ? "+" : ""}{label.score.toFixed(2)}
              </span>
            ))}
          </div>
        </div>

        {/* 角色契合度 */}
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-[#2d1f3d] mb-4 border-b border-[#c9a96e30] pb-2">
            角色契合度
          </h2>
          <div className="space-y-3">
            {affinitySorted.map(([name, score], idx) => (
              <div key={name} className="flex items-center gap-3">
                <span
                  className={`text-xs w-14 shrink-0 font-medium ${
                    idx === 0 ? "text-[#c44b6b]" : "text-[#5a5665]"
                  }`}
                >
                  {name}
                  {idx === 0 && " ★"}
                </span>
                <div className="flex-1 h-2 bg-[#e8e0d0] rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full"
                    style={{
                      width: `${score}%`,
                      background: idx === 0
                        ? "linear-gradient(90deg, #c44b6b, #c9a96e)"
                        : "#8b8694",
                    }}
                  />
                </div>
                <span className="text-xs text-[#8b8694] w-12 text-right">{score}%</span>
              </div>
            ))}
          </div>
          <p className="text-xs text-[#8b7355] mt-3 italic">
            你的选择模式最接近 {report.best_match_character || "..."}。
          </p>
        </div>

        {/* 路线分析 */}
        {report.route_analysis && (
          <div className="mb-8 p-4 bg-[#faf3e6] rounded border border-[#c9a96e20]">
            <h2 className="text-sm font-semibold text-[#2d1f3d] mb-2">
              路线分析: {report.route_analysis.route_name}
            </h2>
            <p className="text-xs text-[#5a5665] leading-relaxed">
              {report.route_analysis.description}
            </p>
          </div>
        )}

        {/* 不确定性 */}
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-[#2d1f3d] mb-2 border-b border-[#c9a96e30] pb-2">
            估计稳定性
          </h2>
          <div className="grid grid-cols-2 gap-4 text-xs">
            <div className="p-3 bg-[#faf3e6] rounded">
              <p className="text-[#8b7355]">平均不确定性</p>
              <p className="text-lg font-semibold text-[#2d1f3d]">
                {report.uncertainty_summary.avg_sigma.toFixed(2)}
              </p>
            </div>
            <div className="p-3 bg-[#faf3e6] rounded">
              <p className="text-[#8b7355]">已稳定维度</p>
              <p className="text-lg font-semibold text-[#2d1f3d]">
                {report.uncertainty_summary.stable_dimensions} / 10
              </p>
            </div>
          </div>
        </div>

        {/* 聚类信息 */}
        <div className="mb-8">
          <h2 className="text-sm font-semibold text-[#2d1f3d] mb-2 border-b border-[#c9a96e30] pb-2">
            聚类分析
          </h2>
          <p className="text-xs text-[#5a5665]">
            所属簇: {report.cluster_name}
            {report.cluster_confidence && ` (置信度: ${(report.cluster_confidence * 100).toFixed(0)}%)`}
          </p>
          {report.cluster_mix && report.cluster_mix.length > 1 && (
            <div className="mt-2 space-y-1">
              {report.cluster_mix.slice(0, 3).map((mix, idx) => (
                <div key={idx} className="flex items-center gap-2 text-xs">
                  <span className="text-[#5a5665]">{mix.cluster_name}</span>
                  <div className="flex-1 h-1.5 bg-[#e8e0d0] rounded-full overflow-hidden">
                    <div
                      className="h-full bg-[#c9a96e] rounded-full"
                      style={{ width: `${(mix.weight * 100).toFixed(0)}%` }}
                    />
                  </div>
                  <span className="text-[#8b8694] w-10 text-right">
                    {(mix.weight * 100).toFixed(0)}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 记录概况 */}
        <div className="mb-4">
          <h2 className="text-sm font-semibold text-[#2d1f3d] mb-2 border-b border-[#c9a96e30] pb-2">
            选择记录
          </h2>
          <p className="text-xs text-[#8b7355] mb-2">
            共 {report.question_count} 次选择 · 当前路线: {report.current_route || "未确定"}
          </p>
          <div className="max-h-60 overflow-y-auto space-y-1.5">
            {report.choice_summary?.map((choice, idx) => (
              <div key={idx} className="text-xs text-[#5a5665] flex gap-2">
                <span className="text-[#8b8694] shrink-0">{idx + 1}.</span>
                <span>
                  [{choice.location}] {choice.option_text?.slice(0, 40)}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 底部操作 */}
      <div className="mt-6 flex justify-center gap-4">
        <Link
          href="/senren/monitor"
          className="text-xs text-[var(--senren-ink-muted)] hover:text-[var(--senren-gold)] transition-colors"
        >
          ← 返回仪表盘
        </Link>
        <Link
          href="/senren/history"
          className="text-xs text-[var(--senren-ink-muted)] hover:text-[var(--senren-gold)] transition-colors"
        >
          历史记录
        </Link>
      </div>

      <p className="mt-12 text-center text-xs text-[var(--senren-ink-dim)]">
        本报告由 Distilled TI 引擎生成。仅供参考娱乐，不构成心理学诊断。
      </p>
    </div>
  );
}
