"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  cleanupExpiredSessions,
  issueAdminSessionAccess,
  issueUserSessionAccess,
  listAdminSessions,
  listUserSessions,
  type SessionHistoryEntry,
} from "@/lib/api";
import { getUserAccess, saveActiveSessionAccess, type UserAccessBundle } from "@/lib/runtime-store";

export function HistoryClient() {
  const router = useRouter();
  const [sessions, setSessions] = useState<SessionHistoryEntry[]>([]);
  const [error, setError] = useState("");
  const [busySessionId, setBusySessionId] = useState("");
  const [userAccess, setUserAccess] = useState<UserAccessBundle | null>(null);

  async function load() {
    try {
      const storedUser = getUserAccess();
      setUserAccess(storedUser);
      const payload = storedUser ? await listUserSessions(storedUser) : await listAdminSessions();
      setSessions(payload.sessions);
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "读取会话失败。");
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function handleCleanup() {
    await cleanupExpiredSessions();
    await load();
  }

  async function handleResume(sessionId: string, destination: "/session" | "/report") {
    try {
      setBusySessionId(sessionId);
      const storedUser = getUserAccess();
      const access = storedUser
        ? await issueUserSessionAccess(storedUser, sessionId)
        : await issueAdminSessionAccess(sessionId);
      saveActiveSessionAccess(access);
      router.push(destination);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "签发会话访问凭证失败。");
    } finally {
      setBusySessionId("");
    }
  }

  return (
    <main className="cockpit-shell">
      <section className="relative z-10 mx-auto max-w-5xl space-y-5">
        <header className="panel fade-rise p-6 md:p-8">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="label-mini">History</p>
              <h1 className="mt-2 text-3xl md:text-4xl">历史记录与结果档案</h1>
              <p className="mt-3 max-w-2xl text-[0.95rem] leading-7 text-[color:var(--ink-muted)] measure">
                {userAccess
                  ? `当前匿名档案 ${userAccess.handle} 的长期会话记录。继续或查看报告前，系统会重新签发一次会话访问凭证。`
                  : "未输入邀请码时，这里退回到本地短期会话视图；输入邀请码后会显示长期档案历史。"}
              </p>
            </div>
            <div className="flex flex-wrap gap-2.5">
              <button className="btn btn-ghost" onClick={() => router.push("/")}>
                返回首页
              </button>
              <button className="btn btn-primary" onClick={() => void handleCleanup()}>
                清理过期会话
              </button>
            </div>
          </div>
        </header>

        {error ? (
          <div className="panel border-[color:var(--danger)]/30 bg-[color:var(--danger-soft)] p-4 text-sm text-[color:var(--danger-ink)]">
            {error}
          </div>
        ) : null}

        <div className="grid gap-3">
          {sessions.length === 0 ? (
            <div className="panel-quiet fade-rise p-6 text-center text-[color:var(--ink-muted)]">
              当前没有可展示的会话。
            </div>
          ) : (
            sessions.map((session, index) => (
              <article
                key={session.session_id}
                className="panel fade-rise flex flex-col gap-4 p-5 lg:flex-row lg:items-center lg:justify-between"
                style={{ animationDelay: `${60 + index * 40}ms` }}
              >
                <div className="min-w-0">
                  <span className="chip">{session.status}</span>
                  {session.user_handle ? <span className="chip ml-2">{session.user_handle}</span> : null}
                  <h2 className="mt-2.5 truncate text-xl text-[color:var(--ink-strong)]">
                    {session.narrative_label ?? "会话进行中"}
                  </h2>
                  <p className="num mt-2 text-[0.85rem] text-[color:var(--ink-muted)]">
                    已答 {session.question_count} 题
                    {session.cluster_name ? ` · ${session.cluster_name}` : ""}
                  </p>
                  <p className="num mt-1 text-[0.72rem] text-[color:var(--ink-faint)]">
                    更新时间 {new Date(session.updated_at).toLocaleString()}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2.5">
                  <button
                    className="btn btn-ghost"
                    disabled={busySessionId === session.session_id}
                    onClick={() => void handleResume(session.session_id, "/session")}
                  >
                    {busySessionId === session.session_id ? "签发中…" : "继续答题"}
                  </button>
                  <button
                    className="btn btn-primary"
                    disabled={busySessionId === session.session_id}
                    onClick={() => void handleResume(session.session_id, "/report")}
                  >
                    查看报告
                  </button>
                </div>
              </article>
            ))
          )}
        </div>
      </section>
    </main>
  );
}
