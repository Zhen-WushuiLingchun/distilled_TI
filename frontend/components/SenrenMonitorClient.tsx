"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/api";

type ChoiceOption = {
  key: string;
  text: string;
  affection_target: string;
};

type RoadmapNode = {
  choice_id: string;
  chapter: string;
  location: string;
  characters: string[];
  context: string;
  prompt: string;
  options: ChoiceOption[];
  completed: boolean;
  user_option?: string;
  locked: boolean;
  is_current_chapter: boolean;
};

type Roadmap = {
  nodes: RoadmapNode[];
  total: number;
  completed: number;
  current_route: string | null;
  chapter_progress: {
    completed_chapters: string[];
    current_chapter: string | null;
    current_chapters: string[];
    locked_chapters: string[];
    total_stages: number;
  };
};

type LiveState = {
  session_id: string;
  mode: string;
  question_count: number;
  current_route: string | null;
  core_mu: Record<string, number>;
  top_dimensions: { key: string; label: string; score: number }[];
  character_affinity: Record<string, number>;
  recent_choices: Array<{
    choice_id: string;
    option_key: string;
    option_text: string;
    context: string;
    location: string;
    characters: string[];
  }>;
  can_generate_report: boolean;
  chapter_progress: Roadmap["chapter_progress"];
};

export default function SenrenMonitorClient() {
  const router = useRouter();
  const [sessionId, setSessionId] = useState("");
  const [sessionSecret, setSessionSecret] = useState("");
  const [gamePath, setGamePath] = useState("");
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null);
  const [liveState, setLiveState] = useState<LiveState | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [justLaunched, setJustLaunched] = useState(false);
  const [launchingGame, setLaunchingGame] = useState(false);

  useEffect(() => {
    const sid = sessionStorage.getItem("senren_session_id");
    const secret = sessionStorage.getItem("senren_session_secret");
    const path = sessionStorage.getItem("senren_game_path") || "";
    if (!sid || !secret) {
      router.push("/senren");
      return;
    }
    setSessionId(sid);
    setSessionSecret(secret);
    setGamePath(path);

    // 检测是否刚启动游戏
    const launched = sessionStorage.getItem("senren_just_launched");
    if (launched === "1") {
      setJustLaunched(true);
      sessionStorage.removeItem("senren_just_launched");
      // 尝试最小化：调用 window.blur 让游戏窗口获得焦点
      try {
        window.blur();
        // 第二次尝试：通过打开再关闭微小窗口触发失焦
        const mini = window.open("about:blank", "_blank", "width=1,height=1,left=-100,top=-100");
        if (mini) setTimeout(() => mini.close(), 100);
      } catch {
        // 浏览器安全策略可能阻止
      }
    }

    void loadData(sid, secret);
  }, [router]);

  async function loadData(sid: string, secret: string) {
    setLoading(true);
    await Promise.all([fetchRoadmap(sid, secret), fetchLiveState(sid, secret)]);
    setLoading(false);
  }

  async function fetchRoadmap(sid: string, secret: string) {
    try {
      const res = await fetch(`${API_BASE}/senren/monitor/${sid}/roadmap`, {
        headers: { "X-Session-Secret": secret },
      });
      if (res.ok) setRoadmap(await res.json());
    } catch {
      // non-critical
    }
  }

  async function fetchLiveState(sid: string, secret: string) {
    try {
      const res = await fetch(`${API_BASE}/senren/monitor/${sid}/live-state`, {
        headers: { "X-Session-Secret": secret },
      });
      if (res.ok) setLiveState(await res.json());
    } catch {
      // non-critical
    }
  }

  async function submitChoice(node: RoadmapNode, option: ChoiceOption) {
    if (!sessionId || !sessionSecret) return;
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
          choice_id: node.choice_id,
          option_key: option.key,
        }),
      });
      if (!res.ok) {
        const detail = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(detail.detail || "选择提交失败");
      }
      await Promise.all([fetchRoadmap(sessionId, sessionSecret), fetchLiveState(sessionId, sessionSecret)]);
      // 记录完成后自动失焦，让用户回到游戏
      try { window.blur(); } catch { /* ignore */ }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  async function relaunchGame() {
    if (!gamePath) return;
    setLaunchingGame(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/senren/local-game/launch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game_path: gamePath }),
      });
      if (!res.ok) {
        const detail = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(detail.detail || "启动失败");
      }
      // 启动成功后自动失焦
      try {
        window.blur();
        const mini = window.open("about:blank", "_blank", "width=1,height=1,left=-100,top=-100");
        if (mini) setTimeout(() => mini.close(), 100);
      } catch { /* ignore */ }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "启动失败");
    } finally {
      setLaunchingGame(false);
    }
  }

  function endSession() {
    sessionStorage.removeItem("senren_session_id");
    sessionStorage.removeItem("senren_session_secret");
    sessionStorage.removeItem("senren_delete_token");
    sessionStorage.removeItem("senren_mode");
    sessionStorage.removeItem("senren_game_path");
    router.push("/senren");
  }

  function goToReport() {
    router.push("/senren/report");
  }

  const availableChoices = roadmap
    ? roadmap.nodes.filter((n) => n.is_current_chapter && !n.completed)
    : [];

  const completedChoices = roadmap
    ? roadmap.nodes.filter((n) => n.completed).reverse()
    : [];

  const allComplete = roadmap ? roadmap.completed >= roadmap.total : false;
  const cp = liveState?.chapter_progress || roadmap?.chapter_progress;
  const topAffinity = liveState?.character_affinity
    ? Object.entries(liveState.character_affinity)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 3)
    : [];
  const choiceCount = liveState?.question_count ?? roadmap?.completed ?? 0;

  if (loading) {
    return (
      <main className="flex min-h-[calc(100vh-3rem)] items-center justify-center">
        <div className="text-center">
          <div className="w-6 h-6 border-2 border-[color:var(--accent)] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-[color:var(--ink-muted)]">连接监视会话…</p>
        </div>
      </main>
    );
  }

  return (
    <main className="max-w-3xl mx-auto px-4 py-6 space-y-6">
      {/* 刚启动提示 */}
      {justLaunched && (
        <div className="surface-sunken p-6 rounded-[var(--r-lg)] text-center border border-[color:var(--accent-soft)]">
          <p className="text-lg font-medium text-[color:var(--ink-strong)]">
            游戏已启动
          </p>
          <p className="mt-2 text-sm text-[color:var(--ink-muted)]">
            请切换到游戏窗口开始游玩。此页面可最小化到后台，
            <br />
            监视器会自动跟踪你的游戏进度。
          </p>
          <button
            type="button"
            className="btn btn-ghost btn-sm mt-4"
            onClick={() => setJustLaunched(false)}
          >
            知道了
          </button>
        </div>
      )}

      {/* 状态栏 */}
      <div className="surface-sunken p-4 rounded-[var(--r-lg)]">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-[color:var(--accent)] animate-pulse" />
            <span className="text-[color:var(--ink-body)]">监视中</span>
          </span>
          <span className="text-[color:var(--ink-muted)]">|</span>
          <span className="text-[color:var(--ink-body)]">
            已记录 <strong>{choiceCount}</strong> 个选择
          </span>
          {liveState?.current_route && (
            <>
              <span className="text-[color:var(--ink-muted)]">|</span>
              <span className="chip chip-accent text-xs">{liveState.current_route}</span>
            </>
          )}
          {cp && (
            <>
              <span className="text-[color:var(--ink-muted)]">|</span>
              <span className="text-xs text-[color:var(--ink-muted)]">
                章节 {cp.completed_chapters.length}/{cp.total_stages}
                {cp.current_chapter
                  ? ` · ${cp.current_chapter}`
                  : cp.current_chapters.length > 1
                    ? " · 分支选择中"
                    : ""}
              </span>
            </>
          )}
        </div>
      </div>

      {/* 操作按钮 */}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          onClick={() => void relaunchGame()}
          disabled={launchingGame || !gamePath}
        >
          {launchingGame ? "启动中…" : "重新启动游戏"}
        </button>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          disabled={!liveState?.can_generate_report}
          onClick={goToReport}
        >
          {liveState?.can_generate_report
            ? "查看人格报告"
            : `还需 ${Math.max(0, 8 - choiceCount)} 个选择可出报告`}
        </button>
        <button type="button" className="btn btn-ghost btn-sm ml-auto" onClick={endSession}>
          结束监视
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-[var(--r-md)] border border-[color:var(--danger-soft)] bg-[color:var(--danger-soft)]/10 text-sm text-[color:var(--danger-ink)]">
          {error}
        </div>
      )}

      {/* 当前可选选择 */}
      {!allComplete && availableChoices.length > 0 && (
        <section className="space-y-4">
          <p className="label-mini">当前可记录的选择</p>
          {availableChoices.map((node) => (
            <div key={node.choice_id} className="surface-sunken p-5 rounded-[var(--r-lg)]">
              <div className="flex items-center gap-2 text-xs text-[color:var(--ink-muted)] mb-2">
                <span>{node.chapter}</span>
                <span>·</span>
                <span>{node.location}</span>
                {node.characters.length > 0 && (
                  <>
                    <span>·</span>
                    <span>{node.characters.join(", ")}</span>
                  </>
                )}
              </div>
              <p className="text-sm text-[color:var(--ink-body)] leading-relaxed mb-1">
                {node.context}
              </p>
              <p className="text-[color:var(--ink-strong)] font-medium mb-4">
                {node.prompt}
              </p>
              <div className="grid gap-2">
                {node.options.map((option) => (
                  <button
                    key={option.key}
                    type="button"
                    className="btn btn-ghost justify-start text-left"
                    disabled={submitting}
                    onClick={() => void submitChoice(node, option)}
                  >
                    <span>{option.text}</span>
                    {option.affection_target !== "none" && (
                      <span className="ml-auto text-xs text-[color:var(--ink-muted)] opacity-60">
                        ♥ {option.affection_target}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </section>
      )}

      {/* 全部完成 */}
      {allComplete && (
        <div className="surface-sunken p-8 rounded-[var(--r-lg)] text-center">
          <p className="text-lg font-medium text-[color:var(--ink-strong)]">
            所有选择已记录完毕
          </p>
          <p className="mt-2 text-sm text-[color:var(--ink-muted)]">
            查看基于全部游戏选择生成的人格画像报告。
          </p>
          <button type="button" className="btn btn-primary mt-4" onClick={goToReport}>
            查看人格报告
          </button>
        </div>
      )}

      {/* 等待下一章 */}
      {!allComplete && availableChoices.length === 0 && (
        <div className="surface-sunken p-6 rounded-[var(--r-lg)] text-center">
          <p className="text-[color:var(--ink-strong)] font-medium">
            等待下一个选择点
          </p>
          <p className="mt-1 text-sm text-[color:var(--ink-muted)]">
            在游戏中推进剧情。当前章节的选择均已完成。
          </p>
          <button
            type="button"
            className="btn btn-ghost btn-sm mt-3"
            onClick={() => loadData(sessionId, sessionSecret)}
          >
            刷新
          </button>
        </div>
      )}

      {/* 角色契合度 */}
      {topAffinity.length > 0 && (
        <section className="surface-sunken p-4 rounded-[var(--r-lg)]">
          <p className="label-mini mb-3">角色契合度</p>
          <div className="space-y-2">
            {topAffinity.map(([name, score]) => (
              <div key={name} className="flex items-center gap-3">
                <span className="text-sm text-[color:var(--ink-body)] w-16">{name}</span>
                <div className="flex-1 h-2 rounded-full bg-[color:var(--bg-sunken)] overflow-hidden">
                  <div
                    className="h-full rounded-full bg-[color:var(--accent)] transition-all"
                    style={{ width: `${Math.min(score, 100)}%` }}
                  />
                </div>
                <span className="text-xs text-[color:var(--ink-muted)] w-10 text-right">
                  {score.toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 选择记录 */}
      {completedChoices.length > 0 && (
        <section>
          <p className="label-mini mb-3">选择记录</p>
          <div className="space-y-2">
            {completedChoices.slice(0, 10).map((node) => (
              <div key={node.choice_id} className="surface-sunken p-3 rounded-[var(--r-md)] text-sm">
                <div className="flex items-center gap-2 text-xs text-[color:var(--ink-muted)] mb-1">
                  <span>{node.chapter}</span>
                  <span>·</span>
                  <span>{node.location}</span>
                </div>
                <p className="text-[color:var(--ink-body)]">{node.context}</p>
                <p className="mt-1 text-[color:var(--accent)] font-medium">
                  →{" "}
                  {node.user_option
                    ? node.options.find((o) => o.key === node.user_option)?.text || node.user_option
                    : "已选择"}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
