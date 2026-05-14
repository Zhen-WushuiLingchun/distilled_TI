"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/api";

export default function SenrenLandingPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function startSession(mode: "monitor" | "story") {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/senren/monitor/start?mode=${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error((detail as any).detail || `Server error ${res.status}`);
      }
      const data = await res.json();

      // Store credentials in sessionStorage for the monitor page
      sessionStorage.setItem("senren_session_id", data.session_id);
      sessionStorage.setItem("senren_session_secret", data.session_secret);
      sessionStorage.setItem("senren_delete_token", data.delete_token);
      sessionStorage.setItem("senren_mode", mode);

      router.push("/senren/monitor");
    } catch (err: any) {
      setError(err.message || "启动失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-[calc(100vh-41px)] flex flex-col items-center justify-center px-4 py-12">
      {/* 标题区域 */}
      <div className="text-center max-w-2xl fade-rise">
        <p className="senren-subtitle mb-3 tracking-[0.15em]">SENREN * BANKA</p>
        <h1 className="senren-title text-4xl md:text-5xl font-semibold mb-4">
          千恋＊万花
        </h1>
        <p className="senren-subtitle text-lg mb-2">人格监视器</p>
        <p className="text-[var(--senren-ink-muted)] text-sm mt-6 leading-relaxed max-w-md mx-auto">
          在穗织镇的羁绊中，每一个选择都在刻画出你独特的人格轮廓。
          <br />
          追踪你的游戏选择，实时映射深层行为倾向。
        </p>
      </div>

      {/* 模式选择 */}
      <div className="mt-10 grid gap-4 w-full max-w-lg fade-rise" style={{ animationDelay: "150ms" }}>
        <button
          onClick={() => startSession("monitor")}
          disabled={loading}
          className="senren-choice-btn text-left group"
        >
          <div className="flex items-start gap-3">
            <span className="senren-pulse mt-0.5 shrink-0" />
            <div>
              <p className="text-[var(--senren-ink-strong)] font-medium mb-1">
                实时监视模式
              </p>
              <p className="text-xs text-[var(--senren-ink-muted)] leading-relaxed">
                一边游玩千恋万花，一边在监视器上记录你的选择。
                系统会实时更新你的人格画像和角色契合度。
              </p>
            </div>
          </div>
        </button>

        <button
          onClick={() => startSession("story")}
          disabled={loading}
          className="senren-choice-btn text-left"
        >
          <div className="flex items-start gap-3">
            <span className="w-2 h-2 rounded-full bg-[var(--senren-gold)] mt-0.5 shrink-0" />
            <div>
              <p className="text-[var(--senren-ink-strong)] font-medium mb-1">
                独立故事模式
              </p>
              <p className="text-xs text-[var(--senren-ink-muted)] leading-relaxed">
                以视觉小说风格依次呈现游戏中的关键选择场景。
                无需运行游戏，即可完成人格测试。
              </p>
            </div>
          </div>
        </button>
      </div>

      {/* 加载/错误 */}
      {loading && (
        <p className="mt-6 text-sm text-[var(--senren-ink-muted)] animate-pulse">
          正在启动监视器...
        </p>
      )}
      {error && (
        <p className="mt-6 text-sm text-[var(--senren-sakura)]">{error}</p>
      )}

      {/* 底部提示 */}
      <p className="mt-16 text-xs text-[var(--senren-ink-dim)] text-center max-w-sm leading-relaxed">
        本工具为娱乐性人格映射系统，不构成心理学诊断。
        <br />
        千恋＊万花 © YUZUSOFT
      </p>
    </main>
  );
}
