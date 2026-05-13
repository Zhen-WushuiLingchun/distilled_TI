"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { getCurrentUser, getUserEvolution, issueUserSessionAccess, type UserEvolutionEntry } from "@/lib/api";
import { getUserAccess, saveActiveSessionAccess, type UserAccessBundle } from "@/lib/runtime-store";

const CORE_LABELS: Record<string, string> = {
  abstraction_tendency: "抽象",
  autonomous_judgment: "自主",
  novelty_seeking: "新奇",
  social_orientation: "社交",
  planning_preference: "规划",
  risk_appetite: "风险",
};

function topCore(entry: UserEvolutionEntry) {
  return Object.entries(entry.core_mu)
    .sort((left, right) => Math.abs(right[1]) - Math.abs(left[1]))
    .slice(0, 3);
}

export function EvolutionClient() {
  const router = useRouter();
  const [user, setUser] = useState<UserAccessBundle | null>(null);
  const [items, setItems] = useState<UserEvolutionEntry[]>([]);
  const [error, setError] = useState("");
  const [shareStatus, setShareStatus] = useState("");
  const latest = items.at(-1);
  const strongestDelta = useMemo(() => {
    if (!latest) return [];
    return Object.entries(latest.core_delta_from_previous)
      .sort((left, right) => Math.abs(right[1]) - Math.abs(left[1]))
      .slice(0, 4);
  }, [latest]);

  useEffect(() => {
    async function load() {
      const stored = getUserAccess();
      setUser(stored);
      if (!stored) return;
      const payload = await getUserEvolution(stored);
      setItems(payload.items);
    }
    void load().catch((reason) => {
      setError(reason instanceof Error ? reason.message : "读取历史演化失败。");
    });
  }, []);

  async function handleOpenSession(sessionId: string, destination: "/session" | "/report") {
    if (!user) return;
    try {
      const access = await issueUserSessionAccess(user, sessionId);
      saveActiveSessionAccess(access);
      router.push(destination);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "打开历史会话失败。");
    }
  }

  async function handleCopyEvolutionShare() {
    if (!user || typeof window === "undefined") return;
    const params = new URLSearchParams({
      invite: "",
      from: user.handle,
      title: `${user.handle} 的 Distilled TI 历史入口`,
    });
    const profileInvite = await getCurrentUser(user).then((profile) => profile.invite_code);
    params.set("invite", profileInvite);
    await navigator.clipboard.writeText(`${window.location.origin}/share?${params.toString()}`);
    setShareStatus("历史入口分享链接已复制，链接包含你的个人邀请码。");
  }

  if (!user) {
    return (
      <main className="cockpit-shell">
        <section className="relative z-10 mx-auto max-w-3xl">
          <div className="panel p-7 md:p-9">
            <p className="label-mini">Evolution</p>
            <h1 className="mt-2 text-3xl md:text-4xl">需要先进入匿名档案</h1>
            <p className="mt-3 text-[color:var(--ink-muted)]">输入邀请码后，系统才会把多次会话串成长期演化轨迹。</p>
            <button className="btn btn-primary mt-6" onClick={() => router.push("/")}>回到首页</button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="cockpit-shell">
      <section className="relative z-10 mx-auto max-w-6xl space-y-5">
        <header className="panel fade-rise p-6 md:p-8">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="label-mini">Report Evolution</p>
              <h1 className="mt-2 text-3xl md:text-4xl">{user.handle} 的历史演化</h1>
              <p className="mt-3 max-w-2xl text-[0.95rem] leading-7 text-[color:var(--ink-muted)]">
                这里按长期匿名 ID 汇总会话，展示聚类标签、核心维度和 zeta 行为信号的变化。它是档案视图，不是诊断结论。
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button className="btn btn-ghost" onClick={() => router.push("/profile")}>用户配置</button>
              <button className="btn btn-ghost" onClick={() => void handleCopyEvolutionShare()}>复制邀请入口</button>
              <button className="btn btn-primary" onClick={() => router.push("/story")}>继续剧情</button>
            </div>
          </div>
          {shareStatus ? <p className="mt-4 text-xs text-[color:var(--accent-ink)]">{shareStatus}</p> : null}
        </header>

        {error ? <div className="panel border-[color:var(--danger)]/30 bg-[color:var(--danger-soft)] p-4 text-sm text-[color:var(--danger-ink)]">{error}</div> : null}

        <section className="grid gap-5 lg:grid-cols-[0.72fr_1.28fr]">
          <div className="panel fade-rise p-5 md:p-6">
            <p className="label-mini">Latest Delta</p>
            <h2 className="mt-1.5 text-2xl">最近一次变化</h2>
            {latest && strongestDelta.length ? (
              <div className="mt-4 space-y-2">
                {strongestDelta.map(([key, value]) => (
                  <div key={key} className="surface-sunken p-3">
                    <div className="flex items-center justify-between gap-3">
                      <span>{CORE_LABELS[key] ?? key}</span>
                      <span className="num">{value >= 0 ? "+" : ""}{value.toFixed(2)}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm leading-6 text-[color:var(--ink-muted)]">至少需要两次会话，才会出现跨会话变化。</p>
            )}
          </div>

          <div className="panel fade-rise p-5 md:p-6">
            <p className="label-mini">Timeline</p>
            <h2 className="mt-1.5 text-2xl">会话轨迹</h2>
            <div className="evolution-timeline mt-5">
              {items.map((item, index) => (
                <article key={item.session_id} className="evolution-row">
                  <div className="evolution-dot">{index + 1}</div>
                  <div className="surface-sunken p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <h3 className="text-lg text-[color:var(--ink-strong)]">{item.narrative_label ?? "会话进行中"}</h3>
                        <p className="num mt-1 text-xs text-[color:var(--ink-muted)]">
                          {item.question_count} questions · {item.cluster_name ?? "unclustered"} · {new Date(item.updated_at).toLocaleString()}
                        </p>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button className="btn btn-ghost px-3 py-1.5 text-xs" onClick={() => void handleOpenSession(item.session_id, "/session")}>
                          继续
                        </button>
                        <button
                          className="btn btn-primary px-3 py-1.5 text-xs"
                          disabled={!item.can_generate_report}
                          onClick={() => void handleOpenSession(item.session_id, "/report")}
                        >
                          报告
                        </button>
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      {topCore(item).map(([key, value]) => (
                        <span key={key} className="chip chip-accent">
                          {CORE_LABELS[key] ?? key} {value >= 0 ? "+" : ""}{value.toFixed(2)}
                        </span>
                      ))}
                    </div>
                    <div className="mt-3 grid gap-2 md:grid-cols-4">
                      {Object.entries(item.zeta).map(([key, value]) => (
                        <div key={key} className="rounded-[var(--r-md)] bg-[color:var(--bg-paper)] p-2.5">
                          <p className="label-mini">{key}</p>
                          <p className="num mt-1 text-lg">{value.toFixed(2)}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </article>
              ))}
              {!items.length ? <p className="text-sm text-[color:var(--ink-muted)]">还没有可展示的长期会话。</p> : null}
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}
