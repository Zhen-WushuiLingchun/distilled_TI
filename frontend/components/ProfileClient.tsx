"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  getCurrentUser,
  generateUserInvite,
  issueUserSessionAccess,
  listCurrentUserRecommendations,
  listUserSessions,
  updateCurrentUser,
  type SessionHistoryEntry,
  type UserProfile,
  type UserRecommendation,
} from "@/lib/api";
import {
  clearUserAccess,
  getUserAccess,
  saveActiveSessionAccess,
  saveUserAccess,
  type UserAccessBundle,
} from "@/lib/runtime-store";

export function ProfileClient() {
  const router = useRouter();
  const [access, setAccess] = useState<UserAccessBundle | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [sessions, setSessions] = useState<SessionHistoryEntry[]>([]);
  const [recommendations, setRecommendations] = useState<UserRecommendation[]>([]);
  const [recommendationsEnabled, setRecommendationsEnabled] = useState(false);
  const [error, setError] = useState("");
  const [shareStatus, setShareStatus] = useState("");
  const [busy, setBusy] = useState(false);

  async function load() {
    const stored = getUserAccess();
    if (!stored) {
      setAccess(null);
      setProfile(null);
      setSessions([]);
      setRecommendations([]);
      setRecommendationsEnabled(false);
      return;
    }
    const [profilePayload, sessionPayload, recommendationPayload] = await Promise.all([
      getCurrentUser(stored),
      listUserSessions(stored),
      listCurrentUserRecommendations(stored).catch(() => ({ enabled: false, items: [] })),
    ]);
    const refreshed = {
      ...stored,
      handle: profilePayload.handle,
      relationship_opt_in: profilePayload.relationship_opt_in,
      recommendation_opt_in: profilePayload.recommendation_opt_in,
    };
    saveUserAccess(refreshed);
    setAccess(refreshed);
    setProfile(profilePayload);
    setSessions(sessionPayload.sessions);
    setRecommendations(recommendationPayload.items);
    setRecommendationsEnabled(recommendationPayload.enabled);
  }

  useEffect(() => {
    void load().catch((reason) => {
      setError(reason instanceof Error ? reason.message : "读取档案失败。");
    });
  }, []);

  async function handleFlagChange(next: Partial<Pick<UserProfile, "relationship_opt_in" | "recommendation_opt_in">>) {
    if (!access || !profile) return;
    try {
      setBusy(true);
      const updated = await updateCurrentUser(access, next);
      const refreshed = {
        ...access,
        relationship_opt_in: updated.relationship_opt_in,
        recommendation_opt_in: updated.recommendation_opt_in,
      };
      saveUserAccess(refreshed);
      setAccess(refreshed);
      setProfile(updated);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "更新档案设置失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleResume(sessionId: string, destination: "/session" | "/story" | "/report") {
    if (!access) return;
    try {
      setBusy(true);
      const sessionAccess = await issueUserSessionAccess(access, sessionId);
      saveActiveSessionAccess(sessionAccess);
      router.push(destination);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "签发会话访问凭证失败。");
    } finally {
      setBusy(false);
    }
  }

  function buildProfileShareLink() {
    if (!profile?.invite_code || typeof window === "undefined") return "";
    const params = new URLSearchParams({
      invite: profile.invite_code,
      from: profile.handle,
      title: `${profile.handle} 的 Distilled TI 入口`,
    });
    return `${window.location.origin}/share?${params.toString()}`;
  }

  async function handleCopyProfileShare() {
    const link = buildProfileShareLink();
    if (!link) return;
    await navigator.clipboard.writeText(link);
    setShareStatus("一次性邀请链接已复制；被使用后会自动失效，需要你再生成新的邀请码。");
  }

  async function handleGenerateInvite() {
    if (!access) return;
    try {
      setBusy(true);
      const updated = await generateUserInvite(access);
      setProfile(updated);
      setShareStatus("已生成一个新的一次性邀请码。旧的未使用邀请码已作废。");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "生成邀请码失败。");
    } finally {
      setBusy(false);
    }
  }

  if (!access || !profile) {
    return (
      <main className="cockpit-shell">
        <section className="relative z-10 mx-auto max-w-3xl space-y-5">
          <div className="panel fade-rise p-6 md:p-8">
            <p className="label-mini">Profile</p>
            <h1 className="mt-2 text-3xl md:text-4xl">还没有匿名档案</h1>
            <p className="mt-3 text-[color:var(--ink-muted)]">请先在首页输入邀请码，再回到这里查看长期历史和档案设置。</p>
            {error ? <p className="mt-3 text-sm text-[color:var(--danger-ink)]">{error}</p> : null}
            <button className="btn btn-primary mt-6" onClick={() => router.push("/")}>
              回到首页
            </button>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="cockpit-shell">
      <section className="relative z-10 mx-auto max-w-6xl space-y-5">
        <header className="panel fade-rise p-6 md:p-8">
          <p className="label-mini">Profile</p>
          <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="text-3xl md:text-4xl">{profile.handle}</h1>
              <p className="num mt-2 text-sm text-[color:var(--ink-muted)]">
                {profile.user_id} · invite {profile.invite_code ?? "none"}
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <button className="btn btn-ghost" onClick={() => router.push("/")}>首页</button>
              <button className="btn btn-ghost" onClick={() => router.push("/evolution")}>历史演化</button>
              <button className="btn btn-primary" onClick={() => router.push("/session")}>继续测量</button>
            </div>
          </div>
        </header>

        {error ? (
          <div className="panel border-[color:var(--danger)]/30 bg-[color:var(--danger-soft)] p-4 text-sm text-[color:var(--danger-ink)]">
            {error}
          </div>
        ) : null}

        <section className="grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="panel fade-rise space-y-4 p-5 md:p-6">
            <p className="label-mini">Privacy Controls</p>
            <h2 className="text-2xl">用户配置</h2>
            <label className="surface-sunken flex items-start gap-3 p-4">
              <input
                type="checkbox"
                className="mt-1"
                checked={profile.relationship_opt_in}
                disabled={busy}
                onChange={(event) => void handleFlagChange({ relationship_opt_in: event.target.checked })}
              />
              <span>
                <span className="block text-sm text-[color:var(--ink-strong)]">允许用于匿名关系图分析</span>
                <span className="mt-1 block text-xs leading-5 text-[color:var(--ink-muted)]">
                  只使用随机 ID、邀请链和聚类结果，不需要真实姓名或联系方式。
                </span>
              </span>
            </label>
            <label className="surface-sunken flex items-start gap-3 p-4">
              <input
                type="checkbox"
                className="mt-1"
                checked={profile.recommendation_opt_in}
                disabled={busy}
                onChange={(event) => void handleFlagChange({ recommendation_opt_in: event.target.checked })}
              />
              <span>
                <span className="block text-sm text-[color:var(--ink-strong)]">允许进入隐藏推荐实验池</span>
                <span className="mt-1 block text-xs leading-5 text-[color:var(--ink-muted)]">
                  公开页只显示匿名 handle、相似理由和分数；已经存在直接邀请关系的人会被排除。
                </span>
              </span>
            </label>
            <div className="surface-sunken p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="label-mini">Invite Link</p>
                  <h3 className="mt-1 text-lg text-[color:var(--ink-strong)]">我的分享入口</h3>
                </div>
                <span className="chip">{profile.invite_code ?? "no active invite"}</span>
              </div>
              <p className="mt-2 text-xs leading-5 text-[color:var(--ink-muted)]">
                每个邀请码只能邀请一个新用户或建立一次关系；用完后会自动失效。需要继续邀请时，在这里手动生成新的邀请码。
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button className="btn btn-primary px-3 py-1.5 text-xs" type="button" disabled={!profile.invite_code || busy} onClick={() => void handleCopyProfileShare()}>
                  复制我的邀请链接
                </button>
                <button className="btn btn-ghost px-3 py-1.5 text-xs" type="button" disabled={!profile.invite_code || busy} onClick={() => profile.invite_code && router.push(`/share?invite=${encodeURIComponent(profile.invite_code)}&from=${encodeURIComponent(profile.handle)}`)}>
                  预览分享页
                </button>
                <button className="btn btn-ghost px-3 py-1.5 text-xs" type="button" disabled={busy} onClick={() => void handleGenerateInvite()}>
                  生成新邀请码
                </button>
              </div>
              {shareStatus ? <p className="mt-2 text-xs text-[color:var(--accent-ink)]">{shareStatus}</p> : null}
            </div>

            <div className="surface-sunken p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="label-mini">Social Lab</p>
                  <h3 className="mt-1 text-lg text-[color:var(--ink-strong)]">匿名推荐</h3>
                </div>
                <span className="chip">{recommendationsEnabled ? "enabled" : "disabled"}</span>
              </div>
              {!recommendationsEnabled ? (
                <p className="mt-3 text-xs leading-5 text-[color:var(--ink-muted)]">
                  后端推荐开关尚未开启。开启后，只有双方都 opt-in 且已有报告样本时才会展示。
                </p>
              ) : recommendations.length ? (
                <div className="mt-3 space-y-2">
                  {recommendations.map((item) => (
                    <article key={item.candidate_user_id} className="rounded-[var(--r-md)] bg-[color:var(--bg-paper)] p-3">
                      <div className="flex items-center justify-between gap-3">
                        <strong className="text-sm">{item.candidate_handle}</strong>
                        <span className="num text-xs">{(item.score * 100).toFixed(1)}%</span>
                      </div>
                      <p className="mt-1 text-xs leading-5 text-[color:var(--ink-muted)]">{item.reason}</p>
                      {item.shared_cluster_name ? <p className="mt-1 text-xs text-[color:var(--accent-ink)]">{item.shared_cluster_name}</p> : null}
                    </article>
                  ))}
                </div>
              ) : (
                <p className="mt-3 text-xs leading-5 text-[color:var(--ink-muted)]">
                  暂无可推荐对象。通常需要双方都开启推荐，并完成至少一次可出报告的会话。
                </p>
              )}
            </div>
            <button
              className="text-xs text-[color:var(--ink-faint)] underline underline-offset-4"
              onClick={() => {
                clearUserAccess();
                router.push("/");
              }}
            >
              清除本机匿名凭证
            </button>
          </div>

          <div className="panel fade-rise space-y-3 p-5 md:p-6">
            <p className="label-mini">Archive</p>
            <h2 className="text-2xl">结果档案</h2>
            {sessions.length === 0 ? (
              <p className="surface-sunken p-4 text-sm text-[color:var(--ink-muted)]">还没有长期会话记录。</p>
            ) : (
              sessions.map((session) => (
                <article key={session.session_id} className="surface-sunken flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
                  <div>
                    <div className="mb-1 flex flex-wrap gap-1.5">
                      <span className="chip">{session.mode === "story" ? "Story Archive" : "Core Archive"}</span>
                      <span className="chip">{session.status}</span>
                    </div>
                    <p className="text-sm text-[color:var(--ink-strong)]">{session.narrative_label ?? "会话进行中"}</p>
                    <p className="num mt-1 text-xs text-[color:var(--ink-muted)]">
                      {session.question_count} questions · {session.cluster_name ?? "unclustered"} · {new Date(session.updated_at).toLocaleString()}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button className="btn btn-ghost px-3 py-1.5 text-xs" disabled={busy} onClick={() => void handleResume(session.session_id, session.mode === "story" ? "/story" : "/session")}>
                      {session.mode === "story" ? "继续剧情" : "继续"}
                    </button>
                    <button className="btn btn-primary px-3 py-1.5 text-xs" disabled={busy || !session.can_generate_report} onClick={() => void handleResume(session.session_id, "/report")}>
                      报告
                    </button>
                  </div>
                </article>
              ))
            )}
          </div>
        </section>
      </section>
    </main>
  );
}
