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
  type WorkbenchCheckpoint,
  type WorkbenchMilestone,
  type WorkbenchSignal,
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

const CORE_LABELS: Record<string, string> = {
  social_initiative: "社交主动性",
  social_stimulation_tolerance: "社交刺激耐受",
  autonomous_judgment: "自主决断倾向",
  planning_preference: "规划结构偏好",
  risk_tolerance: "风险容忍度",
  abstraction_tendency: "抽象化倾向",
  novelty_seeking: "新奇寻求",
  competition_cooperation: "竞争合作取向",
  emotional_stability: "情绪稳定性",
  execution_drive: "推进执行力",
};

const SUBDIMENSION_LABELS: Record<string, string> = {
  entry_speed: "进入速度",
  familiar_expression_intensity: "熟人表达强度",
  conflict_speaking_threshold: "冲突开口阈值",
  low_info_decision_speed: "低信息决断速度",
  authority_dependence: "权威依赖度",
  ambiguity_tolerance: "模糊容忍度",
  start_speed: "启动速度",
  switching_tendency: "中途切换倾向",
  closure_strength: "收尾能力",
  academic_utility_scope: "学科效用边界",
  theory_application_balance: "理论-应用平衡",
  canon_reliance: "经典依附度",
  aesthetic_density: "审美密度偏好",
};

const MODULE_LABELS: Record<string, string> = {
  study_style: "学习协作风格",
  project_role: "项目组人格",
  conflict_mode: "冲突处理风格",
  chat_mode: "网聊人格",
  creative_mode: "创作人格",
  team_mode: "队友人格",
};

const MILESTONES = [5, 10, 20, 40];

function clamp(value: number, min = 0, max = 100) {
  return Math.max(min, Math.min(max, value));
}

function formatKey(key: string) {
  return key
    .split("_")
    .filter(Boolean)
    .map((part) => part.slice(0, 1).toUpperCase() + part.slice(1))
    .join(" ");
}

function coreLabel(key: string) {
  return CORE_LABELS[key] ?? formatKey(key);
}

function subdimensionLabel(key: string) {
  return SUBDIMENSION_LABELS[key] ?? formatKey(key);
}

function moduleLabel(key: string) {
  return MODULE_LABELS[key] ?? formatKey(key);
}

function formatPercent(value: number) {
  return `${value.toFixed(0)}%`;
}

function formatSigned(value: number) {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}

function formatLatency(value: number | null) {
  if (value === null) return "未记录";
  if (value < 1000) return `${value}ms`;
  return `${(value / 1000).toFixed(1)}s`;
}

function scoreToPercent(score: number) {
  return clamp(((score + 3) / 6) * 100);
}

function sigmaToConfidence(sigma: number) {
  return clamp((1 - sigma / 1.5) * 100);
}

function optionSideLabel(questionType: string, score: number) {
  if (questionType === "contrast_5") {
    return score > 0 ? "偏向右侧" : score < 0 ? "偏向左侧" : "中间 / 看情况";
  }
  return score > 0 ? "趋向高侧" : score < 0 ? "趋向低侧" : "中性";
}

function generationLabel(mode?: string) {
  if (mode === "llm_rewrite") return "AI Rewrite";
  if (mode === "probe") return "AI Probe";
  if (mode === "anchor") return "Anchor";
  return "Template";
}

function layerLabel(layer?: string) {
  if (layer === "probe") return "追问校准";
  if (layer === "subdimension") return "子维度细化";
  if (layer === "module") return "场景模块";
  if (layer === "anchor") return "锚题复核";
  return "核心维度";
}

function answerQualityLabel(residual: number) {
  const abs = Math.abs(residual);
  if (abs < 0.35) return "贴近预测";
  if (abs < 0.85) return "提供新信息";
  return "强偏移信号";
}

function signalTagLabel(signal: WorkbenchSignal) {
  const confidence = Number.isFinite(signal.confidence_percent) ? ` · ${formatPercent(signal.confidence_percent)}` : "";
  const count = signal.sample_count > 0 ? ` · n=${signal.sample_count}` : "";
  return `${signal.label} ${formatSigned(signal.value)}${confidence}${count}`;
}

function buildQuestionRationale(question: Question | null, state: SessionState | null) {
  const rationale: string[] = [];
  if (!question) return rationale;

  rationale.push(`${layerLabel(question.layer)}：这题用于继续压缩当前画像的不确定区域。`);

  if (question.generation_mode === "probe") {
    rationale.push("AI Probe：系统在当前模糊方向上插入追问，而不是继续按题库平铺。");
  } else if (question.generation_mode === "llm_rewrite") {
    rationale.push("AI Rewrite：题面经过改写，但仍保留原模板的测量方向。");
  } else if (question.generation_mode === "anchor") {
    rationale.push("Anchor：这类题用于复核前后稳定性，避免单一路径漂移。");
  }

  if (question.scenario_tags.length > 0) {
    rationale.push(`场景锚点：${question.scenario_tags.slice(0, 3).join(" / ")}。`);
  }

  if (state) {
    const uncertain = Object.entries(state.core_sigma).sort((left, right) => right[1] - left[1])[0];
    if (uncertain) {
      rationale.push(`当前最高不确定项是 ${coreLabel(uncertain[0])}，系统会继续用题目缩小误差带。`);
    }
  }

  return rationale.slice(0, 4);
}

export function SessionClient() {
  const router = useRouter();
  const [access, setAccess] = useState<SessionAccessBundle | null>(null);
  const [question, setQuestion] = useState<Question | null>(null);
  const [state, setState] = useState<SessionState | null>(null);
  const [remainingUntilReport, setRemainingUntilReport] = useState(20);
  const [canGenerateReport, setCanGenerateReport] = useState(false);
  const [checkpoint, setCheckpoint] = useState<WorkbenchCheckpoint | null>(null);
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
          setCheckpoint(summary.workbench_checkpoint ?? null);
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
          setCheckpoint(started.workbench_checkpoint ?? null);
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

  const questionCount = state?.question_count ?? 0;
  const reportTarget = Math.max(questionCount + remainingUntilReport, 1);
  const reportProgress =
    checkpoint?.report_progress_percent ?? (canGenerateReport ? 100 : clamp((questionCount / reportTarget) * 100));
  const fallbackNextMilestone =
    MILESTONES.find((milestone) => milestone > questionCount) ?? MILESTONES[MILESTONES.length - 1];
  const nextMilestone = checkpoint?.next_milestone ?? fallbackNextMilestone;
  const nextMilestoneLabel = checkpoint && checkpoint.next_milestone === null ? "全部完成" : String(nextMilestone ?? fallbackNextMilestone);
  const previousMilestone = [...MILESTONES].reverse().find((milestone) => milestone <= questionCount) ?? 0;
  const localMilestoneProgress =
    nextMilestone === previousMilestone ? 100 : clamp(((questionCount - previousMilestone) / (nextMilestone - previousMilestone)) * 100);
  const milestoneProgress = checkpoint?.milestone_progress_percent ?? localMilestoneProgress;

  const topSignals = useMemo(() => {
    if (checkpoint?.top_core_signals.length) {
      return checkpoint.top_core_signals.map((signal) => ({
        key: signal.key,
        label: signal.label,
        value: signal.value,
        percent: scoreToPercent(signal.value),
        confidence: signal.confidence_percent,
        sampleCount: signal.sample_count,
      }));
    }
    if (!state) return [];
    return Object.entries(state.core_mu)
      .map(([key, value]) => ({
        key,
        label: coreLabel(key),
        value,
        percent: scoreToPercent(value),
        confidence: sigmaToConfidence(state.core_sigma[key] ?? 1.5),
        sampleCount: state.dimension_counts[key] ?? 0,
      }))
      .sort((left, right) => Math.abs(right.value) - Math.abs(left.value))
      .slice(0, 5);
  }, [checkpoint, state]);

  const uncertaintySignals = useMemo(() => {
    if (checkpoint?.uncertainty_queue.length) {
      return checkpoint.uncertainty_queue.map((signal) => ({
        key: signal.key,
        label: signal.label,
        sigma: signal.value,
        confidence: signal.confidence_percent,
        count: signal.sample_count,
        detail: signal.detail,
      }));
    }
    if (!state) return [];
    return Object.entries(state.core_sigma)
      .map(([key, sigma]) => ({
        key,
        label: coreLabel(key),
        sigma,
        confidence: sigmaToConfidence(sigma),
        count: state.dimension_counts[key] ?? 0,
        detail: "sigma 越高，越需要继续压缩误差带",
      }))
      .sort((left, right) => right.sigma - left.sigma)
      .slice(0, 4);
  }, [checkpoint, state]);

  const moduleSignals = useMemo(() => {
    if (checkpoint?.active_modules.length) {
      return checkpoint.active_modules.map((signal) => ({
        key: signal.key,
        label: signal.label,
        value: signal.value,
        count: signal.sample_count,
        confidence: signal.confidence_percent,
        detail: signal.detail,
      }));
    }
    if (!state) return [];
    const active = new Set(state.active_modules);
    return Object.entries(state.module_scores)
      .filter(([key, value]) => active.has(key) || Math.abs(value) > 0.01)
      .map(([key, value]) => ({
        key,
        label: moduleLabel(key),
        value,
        count: state.module_counts[key] ?? 0,
        confidence: active.has(key) ? 100 : 35,
        detail: active.has(key) ? "已出现足够场景证据" : "仍在观察",
      }))
      .sort((left, right) => Math.abs(right.value) - Math.abs(left.value))
      .slice(0, 4);
  }, [checkpoint, state]);

  const unlockedSubdimensionSignals = useMemo(() => {
    if (checkpoint?.unlocked_subdimensions.length) return checkpoint.unlocked_subdimensions;
    return (state?.unlocked_subdimensions ?? []).map((key) => ({
      key,
      label: subdimensionLabel(key),
      value: state?.sub_mu[key] ?? 0,
      confidence_percent: sigmaToConfidence(state?.sub_sigma[key] ?? 1.5),
      sample_count: state?.sub_counts[key] ?? 0,
      detail: "已达到子维度展开条件",
    }));
  }, [checkpoint, state]);

  const checkpointMilestones = useMemo<WorkbenchMilestone[]>(() => {
    if (checkpoint?.milestones.length) return checkpoint.milestones;
    const next = MILESTONES.find((milestone) => milestone > questionCount) ?? null;
    return MILESTONES.map((milestone) => {
      if (questionCount >= milestone) {
        return {
          milestone,
          status: "completed",
          question_delta: 0,
          progress_percent: 100,
          snapshot_expected: questionCount === milestone,
        };
      }
      const previous = [...MILESTONES].reverse().find((value) => value < milestone) ?? 0;
      return {
        milestone,
        status: milestone === next ? "current" : "upcoming",
        question_delta: milestone - questionCount,
        progress_percent: milestone === next ? clamp(((questionCount - previous) / Math.max(milestone - previous, 1)) * 100) : 0,
        snapshot_expected: false,
      };
    }) as WorkbenchMilestone[];
  }, [checkpoint, questionCount]);

  const recentAnswers = useMemo(() => {
    if (!state) return [];
    return state.answers.slice(-6).reverse();
  }, [state]);

  const questionRationale = useMemo(() => buildQuestionRationale(question, state), [question, state]);

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
      setCheckpoint(response.workbench_checkpoint ?? null);
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
    return (
      <main className="session-shell session-workbench">
        <div className="mx-auto flex min-h-[72vh] max-w-4xl flex-col items-center justify-center text-center">
          <p className="text-xs uppercase tracking-[0.45em] text-cyan-200/70">Distilled TI</p>
          <h1 className="mt-5 text-5xl text-white">正在构建本次测量工作台</h1>
          <p className="mt-5 max-w-xl text-slate-300">系统正在恢复会话状态、当前题目和可用报告进度。</p>
        </div>
      </main>
    );
  }

  return (
    <main className="session-shell session-workbench">
      <div className="workbench-orbit workbench-orbit-a" />
      <div className="workbench-orbit workbench-orbit-b" />

      <section className="relative z-10 mx-auto max-w-[1520px] space-y-6">
        <header className="workbench-panel workbench-load grid gap-6 p-6 md:grid-cols-[1fr_auto] md:items-end lg:p-8">
          <div>
            <p className="text-xs uppercase tracking-[0.42em] text-cyan-200/70">Distilled TI / Live Session</p>
            <h1 className="mt-4 text-5xl leading-[0.9] text-white md:text-7xl">测量工作台</h1>
            <p className="mt-5 max-w-3xl text-base leading-7 text-slate-300">
              这里不只是逐题作答。左侧显示画像正在怎样收敛，中间保持答题主流程，右侧解释为什么此刻问这题，以及距离报告和 milestone 还有多远。
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-3 md:min-w-[420px] md:grid-cols-1">
            <StatusTile label="已答题" value={`${questionCount}`} detail={`下一题 Q${questionCount + 1}`} />
            <StatusTile
              label="报告准备度"
              value={canGenerateReport ? "Ready" : `${remainingUntilReport} left`}
              detail={canGenerateReport ? "可生成正式报告" : `${formatPercent(reportProgress)} 已完成`}
            />
            <StatusTile label="当前题型" value={generationLabel(question?.generation_mode)} detail={layerLabel(question?.layer)} />
          </div>
        </header>

        {error ? (
          <div className="rounded-[1.6rem] border border-rose-300/25 bg-rose-300/10 p-4 text-sm text-rose-100">{error}</div>
        ) : null}

        <section className="grid gap-6 xl:grid-cols-[0.88fr_1.22fr_0.9fr]">
          <aside className="space-y-6">
            <section className="workbench-panel workbench-load p-5" style={{ animationDelay: "80ms" }}>
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="label-mini">Live Profile</p>
                  <h2 className="mt-2 text-3xl text-white">实时画像</h2>
                </div>
                <div className="rounded-full border border-cyan-200/20 bg-cyan-200/10 px-4 py-2 text-xs font-semibold text-cyan-100">
                  {state?.answers.length ?? 0} signals
                </div>
              </div>

              <div className="mt-6 grid grid-cols-2 gap-3">
                <MetricCard label="解锁 Sub" value={state?.unlocked_subdimensions.length ?? 0} />
                <MetricCard label="活跃模块" value={state?.active_modules.length ?? 0} />
                <MetricCard label="一致性" value={formatPercent((state?.zeta.consistency ?? 0) * 100)} compact />
                <MetricCard label="探索度" value={formatPercent((state?.zeta.exploration ?? 0) * 100)} compact />
              </div>

              <div className="mt-7 space-y-5">
                {topSignals.length > 0 ? (
                  topSignals.map((signal) => (
                    <div key={signal.key}>
                      <div className="mb-2 flex items-center justify-between gap-4 text-sm text-slate-200">
                        <span>{signal.label}</span>
                        <span className="font-mono text-cyan-200">{formatSigned(signal.value)}</span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-white/8">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-sky-300 via-cyan-200 to-lime-200"
                          style={{ width: `${signal.percent}%` }}
                        />
                      </div>
                      <p className="mt-1 text-xs text-slate-500">
                        置信度约 {formatPercent(signal.confidence)} · 样本 {signal.sampleCount}
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="rounded-[1.4rem] border border-white/10 bg-black/20 p-4 text-sm text-slate-400">
                    还没有足够信号。答完前几题后，这里会显示最突出的核心维度。
                  </p>
                )}
              </div>
            </section>

            <section className="workbench-panel workbench-load p-5" style={{ animationDelay: "140ms" }}>
              <p className="label-mini">Uncertainty Queue</p>
              <h2 className="mt-2 text-2xl text-white">下一批需要压缩的误差带</h2>
              <div className="mt-5 space-y-4">
                {uncertaintySignals.map((signal) => (
                  <div key={signal.key} className="rounded-[1.25rem] border border-white/10 bg-white/[0.035] p-4">
                    <div className="flex items-center justify-between gap-3 text-sm">
                      <span className="text-slate-100">{signal.label}</span>
                      <span className="font-mono text-amber-100">sigma {signal.sigma.toFixed(2)}</span>
                    </div>
                    <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/8">
                      <div className="h-full rounded-full bg-gradient-to-r from-amber-200 to-cyan-200" style={{ width: `${signal.confidence}%` }} />
                    </div>
                    <p className="mt-2 text-xs text-slate-500">
                      已覆盖 {signal.count} 次，置信度 {formatPercent(signal.confidence)}
                      {signal.detail ? ` · ${signal.detail}` : ""}
                    </p>
                  </div>
                ))}
              </div>
            </section>
          </aside>

          <section className="space-y-6">
            <section className="workbench-panel workbench-load overflow-hidden p-0" style={{ animationDelay: "110ms" }}>
              {question ? (
                <>
                  <div className="border-b border-white/10 bg-white/[0.035] p-5 md:p-7">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex flex-wrap gap-2">
                        <Badge>{question.layer}</Badge>
                        <Badge>{generationLabel(question.generation_mode)}</Badge>
                        {question.scenario_tags.slice(0, 3).map((tag) => (
                          <Badge key={tag}>{tag}</Badge>
                        ))}
                      </div>
                      <div className="rounded-full border border-white/10 bg-black/25 px-4 py-2 font-mono text-xs uppercase tracking-[0.25em] text-slate-300">
                        Q {questionCount + 1}
                      </div>
                    </div>
                    <h2 className="mt-7 max-w-4xl text-4xl leading-tight text-white md:text-5xl">{question.prompt}</h2>
                  </div>

                  <div className="grid gap-4 p-5 md:p-7">
                    {question.options.map((option, index) => (
                      <button
                        key={option.key}
                        type="button"
                        className="answer-option-button group"
                        onClick={() => void handleAnswer(option.key)}
                        disabled={busy}
                        style={{ animationDelay: `${160 + index * 45}ms` }}
                      >
                        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-cyan-200/20 bg-cyan-200/10 font-mono text-xs text-cyan-100">
                          {option.key}
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="block text-xs uppercase tracking-[0.26em] text-cyan-200/55">
                            {optionSideLabel(question.question_type, option.score)}
                          </span>
                          <span className="mt-2 block text-lg leading-8 text-white">{option.text}</span>
                        </span>
                        <span className="hidden rounded-full border border-white/10 px-3 py-1 font-mono text-xs text-slate-400 transition group-hover:border-cyan-200/30 group-hover:text-cyan-100 md:inline-flex">
                          {formatSigned(option.score)}
                        </span>
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <div className="flex min-h-[520px] flex-col items-center justify-center p-8 text-center">
                  <p className="text-sm uppercase tracking-[0.35em] text-cyan-200/70">Session Complete</p>
                  <h2 className="mt-4 text-4xl text-white">当前这一轮已经没有待答题目</h2>
                  <p className="mt-4 max-w-xl text-slate-300">你可以直接查看报告，也可以结束并删除这次会话。</p>
                  <div className="mt-8 flex flex-wrap justify-center gap-4">
                    <button
                      type="button"
                      className="rounded-full bg-cyan-300 px-6 py-3 text-sm font-semibold text-slate-950"
                      onClick={() => void handleFinalizeReport()}
                      disabled={!canGenerateReport || busy}
                    >
                      查看最终报告
                    </button>
                    <button
                      type="button"
                      className="rounded-full border border-white/15 px-6 py-3 text-sm font-semibold text-white"
                      onClick={() => void handleDelete()}
                      disabled={busy}
                    >
                      删除会话
                    </button>
                  </div>
                </div>
              )}
            </section>

            <section className="workbench-panel workbench-load p-5" style={{ animationDelay: "180ms" }}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="label-mini">Trajectory</p>
                  <h2 className="mt-2 text-2xl text-white">最近答题轨迹</h2>
                </div>
                <span className="text-sm text-slate-400">显示最近 {recentAnswers.length} 个信号</span>
              </div>
              <div className="mt-5 grid gap-3 md:grid-cols-2">
                {recentAnswers.length > 0 ? (
                  recentAnswers.map((answer, index) => (
                    <div key={`${answer.item_id}-${index}`} className="rounded-[1.25rem] border border-white/10 bg-black/20 p-4">
                      <div className="flex items-center justify-between gap-3">
                        <p className="truncate text-sm text-slate-100">{answer.item_id}</p>
                        <span className="rounded-full bg-white/8 px-3 py-1 text-xs text-slate-300">{answerQualityLabel(answer.residual)}</span>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-400">
                        <span>回答 {formatSigned(answer.mapped_score)}</span>
                        <span>预测 {formatSigned(answer.predicted_score)}</span>
                        <span>耗时 {formatLatency(answer.latency_ms)}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="rounded-[1.4rem] border border-white/10 bg-black/20 p-4 text-sm text-slate-400">
                    轨迹会在提交第一题后出现。
                  </p>
                )}
              </div>
            </section>
          </section>

          <aside className="space-y-6">
            <section className="workbench-panel workbench-load p-5" style={{ animationDelay: "160ms" }}>
              <p className="label-mini">Why This Question</p>
              <h2 className="mt-2 text-2xl text-white">为什么现在问这题</h2>
              <div className="mt-5 space-y-3">
                {questionRationale.length > 0 ? (
                  questionRationale.map((item) => (
                    <div key={item} className="rounded-[1.25rem] border border-white/10 bg-white/[0.035] p-4 text-sm leading-6 text-slate-200">
                      {item}
                    </div>
                  ))
                ) : (
                  <p className="rounded-[1.25rem] border border-white/10 bg-white/[0.035] p-4 text-sm leading-6 text-slate-400">
                    当前没有待答题目，系统已暂停选题解释。
                  </p>
                )}
              </div>
            </section>

            <section className="workbench-panel workbench-load p-5" style={{ animationDelay: "220ms" }}>
              <p className="label-mini">Checkpoint</p>
              <h2 className="mt-2 text-2xl text-white">报告与 milestone</h2>
              {checkpoint?.narrative ? (
                <p className="mt-4 rounded-[1.25rem] border border-white/10 bg-white/[0.035] p-4 text-sm leading-6 text-slate-200">
                  {checkpoint.narrative}
                </p>
              ) : null}
              <div className="mt-5 rounded-[1.5rem] border border-cyan-200/15 bg-cyan-200/[0.07] p-5">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm text-slate-300">正式报告</p>
                    <p className="mt-1 text-3xl text-white">{canGenerateReport ? "已解锁" : `还需 ${remainingUntilReport} 题`}</p>
                  </div>
                  <span className="font-mono text-lg text-cyan-100">{formatPercent(reportProgress)}</span>
                </div>
                <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full rounded-full bg-gradient-to-r from-cyan-200 to-lime-200" style={{ width: `${reportProgress}%` }} />
                </div>
              </div>

              <div className="mt-4 rounded-[1.5rem] border border-white/10 bg-black/20 p-5">
                <div className="flex items-center justify-between gap-4">
                  <p className="text-sm text-slate-300">下一次 session vector 快照</p>
                  <span className="font-mono text-cyan-100">{nextMilestoneLabel}</span>
                </div>
                <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/10">
                  <div className="h-full rounded-full bg-gradient-to-r from-amber-200 to-cyan-200" style={{ width: `${milestoneProgress}%` }} />
                </div>
                <p className="mt-3 text-xs leading-5 text-slate-500">
                  命中 5 / 10 / 20 / 40 题时，后端会 best-effort 写入 `session_vectors`，用于相似会话检索和后续诊断。
                </p>
              </div>

              <div className="mt-4 grid grid-cols-2 gap-3">
                {checkpointMilestones.map((milestone) => (
                  <MilestoneCard key={milestone.milestone} milestone={milestone} />
                ))}
              </div>

              <div className="mt-4 flex flex-wrap gap-3">
                <button
                  type="button"
                  className="rounded-full border border-white/15 bg-white/6 px-5 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
                  onClick={() => void handleFinalizeReport()}
                  disabled={!canGenerateReport || busy}
                >
                  {canGenerateReport ? "生成并查看报告" : "报告尚未解锁"}
                </button>
                <button
                  type="button"
                  className="rounded-full border border-rose-300/20 bg-rose-300/10 px-5 py-3 text-sm font-semibold text-rose-100 transition hover:bg-rose-300/20"
                  onClick={() => void handleDelete()}
                  disabled={busy}
                >
                  删除会话
                </button>
              </div>
            </section>

            <section className="workbench-panel workbench-load p-5" style={{ animationDelay: "260ms" }}>
              <p className="label-mini">Unlocked Context</p>
              <h2 className="mt-2 text-2xl text-white">已展开的侧面信息</h2>
              <div className="mt-5 space-y-4">
                <TagGroup
                  title="Subdimensions"
                  empty="还没有解锁子维度"
                  items={unlockedSubdimensionSignals.map(signalTagLabel)}
                />
                <TagGroup title="Modules" empty="还没有活跃模块" items={moduleSignals.map((module) => `${module.label} ${formatSigned(module.value)}`)} />
              </div>
            </section>
          </aside>
        </section>
      </section>
    </main>
  );
}

function StatusTile({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-[1.4rem] border border-white/10 bg-black/25 px-4 py-3">
      <p className="text-[0.65rem] uppercase tracking-[0.28em] text-cyan-200/60">{label}</p>
      <p className="mt-1 text-xl text-white">{value}</p>
      <p className="mt-1 text-xs text-slate-500">{detail}</p>
    </div>
  );
}

function MetricCard({ label, value, compact = false }: { label: string; value: string | number; compact?: boolean }) {
  return (
    <div className="glass-card">
      <p className="label-mini">{label}</p>
      <p className={compact ? "mt-2 text-2xl text-white" : "metric-big"}>{value}</p>
    </div>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-white/10 bg-white/[0.06] px-3 py-1.5 text-xs uppercase tracking-[0.22em] text-slate-300">
      {children}
    </span>
  );
}

function MilestoneCard({ milestone }: { milestone: WorkbenchMilestone }) {
  const statusLabel =
    milestone.status === "completed" ? "已完成" : milestone.status === "current" ? "进行中" : "等待";
  const tone =
    milestone.status === "completed"
      ? "border-lime-200/25 bg-lime-200/[0.08] text-lime-100"
      : milestone.status === "current"
        ? "border-cyan-200/25 bg-cyan-200/[0.08] text-cyan-100"
        : "border-white/10 bg-white/[0.035] text-slate-300";

  return (
    <div className={`rounded-[1.15rem] border p-3 ${tone}`}>
      <div className="flex items-center justify-between gap-2">
        <p className="font-mono text-lg">Q{milestone.milestone}</p>
        <span className="rounded-full bg-black/20 px-2.5 py-1 text-[0.65rem] uppercase tracking-[0.18em]">
          {milestone.snapshot_expected ? "snapshot" : statusLabel}
        </span>
      </div>
      <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-black/20">
        <div className="h-full rounded-full bg-current" style={{ width: `${milestone.progress_percent}%` }} />
      </div>
      <p className="mt-2 text-xs opacity-75">
        {milestone.question_delta > 0 ? `还差 ${milestone.question_delta} 题` : "快照点已覆盖"}
      </p>
    </div>
  );
}

function TagGroup({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <div>
      <p className="text-xs uppercase tracking-[0.24em] text-slate-500">{title}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        {items.length > 0 ? (
          items.map((item) => (
            <span key={item} className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1.5 text-xs text-slate-200">
              {item}
            </span>
          ))
        ) : (
          <span className="rounded-full border border-white/10 bg-black/20 px-3 py-1.5 text-xs text-slate-500">{empty}</span>
        )}
      </div>
    </div>
  );
}
