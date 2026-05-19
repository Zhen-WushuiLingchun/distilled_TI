"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { SenrenDisabledNotice } from "@/components/SenrenDisabledNotice";
import { SENREN_ENABLED } from "@/lib/features";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/api";

type ValidationResult = {
  valid?: boolean;
  path?: string;
  found_files?: string[];
  missing_files?: string[];
  found_dirs?: string[];
  hint?: string;
};

export default function SenrenLandingPage() {
  const router = useRouter();
  const [gamePath, setGamePath] = useState("");
  const [validating, setValidating] = useState(false);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [launching, setLaunching] = useState(false);
  const [error, setError] = useState("");
  const [existingSession, setExistingSession] = useState<string | null>(null);

  useEffect(() => {
    const stored = localStorage.getItem("senren_game_path");
    if (stored) setGamePath(stored);
    const sid = sessionStorage.getItem("senren_session_id");
    const mode = sessionStorage.getItem("senren_mode");
    if (sid && mode === "local") {
      setExistingSession(sid);
    }
  }, []);

  if (!SENREN_ENABLED) {
    return <SenrenDisabledNotice />;
  }

  async function handleValidate() {
    if (!gamePath.trim()) return;
    setValidating(true);
    setError("");
    setValidation(null);
    try {
      const res = await fetch(`${API_BASE}/senren/local-game/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game_path: gamePath.trim() }),
      });
      const result: ValidationResult = await res.json();
      setValidation(result);
      if (result.valid) {
        localStorage.setItem("senren_game_path", gamePath.trim());
      }
    } catch {
      setError("验证请求失败，请检查后端服务是否已启动。");
    } finally {
      setValidating(false);
    }
  }

  async function handleLaunch() {
    if (!validation?.valid) return;
    setLaunching(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/senren/local-game/launch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game_path: gamePath.trim() }),
      });
      if (!res.ok) {
        const detail = (await res.json().catch(() => ({}))) as { detail?: string };
        throw new Error(detail.detail || "启动失败");
      }
      const data = await res.json();
      sessionStorage.setItem("senren_session_id", data.session_id);
      sessionStorage.setItem("senren_session_secret", data.session_secret);
      sessionStorage.setItem("senren_delete_token", data.delete_token);
      sessionStorage.setItem("senren_mode", "local");
      sessionStorage.setItem("senren_game_path", gamePath.trim());
      sessionStorage.setItem("senren_just_launched", "1");

      // 尝试将焦点转移给游戏窗口：打开微小窗口后立即关闭
      try {
        const mini = window.open("about:blank", "_blank", "width=1,height=1,left=-100,top=-100");
        if (mini) {
          setTimeout(() => mini.close(), 100);
        }
      } catch {
        // 忽略弹窗拦截
      }

      router.push("/senren/monitor");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "启动失败");
    } finally {
      setLaunching(false);
    }
  }

  return (
    <main className="flex min-h-[calc(100vh-3rem)] items-center justify-center px-4">
      <div className="w-full max-w-lg">
        <div className="text-center mb-8">
          <p className="text-xs tracking-[0.2em] text-[color:var(--ink-muted)] uppercase mb-2">
            Senren Banka · Personality Monitor
          </p>
          <h1 className="text-3xl font-semibold text-[color:var(--ink-strong)]">
            千恋＊万花 人格监视器
          </h1>
          <p className="mt-2 text-sm text-[color:var(--ink-muted)] leading-relaxed">
            输入游戏目录，一键启动，自动追踪选择。
          </p>
        </div>

        {existingSession && (
          <div className="surface-sunken p-4 rounded-[var(--r-md)] mb-4">
            <p className="text-sm text-[color:var(--ink-body)]">
              检测到未完成的监视会话
            </p>
            <button
              type="button"
              className="btn btn-primary mt-2 w-full"
              onClick={() => router.push("/senren/monitor")}
            >
              继续上次监视
            </button>
          </div>
        )}

        <div className="surface-sunken p-5 rounded-[var(--r-lg)] space-y-4">
          <label className="block">
            <span className="label-mini mb-2 block">千恋万花游戏目录</span>
            <div className="flex gap-2">
              <input
                className="field flex-1"
                value={gamePath}
                onChange={(e) => {
                  setGamePath(e.target.value);
                  setValidation(null);
                }}
                placeholder="例如: G:\trae galgame\SenrenBanka\千恋＊万花"
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !validation) void handleValidate();
                  if (e.key === "Enter" && validation?.valid) void handleLaunch();
                }}
              />
              <button
                type="button"
                className="btn btn-ghost"
                disabled={validating || !gamePath.trim()}
                onClick={() => void handleValidate()}
              >
                {validating ? "验证中…" : "验证"}
              </button>
            </div>
          </label>

          {validation && (
            <div
              className={`p-3 rounded-[var(--r-md)] text-sm ${
                validation.valid
                  ? "border border-[color:var(--accent-soft)] bg-[color:var(--accent-soft)]/20"
                  : "border border-[color:var(--danger-soft)] bg-[color:var(--danger-soft)]/15"
              }`}
            >
              {validation.valid ? (
                <div className="text-[color:var(--ink-body)]">
                  <p className="font-medium">目录验证通过</p>
                  {validation.found_files && (
                    <p className="mt-1 text-xs text-[color:var(--ink-muted)]">
                      找到: {validation.found_files.join(", ")}
                    </p>
                  )}
                </div>
              ) : (
                <div className="text-[color:var(--danger-ink)]">
                  <p>{validation.hint || "目录无效"}</p>
                </div>
              )}
            </div>
          )}

          {error && (
            <p className="text-xs text-[color:var(--danger-ink)]">{error}</p>
          )}

          <button
            type="button"
            className="btn btn-primary w-full"
            disabled={!validation?.valid || launching}
            onClick={() => void handleLaunch()}
          >
            {launching ? "启动中…" : "启动本地游戏"}
          </button>

          <p className="text-[0.7rem] text-[color:var(--ink-faint)] leading-relaxed">
            点击按钮后，千恋万花将直接启动。浏览器窗口会自动失焦，
            你可以直接切换到游戏窗口开始游玩。选择监视在后台自动运行。
          </p>
        </div>

        <div className="mt-6 text-center">
          <Link href="/" className="text-xs text-[color:var(--ink-faint)] hover:text-[color:var(--ink-body)] transition-colors">
            ← 返回首页
          </Link>
        </div>
      </div>
    </main>
  );
}
