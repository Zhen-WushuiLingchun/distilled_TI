"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/api";

type ApiErrorPayload = {
  detail?: string;
};

export default function SenrenLandingPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // 本地游戏模式状态
  const [showLocalModal, setShowLocalModal] = useState(false);
  const [gamePath, setGamePath] = useState("");
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<{
    valid?: boolean;
    found_files?: string[];
    missing_files?: string[];
    hint?: string;
  } | null>(null);

  async function startSession(mode: "monitor" | "story") {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/senren/monitor/start?mode=${mode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!res.ok) {
        const detail = (await res.json().catch(() => ({}))) as ApiErrorPayload;
        throw new Error(detail.detail || `Server error ${res.status}`);
      }
      const data = await res.json();

      sessionStorage.setItem("senren_session_id", data.session_id);
      sessionStorage.setItem("senren_session_secret", data.session_secret);
      sessionStorage.setItem("senren_delete_token", data.delete_token);
      sessionStorage.setItem("senren_mode", mode);

      router.push("/senren/monitor");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "启动失败");
    } finally {
      setLoading(false);
    }
  }

  async function validateGamePath() {
    if (!gamePath.trim()) return;
    setValidating(true);
    setValidationResult(null);
    try {
      const res = await fetch(`${API_BASE}/senren/local-game/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game_path: gamePath.trim() }),
      });
      const data = await res.json();
      setValidationResult(data);
    } catch {
      setValidationResult({ valid: false, hint: "验证请求失败，请检查后端服务" });
    } finally {
      setValidating(false);
    }
  }

  async function startLocalGame() {
    if (!validationResult?.valid) return;
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/senren/local-game/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game_path: gamePath.trim(), mode: "local" }),
      });
      if (!res.ok) {
        const detail = await res.json().catch(() => ({}));
        throw new Error((detail as any).detail || `Server error ${res.status}`);
      }
      const data = await res.json();

      sessionStorage.setItem("senren_session_id", data.session_id);
      sessionStorage.setItem("senren_session_secret", data.session_secret);
      sessionStorage.setItem("senren_delete_token", data.delete_token);
      sessionStorage.setItem("senren_mode", "local");
      sessionStorage.setItem("senren_game_path", gamePath.trim());

      setShowLocalModal(false);
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
        {/* 实时监视模式 */}
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

        {/* 独立故事模式 */}
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
                无需运行游戏，即可完成人格测试。角色将以 skills 人设驱动对话。
              </p>
            </div>
          </div>
        </button>

        {/* 本地游戏模式 */}
        <button
          onClick={() => {
            setShowLocalModal(true);
            setValidationResult(null);
            setGamePath("");
            setError("");
          }}
          disabled={loading}
          className="senren-choice-btn text-left border-[var(--senren-indigo)]/50 hover:border-[var(--senren-indigo)]"
        >
          <div className="flex items-start gap-3">
            <span className="w-2 h-2 rounded-full bg-[var(--senren-indigo)] mt-0.5 shrink-0" />
            <div>
              <p className="text-[var(--senren-ink-strong)] font-medium mb-1">
                本地游戏模式
                <span className="ml-2 text-[10px] text-[var(--senren-gold)] border border-[var(--senren-gold)]/30 rounded px-1.5 py-0.5">
                  新
                </span>
              </p>
              <p className="text-xs text-[var(--senren-ink-muted)] leading-relaxed">
                指定你电脑上的千恋万花安装目录，系统自动验证游戏完整性，
                并在你游玩时实时追踪人格变化。
              </p>
            </div>
          </div>
        </button>
      </div>

      {/* 本地游戏路径弹窗 */}
      {showLocalModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="senren-dialogue-box max-w-md w-full mx-4 fade-rise">
            <p className="senren-character-name mb-3">指定千恋万花安装目录</p>
            <p className="text-xs text-[var(--senren-ink-muted)] mb-4 leading-relaxed">
              请输入你电脑上安装千恋万花的目录路径。系统会检查关键游戏文件（scenario.pck、Script.pck
              等）以确认目录有效。
            </p>

            <div className="flex gap-2 mb-3">
              <input
                type="text"
                value={gamePath}
                onChange={(e) => setGamePath(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && validateGamePath()}
                placeholder="例如: D:\Games\千恋＊万花"
                className="flex-1 bg-[var(--senren-bg-deep)] border border-[var(--senren-line-mid)] rounded px-3 py-2 text-sm text-[var(--senren-ink-body)] placeholder:text-[var(--senren-ink-dim)] focus:outline-none focus:border-[var(--senren-gold)]"
                autoFocus
              />
              <button
                onClick={validateGamePath}
                disabled={validating || !gamePath.trim()}
                className="px-4 py-2 text-xs font-medium rounded bg-[var(--senren-indigo)]/20 text-[var(--senren-indigo)] border border-[var(--senren-indigo)]/30 hover:bg-[var(--senren-indigo)]/30 disabled:opacity-40 transition-colors"
              >
                {validating ? "检查中..." : "验证"}
              </button>
            </div>

            {/* 验证结果 */}
            {validationResult && (
              <div
                className={`p-3 rounded text-xs mb-3 ${
                  validationResult.valid
                    ? "bg-[var(--senren-jade)]/10 border border-[var(--senren-jade)]/30 text-[var(--senren-jade)]"
                    : "bg-[var(--senren-sakura)]/10 border border-[var(--senren-sakura)]/30 text-[var(--senren-sakura)]"
                }`}
              >
                {validationResult.valid ? (
                  <>
                    <p className="font-medium mb-1">✓ 目录有效</p>
                    <p className="opacity-80">
                      找到: {validationResult.found_files?.join(", ") || "无"}
                    </p>
                  </>
                ) : (
                  <>
                    <p className="font-medium mb-1">✗ {validationResult.hint}</p>
                    {validationResult.missing_files && validationResult.missing_files.length > 0 && (
                      <p className="opacity-80 mt-1">
                        缺失文件: {validationResult.missing_files.join(", ")}
                      </p>
                    )}
                  </>
                )}
              </div>
            )}

            <div className="flex gap-2 justify-end">
              <button
                onClick={() => setShowLocalModal(false)}
                className="px-4 py-2 text-xs rounded border border-[var(--senren-line-mid)] text-[var(--senren-ink-muted)] hover:text-[var(--senren-ink-body)] transition-colors"
              >
                取消
              </button>
              <button
                onClick={startLocalGame}
                disabled={!validationResult?.valid || loading}
                className="px-6 py-2 text-xs font-medium rounded bg-[var(--senren-sakura)]/20 text-[var(--senren-sakura)] border border-[var(--senren-sakura)]/30 hover:bg-[var(--senren-sakura)]/30 disabled:opacity-40 transition-colors"
              >
                {loading ? "启动中..." : "开始监视"}
              </button>
            </div>
          </div>
        </div>
      )}

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
