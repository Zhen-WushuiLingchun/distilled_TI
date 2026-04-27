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
  listVectorSyncFailures,
  previewRewrite,
  reindexVectors,
  saveClusterLabelOverride,
  searchSimilarSessions,
  searchSimilarTemplates,
  type ClusterOverview,
  type Question,
  type RewritePreviewBundle,
  type RuntimeAIConfig,
  type SessionHistoryEntry,
  type VectorReindexResponse,
  type VectorSearchHit,
  type VectorSyncFailure,
  updateTemplate,
} from "@/lib/api";

const defaultOptions = [
  { key: "strongly_disagree", text: "Strongly disagree", score: -1 },
  { key: "disagree", text: "Disagree", score: -0.5 },
  { key: "neutral", text: "Neutral", score: 0 },
  { key: "agree", text: "Agree", score: 0.5 },
  { key: "strongly_agree", text: "Strongly agree", score: 1 },
];

export function AdminClient() {
  const [sessions, setSessions] = useState<SessionHistoryEntry[]>([]);
  const [templates, setTemplates] = useState<Question[]>([]);
  const [instances, setInstances] = useState<Question[]>([]);
  const [clusterOverview, setClusterOverview] = useState<ClusterOverview | null>(null);
  const [vectorFailures, setVectorFailures] = useState<VectorSyncFailure[]>([]);
  const [preview, setPreview] = useState<RewritePreviewBundle | null>(null);
  const [similarHits, setSimilarHits] = useState<VectorSearchHit[]>([]);
  const [similarSessionHits, setSimilarSessionHits] = useState<VectorSearchHit[]>([]);
  const [lastReindex, setLastReindex] = useState<VectorReindexResponse | null>(null);
  const [feedback, setFeedback] = useState("");

  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [similarTemplateId, setSimilarTemplateId] = useState("");
  const [similarSessionId, setSimilarSessionId] = useState("");
  const [similarPrompt, setSimilarPrompt] = useState("");
  const [vectorScope, setVectorScope] = useState<"templates" | "instances" | "sessions" | "all">("all");

  const [aiConfig, setAiConfig] = useState<RuntimeAIConfig>({
    provider: "siliconflow",
    model: "Qwen/Qwen3-32B",
    base_url: "https://api.siliconflow.cn/v1",
    api_key: "",
  });
  const [aiStatus, setAiStatus] = useState<{ configured: boolean; provider?: string | null; model?: string | null; base_url?: string | null }>({ configured: false });
  const [overrideForm, setOverrideForm] = useState({ cluster_index: "0", name: "", narrative_label: "" });
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

  const selectedSession = useMemo(
    () => sessions.find((item) => item.session_id === selectedSessionId),
    [sessions, selectedSessionId]
  );

  async function load() {
    const [sessionPayload, templatePayload, instancePayload, clusterPayload, aiStatusPayload, failurePayload] =
      await Promise.all([
        listAdminSessions(),
        listTemplates(),
        listItemInstances(),
        getClusterOverview(),
        getAIConfigStatus(),
        listVectorSyncFailures(),
      ]);
    setSessions(sessionPayload.sessions);
    setTemplates(templatePayload.items);
    setInstances(instancePayload.items);
    setClusterOverview(clusterPayload);
    setAiStatus(aiStatusPayload);
    setVectorFailures(failurePayload.items);
    setSelectedSessionId((current) => current || sessionPayload.sessions[0]?.session_id || "");
    setSimilarSessionId((current) => current || sessionPayload.sessions[0]?.session_id || "");
    setSelectedTemplateId((current) => current || templatePayload.items[0]?.id || "");
    setSimilarTemplateId((current) => current || templatePayload.items[0]?.id || "");
  }

  useEffect(() => {
    let cancelled = false;
    void Promise.all([
      listAdminSessions(),
      listTemplates(),
      listItemInstances(),
      getClusterOverview(),
      getAIConfigStatus(),
      listVectorSyncFailures(),
    ]).then(([sessionPayload, templatePayload, instancePayload, clusterPayload, aiStatusPayload, failurePayload]) => {
      if (cancelled) return;
      setSessions(sessionPayload.sessions);
      setTemplates(templatePayload.items);
      setInstances(instancePayload.items);
      setClusterOverview(clusterPayload);
      setAiStatus(aiStatusPayload);
      setVectorFailures(failurePayload.items);
      setSelectedSessionId((current) => current || sessionPayload.sessions[0]?.session_id || "");
      setSimilarSessionId((current) => current || sessionPayload.sessions[0]?.session_id || "");
      setSelectedTemplateId((current) => current || templatePayload.items[0]?.id || "");
      setSimilarTemplateId((current) => current || templatePayload.items[0]?.id || "");
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleConfigureAI() {
    const response = await configureAI(aiConfig);
    setFeedback(response.message);
    setAiConfig((current) => ({ ...current, api_key: "" }));
    await load();
  }

  async function handleVectorReindex() {
    const response = await reindexVectors(vectorScope);
    setLastReindex(response);
    setFeedback(`Reindex finished: ${response.scope} / indexed ${response.indexed_count} / failed ${response.failed_count}`);
    await load();
  }

  async function handleSimilarTemplateSearch() {
    const response = await searchSimilarTemplates({
      templateId: similarTemplateId || undefined,
      prompt: similarPrompt.trim() || undefined,
      topK: 6,
    });
    setSimilarHits(response.hits);
    setFeedback(response.hits.length ? `Found ${response.hits.length} similar template hits` : "No similar templates above threshold");
  }

  async function handleSimilarSessionSearch() {
    if (!similarSessionId) return;
    const response = await searchSimilarSessions({ sessionId: similarSessionId, topK: 5 });
    setSimilarSessionHits(response.hits);
    setFeedback(response.hits.length ? `Found ${response.hits.length} similar session hits` : "No similar sessions above threshold");
  }

  async function handlePreview() {
    if (!selectedSessionId || !selectedTemplateId) return;
    const response = await previewRewrite({
      session_id: selectedSessionId,
      item_id: selectedTemplateId,
      style_hint: "more specific, higher pressure, avoid generic phrasing",
    });
    setPreview(response.preview);
    setFeedback(response.message);
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
    setFeedback(`Created template ${response.item.id}`);
    await load();
  }

  async function handleUpdateTemplate() {
    if (!form.template_id) return;
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
    setFeedback(`Updated template ${response.item.id}`);
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
    setFeedback("Saved cluster label override");
    await load();
  }

  async function handleArchiveTemplate(templateId: string) {
    await archiveTemplate(templateId);
    setFeedback(`Archived ${templateId}`);
    await load();
  }

  async function handleDeleteTemplate(templateId: string) {
    await deleteTemplate(templateId);
    setFeedback(`Deleted ${templateId}`);
    await load();
  }

  function renderHits(hits: VectorSearchHit[]) {
    if (!hits.length) {
      return <p className="mt-3 text-sm text-slate-400">No hits</p>;
    }
    return (
      <div className="mt-3 space-y-2">
        {hits.map((hit) => (
          <div key={`${hit.object_id}-${hit.object_type}`} className="rounded-xl border border-white/8 bg-black/20 p-3">
            <div className="flex items-center justify-between gap-3 text-xs text-slate-300">
              <span>
                {hit.object_type} / {hit.score.toFixed(3)}
                {typeof hit.snapshot_milestone === "number" ? ` / m${hit.snapshot_milestone}` : ""}
              </span>
              <span>{hit.session_id ?? hit.template_id ?? hit.instance_id ?? hit.object_id}</span>
            </div>
            <p className="mt-2 text-sm leading-6 text-white">{hit.prompt_excerpt}</p>
            {typeof hit.rerank_score === "number" ? (
              <p className="mt-1 text-xs text-slate-400">rerank {hit.rerank_score.toFixed(3)}</p>
            ) : null}
          </div>
        ))}
      </div>
    );
  }

  return (
    <main className="session-shell">
      <section className="mx-auto max-w-7xl space-y-8">
        <div className="rounded-[2.4rem] border border-white/10 bg-white/6 p-8 backdrop-blur-2xl">
          <p className="label-mini">Admin</p>
          <h1 className="mt-3 text-5xl text-white">Question and Vector Console</h1>
          {feedback ? (
            <p className="mt-4 rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-sm text-cyan-100">{feedback}</p>
          ) : null}
        </div>

        <section className="grid gap-8 xl:grid-cols-2">
          <div className="space-y-8">
            <div className="glass-card space-y-4">
              <p className="label-mini">AI</p>
              <input className="field" value={aiConfig.provider} onChange={(event) => setAiConfig((current) => ({ ...current, provider: event.target.value }))} placeholder="provider" />
              <input className="field" value={aiConfig.model} onChange={(event) => setAiConfig((current) => ({ ...current, model: event.target.value }))} placeholder="model" />
              <input className="field" value={aiConfig.base_url} onChange={(event) => setAiConfig((current) => ({ ...current, base_url: event.target.value }))} placeholder="base url" />
              <input className="field" type="password" value={aiConfig.api_key} onChange={(event) => setAiConfig((current) => ({ ...current, api_key: event.target.value }))} placeholder="api key" />
              <p className="text-sm text-slate-300">{aiStatus.configured ? `${aiStatus.provider} / ${aiStatus.model} / ${aiStatus.base_url}` : "AI is not configured yet"}</p>
              <button className="rounded-full bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950" onClick={() => void handleConfigureAI()}>
                Save and test AI config
              </button>
            </div>

            <div className="glass-card space-y-4">
              <p className="label-mini">Vectors</p>
              <div className="flex gap-3">
                <select className="field" value={vectorScope} onChange={(event) => setVectorScope(event.target.value as "templates" | "instances" | "sessions" | "all")}>
                  <option value="all">all</option>
                  <option value="templates">templates</option>
                  <option value="instances">instances</option>
                  <option value="sessions">sessions</option>
                </select>
                <button className="rounded-full bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950" onClick={() => void handleVectorReindex()}>
                  Reindex
                </button>
              </div>
              {lastReindex ? <p className="text-sm text-slate-300">{lastReindex.scope} / indexed {lastReindex.indexed_count} / failed {lastReindex.failed_count}</p> : null}

              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/70">Similar Templates</p>
                <select className="field mt-3" value={similarTemplateId} onChange={(event) => setSimilarTemplateId(event.target.value)}>
                  <option value="">search by template id</option>
                  {templates.slice(0, 80).map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.id}
                    </option>
                  ))}
                </select>
                <textarea className="field mt-3 min-h-24" value={similarPrompt} onChange={(event) => setSimilarPrompt(event.target.value)} placeholder="or type a raw prompt" />
                <button className="mt-3 rounded-full border border-white/15 px-5 py-3 text-sm text-white" onClick={() => void handleSimilarTemplateSearch()}>
                  Search similar templates
                </button>
                {renderHits(similarHits)}
              </div>

              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/70">Similar Sessions</p>
                <select className="field mt-3" value={similarSessionId} onChange={(event) => setSimilarSessionId(event.target.value)}>
                  <option value="">search by session id</option>
                  {sessions.map((session) => (
                    <option key={session.session_id} value={session.session_id}>
                      {session.session_id} / {session.question_count} questions
                    </option>
                  ))}
                </select>
                <button className="mt-3 rounded-full border border-white/15 px-5 py-3 text-sm text-white" onClick={() => void handleSimilarSessionSearch()}>
                  Search similar sessions
                </button>
                {renderHits(similarSessionHits)}
              </div>

              <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
                <p className="text-xs uppercase tracking-[0.3em] text-cyan-200/70">Sync Failures</p>
                {vectorFailures.length ? (
                  vectorFailures.map((failure) => (
                    <p key={failure.failure_id} className="mt-2 text-sm text-slate-300">
                      {failure.object_type} / {failure.operation} / {failure.error_message}
                    </p>
                  ))
                ) : (
                  <p className="mt-2 text-sm text-slate-400">No failure records</p>
                )}
              </div>
            </div>

            <div className="glass-card space-y-4">
              <p className="label-mini">Rewrite</p>
              <select className="field" value={selectedSessionId} onChange={(event) => setSelectedSessionId(event.target.value)}>
                <option value="">select session</option>
                {sessions.map((session) => (
                  <option key={session.session_id} value={session.session_id}>
                    {session.session_id} / {session.question_count} questions
                  </option>
                ))}
              </select>
              <select className="field" value={selectedTemplateId} onChange={(event) => setSelectedTemplateId(event.target.value)}>
                <option value="">select template</option>
                {templates.slice(0, 80).map((template) => (
                  <option key={template.id} value={template.id}>
                    {template.id}
                  </option>
                ))}
              </select>
              <button className="rounded-full bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950" onClick={() => void handlePreview()}>
                Generate rewrite preview
              </button>
              {preview ? (
                <div className="rounded-2xl border border-cyan-300/15 bg-cyan-300/8 p-4">
                  <p className="text-sm text-white">{preview.selected.rewritten_prompt}</p>
                  <p className="mt-2 text-xs text-slate-300">
                    retrieval {preview.retrieval_context?.enabled ? "on" : "off"} / reranker {preview.retrieval_context?.reranker_applied ? "on" : "off"}
                  </p>
                  {preview.retrieval_context ? (
                    <div className="mt-3 grid gap-3 md:grid-cols-3">
                      <div>{renderHits(preview.retrieval_context.template_hits)}</div>
                      <div>{renderHits(preview.retrieval_context.item_instance_hits)}</div>
                      <div>{renderHits(preview.retrieval_context.rewrite_candidate_hits)}</div>
                    </div>
                  ) : null}
                </div>
              ) : null}
              {selectedSession ? <p className="text-xs text-slate-400">Current session: {selectedSession.session_id} / {selectedSession.narrative_label ?? "unnamed"}</p> : null}
            </div>
          </div>

          <div className="space-y-8">
            <div className="glass-card space-y-4">
              <p className="label-mini">Templates</p>
              <textarea className="field min-h-32" value={form.prompt} onChange={(event) => setForm((current) => ({ ...current, prompt: event.target.value }))} placeholder="prompt" />
              <input className="field" value={form.template_id} onChange={(event) => setForm((current) => ({ ...current, template_id: event.target.value }))} placeholder="template id for update" />
              <input className="field" value={form.layer} onChange={(event) => setForm((current) => ({ ...current, layer: event.target.value }))} placeholder="layer" />
              <input className="field" value={form.dimension_weights} onChange={(event) => setForm((current) => ({ ...current, dimension_weights: event.target.value }))} />
              <input className="field" value={form.subdimension_weights} onChange={(event) => setForm((current) => ({ ...current, subdimension_weights: event.target.value }))} />
              <input className="field" value={form.module_affinities} onChange={(event) => setForm((current) => ({ ...current, module_affinities: event.target.value }))} />
              <input className="field" value={form.scenario_tags} onChange={(event) => setForm((current) => ({ ...current, scenario_tags: event.target.value }))} />
              <div className="grid grid-cols-2 gap-3">
                <input className="field" value={form.discrimination} onChange={(event) => setForm((current) => ({ ...current, discrimination: event.target.value }))} />
                <input className="field" value={form.difficulty} onChange={(event) => setForm((current) => ({ ...current, difficulty: event.target.value }))} />
              </div>
              <div className="flex gap-3">
                <button className="rounded-full bg-white px-5 py-3 text-sm font-semibold text-slate-950" onClick={() => void handleCreateTemplate()}>
                  Create
                </button>
                <button className="rounded-full border border-white/15 px-5 py-3 text-sm text-white" onClick={() => void handleUpdateTemplate()}>
                  Update
                </button>
              </div>
              <div className="space-y-3">
                {templates.map((template) => (
                  <div key={template.id} className="rounded-xl border border-white/8 bg-black/20 p-3">
                    <p className="text-xs text-slate-300">
                      {template.id} / {template.layer}
                      {template.archived ? " / archived" : ""}
                    </p>
                    <p className="mt-2 text-sm text-white">{template.prompt}</p>
                    <div className="mt-3 flex gap-2">
                      <button
                        className="rounded-full border border-white/15 px-3 py-1 text-xs text-white"
                        onClick={() =>
                          setForm((current) => ({
                            ...current,
                            template_id: template.id,
                            prompt: template.prompt,
                            layer: template.layer,
                            scenario_tags: template.scenario_tags.join(","),
                          }))
                        }
                      >
                        Load
                      </button>
                      <button className="rounded-full border border-amber-300/20 bg-amber-300/10 px-3 py-1 text-xs text-amber-100" onClick={() => void handleArchiveTemplate(template.id)}>
                        Archive
                      </button>
                      <button className="rounded-full border border-rose-300/20 bg-rose-300/10 px-3 py-1 text-xs text-rose-100" onClick={() => void handleDeleteTemplate(template.id)}>
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="glass-card space-y-4">
              <p className="label-mini">Clusters</p>
              <p className="text-sm text-slate-300">{clusterOverview ? `${clusterOverview.current_version} / samples ${clusterOverview.sample_size}` : "No cluster data"}</p>
              <div className="grid gap-3 md:grid-cols-3">
                <input className="field" value={overrideForm.cluster_index} onChange={(event) => setOverrideForm((current) => ({ ...current, cluster_index: event.target.value }))} placeholder="cluster index" />
                <input className="field" value={overrideForm.name} onChange={(event) => setOverrideForm((current) => ({ ...current, name: event.target.value }))} placeholder="display name" />
                <input className="field" value={overrideForm.narrative_label} onChange={(event) => setOverrideForm((current) => ({ ...current, narrative_label: event.target.value }))} placeholder="narrative label" />
              </div>
              <button className="rounded-full bg-cyan-300 px-5 py-3 text-sm font-semibold text-slate-950" onClick={() => void handleSaveOverride()}>
                Save cluster override
              </button>
              <div className="space-y-2">
                {clusterOverview?.training_history.map((item) => (
                  <p key={item.version} className="text-sm text-slate-300">
                    {item.version} / {item.sample_size} samples
                  </p>
                ))}
              </div>
            </div>

            <div className="glass-card space-y-3">
              <p className="label-mini">Instances</p>
              {instances.map((item) => (
                <div key={item.id} className="rounded-xl border border-cyan-300/10 bg-cyan-300/6 p-3">
                  <p className="text-xs text-slate-300">
                    {item.id} / {item.generation_mode} / {item.layer}
                  </p>
                  <p className="mt-2 text-sm text-white">{item.prompt}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}
