"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  generateSessionReport,
  getGalgameScene,
  getSessionMap,
  respondGalgameScene,
  startSession,
  type GalgameScene,
  type SessionState,
} from "@/lib/api";
import {
  clearFinalReportSnapshot,
  getActiveSessionAccess,
  getReportViewPreferences,
  getUserAccess,
  saveActiveSessionAccess,
  saveFinalReportSnapshot,
  type SessionAccessBundle,
} from "@/lib/runtime-store";

function formatSigned(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}

function moodLabel(mood: string) {
  if (mood === "追问") return "Probe";
  if (mood === "低电量") return "Low Battery";
  if (mood === "分岔") return "Branch";
  if (mood === "校准") return "Calibration";
  return "Opening";
}

export function StoryClient() {
  const router = useRouter();
  const [access, setAccess] = useState<SessionAccessBundle | null>(null);
  const [scene, setScene] = useState<GalgameScene | null>(null);
  const [state, setState] = useState<SessionState | null>(null);
  const [customText, setCustomText] = useState("");
  const [selectedOptionKey, setSelectedOptionKey] = useState("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [remainingUntilReport, setRemainingUntilReport] = useState(20);
  const [canGenerateReport, setCanGenerateReport] = useState(false);
  const startedAtRef = useRef<number>(Date.now());

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        setBusy(true);
        let currentAccess = getActiveSessionAccess();
        if (!currentAccess) {
          clearFinalReportSnapshot();
          const started = await startSession(getUserAccess());
          currentAccess = {
            session_id: started.session_id,
            session_secret: started.session_secret,
            delete_token: started.delete_token,
          };
          saveActiveSessionAccess(currentAccess);
          setState(started.state);
          setRemainingUntilReport(started.min_questions_for_report);
        }
        const nextScene = await getGalgameScene(currentAccess);
        if (cancelled) return;
        setAccess(currentAccess);
        setScene(nextScene);
        setSelectedOptionKey(nextScene.choices.find((choice) => choice.tone === "ambivalent")?.option_key ?? nextScene.choices[0]?.option_key ?? "");
        startedAtRef.current = performance.now();
        setError("");
      } catch (reason) {
        if (!cancelled) setError(reason instanceof Error ? reason.message : "剧情模式初始化失败。");
      } finally {
        if (!cancelled) setBusy(false);
      }
    }

    void bootstrap();

    return () => {
      cancelled = true;
    };
  }, []);

  async function handleChoice(optionKey: string, textOverride?: string) {
    if (!access || !scene) return;
    try {
      setBusy(true);
      const latencyMs = Math.round(performance.now() - startedAtRef.current);
      const response = await respondGalgameScene(access, {
        item_id: scene.item_id,
        scene_id: scene.scene_id,
        option_key: optionKey,
        custom_text: textOverride?.trim() || undefined,
        latency_ms: latencyMs,
      });
      setState(response.state);
      setScene(response.scene);
      setRemainingUntilReport(response.remaining_until_report);
      setCanGenerateReport(response.can_generate_report);
      setCustomText("");
      setSelectedOptionKey(response.scene?.choices.find((choice) => choice.tone === "ambivalent")?.option_key ?? response.scene?.choices[0]?.option_key ?? "");
      startedAtRef.current = performance.now();
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "提交剧情选择失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleReport() {
    if (!access || !canGenerateReport) return;
    try {
      setBusy(true);
      const preferences = getReportViewPreferences();
      const [report, map] = await Promise.all([
        generateSessionReport(access, preferences.namingStyle),
        getSessionMap(access, preferences.projectionMode),
      ]);
      saveFinalReportSnapshot({ access, report, map });
      router.push("/report");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "生成报告失败。");
    } finally {
      setBusy(false);
    }
  }

  if (busy && !scene) {
    return (
      <main className="story-shell">
        <section className="story-stage mx-auto flex min-h-[72vh] max-w-5xl items-center justify-center p-8 text-center">
          <div>
            <p className="eyebrow">Distilled TI / Story Mode</p>
            <h1 className="mt-4 text-4xl">正在生成第一幕</h1>
            <p className="mt-3 text-[color:var(--ink-muted)]">系统会把测量题转换成校园情景选择。</p>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="story-shell">
      <section className="relative z-10 mx-auto grid min-h-[calc(100vh-3rem)] max-w-[1440px] gap-5 p-4 lg:grid-cols-[1fr_360px]">
        <div className="story-stage fade-rise flex flex-col overflow-hidden">
          <div className="story-sky">
            <div className="story-character" aria-hidden>
              <div className="story-character-face" />
            </div>
            <div className="absolute left-5 top-5 flex flex-wrap gap-2">
              <span className="chip chip-accent">{scene?.location ?? "Unknown"}</span>
              <span className="chip">{scene ? moodLabel(scene.mood) : "Loading"}</span>
              <span className="chip">Q{(state?.question_count ?? 0) + 1}</span>
            </div>
          </div>

          <div className="story-dialogue mt-auto">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="label-mini">{scene?.title ?? "Story Mode"}</p>
                <h1 className="mt-1 text-2xl md:text-3xl">{scene?.speaker ?? "同桌"}</h1>
              </div>
              <button className="btn btn-ghost px-3 py-1.5 text-xs" onClick={() => router.push("/session")}>
                切回工作台
              </button>
            </div>
            <p className="text-[0.92rem] leading-7 text-[color:var(--ink-muted)]">{scene?.narrator_text}</p>
            <p className="mt-3 text-[1.15rem] leading-8 text-[color:var(--ink-strong)]">{scene?.character_text}</p>
          </div>
        </div>

        <aside className="space-y-4">
          <div className="panel fade-rise p-5">
            <p className="label-mini">Choices</p>
            <h2 className="mt-1.5 text-2xl">你会怎么做</h2>
            <div className="mt-4 space-y-2.5">
              {scene?.choices.map((choice) => (
                <button
                  key={choice.key}
                  className={`story-choice ${choice.tone}`}
                  disabled={busy}
                  onClick={() => void handleChoice(choice.option_key)}
                >
                  <span>{choice.text}</span>
                  <span className="num">{formatSigned(choice.score)}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="panel fade-rise p-5">
            <p className="label-mini">Free Line</p>
            <h2 className="mt-1.5 text-xl">自己写一句台词</h2>
            <textarea
              className="field mt-3 min-h-28"
              value={customText}
              onChange={(event) => setCustomText(event.target.value)}
              placeholder="例如：我先不表态，但会把所有人的真实顾虑问出来。"
            />
            <select className="field mt-2.5" value={selectedOptionKey} onChange={(event) => setSelectedOptionKey(event.target.value)}>
              {scene?.choices.map((choice) => (
                <option key={choice.key} value={choice.option_key}>
                  {choice.text}
                </option>
              ))}
            </select>
            <button
              className="btn btn-primary mt-3 w-full"
              disabled={busy || !selectedOptionKey}
              onClick={() => void handleChoice(selectedOptionKey, customText)}
            >
              以这句台词推进
            </button>
          </div>

          <div className="panel fade-rise p-5">
            <p className="label-mini">Context</p>
            <h2 className="mt-1.5 text-xl">剧情记忆</h2>
            {scene?.memory_fragments.length ? (
              <div className="mt-3 space-y-2">
                {scene.memory_fragments.map((fragment, index) => (
                  <p key={`${fragment}-${index}`} className="surface-sunken p-3 text-xs leading-5 text-[color:var(--ink-muted)]">
                    {fragment}
                  </p>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-sm text-[color:var(--ink-muted)]">第一幕还没有留下长期上下文。</p>
            )}
            <div className="hairline my-4" />
            <p className="num text-sm text-[color:var(--ink-muted)]">
              已答 {state?.question_count ?? 0} · 报告还差 {remainingUntilReport}
            </p>
            <button className="btn btn-success-soft mt-3 w-full" disabled={!canGenerateReport || busy} onClick={() => void handleReport()}>
              {canGenerateReport ? "生成报告" : "报告未解锁"}
            </button>
          </div>

          {error ? (
            <div className="panel border-[color:var(--danger)]/30 bg-[color:var(--danger-soft)] p-4 text-sm text-[color:var(--danger-ink)]">
              {error}
            </div>
          ) : null}
        </aside>
      </section>
    </main>
  );
}
