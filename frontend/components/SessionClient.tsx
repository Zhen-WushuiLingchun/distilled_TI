"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  deleteSession,
  generateSessionReport,
  getSessionMap,
  getSessionSummary,
  startSession,
  submitAnswer,
  type Question,
  type SessionMap,
  type SessionReport,
  type SessionState,
} from "@/lib/api";
import {
  clearActiveSessionAccess,
  clearFinalReportSnapshot,
  getActiveSessionAccess,
  getReportViewPreferences,
  saveActiveSessionAccess,
  saveFinalReportSnapshot,
  type SessionAccessBundle,
} from "@/lib/runtime-store";

function formatPercent(value: number) {
  return `${value.toFixed(0)}%`;
}

function scoreToPercent(score: number) {
  return Math.max(0, Math.min(100, ((score + 3) / 6) * 100));
}

function optionSideLabel(questionType: string, score: number) {
  if (questionType === "contrast_5") {
    return score > 0 ? "偏向右侧" : score < 0 ? "偏向左侧" : "中间 / 看情况";
  }
  return score > 0 ? "趋向高侧" : score < 0 ? "趋向低侧" : "中性";
}

export function SessionClient() {
  const router = useRouter();
  const [access, setAccess] = useState<SessionAccessBundle | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [state, setState] = useState<SessionState | null>(null);
  const [remainingUntilReport, setRemainingUntilReport] = useState(20);
  const [canGenerateReport, setCanGenerateReport] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const questionStartRef = useRef<number>(Date.now());

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        setBusy(true);
        const storedAccess = getActiveSessionAccess();
        if (storedAccess) {
          const summary = await getSessionSummary(storedAccess);
          if (cancelled) return;
          setAccess(storedAccess);
          setState(summary.state);
          setQuestion(summary.current_question ?? null);
          setCanGenerateReport(summary.can_generate_report);
          setRemainingUntilReport(summary.remaining_until_report);
          setError("");
        } else {
          clearFinalReportSnapshot();
          const started = await startSession();
          if (cancelled) return;
          const nextAccess: SessionAccessBundle = {
            session_id: started.session_id,
            session_secret: started.session_secret,
            delete_token: started.delete_token,
          };
          saveActiveSessionAccess(nextAccess);
          setAccess(nextAccess);
          setState(started.state);
          setQuestion(started.question);
          setCanGenerateReport(false);
          setRemainingUntilReport(started.min_questions_for_report);
          setError("");
        }
        questionStartRef.current = performance.now();
      } catch (reason) {
        if (cancelled) return;
        clearActiveSessionAccess();
        setAccess(null);
        setQuestion(null);
        setState(null);
        setError(reason instanceof Error ? reason.message : "会话初始化失败。");
      } finally {
        if (!cancelled) {
          setBusy(false);
        }
      }
    }

    void bootstrap();

    return () => {
      cancelled = true;
    };
  }, []);

  const topSignals = useMemo(() => {
    if (!state) return [];
    return Object.entries(state.core_mu)
      .sort((left, right) => Math.abs(right[1]) - Math.abs(left[1]))
      .slice(0, 5);
  }, [state]);

  async function handleAnswer(optionKey: string) {
    if (!question || !access) return;

    try {
      setBusy(true);
      const latency = Math.round(performance.now() - questionStartRef.current);
      const response = await submitAnswer(access, question.id, optionKey, latency);
      saveActiveSessionAccess(access);
      setState(response.state);
      setQuestion(response.next_question);
      setCanGenerateReport(response.can_generate_report);
      setRemainingUntilReport(response.remaining_until_report);
      questionStartRef.current = performance.now();
      setError("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "提交答案失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!access) return;
    try {
      setBusy(true);
      await deleteSession(access);
      clearActiveSessionAccess();
      clearFinalReportSnapshot();
      router.push("/");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "清理会话失败。");
    } finally {
      setBusy(false);
    }
  }

  async function handleFinalizeReport() {
    if (!access || !canGenerateReport) return;
    try {
      setBusy(true);
      const preferences = getReportViewPreferences();
      const [report, map]: [SessionReport, SessionMap] = await Promise.all([
        generateSessionReport(access, preferences.namingStyle),
        getSessionMap(access, preferences.projectionMode),
      ]);
      saveFinalReportSnapshot({
        mode: "finalized",
        sessionId: access.session_id,
        report,
        map,
      });
      router.push("/report");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "生成最终报告失败。");
    } finally {
      setBusy(false);
    }
  }

  if (busy && !question) {
    return <main className="session-shell">正在构建本次测试会话...</main>;
  }

  return (
    <main className="session-shell">
      <section className="grid gap-8 xl:grid-cols-[0.9fr_1.1fr]">
        <aside className="rounded-[2rem] border border-white/10 bg-white/6 p-6 backdrop-blur-xl">
          <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/70">Session</p>
          <h1 className="mt-3 text-3xl text-white">连续作答中</h1>
          <p className="mt-4 text-sm leading-6 text-slate-300">
            你可以一路答下去，也可以在达到 20 题后先拿一份报告，再回来继续细化。
          </p>

          <div className="mt-8 grid grid-cols-2 gap-4">
            <div className="glass-card">
              <p className="label-mini">已答题数</p>
              <p className="metric-big">{state?.question_count ?? 0}</p>
            </div>
            <div className="glass-card">
              <p className="label-mini">距报告</p>
              <p className="metric-big">{remainingUntilReport}</p>
            </div>
            <div className="glass-card">
              <p className="label-mini">已解锁 Sub</p>
              <p className="metric-big">{state?.unlocked_subdimensions.length ?? 0}</p>
            </div>
            <div className="glass-card">
              <p className="label-mini">活跃 Module</p>
              <p className="metric-big">{state?.active_modules.length ?? 0}</p>
            </div>
          </div>

          <div className="mt-8 rounded-[1.5rem] border border-white/10 bg-black/20 p-5">
            <p className="label-mini">Core Signal Preview</p>
            <div className="mt-4 space-y-4">
              {topSignals.map(([label, score]) => (
                <div key={label}>
                  <div className="mb-2 flex items-center justify-between text-sm text-slate-200">
                    <span>{label}</span>
                    <span className="text-cyan-200">{formatPercent(scoreToPercent(score))}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-white/8">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-indigo-300 via-cyan-300 to-emerald-300"
                      style={{ width: `${scoreToPercent(score)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-8 flex flex-wrap gap-3">
            <button
              type="button"
              className="rounded-full border border-white/15 bg-white/6 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
              onClick={() => void handleFinalizeReport()}
              disabled={!canGenerateReport}
            >
              {canGenerateReport ? "查看最终报告" : `还需 ${remainingUntilReport} 题`}
            </button>
            <button
              type="button"
              className="rounded-full border border-rose-300/20 bg-rose-300/10 px-5 py-3 text-sm font-semibold text-rose-100 transition hover:bg-rose-300/20"
              onClick={() => void handleDelete()}
            >
              放弃并删除本次会话
            </button>
          </div>
          {error ? <p className="mt-4 text-sm text-rose-200">{error}</p> : null}
        </aside>

        <section className="rounded-[2rem] border border-white/10 bg-black/30 p-6 backdrop-blur-2xl">
          {question ? (
            <>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.35em] text-cyan-200/70">
                    {question.layer} / {question.scenario_tags.join(" / ")}
                  </p>
                  <p className="mt-2 text-xs uppercase tracking-[0.28em] text-slate-400">
                    {question.generation_mode === "llm_rewrite"
                      ? "AI Rewrite"
                      : question.generation_mode === "probe"
                        ? "AI Probe"
                        : question.generation_mode === "anchor"
                          ? "Anchor"
                          : "Template"}
                  </p>
                  <h2 className="mt-4 max-w-3xl text-3xl leading-tight text-white md:text-4xl">{question.prompt}</h2>
                </div>
                <div className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs uppercase tracking-[0.3em] text-slate-300">
                  Q {state ? state.question_count + 1 : 1}
                </div>
              </div>

              <div className="mt-8 grid gap-4">
                {question.options.map((option) => (
                  <button
                    key={option.key}
                    type="button"
                    className="group rounded-[1.6rem] border border-white/10 bg-white/[0.04] p-5 text-left transition hover:-translate-y-0.5 hover:border-cyan-300/35 hover:bg-white/[0.08]"
                    onClick={() => void handleAnswer(option.key)}
                    disabled={busy}
                  >
                    <span className="text-sm uppercase tracking-[0.25em] text-cyan-200/55">
                      {optionSideLabel(question.question_type, option.score)}
                    </span>
                    <p className="mt-3 text-lg leading-8 text-white">{option.text}</p>
                  </button>
                ))}
              </div>
            </>
          ) : (
            <div className="flex min-h-[420px] flex-col items-center justify-center text-center">
              <p className="text-sm uppercase tracking-[0.35em] text-cyan-200/70">Session Complete</p>
              <h2 className="mt-4 text-4xl text-white">当前这一轮已经没有待答题目</h2>
              <p className="mt-4 max-w-xl text-slate-300">
                你可以直接查看报告，也可以结束并删除这次会话。
              </p>
              <div className="mt-8 flex gap-4">
                <button
                  type="button"
                  className="rounded-full bg-cyan-300 px-6 py-3 text-sm font-semibold text-slate-950"
                  onClick={() => void handleFinalizeReport()}
                >
                  查看最终报告
                </button>
                <button
                  type="button"
                  className="rounded-full border border-white/15 px-6 py-3 text-sm font-semibold text-white"
                  onClick={() => void handleDelete()}
                >
                  删除会话
                </button>
              </div>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
