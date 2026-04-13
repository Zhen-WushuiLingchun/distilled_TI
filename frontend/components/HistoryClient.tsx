"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  cleanupExpiredSessions,
  issueAdminSessionAccess,
  listAdminSessions,
  type SessionHistoryEntry,
} from "@/lib/api";
import { saveActiveSessionAccess } from "@/lib/runtime-store";

export function HistoryClient() {
  const router = useRouter();
  const [sessions, setSessions] = useState<SessionHistoryEntry[]>([]);
  const [error, setError] = useState("");
  const [busySessionId, setBusySessionId] = useState("");

  async function load() {
    try {
      const payload = await listAdminSessions();
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
      const access = await issueAdminSessionAccess(sessionId);
      saveActiveSessionAccess(access);
      router.push(destination);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "签发会话访问凭证失败。");
    } finally {
      setBusySessionId("");
    }
  }

  return (
    <main className="session-shell">
      <section className="mx-auto max-w-6xl rounded-[2.5rem] border border-white/10 bg-white/6 p-8 backdrop-blur-2xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="label-mini">History</p>
            <h1 className="mt-3 text-5xl text-white">本地会话与短期历史</h1>
            <p className="mt-4 max-w-2xl text-slate-300">
              这里展示仍在 1 小时生命周期内的本地会话。继续或查看报告前，页面会通过 localhost 管理端重新签发一次访问凭证。
            </p>
          </div>
          <div className="flex gap-3">
            <button className="rounded-full border border-white/15 px-5 py-3 text-sm text-white" onClick={() => router.push("/")}>
              返回首页
            </button>
            <button className="rounded-full bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950" onClick={() => void handleCleanup()}>
              清理过期会话
            </button>
          </div>
        </div>

        {error ? <p className="mt-6 text-rose-200">{error}</p> : null}

        <div className="mt-8 grid gap-4">
          {sessions.length === 0 ? (
            <div className="glass-card text-slate-300">当前没有可展示的本地会话。</div>
          ) : (
            sessions.map((session) => (
              <div key={session.session_id} className="glass-card flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/70">{session.status}</p>
                  <h2 className="mt-2 text-2xl text-white">{session.narrative_label ?? "会话进行中"}</h2>
                  <p className="mt-3 text-sm text-slate-300">
                    已答 {session.question_count} 题
                    {session.cluster_name ? ` / ${session.cluster_name}` : ""}
                  </p>
                  <p className="mt-2 text-xs text-slate-400">更新时间 {new Date(session.updated_at).toLocaleString()}</p>
                </div>
                <div className="flex gap-3">
                  <button
                    className="rounded-full border border-white/15 px-5 py-3 text-sm text-white"
                    disabled={busySessionId === session.session_id}
                    onClick={() => void handleResume(session.session_id, "/session")}
                  >
                    {busySessionId === session.session_id ? "签发中..." : "继续答题"}
                  </button>
                  <button
                    className="rounded-full bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950"
                    disabled={busySessionId === session.session_id}
                    onClick={() => void handleResume(session.session_id, "/report")}
                  >
                    查看报告
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </section>
    </main>
  );
}
