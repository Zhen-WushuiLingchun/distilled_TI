"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/api";

interface SessionEntry {
  session_id: string;
  mode: string;
  current_route: string | null;
  choices_count: number;
  created_at: string;
  updated_at: string;
}

export default function SenrenHistoryPage() {
  const router = useRouter();
  const [sessions, setSessions] = useState<SessionEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetchSessions();
  }, []);

  async function fetchSessions() {
    try {
      const res = await fetch(`${API_BASE}/senren/sessions`);
      if (!res.ok) throw new Error("无法获取会话列表");
      const data = await res.json();
      setSessions(data.sessions || []);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function resumeSession(sessionId: string) {
    // Try to recover stored credentials
    const storedSid = sessionStorage.getItem("senren_session_id");
    if (storedSid === sessionId) {
      router.push("/senren/monitor");
      return;
    }
    setError("此会话的凭证未在本地存储。当前版本仅支持当前浏览器会话中的监视会话恢复。");
  }

  if (loading) {
    return (
      <div className="min-h-[calc(100vh-41px)] flex items-center justify-center">
        <p className="text-[var(--senren-ink-muted)] animate-pulse">加载历史记录...</p>
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-41px)] px-4 py-8 max-w-2xl mx-auto">
      <div className="mb-8">
        <h1 className="senren-title text-2xl mb-2">监视历史</h1>
        <p className="text-xs text-[var(--senren-ink-muted)]">
          最近的千恋万花人格监视会话
        </p>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded bg-[var(--danger-soft)] text-[var(--danger-ink)] text-sm">
          {error}
        </div>
      )}

      {sessions.length === 0 ? (
        <div className="senren-dashboard-panel text-center py-16">
          <p className="text-[var(--senren-ink-muted)] text-sm mb-4">
            暂无监视记录
          </p>
          <a
            href="/senren"
            className="senren-choice-btn inline-block text-center"
          >
            开始新的监视会话
          </a>
        </div>
      ) : (
        <div className="space-y-3">
          {sessions.map((session) => (
            <div
              key={session.session_id}
              className="senren-dashboard-panel flex items-center justify-between cursor-pointer hover:border-[var(--senren-line-gold)] transition-colors"
              onClick={() => resumeSession(session.session_id)}
            >
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-mono text-[var(--senren-gold)]">
                    {session.session_id}
                  </span>
                  <span className="text-xs px-1.5 py-0.5 rounded bg-[var(--senren-sakura-soft)] text-[var(--senren-sakura)]">
                    {session.mode === "monitor" ? "监视模式" : "故事模式"}
                  </span>
                </div>
                <p className="text-xs text-[var(--senren-ink-muted)]">
                  {session.choices_count} 次选择
                  {session.current_route && ` · ${session.current_route}`}
                  {` · ${new Date(session.updated_at).toLocaleString("zh-CN")}`}
                </p>
              </div>
              <span className="text-xs text-[var(--senren-ink-dim)]">→</span>
            </div>
          ))}

          {sessions.length > 0 && (
            <div className="text-center mt-6">
              <a
                href="/senren"
                className="text-xs text-[var(--senren-gold)] hover:underline"
              >
                + 开始新会话
              </a>
            </div>
          )}
        </div>
      )}

      <div className="mt-12 text-center">
        <a
          href="/senren/monitor"
          className="text-xs text-[var(--senren-ink-dim)] hover:text-[var(--senren-ink-muted)] transition-colors"
        >
          ← 返回仪表盘
        </a>
      </div>
    </div>
  );
}
