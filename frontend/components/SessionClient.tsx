"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  deleteSession,
  generateSessionReport,
  getSessionMap,
  getSessionSummary,
  getWorkbenchEvidence,
  startSession,
  submitAnswer,
  type Question,
  type SessionMap,
  type SessionReport,
  type SessionState,
  type WorkbenchCheckpoint,
  type WorkbenchEvidence,
  type WorkbenchEvidenceItem,
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
  const [evidence, setEvidence] = useState<WorkbenchEvidence | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceError, setEvidenceError] = useState("");
  const [reportPreview, setReportPreview] = useState<SessionReport | null>(null);
  const [reportPreviewLoading, setReportPreviewLoading] = useState(false);
  const [reportPreviewError, setReportPreviewError] = useState("");
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

  async function handleLoadEvidence() {
    if (!access) return;
    try {
      setEvidenceOpen(true);
      setEvidenceLoading(true);
      setEvidenceError("");
      const payload = await getWorkbenchEvidence(access);
      setEvidence(payload);
    } catch (reason) {
      setEvidenceError(reason instanceof Error ? reason.message : "检索证据加载失败。");
    } finally {
      setEvidenceLoading(false);
    }
  }

  async function handleLoadReportPreview() {
    if (!access || !canGenerateReport) return;
    try {
      setReportPreviewLoading(true);
      setReportPreviewError("");
      const preferences = getReportViewPreferences();
      const report = await generateSessionReport(access, preferences.namingStyle);
      setReportPreview(report);
    } catch (reason) {
      setReportPreviewError(reason instanceof Error ? reason.message : "报告预览生成失败。");
    } finally {
      setReportPreviewLoading(false);
    }
  }

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
      setEvidence(null);
      setEvidenceOpen(false);
      setEvidenceError("");
      setReportPreview(null);
      setReportPreviewError("");
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
      <main className="cockpit-shell">
        <div className="relative z-10 mx-auto flex min-h-[72vh] max-w-3xl flex-col items-center justify-center text-center">
          <p className="eyebrow">Distilled TI</p>
          <h1 className="mt-5 text-4xl md:text-5xl">正在构建本次测量工作台</h1>
          <p className="mt-5 max-w-xl text-[color:var(--ink-muted)]">系统正在恢复会话状态、当前题目和可用报告进度。</p>
          <div className="mt-8 flex gap-1.5">
            <span className="h-2 w-2 animate-pulse rounded-full bg-[color:var(--accent)]" />
            <span className="h-2 w-2 animate-pulse rounded-full bg-[color:var(--accent)] [animation-delay:120ms]" />
            <span className="h-2 w-2 animate-pulse rounded-full bg-[color:var(--accent)] [animation-delay:240ms]" />
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="cockpit-shell">
      <section className="relative z-10 mx-auto max-w-[1480px] space-y-5">
        {/* ============== HEADER ============== */}
        <header className="panel fade-rise grid gap-6 p-5 md:grid-cols-[1fr_auto] md:items-end md:p-7">
          <div>
            <div className="flex items-center gap-3">
              <span className="eyebrow">Distilled TI</span>
              <span className="hairline-strong h-px w-8" aria-hidden />
              <span className="eyebrow">Live Session</span>
            </div>
            <h1 className="mt-3 text-4xl leading-[1.05] md:text-5xl lg:text-6xl">测量工作台</h1>
            <p className="mt-4 max-w-2xl text-[0.95rem] leading-7 text-[color:var(--ink-muted)]">
              这里不只是逐题作答。左栏显示画像正在怎样收敛，中栏保持答题主流程，右栏解释为什么此刻问这题、距离报告与 milestone 还有多远。
            </p>
          </div>
          <div className="grid gap-2.5 sm:grid-cols-3 md:min-w-[400px] md:grid-cols-1 lg:grid-cols-3">
            <StatusTile
              label="已答题"
              value={`${questionCount}`}
              detail={`下一题 Q${questionCount + 1}`}
            />
            <StatusTile
              label="报告准备度"
              value={canGenerateReport ? "Ready" : `还差 ${remainingUntilReport}`}
              detail={canGenerateReport ? "可生成正式报告" : `已完成 ${formatPercent(reportProgress)}`}
              tone={canGenerateReport ? "success" : "default"}
            />
            <StatusTile
              label="当前题型"
              value={generationLabel(question?.generation_mode)}
              detail={layerLabel(question?.layer)}
            />
          </div>
        </header>

        {error ? (
          <div className="panel border-[color:var(--danger)]/30 bg-[color:var(--danger-soft)] p-4 text-sm text-[color:var(--danger-ink)]">
            {error}
          </div>
        ) : null}

        {/* ============== MAIN GRID ============== */}
        <section className="grid gap-5 xl:grid-cols-[0.85fr_1.3fr_0.85fr]">
          {/* ============== LEFT: Live Profile + Uncertainty Queue ============== */}
          <aside className="space-y-5">
            {/* Live Profile */}
            <section className="panel fade-rise p-5" style={{ animationDelay: "60ms" }}>
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="label-mini">Live Profile</p>
                  <h2 className="mt-1.5 text-2xl">实时画像</h2>
                </div>
                <span className="chip chip-accent num">{state?.answers.length ?? 0} signals</span>
              </div>

              <div className="mt-5 grid grid-cols-2 gap-2.5">
                <MetricCard label="解锁 Sub" value={state?.unlocked_subdimensions.length ?? 0} />
                <MetricCard label="活跃模块" value={state?.active_modules.length ?? 0} />
                <MetricCard label="一致性" value={formatPercent((state?.zeta.consistency ?? 0) * 100)} compact />
                <MetricCard label="探索度" value={formatPercent((state?.zeta.exploration ?? 0) * 100)} compact />
              </div>

              <div className="hairline mt-6" />

              <div className="mt-5 space-y-4">
                {topSignals.length > 0 ? (
                  topSignals.map((signal) => (
                    <div key={signal.key}>
                      <div className="mb-1.5 flex items-center justify-between gap-3 text-sm">
                        <span className="text-[color:var(--ink-strong)]">{signal.label}</span>
                        <span className="num text-[color:var(--accent-ink)]">{formatSigned(signal.value)}</span>
                      </div>
                      <div className="bar-track">
                        <div className="bar-fill" style={{ width: `${signal.percent}%` }} />
                      </div>
                      <p className="num mt-1.5 text-[0.7rem] text-[color:var(--ink-faint)]">
                        置信度 {formatPercent(signal.confidence)} · 样本 {signal.sampleCount}
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="surface-sunken p-4 text-sm text-[color:var(--ink-muted)]">
                    还没有足够信号。答完前几题后，这里会显示最突出的核心维度。
                  </p>
                )}
              </div>
            </section>

            {/* Uncertainty Queue */}
            <section className="panel fade-rise p-5" style={{ animationDelay: "120ms" }}>
              <p className="label-mini">Uncertainty Queue</p>
              <h2 className="mt-1.5 text-xl">下一批待压缩的误差带</h2>
              <div className="mt-4 space-y-3">
                {uncertaintySignals.map((signal) => (
                  <div key={signal.key} className="surface-sunken p-3.5">
                    <div className="flex items-center justify-between gap-3 text-sm">
                      <span className="text-[color:var(--ink-strong)]">{signal.label}</span>
                      <span className="num text-[color:var(--warn-ink)]">σ {signal.sigma.toFixed(2)}</span>
                    </div>
                    <div className="bar-track mt-2.5">
                      <div className="bar-fill bar-fill-warn" style={{ width: `${signal.confidence}%` }} />
                    </div>
                    <p className="num mt-2 text-[0.7rem] text-[color:var(--ink-faint)]">
                      已覆盖 {signal.count} 次 · 置信度 {formatPercent(signal.confidence)}
                      {signal.detail ? ` · ${signal.detail}` : ""}
                    </p>
                  </div>
                ))}
                {uncertaintySignals.length === 0 ? (
                  <p className="surface-sunken p-4 text-sm text-[color:var(--ink-muted)]">
                    前几题之后，这里会按 sigma 排序列出最需要压缩的维度。
                  </p>
                ) : null}
              </div>
            </section>
          </aside>

          {/* ============== CENTER: 主答题区 + Trajectory ============== */}
          <section className="space-y-5">
            <section className="panel-paper fade-rise overflow-hidden p-0" style={{ animationDelay: "90ms" }}>
              {question ? (
                <>
                  <div className="border-b border-[color:var(--line-soft)] bg-[color:var(--bg-raised)] px-5 py-5 md:px-7 md:py-6">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex flex-wrap gap-2">
                        <span className="chip chip-accent">{layerLabel(question.layer)}</span>
                        <span className="chip">{generationLabel(question.generation_mode)}</span>
                        {question.scenario_tags.slice(0, 3).map((tag, index) => (
                          <span key={`${tag}-${index}`} className="chip">{tag}</span>
                        ))}
                      </div>
                      <span className="num chip">Q {questionCount + 1}</span>
                    </div>
                    <h2 className="mt-6 max-w-3xl text-[1.7rem] leading-[1.35] text-[color:var(--ink-strong)] md:text-[2rem] md:leading-[1.3]">
                      {question.prompt}
                    </h2>
                  </div>

                  <div className="grid gap-2.5 px-5 py-5 md:px-7 md:py-6">
                    {question.options.map((option, index) => (
                      <button
                        key={option.key}
                        type="button"
                        className="option-row group"
                        onClick={() => void handleAnswer(option.key)}
                        disabled={busy}
                        style={{ animationDelay: `${120 + index * 50}ms` }}
                      >
                        <span className="option-key">{option.key}</span>
                        <span className="min-w-0 flex-1">
                          <span className="label-mini block">
                            {optionSideLabel(question.question_type, option.score)}
                          </span>
                          <span className="mt-1.5 block text-[1rem] leading-[1.65] text-[color:var(--ink-strong)] md:text-[1.05rem]">
                            {option.text}
                          </span>
                        </span>
                        <span className="num hidden self-center rounded-full border border-[color:var(--line-soft)] bg-[color:var(--bg-sunken)] px-2.5 py-1 text-[0.7rem] text-[color:var(--ink-muted)] transition group-hover:border-[color:var(--accent)] group-hover:text-[color:var(--accent-ink)] md:inline-flex">
                          {formatSigned(option.score)}
                        </span>
                      </button>
                    ))}
                  </div>
                </>
              ) : (
                <div className="flex min-h-[480px] flex-col items-center justify-center p-8 text-center">
                  <p className="label-mini">Session Complete</p>
                  <h2 className="mt-3 text-3xl md:text-4xl">当前这一轮已经没有待答题目</h2>
                  <p className="mt-4 max-w-xl text-[color:var(--ink-muted)]">
                    你可以直接查看报告，也可以结束并删除这次会话。
                  </p>
                  <div className="mt-7 flex flex-wrap justify-center gap-3">
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => void handleFinalizeReport()}
                      disabled={!canGenerateReport || busy}
                    >
                      查看最终报告
                    </button>
                    <button
                      type="button"
                      className="btn btn-danger"
                      onClick={() => void handleDelete()}
                      disabled={busy}
                    >
                      删除会话
                    </button>
                  </div>
                </div>
              )}
            </section>

            {/* Trajectory */}
            <section className="panel fade-rise p-5" style={{ animationDelay: "150ms" }}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="label-mini">Trajectory</p>
                  <h2 className="mt-1.5 text-xl">最近答题轨迹</h2>
                </div>
                <span className="num text-[0.75rem] text-[color:var(--ink-faint)]">最近 {recentAnswers.length} 个信号</span>
              </div>
              <div className="mt-4 grid gap-2.5 md:grid-cols-2">
                {recentAnswers.length > 0 ? (
                  recentAnswers.map((answer, index) => (
                    <div key={`${answer.item_id}-${index}`} className="surface-sunken p-3.5">
                      <div className="flex items-center justify-between gap-3">
                        <p className="num truncate text-[0.8rem] text-[color:var(--ink-strong)]">{answer.item_id}</p>
                        <span className="chip">{answerQualityLabel(answer.residual)}</span>
                      </div>
                      <div className="num mt-2 flex flex-wrap gap-x-3 gap-y-0.5 text-[0.72rem] text-[color:var(--ink-muted)]">
                        <span>回答 {formatSigned(answer.mapped_score)}</span>
                        <span>预测 {formatSigned(answer.predicted_score)}</span>
                        <span>耗时 {formatLatency(answer.latency_ms)}</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="surface-sunken p-4 text-sm text-[color:var(--ink-muted)] md:col-span-2">
                    轨迹会在提交第一题后出现。
                  </p>
                )}
              </div>
            </section>
          </section>

          {/* ============== RIGHT: Why + Checkpoint + Unlocked ============== */}
          <aside className="space-y-5">
            {/* Why This Question */}
            <section className="panel fade-rise p-5" style={{ animationDelay: "120ms" }}>
              <p className="label-mini">Why This Question</p>
              <h2 className="mt-1.5 text-xl">为什么现在问这题</h2>
              <div className="mt-4 space-y-2.5">
                {questionRationale.length > 0 ? (
                  questionRationale.map((item) => (
                    <div
                      key={item}
                      className="surface-sunken border-l-2 border-l-[color:var(--accent)] py-3 pl-3.5 pr-3 text-sm leading-6 text-[color:var(--ink-body)]"
                    >
                      {item}
                    </div>
                  ))
                ) : (
                  <p className="surface-sunken p-4 text-sm text-[color:var(--ink-muted)]">
                    当前没有待答题目，系统已暂停选题解释。
                  </p>
                )}
              </div>

              {/* Retrieval Evidence trigger */}
              <div className="mt-4 rounded-[var(--r-md)] border border-[color:var(--line-soft)] bg-[color:var(--accent-soft)]/40 p-3.5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="label-mini">Retrieval Evidence</p>
                    <p className="mt-1.5 text-[0.82rem] leading-5 text-[color:var(--ink-muted)]">
                      按需读取相近题目和匿名会话快照，只作为解释证据。
                    </p>
                  </div>
                  <button
                    type="button"
                    className="btn btn-ghost shrink-0 px-3 py-1.5 text-xs"
                    onClick={() => void handleLoadEvidence()}
                    disabled={!access || evidenceLoading}
                  >
                    {evidenceLoading ? "检索中…" : evidence ? "刷新" : "加载证据"}
                  </button>
                </div>
                {evidenceError ? (
                  <p className="mt-2.5 text-xs text-[color:var(--danger-ink)]">{evidenceError}</p>
                ) : null}
                {evidenceOpen ? <EvidenceDrawer evidence={evidence} loading={evidenceLoading} /> : null}
              </div>
            </section>

            {/* Checkpoint */}
            <section className="panel fade-rise p-5" style={{ animationDelay: "180ms" }}>
              <p className="label-mini">Checkpoint</p>
              <h2 className="mt-1.5 text-xl">报告与 milestone</h2>

              {checkpoint?.narrative ? (
                <p className="surface-sunken mt-4 p-3.5 text-sm leading-6 text-[color:var(--ink-body)]">
                  {checkpoint.narrative}
                </p>
              ) : null}

              {/* 报告进度 */}
              <div className="mt-4 rounded-[var(--r-md)] border border-[color:var(--accent-soft)] bg-[color:var(--accent-soft)]/50 p-4">
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="label-mini">正式报告</p>
                    <p className="mt-1 text-2xl text-[color:var(--ink-strong)]">
                      {canGenerateReport ? "已解锁" : `还需 ${remainingUntilReport} 题`}
                    </p>
                  </div>
                  <span className="num text-base text-[color:var(--accent-ink)]">{formatPercent(reportProgress)}</span>
                </div>
                <div className="bar-track mt-3">
                  <div className="bar-fill" style={{ width: `${reportProgress}%` }} />
                </div>
              </div>

              {/* milestone 进度 */}
              <div className="mt-3 rounded-[var(--r-md)] border border-[color:var(--line-soft)] bg-[color:var(--bg-raised)] p-4">
                <div className="flex items-center justify-between gap-4">
                  <p className="text-sm text-[color:var(--ink-muted)]">下一次 session vector 快照</p>
                  <span className="num text-sm text-[color:var(--ink-strong)]">{nextMilestoneLabel}</span>
                </div>
                <div className="bar-track mt-3">
                  <div className="bar-fill bar-fill-warn" style={{ width: `${milestoneProgress}%` }} />
                </div>
                <p className="mt-2.5 text-[0.72rem] leading-5 text-[color:var(--ink-faint)]">
                  命中 5 / 10 / 20 / 40 题时，后端会 best-effort 写入 session_vectors，用于相似会话检索和后续诊断。
                </p>
              </div>

              {/* Report preview */}
              <ReportPreviewPanel
                canGenerateReport={canGenerateReport}
                remainingUntilReport={remainingUntilReport}
                report={reportPreview}
                loading={reportPreviewLoading}
                error={reportPreviewError}
                onLoad={() => void handleLoadReportPreview()}
                onFinalize={() => void handleFinalizeReport()}
              />

              {/* Milestones grid */}
              <div className="mt-3 grid grid-cols-2 gap-2">
                {checkpointMilestones.map((milestone) => (
                  <MilestoneCard key={milestone.milestone} milestone={milestone} />
                ))}
              </div>

              {/* Action buttons */}
              <div className="mt-4 flex flex-wrap gap-2.5">
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => void handleFinalizeReport()}
                  disabled={!canGenerateReport || busy}
                >
                  {canGenerateReport ? "生成并查看报告" : "报告尚未解锁"}
                </button>
                <button
                  type="button"
                  className="btn btn-danger"
                  onClick={() => void handleDelete()}
                  disabled={busy}
                >
                  删除会话
                </button>
              </div>
            </section>

            {/* Unlocked context */}
            <section className="panel fade-rise p-5" style={{ animationDelay: "240ms" }}>
              <p className="label-mini">Unlocked Context</p>
              <h2 className="mt-1.5 text-xl">已展开的侧面信息</h2>
              <div className="mt-4 space-y-3.5">
                <TagGroup
                  title="Subdimensions"
                  empty="还没有解锁子维度"
                  items={unlockedSubdimensionSignals.map(signalTagLabel)}
                />
                <TagGroup
                  title="Modules"
                  empty="还没有活跃模块"
                  items={moduleSignals.map((module) => `${module.label} ${formatSigned(module.value)}`)}
                />
              </div>
            </section>
          </aside>
        </section>
      </section>
    </main>
  );
}

/* ====================================================================== */
/*  Sub-components                                                         */
/* ====================================================================== */

function ReportPreviewPanel({
  canGenerateReport,
  remainingUntilReport,
  report,
  loading,
  error,
  onLoad,
  onFinalize,
}: {
  canGenerateReport: boolean;
  remainingUntilReport: number;
  report: SessionReport | null;
  loading: boolean;
  error: string;
  onLoad: () => void;
  onFinalize: () => void;
}) {
  if (!canGenerateReport) {
    return (
      <div className="surface-sunken mt-3 p-4">
        <p className="label-mini">Report Preview</p>
        <h3 className="mt-1.5 text-base text-[color:var(--ink-strong)]">预览尚未开放</h3>
        <p className="mt-2 text-sm leading-6 text-[color:var(--ink-muted)]">
          还差 {remainingUntilReport} 题达到正式报告阈值。到达阈值后，这里会先给出摘要预览，再决定是否进入完整报告页。
        </p>
      </div>
    );
  }

  return (
    <div className="mt-3 rounded-[var(--r-md)] border border-[color:var(--success-soft)] bg-[color:var(--success-soft)]/55 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="label-mini">Report Preview</p>
          <h3 className="mt-1.5 text-base text-[color:var(--ink-strong)]">先看摘要，再决定是否结束</h3>
        </div>
        <button
          type="button"
          className="btn btn-success-soft px-3 py-1.5 text-xs"
          onClick={onLoad}
          disabled={loading}
        >
          {loading ? "生成中…" : report ? "刷新预览" : "生成预览"}
        </button>
      </div>

      {error ? <p className="mt-2.5 text-xs text-[color:var(--danger-ink)]">{error}</p> : null}

      {report ? (
        <div className="mt-3.5 space-y-3.5">
          <div className="rounded-[var(--r-md)] border border-[color:var(--line-soft)] bg-[color:var(--bg-paper)] p-3.5">
            <p className="label-mini">{report.cluster_name}</p>
            <h4 className="mt-1.5 text-lg text-[color:var(--ink-strong)]">{report.narrative_label}</h4>
            {report.ai_aliases.length > 0 ? (
              <div className="mt-2.5 flex flex-wrap gap-1.5">
                {report.ai_aliases.slice(0, 3).map((alias) => (
                  <span key={alias} className="chip chip-success">{alias}</span>
                ))}
              </div>
            ) : null}
            <p className="mt-3 text-[0.85rem] leading-6 text-[color:var(--ink-body)]">{report.ai_summary}</p>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <PreviewMetric label="题量" value={`${report.question_count}`} />
            <PreviewMetric label="簇置信度" value={formatPercent(report.cluster_confidence * 100)} />
            <PreviewMetric label="平均误差带" value={report.uncertainty_summary.avg_sigma?.toFixed(2) ?? "—"} />
            <PreviewMetric label="稳定维度" value={`${report.uncertainty_summary.stable_dimensions ?? 0}`} />
          </div>

          <div>
            <p className="label-mini">Structural Signals</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {report.structural_labels.slice(0, 4).map((item) => (
                <span key={item.dimension} className="chip">
                  {item.label} {item.score >= 0 ? "偏高" : "偏低"}
                </span>
              ))}
            </div>
          </div>

          <div>
            <p className="label-mini">展开项</p>
            <p className="mt-2 text-[0.82rem] leading-6 text-[color:var(--ink-muted)]">
              {report.salient_subdimensions.slice(0, 3).join(" / ") || "子维度仍在采样中"}
              {report.active_module_labels.length > 0
                ? ` · ${report.active_module_labels.slice(0, 2).join(" / ")}`
                : ""}
            </p>
          </div>

          <button
            type="button"
            className="btn btn-primary w-full"
            onClick={onFinalize}
          >
            进入完整报告页
          </button>
        </div>
      ) : (
        <p className="mt-3 text-[0.82rem] leading-6 text-[color:var(--ink-muted)]">
          报告已解锁。点击生成预览会读取当前状态并生成一版摘要，但不会删除会话，也不会阻止你继续答题细化画像。
        </p>
      )}
    </div>
  );
}

function PreviewMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[var(--r-sm)] border border-[color:var(--line-soft)] bg-[color:var(--bg-paper)] px-3 py-2.5">
      <p className="label-mini text-[0.62rem]">{label}</p>
      <p className="num mt-1 text-[1.05rem] text-[color:var(--ink-strong)]">{value}</p>
    </div>
  );
}

function EvidenceDrawer({ evidence, loading }: { evidence: WorkbenchEvidence | null; loading: boolean }) {
  if (loading && !evidence) {
    return (
      <div className="surface-sunken mt-3 p-3.5 text-sm text-[color:var(--ink-muted)]">
        正在从向量层读取近邻证据…
      </div>
    );
  }

  if (!evidence) return null;

  const hasEvidence = evidence.item_evidence.length > 0 || evidence.session_evidence.length > 0;

  return (
    <div className="mt-3 space-y-3">
      <div className="flex flex-wrap gap-1.5">
        <span className="chip">vector {evidence.vector_available ? "available" : "offline"}</span>
        <span className="chip">reranker {evidence.reranker_applied ? "applied" : "not applied"}</span>
      </div>

      {!evidence.enabled || !hasEvidence ? (
        <div className="surface-sunken p-3.5 text-sm leading-6 text-[color:var(--ink-muted)]">
          {evidence.notes.length > 0 ? evidence.notes.join(" ") : "当前没有可展示的检索证据。"}
        </div>
      ) : (
        <>
          <EvidenceList title="相近题目证据" items={evidence.item_evidence} empty="没有稳定的相近题目证据。" />
          <EvidenceList title="相似会话快照" items={evidence.session_evidence} empty="暂无相似会话快照。" />
          {evidence.notes.length > 0 ? (
            <p className="text-[0.72rem] leading-5 text-[color:var(--ink-faint)]">{evidence.notes.join(" ")}</p>
          ) : null}
        </>
      )}
    </div>
  );
}

function EvidenceList({ title, items, empty }: { title: string; items: WorkbenchEvidenceItem[]; empty: string }) {
  return (
    <div>
      <p className="label-mini">{title}</p>
      <div className="mt-2 space-y-2">
        {items.length > 0 ? (
          items.map((item) => <EvidenceCard key={item.reference_key} item={item} />)
        ) : (
          <p className="surface-sunken p-3 text-[0.82rem] text-[color:var(--ink-muted)]">{empty}</p>
        )}
      </div>
    </div>
  );
}

function EvidenceCard({ item }: { item: WorkbenchEvidenceItem }) {
  return (
    <div className="rounded-[var(--r-md)] border border-[color:var(--line-soft)] bg-[color:var(--bg-paper)] p-3.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="chip chip-accent">{item.label}</span>
          <span className={`chip ${confidenceTone(item.confidence_tier)}`}>
            {confidenceLabel(item.confidence_tier)}
          </span>
        </div>
        <span className="num text-[0.65rem] uppercase tracking-[0.2em] text-[color:var(--ink-faint)]">
          {item.reference_key}
        </span>
      </div>
      <p className="mt-2.5 text-[0.85rem] leading-6 text-[color:var(--ink-body)]">{item.prompt_excerpt}</p>
      <p className="mt-2 text-[0.72rem] leading-5 text-[color:var(--ink-faint)]">{item.relationship}</p>
      {item.scenario_tags.length > 0 ? (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {item.scenario_tags.map((tag, index) => (
            <span key={`${tag}-${index}`} className="chip text-[0.65rem]">
              {tag}
            </span>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function confidenceLabel(tier: WorkbenchEvidenceItem["confidence_tier"]) {
  if (tier === "high") return "高置信近邻";
  if (tier === "medium") return "中置信近邻";
  return "弱近邻";
}

function confidenceTone(tier: WorkbenchEvidenceItem["confidence_tier"]) {
  if (tier === "high") return "chip-success";
  if (tier === "medium") return "chip-warn";
  return "";
}

function StatusTile({
  label,
  value,
  detail,
  tone = "default",
}: {
  label: string;
  value: string;
  detail: string;
  tone?: "default" | "success";
}) {
  const valueClass =
    tone === "success" ? "text-[color:var(--success-ink)]" : "text-[color:var(--ink-strong)]";
  return (
    <div className="status-tile">
      <p className="label-mini">{label}</p>
      <p className={`mt-1 text-lg ${valueClass} num`}>{value}</p>
      <p className="mt-0.5 text-[0.72rem] text-[color:var(--ink-muted)]">{detail}</p>
    </div>
  );
}

function MetricCard({
  label,
  value,
  compact = false,
}: {
  label: string;
  value: string | number;
  compact?: boolean;
}) {
  return (
    <div className="surface-flat px-3 py-2.5">
      <p className="label-mini text-[0.62rem]">{label}</p>
      <p
        className={
          compact
            ? "num mt-1 text-lg text-[color:var(--ink-strong)]"
            : "num mt-1 text-2xl text-[color:var(--ink-strong)]"
        }
      >
        {value}
      </p>
    </div>
  );
}

function MilestoneCard({ milestone }: { milestone: WorkbenchMilestone }) {
  const statusLabel =
    milestone.status === "completed" ? "已完成" : milestone.status === "current" ? "进行中" : "等待";

  let toneClasses: string;
  let chipClasses: string;
  let barClasses: string;

  if (milestone.status === "completed") {
    toneClasses = "border-[color:var(--success-soft)] bg-[color:var(--success-soft)]/55 text-[color:var(--success-ink)]";
    chipClasses = "chip chip-success";
    barClasses = "bar-fill bar-fill-success";
  } else if (milestone.status === "current") {
    toneClasses = "border-[color:var(--accent-soft)] bg-[color:var(--accent-soft)]/55 text-[color:var(--accent-ink)]";
    chipClasses = "chip chip-accent";
    barClasses = "bar-fill";
  } else {
    toneClasses = "border-[color:var(--line-soft)] bg-[color:var(--bg-raised)] text-[color:var(--ink-muted)]";
    chipClasses = "chip";
    barClasses = "bar-fill bg-[color:var(--ink-faint)]";
  }

  return (
    <div className={`rounded-[var(--r-md)] border p-3 ${toneClasses}`}>
      <div className="flex items-center justify-between gap-2">
        <p className="num text-base text-[color:var(--ink-strong)]">Q{milestone.milestone}</p>
        <span className={chipClasses}>
          {milestone.snapshot_expected ? "snapshot" : statusLabel}
        </span>
      </div>
      <div className="bar-track mt-2.5">
        <div className={barClasses} style={{ width: `${milestone.progress_percent}%` }} />
      </div>
      <p className="num mt-1.5 text-[0.7rem] opacity-80">
        {milestone.question_delta > 0 ? `还差 ${milestone.question_delta} 题` : "快照点已覆盖"}
      </p>
    </div>
  );
}

function TagGroup({ title, items, empty }: { title: string; items: string[]; empty: string }) {
  return (
    <div>
      <p className="label-mini">{title}</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {items.length > 0 ? (
          items.map((item) => (
            <span key={item} className="chip">
              {item}
            </span>
          ))
        ) : (
          <span className="chip text-[color:var(--ink-faint)]">{empty}</span>
        )}
      </div>
    </div>
  );
}
