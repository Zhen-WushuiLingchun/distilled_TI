"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import SenrenChoicePanel from "./SenrenChoicePanel";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/api";

interface ChoiceNode {
  choice_id: string;
  chapter: string;
  location: string;
  characters: string[];
  context: string;
  prompt: string;
  options: { key: string; text: string; affection_target: string }[];
  completed?: boolean;
  user_option?: string;
}

interface LiveState {
  session_id: string;
  mode: string;
  question_count: number;
  current_route: string | null;
  core_mu: Record<string, number>;
  core_sigma: Record<string, number>;
  top_dimensions: { key: string; label: string; score: number }[];
  character_affinity: Record<string, number>;
  recent_choices: any[];
  can_generate_report: boolean;
}

const DIM_LABELS: Record<string, string> = {
  social_initiative: "社交主动性",
  social_stimulation_tolerance: "社交刺激耐受",
  autonomous_judgment: "自主决断",
  planning_preference: "规划偏好",
  risk_tolerance: "风险容忍",
  abstraction_tendency: "抽象化",
  novelty_seeking: "新奇寻求",
  competition_cooperation: "竞争合作",
  emotional_stability: "情绪稳定",
  execution_drive: "执行力",
};

const AFFINITY_COLORS = ["sakura", "gold", "indigo", "jade", "vermillion"] as const;

export default function SenrenMonitorClient() {
  const router = useRouter();

  const [sessionId, setSessionId] = useState("");
  const [sessionSecret, setSessionSecret] = useState("");
  const [deleteToken, setDeleteToken] = useState("");

  const [roadmap, setRoadmap] = useState<ChoiceNode[]>([]);
  const [liveState, setLiveState] = useState<LiveState | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [showReport, setShowReport] = useState(false);

  // Current scenario being displayed
  const [currentScene, setCurrentScene] = useState<ChoiceNode | null>(null);
  const [allCompleted, setAllCompleted] = useState(false);

  // Fetch roadmap on mount
  useEffect(() => {
    const sid = sessionStorage.getItem("senren_session_id") || "";
    const secret = sessionStorage.getItem("senren_session_secret") || "";
    const dt = sessionStorage.getItem("senren_delete_token") || "";

    if (!sid || !secret) {
      router.push("/senren");
      return;
    }

    setSessionId(sid);
    setSessionSecret(secret);
    setDeleteToken(dt);

    fetchRoadmap(sid, secret);
    fetchLiveState(sid, secret);
  }, []);

  async function fetchRoadmap(sid: string, secret: string) {
    try {
      const res = await fetch(`${API_BASE}/senren/monitor/${sid}/roadmap`, {
        headers: { "X-Session-Secret": secret },
      });
      if (!res.ok) throw new Error("无法加载路线图");
      const data = await res.json();
      setRoadmap(data.nodes);

      // Find first incomplete node
      const next = data.nodes.find((n: ChoiceNode) => !n.completed);
      if (next) {
        setCurrentScene(next);
      } else if (data.nodes.length > 0) {
        // All completed
        setAllCompleted(true);
      }
    } catch (err: any) {
      setError(err.message);
    }
  }

  async function fetchLiveState(sid: string, secret: string) {
    try {
      const res = await fetch(`${API_BASE}/senren/monitor/${sid}/live-state`, {
        headers: { "X-Session-Secret": secret },
      });
      if (!res.ok) throw new Error("无法获取状态");
      const data = await res.json();
      setLiveState(data);
    } catch {
      // silently fail for live state
    } finally {
      setLoading(false);
    }
  }

  const handleChoiceSubmit = useCallback(
    async (choiceId: string, optionKey: string) => {
      setSubmitting(true);
      setError("");
      try {
        const res = await fetch(`${API_BASE}/senren/monitor/choice`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Session-Secret": sessionSecret,
          },
          body: JSON.stringify({
            session_id: sessionId,
            choice_id: choiceId,
            option_key: optionKey,
          }),
        });
        if (!res.ok) {
          const detail = await res.json().catch(() => ({}));
          throw new Error((detail as any).detail || "提交失败");
        }

        // Refresh state after choice
        await fetchLiveState(sessionId, sessionSecret);
        await fetchRoadmap(sessionId, sessionSecret);
        setCurrentScene(null);
      } catch (err: any) {
        setError(err.message);
      } finally {
        setSubmitting(false);
      }
    },
    [sessionId, sessionSecret]
  );

  // Scroll to next available scene
  const jumpToScene = useCallback(
    (choiceId: string) => {
      const node = roadmap.find((n) => n.choice_id === choiceId);
      if (node && !node.completed) {
        setCurrentScene(node);
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
    },
    [roadmap]
  );

  function goToReport() {
    router.push("/senren/report");
  }

  if (loading) {
    return (
      <div className="min-h-[calc(100vh-41px)] flex items-center justify-center">
        <p className="text-[var(--senren-ink-muted)] animate-pulse">正在加载千恋万花路线图...</p>
      </div>
    );
  }

  // ============================================================
  // 渲染：实时仪表盘
  // ============================================================
  return (
    <div className="min-h-[calc(100vh-41px)] px-4 py-6 max-w-6xl mx-auto">
      {/* 头部状态栏 */}
      <div className="flex items-center justify-between mb-6 senren-dashboard-panel">
        <div className="flex items-center gap-3">
          <span className="senren-pulse" />
          <div>
            <p className="text-[var(--senren-ink-strong)] text-sm font-medium">
              千恋万花 · 人格监视器
            </p>
            <p className="text-xs text-[var(--senren-ink-muted)]">
              已记录 {liveState?.question_count || 0} 个选择
              {liveState?.current_route && ` · ${liveState.current_route}`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {liveState?.can_generate_report && (
            <button
              onClick={goToReport}
              className="px-4 py-1.5 text-xs font-medium rounded border border-[var(--senren-sakura)] text-[var(--senren-sakura)] hover:bg-[var(--senren-sakura-soft)] transition-colors"
            >
              查看报告
            </button>
          )}
          <button
            onClick={() => {
              sessionStorage.clear();
              router.push("/senren");
            }}
            className="px-3 py-1.5 text-xs text-[var(--senren-ink-muted)] hover:text-[var(--senren-ink-body)] transition-colors"
          >
            退出
          </button>
        </div>
      </div>

      {/* 主布局：左侧场景 + 右侧仪表盘 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* 左侧：当前场景 / 路线图 */}
        <div className="lg:col-span-2 space-y-6">
          {/* 当前场景选择面板 */}
          {currentScene && !allCompleted && (
            <SenrenChoicePanel
              scene={currentScene}
              onSubmit={handleChoiceSubmit}
              submitting={submitting}
              error={error}
            />
          )}

          {allCompleted && (
            <div className="senren-dashboard-panel text-center py-12">
              <p className="text-[var(--senren-gold)] text-lg mb-3">✦ 所有选择已完成 ✦</p>
              <p className="text-[var(--senren-ink-muted)] text-sm mb-6">
                你已经在千恋万花中做出了所有关键选择。
              </p>
              {liveState?.can_generate_report && (
                <button
                  onClick={goToReport}
                  className="senren-choice-btn inline-block text-center w-auto px-8"
                >
                  查看完整人格报告
                </button>
              )}
            </div>
          )}

          {!currentScene && !allCompleted && (
            <div className="senren-dashboard-panel text-center py-12">
              <p className="text-[var(--senren-ink-muted)] text-sm">
                从下方路线图选择下一个场景...
              </p>
            </div>
          )}

          {/* 路线图 */}
          <div className="senren-dashboard-panel">
            <h2>选择路线图</h2>
            <div className="space-y-2 max-h-[400px] overflow-y-auto pr-2">
              {roadmap.map((node, idx) => (
                <button
                  key={node.choice_id}
                  onClick={() => jumpToScene(node.choice_id)}
                  disabled={node.completed}
                  className={`w-full text-left p-3 rounded transition-all ${
                    node.completed
                      ? "opacity-40 cursor-default"
                      : "hover:bg-[var(--senren-sakura-soft)] cursor-pointer border border-[var(--senren-line-soft)]"
                  } ${currentScene?.choice_id === node.choice_id ? "border-[var(--senren-sakura)] bg-[var(--senren-sakura-soft)]" : ""}`}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-[var(--senren-ink-dim)] w-5 shrink-0">
                      {node.completed ? "✓" : idx + 1}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm text-[var(--senren-ink-body)] truncate">
                        {node.context.slice(0, 50)}...
                      </p>
                      <p className="text-xs text-[var(--senren-ink-dim)] mt-0.5">
                        {node.location} · {node.characters.join("、")}
                      </p>
                    </div>
                    {node.completed && node.user_option && (
                      <span className="text-xs text-[var(--senren-gold)] shrink-0">
                        {node.options.find((o) => o.key === node.user_option)?.text.slice(0, 10)}...
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* 右侧：实时仪表盘 */}
        <div className="space-y-5">
          {/* 进度 */}
          <div className="senren-dashboard-panel">
            <h2>监视进度</h2>
            <div className="flex items-center justify-between mb-2">
              <span className="text-2xl font-semibold text-[var(--senren-ink-strong)]">
                {liveState?.question_count || 0}
              </span>
              <span className="text-xs text-[var(--senren-ink-dim)]">次选择</span>
            </div>
            <div className="senren-progress-bar mb-2">
              <div
                className="senren-progress-fill"
                style={{
                  width: `${Math.min(((liveState?.question_count || 0) / 20) * 100, 100)}%`,
                }}
              />
            </div>
            <p className="text-xs text-[var(--senren-ink-dim)]">
              {liveState?.can_generate_report
                ? "✓ 已达到报告生成要求"
                : `距报告解锁还需 ${8 - (liveState?.question_count || 0)} 次选择`}
            </p>
            {liveState?.current_route && (
              <p className="text-xs text-[var(--senren-gold)] mt-1">当前路线: {liveState.current_route}</p>
            )}
          </div>

          {/* 核心维度雷达（简化版：条形图） */}
          <div className="senren-dashboard-panel">
            <h2>核心人格维度</h2>
            <div className="space-y-2">
              {liveState?.top_dimensions?.map((dim) => (
                <div key={dim.key} className="flex items-center gap-2">
                  <span className="text-xs text-[var(--senren-ink-muted)] w-20 shrink-0 truncate">
                    {DIM_LABELS[dim.key] || dim.key}
                  </span>
                  <div className="flex-1 senren-progress-bar h-3">
                    <div
                      className="senren-progress-fill h-full"
                      style={{
                        width: `${Math.abs(dim.score) / 3 * 100}%`,
                        background: dim.score > 0
                          ? "linear-gradient(90deg, var(--senren-sakura), var(--senren-gold))"
                          : "linear-gradient(90deg, var(--senren-indigo-light), var(--senren-jade))",
                      }}
                    />
                  </div>
                  <span className="text-xs text-[var(--senren-ink-dim)] w-10 text-right">
                    {dim.score > 0 ? "+" : ""}{dim.score.toFixed(1)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* 角色契合度 */}
          <div className="senren-dashboard-panel">
            <h2>角色契合度</h2>
            <div className="space-y-3">
              {liveState?.character_affinity &&
                Object.entries(liveState.character_affinity)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 6)
                  .map(([name, score], idx) => (
                    <div key={name}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-[var(--senren-ink-body)]">{name}</span>
                        <span className="text-xs text-[var(--senren-ink-dim)]">{score}%</span>
                      </div>
                      <div className="senren-affinity-bar">
                        <div
                          className={`senren-affinity-fill ${AFFINITY_COLORS[idx % AFFINITY_COLORS.length]}`}
                          style={{ width: `${Math.min(score, 100)}%` }}
                        />
                      </div>
                    </div>
                  ))}
            </div>
          </div>

          {/* 最近选择时间线 */}
          <div className="senren-dashboard-panel">
            <h2>最近选择</h2>
            <div className="space-y-2.5 max-h-[260px] overflow-y-auto">
              {liveState?.recent_choices?.length ? (
                [...liveState.recent_choices].reverse().map((choice: any, idx: number) => (
                  <div key={idx} className="text-xs border-l-2 border-[var(--senren-line-soft)] pl-3">
                    <p className="text-[var(--senren-ink-muted)]">
                      {choice.context?.slice(0, 40)}...
                    </p>
                    <p className="text-[var(--senren-ink-body)] mt-0.5">
                      → {choice.option_text?.slice(0, 30)}
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-xs text-[var(--senren-ink-dim)]">等待第一个选择...</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {error && (
        <div className="mt-4 p-3 rounded bg-[var(--danger-soft)] text-[var(--danger-ink)] text-sm">
          {error}
        </div>
      )}
    </div>
  );
}
