"use client";

import { useEffect, useMemo, useState } from "react";

import {
  archiveTemplate,
  configureAI,
  createTemplate,
  deleteTemplate,
  getAIConfigStatus,
  getClusterOverview,
  listAdminSessions,
  listItemInstances,
  listTemplates,
  previewRewrite,
  saveClusterLabelOverride,
  type RuntimeAIConfig,
  type Question,
  type RewritePreviewBundle,
  type ClusterOverview,
  type SessionHistoryEntry,
  updateTemplate,
} from "@/lib/api";

const defaultOptions = [
  { key: "strongly_disagree", text: "非常不同意", score: -1 },
  { key: "disagree", text: "不同意", score: -0.5 },
  { key: "neutral", text: "不确定 / 看情况", score: 0 },
  { key: "agree", text: "同意", score: 0.5 },
  { key: "strongly_agree", text: "非常同意", score: 1 },
];

export function AdminClient() {
  const [sessions, setSessions] = useState<SessionHistoryEntry[]>([]);
  const [templates, setTemplates] = useState<Question[]>([]);
  const [instances, setInstances] = useState<Question[]>([]);
  const [clusterOverview, setClusterOverview] = useState<ClusterOverview | null>(null);
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [compareLeftId, setCompareLeftId] = useState("");
  const [compareRightId, setCompareRightId] = useState("");
  const [preview, setPreview] = useState<RewritePreviewBundle | null>(null);
  const [feedback, setFeedback] = useState("");
  const [aiConfig, setAiConfig] = useState<RuntimeAIConfig>({
    provider: "deepseek",
    model: "deepseek-chat",
    base_url: "https://api.deepseek.com",
    api_key: "",
  });
  const [aiStatus, setAiStatus] = useState<{
    configured: boolean;
    provider?: string | null;
    model?: string | null;
    base_url?: string | null;
  }>({ configured: false });
  const [overrideForm, setOverrideForm] = useState({
    cluster_index: "0",
    name: "",
    narrative_label: "",
  });
  const [form, setForm] = useState({
    template_id: "",
    prompt: "",
    layer: "core",
    dimension_weights: '{"execution_drive": 0.7, "planning_preference": 0.3}',
    subdimension_weights: "{}",
    module_affinities: "{}",
    scenario_tags: "project,high_stakes",
    discrimination: "1.45",
    difficulty: "0",
  });

  async function load() {
    const [sessionPayload, templatePayload, instancePayload, clusterPayload, aiStatusPayload] = await Promise.all([
      listAdminSessions(),
      listTemplates(),
      listItemInstances(),
      getClusterOverview(),
      getAIConfigStatus(),
    ]);
    setSessions(sessionPayload.sessions);
    setTemplates(templatePayload.items);
    setInstances(instancePayload.items);
    setClusterOverview(clusterPayload);
    setAiStatus(aiStatusPayload);
    if (!selectedSessionId && sessionPayload.sessions[0]) {
      setSelectedSessionId(sessionPayload.sessions[0].session_id);
    }
    if (!selectedTemplateId && templatePayload.items[0]) {
      setSelectedTemplateId(templatePayload.items[0].id);
    }
  }

  useEffect(() => {
    let cancelled = false;
    void Promise.all([listAdminSessions(), listTemplates(), listItemInstances(), getClusterOverview(), getAIConfigStatus()])
      .then(([sessionPayload, templatePayload, instancePayload, clusterPayload, aiStatusPayload]) => {
        if (cancelled) return;
        setSessions(sessionPayload.sessions);
        setTemplates(templatePayload.items);
        setInstances(instancePayload.items);
        setClusterOverview(clusterPayload);
        setAiStatus(aiStatusPayload);
        setSelectedSessionId((current) => current || sessionPayload.sessions[0]?.session_id || "");
        setSelectedTemplateId((current) => current || templatePayload.items[0]?.id || "");
        setCompareLeftId((current) => current || instancePayload.items[0]?.id || "");
        setCompareRightId((current) => current || instancePayload.items[1]?.id || instancePayload.items[0]?.id || "");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedSession = useMemo(
    () => sessions.find((session) => session.session_id === selectedSessionId),
    [selectedSessionId, sessions]
  );
  const leftInstance = useMemo(() => instances.find((item) => item.id === compareLeftId), [compareLeftId, instances]);
  const rightInstance = useMemo(() => instances.find((item) => item.id === compareRightId), [compareRightId, instances]);

  async function handlePreview() {
    if (!selectedSessionId || !selectedTemplateId) return;
    const response = await previewRewrite({
      session_id: selectedSessionId,
      item_id: selectedTemplateId,
      style_hint: "更高压、更具体、更能拉开差异的现实场景",
    });
    setPreview(response.preview);
    setFeedback(response.message);
  }

  async function handleConfigureAI() {
    const response = await configureAI(aiConfig);
    setFeedback(response.message);
    setAiConfig((current) => ({ ...current, api_key: "" }));
    await load();
  }

  async function handleCreateTemplate() {
    const payload = {
      prompt: form.prompt,
      question_type: "likert_5",
      layer: form.layer,
      dimension_weights: JSON.parse(form.dimension_weights) as Record<string, number>,
      subdimension_weights: JSON.parse(form.subdimension_weights) as Record<string, number>,
      module_affinities: JSON.parse(form.module_affinities) as Record<string, number>,
      discrimination: Number(form.discrimination),
      difficulty: Number(form.difficulty),
      scenario_tags: form.scenario_tags.split(",").map((item) => item.trim()).filter(Boolean),
      is_anchor: false,
      allow_rewrite: true,
      options: defaultOptions,
    };

    const response = await createTemplate(payload);
    setFeedback(`已创建模板 ${response.item.id}`);
    setForm((current) => ({ ...current, prompt: "", template_id: response.item.id }));
    await load();
  }

  async function handleUpdateTemplate() {
    if (!form.template_id) {
      setFeedback("请先在模板库中选一个模板再更新。");
      return;
    }
    const payload = {
      prompt: form.prompt,
      question_type: "likert_5",
      layer: form.layer,
      dimension_weights: JSON.parse(form.dimension_weights) as Record<string, number>,
      subdimension_weights: JSON.parse(form.subdimension_weights) as Record<string, number>,
      module_affinities: JSON.parse(form.module_affinities) as Record<string, number>,
      discrimination: Number(form.discrimination),
      difficulty: Number(form.difficulty),
      scenario_tags: form.scenario_tags.split(",").map((item) => item.trim()).filter(Boolean),
      is_anchor: false,
      allow_rewrite: true,
      options: defaultOptions,
    };
    const response = await updateTemplate(form.template_id, payload);
    setFeedback(`已更新模板 ${response.item.id}`);
    await load();
  }

  async function handleArchiveTemplate(templateId: string) {
    await archiveTemplate(templateId);
    setFeedback(`已归档模板 ${templateId}`);
    await load();
  }

  async function handleDeleteTemplate(templateId: string) {
    await deleteTemplate(templateId);
    setFeedback(`已删除模板 ${templateId}`);
    await load();
  }

  async function handleSaveOverride() {
    if (!clusterOverview) return;
    await saveClusterLabelOverride({
      version: clusterOverview.current_version,
      cluster_index: Number(overrideForm.cluster_index),
      name: overrideForm.name,
      narrative_label: overrideForm.narrative_label,
    });
    setFeedback(`已保存 ${clusterOverview.current_version} 的标签修订`);
    await load();
  }

  function loadTemplateIntoEditor(template: Question) {
    setForm((current) => ({
      ...current,
      template_id: template.id,
      prompt: template.prompt,
      layer: template.layer,
      scenario_tags: template.scenario_tags.join(","),
    }));
  }

  return (
    <main className="session-shell">
      <section className="mx-auto max-w-7xl space-y-8">
        <div className="rounded-[2.4rem] border border-white/10 bg-white/6 p-8 backdrop-blur-2xl">
          <p className="label-mini">Admin</p>
          <h1 className="mt-3 text-5xl text-white">题库与实例管理台</h1>
          <p className="mt-4 max-w-3xl text-slate-300">
            这里可以查看短期会话、模板、实例化题目，并直接触发真实模型改写预览。题目区分度和细分纤维都在这里往上推。
          </p>
          {feedback ? <p className="mt-5 rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-cyan-100">{feedback}</p> : null}
        </div>

        <section className="grid gap-8 xl:grid-cols-[0.92fr_1.08fr]">
          <div className="space-y-8">
            <div className="glass-card">
              <p className="label-mini">AI Control</p>
              <h2 className="mt-3 text-3xl text-white">本地 AI 配置</h2>
              <p className="mt-4 max-w-3xl text-slate-300">
                这个面板走独立的 localhost-only 管理 API。配置成功后，普通测试入口会直接消费这里保存的服务端配置，不再在浏览器里存 API Key。
              </p>
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <label className="block">
                  <span className="mb-2 block text-sm text-slate-300">Provider</span>
                  <input
                    className="field"
                    value={aiConfig.provider}
                    onChange={(event) => setAiConfig((current) => ({ ...current, provider: event.target.value }))}
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm text-slate-300">Model</span>
                  <input
                    className="field"
                    value={aiConfig.model}
                    onChange={(event) => setAiConfig((current) => ({ ...current, model: event.target.value }))}
                  />
                </label>
              </div>
              <div className="mt-4 grid gap-4 md:grid-cols-[1.25fr_0.75fr]">
                <label className="block">
                  <span className="mb-2 block text-sm text-slate-300">Base URL</span>
                  <input
                    className="field"
                    value={aiConfig.base_url}
                    onChange={(event) => setAiConfig((current) => ({ ...current, base_url: event.target.value }))}
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-sm text-slate-300">API Key</span>
                  <input
                    className="field"
                    type="password"
                    value={aiConfig.api_key}
                    onChange={(event) => setAiConfig((current) => ({ ...current, api_key: event.target.value }))}
                    placeholder="仅在当前内存里保存"
                  />
                </label>
              </div>
              <div className="mt-5 rounded-2xl border border-white/10 bg-black/20 p-4 text-sm text-slate-300">
                {aiStatus.configured ? (
                  <span>
                    当前已配置：{aiStatus.provider ?? "--"} / {aiStatus.model ?? "--"} / {aiStatus.base_url ?? "--"}
                  </span>
                ) : (
                  <span>当前还没有可用的 AI 服务端配置，公开入口会自动回退到本地摘要。</span>
                )}
              </div>
              <div className="mt-4 flex flex-wrap gap-3">
                <button className="rounded-full bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950" onClick={() => void handleConfigureAI()}>
                  保存并测试 AI 配置
                </button>
              </div>
            </div>

            <div className="glass-card">
              <p className="label-mini">Cluster Overview</p>
              <h2 className="mt-3 text-3xl text-white">聚类概览与版本轨迹</h2>
              <div className="mt-5 grid gap-4 md:grid-cols-3">
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/70">Current Version</p>
                  <p className="mt-3 text-2xl text-white">{clusterOverview?.current_version ?? "--"}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/70">Sample Size</p>
                  <p className="mt-3 text-2xl text-white">{clusterOverview?.sample_size ?? 0}</p>
                </div>
                <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                  <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/70">Labels</p>
                  <p className="mt-3 text-sm leading-7 text-white">{clusterOverview?.labels.join(" / ") ?? "--"}</p>
                </div>
              </div>
              <div className="mt-5 space-y-3">
                {clusterOverview?.training_history.map((version) => (
                  <div key={version.version} className="rounded-2xl border border-cyan-300/10 bg-cyan-300/6 p-4">
                    <div className="flex items-center justify-between gap-4">
                      <p className="text-sm text-white">{version.version}</p>
                      <span className="text-xs text-slate-300">{version.sample_size} samples</span>
                    </div>
                    <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/8">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-cyan-300 to-indigo-400"
                        style={{ width: `${Math.min(100, version.sample_size * 4)}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-6 rounded-2xl border border-white/10 bg-black/20 p-4">
                <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/70">Manual Label Override</p>
                <div className="mt-4 grid gap-3 md:grid-cols-3">
                  <input className="field" value={overrideForm.cluster_index} onChange={(event) => setOverrideForm((current) => ({ ...current, cluster_index: event.target.value }))} placeholder="cluster index" />
                  <input className="field" value={overrideForm.name} onChange={(event) => setOverrideForm((current) => ({ ...current, name: event.target.value }))} placeholder="显示名称" />
                  <input className="field" value={overrideForm.narrative_label} onChange={(event) => setOverrideForm((current) => ({ ...current, narrative_label: event.target.value }))} placeholder="叙事标签" />
                </div>
                <button className="mt-4 rounded-full bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950" onClick={() => void handleSaveOverride()}>
                  保存标签修订
                </button>
                {clusterOverview?.label_overrides.length ? (
                  <div className="mt-4 flex flex-wrap gap-2">
                    {clusterOverview.label_overrides.map((item) => (
                      <span key={`${item.version}-${item.cluster_index}`} className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-200">
                        #{item.cluster_index} {item.name}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
              <div className="mt-6 rounded-2xl border border-white/10 bg-black/20 p-4">
                <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/70">Scatter</p>
                <div className="mt-4 overflow-hidden rounded-2xl border border-white/8 bg-[#07101c] p-3">
                  <svg viewBox="0 0 320 240" className="h-[240px] w-full">
                    <line x1="20" y1="120" x2="300" y2="120" stroke="rgba(255,255,255,0.12)" />
                    <line x1="160" y1="20" x2="160" y2="220" stroke="rgba(255,255,255,0.12)" />
                    {clusterOverview?.scatter_points.map((point) => {
                      const x = 160 + point.x * 34;
                      const y = 120 - point.y * 34;
                      const radius = Math.max(4, Math.min(10, point.question_count / 4));
                      return (
                        <g key={point.session_id}>
                          <circle cx={x} cy={y} r={radius} fill="rgba(103,232,249,0.72)" />
                          <title>{`${point.cluster_name} · ${point.question_count}题 · ${point.confidence}`}</title>
                        </g>
                      );
                    })}
                  </svg>
                </div>
              </div>
            </div>

            <div className="glass-card">
              <p className="label-mini">Rewrite Preview</p>
              <h2 className="mt-3 text-3xl text-white">受限改写预览</h2>
              <div className="mt-5 space-y-4">
                <select className="field" value={selectedSessionId} onChange={(event) => setSelectedSessionId(event.target.value)}>
                  <option value="">选择会话</option>
                  {sessions.map((session) => (
                    <option key={session.session_id} value={session.session_id}>
                      {session.session_id} · {session.question_count} 题
                    </option>
                  ))}
                </select>
                <select className="field" value={selectedTemplateId} onChange={(event) => setSelectedTemplateId(event.target.value)}>
                  <option value="">选择模板</option>
                  {templates.slice(0, 50).map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.id} · {template.layer}
                    </option>
                  ))}
                </select>
                <button className="rounded-full bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950" onClick={() => void handlePreview()}>
                  生成改写预览
                </button>
              </div>
              {preview ? (
                <div className="mt-5 rounded-[1.4rem] border border-cyan-300/15 bg-cyan-300/8 p-4">
                  <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/80">
                    {preview.selected.generation_mode} / {preview.selected.validator_passed ? "validator_passed" : "fallback"}
                  </p>
                  <p className="mt-3 text-base leading-7 text-white">{preview.selected.rewritten_prompt}</p>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {preview.selected.reasons.map((reason) => (
                      <span key={reason} className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-200">
                        {reason}
                      </span>
                    ))}
                  </div>
                  <div className="mt-5 space-y-3">
                    {preview.candidates.map((candidate, index) => (
                      <div key={`${candidate.rewritten_prompt}-${index}`} className="rounded-xl border border-white/8 bg-black/20 p-3">
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-xs uppercase tracking-[0.25em] text-cyan-200/70">
                            Candidate {index + 1} · {candidate.score.toFixed(2)}
                          </p>
                          <span className="text-xs text-slate-300">{candidate.generation_mode}</span>
                        </div>
                        <p className="mt-2 text-sm leading-6 text-white">{candidate.rewritten_prompt}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {selectedSession ? (
                <p className="mt-4 text-xs text-slate-400">
                  当前会话：{selectedSession.session_id} · {selectedSession.narrative_label ?? "未命名"}
                </p>
              ) : null}
            </div>

            <div className="glass-card">
              <p className="label-mini">Template Forge</p>
              <h2 className="mt-3 text-3xl text-white">新增高区分度模板</h2>
              <div className="mt-5 space-y-4">
                <textarea
                  className="field min-h-32"
                  placeholder="请输入更高区分度的题面"
                  value={form.prompt}
                  onChange={(event) => setForm((current) => ({ ...current, prompt: event.target.value }))}
                />
                <input
                  className="field"
                  placeholder="模板 ID（更新时使用）"
                  value={form.template_id}
                  onChange={(event) => setForm((current) => ({ ...current, template_id: event.target.value }))}
                />
                <input className="field" value={form.layer} onChange={(event) => setForm((current) => ({ ...current, layer: event.target.value }))} />
                <input className="field" value={form.dimension_weights} onChange={(event) => setForm((current) => ({ ...current, dimension_weights: event.target.value }))} />
                <input className="field" value={form.subdimension_weights} onChange={(event) => setForm((current) => ({ ...current, subdimension_weights: event.target.value }))} />
                <input className="field" value={form.module_affinities} onChange={(event) => setForm((current) => ({ ...current, module_affinities: event.target.value }))} />
                <input className="field" value={form.scenario_tags} onChange={(event) => setForm((current) => ({ ...current, scenario_tags: event.target.value }))} />
                <div className="grid grid-cols-2 gap-4">
                  <input className="field" value={form.discrimination} onChange={(event) => setForm((current) => ({ ...current, discrimination: event.target.value }))} />
                  <input className="field" value={form.difficulty} onChange={(event) => setForm((current) => ({ ...current, difficulty: event.target.value }))} />
                </div>
                <div className="flex flex-wrap gap-3">
                  <button className="rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950" onClick={() => void handleCreateTemplate()}>
                    创建模板
                  </button>
                  <button className="rounded-full border border-white/15 px-5 py-3 text-sm text-white" onClick={() => void handleUpdateTemplate()}>
                    更新模板
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="space-y-8">
            <div className="glass-card">
              <p className="label-mini">Template Library</p>
              <h2 className="mt-3 text-3xl text-white">模板库</h2>
              <div className="mt-5 grid gap-3 max-h-[360px] overflow-y-auto">
                {templates.map((template) => (
                  <div key={template.id} className="rounded-2xl border border-white/8 bg-black/20 p-4 text-left">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/70">
                          {template.layer} {template.archived ? " / archived" : ""}
                        </p>
                        <p className="mt-2 text-base leading-7 text-white">{template.prompt}</p>
                      </div>
                      <span className="rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300">
                        {template.id}
                      </span>
                    </div>
                    <div className="mt-4 flex flex-wrap gap-3">
                      <button className="rounded-full border border-white/15 px-4 py-2 text-xs text-white" onClick={() => loadTemplateIntoEditor(template)}>
                        载入编辑器
                      </button>
                      <button className="rounded-full border border-amber-300/20 bg-amber-300/10 px-4 py-2 text-xs text-amber-100" onClick={() => void handleArchiveTemplate(template.id)}>
                        归档
                      </button>
                      <button className="rounded-full border border-rose-300/20 bg-rose-300/10 px-4 py-2 text-xs text-rose-100" onClick={() => void handleDeleteTemplate(template.id)}>
                        删除
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="glass-card">
              <p className="label-mini">Generated Instances</p>
              <h2 className="mt-3 text-3xl text-white">最近实例题</h2>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                <select className="field" value={compareLeftId} onChange={(event) => setCompareLeftId(event.target.value)}>
                  <option value="">左侧实例</option>
                  {instances.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.id}
                    </option>
                  ))}
                </select>
                <select className="field" value={compareRightId} onChange={(event) => setCompareRightId(event.target.value)}>
                  <option value="">右侧实例</option>
                  {instances.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.id}
                    </option>
                  ))}
                </select>
              </div>
              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
                  <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/70">Left</p>
                  <p className="mt-3 text-sm leading-6 text-white">{leftInstance?.prompt ?? "请选择实例"}</p>
                </div>
                <div className="rounded-2xl border border-white/8 bg-black/20 p-4">
                  <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/70">Right</p>
                  <p className="mt-3 text-sm leading-6 text-white">{rightInstance?.prompt ?? "请选择实例"}</p>
                </div>
              </div>
              <div className="mt-5 grid gap-3 max-h-[360px] overflow-y-auto">
                {instances.map((item) => (
                  <div key={item.id} className="rounded-2xl border border-cyan-300/10 bg-cyan-300/6 p-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/80">
                        {item.generation_mode} / {item.layer}
                      </p>
                      <span className="text-xs text-slate-300">{item.template_id}</span>
                    </div>
                    <p className="mt-3 text-base leading-7 text-white">{item.prompt}</p>
                    <div className="mt-3 flex flex-wrap gap-4 text-xs text-slate-300">
                      <span>质量分 {item.quality_score?.toFixed(2) ?? "--"}</span>
                      <span>相似惩罚 {item.similarity_penalty?.toFixed(2) ?? "--"}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}
