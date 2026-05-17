"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { SenrenLocalSetupModal } from "@/components/senren-vn/SenrenLocalSetupModal";
import { SenrenTitleScreen } from "@/components/senren-vn/SenrenTitleScreen";
import type { ApiErrorPayload, PersonaOverview, SenrenMode, ValidationResult } from "@/components/senren-vn/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/api";

export default function SenrenLandingPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showLocalSetup, setShowLocalSetup] = useState(false);
  const [showCredits, setShowCredits] = useState(false);
  const [gamePath, setGamePath] = useState("");
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [personaOverview, setPersonaOverview] = useState<PersonaOverview | null>(null);

  useEffect(() => {
    void fetchPersonaOverview();
  }, []);

  async function fetchPersonaOverview() {
    try {
      const res = await fetch(`${API_BASE}/senren/skills/personas`);
      if (res.ok) setPersonaOverview(await res.json());
    } catch {
      // Landing remains usable without the overview.
    }
  }

  async function startSession(mode: Extract<SenrenMode, "monitor" | "story">) {
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
      sessionStorage.removeItem("senren_game_path");

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
    setError("");
    try {
      const res = await fetch(`${API_BASE}/senren/local-game/validate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ game_path: gamePath.trim() }),
      });
      setValidationResult(await res.json());
    } catch {
      setValidationResult({ valid: false, hint: "验证请求失败，请检查后端服务。" });
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
        const detail = (await res.json().catch(() => ({}))) as ApiErrorPayload;
        throw new Error(detail.detail || `Server error ${res.status}`);
      }
      const data = await res.json();

      sessionStorage.setItem("senren_session_id", data.session_id);
      sessionStorage.setItem("senren_session_secret", data.session_secret);
      sessionStorage.setItem("senren_delete_token", data.delete_token);
      sessionStorage.setItem("senren_mode", "local");
      sessionStorage.setItem("senren_game_path", gamePath.trim());

      router.push("/senren/monitor");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "启动失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="senren-title-stage">
      <SenrenTitleScreen
        loading={loading}
        error={error}
        personaOverview={personaOverview}
        onStartMode={startSession}
        onOpenLocalSetup={() => setShowLocalSetup(true)}
        onOpenCredits={() => setShowCredits(true)}
      />

      {showLocalSetup && (
        <SenrenLocalSetupModal
          gamePath={gamePath}
          validationResult={validationResult}
          personaOverview={personaOverview}
          validating={validating}
          loading={loading}
          onGamePathChange={setGamePath}
          onValidate={validateGamePath}
          onStartLocalGame={startLocalGame}
          onClose={() => setShowLocalSetup(false)}
        />
      )}

      {showCredits && <RuntimeNotesModal onClose={() => setShowCredits(false)} />}
    </main>
  );
}

function RuntimeNotesModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="senren-title-modal-backdrop" onClick={onClose}>
      <div className="senren-title-modal is-compact" onClick={(event) => event.stopPropagation()}>
        <header>
          <div>
            <span>Runtime Notes</span>
            <h2>当前实现边界</h2>
          </div>
          <button onClick={onClose}>Close</button>
        </header>
        <div className="senren-title-notes">
          <article>
            <strong>结构</strong>
            <p>
              按 Paper2Gal 的 Title / Setup / Game screen 拆分，但没有复制其源码；当前仓库只保留等价架构和交互模型。
            </p>
          </article>
          <article>
            <strong>内容</strong>
            <p>使用 Senren choice tree、9 个角色 skills、已生成 SD/本地资产，并通过 DeepSeek-compatible provider 做场景润色。</p>
          </article>
          <article>
            <strong>测量 API</strong>
            <p>VN 层只负责展示和提交选择；心理测量、embedding、聚类与报告分析都通过容器回调/后端接口接入。</p>
          </article>
          <article>
            <strong>当前限制</strong>
            <p>本地游戏目录只用于合法性/存在性校验；目前不 hook 原游戏进程、不读取原游戏存档、不修改原游戏文件。</p>
          </article>
        </div>
      </div>
    </div>
  );
}
