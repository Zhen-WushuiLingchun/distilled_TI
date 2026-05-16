"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import {
  archiveTemplate,
  configureAI,
  createGalgameStoryTemplate,
  createInvite,
  createTemplate,
  deleteGalgameStoryTemplate,
  deleteTemplate,
  cleanupGalgameAssets,
  generateGalgameAsset,
  generateGalgameStoryTemplateAssets,
  getAIConfigStatus,
  getGalgameAssetStatus,
  getClusterOverview,
  getUserRecommendations,
  listGalgameStoryTemplates,
  listInvites,
  listAdminSessions,
  listItemInstances,
  listTemplates,
  listUserRelationships,
  listUsers,
  listVectorSyncFailures,
  previewRewrite,
  reindexVectors,
  saveClusterLabelOverride,
  searchSimilarGalgameTurns,
  searchSimilarSessions,
  searchSimilarTemplates,
  type GalgameStoryTemplate,
  type GalgameAssetReference,
  type GalgameAssetStatus,
  type ClusterOverview,
  type InviteCode,
  type Question,
  type RewritePreviewBundle,
  type RuntimeAIConfig,
  type SessionHistoryEntry,
  type UserProfile,
  type UserRecommendation,
  type VectorReindexResponse,
  type VectorSearchHit,
  type VectorSyncFailure,
  updateTemplate,
  updateGalgameStoryTemplate,
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
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [invites, setInvites] = useState<InviteCode[]>([]);
  const [relationships, setRelationships] = useState<Array<{ relationship_id: string; source_user_id: string; target_user_id: string; relationship_type: string; created_at: string }>>([]);
  const [recommendations, setRecommendations] = useState<UserRecommendation[]>([]);
  const [recommendationsEnabled, setRecommendationsEnabled] = useState(false);
  const [templates, setTemplates] = useState<Question[]>([]);
  const [instances, setInstances] = useState<Question[]>([]);
  const [storyTemplates, setStoryTemplates] = useState<GalgameStoryTemplate[]>([]);
  const [assetStatus, setAssetStatus] = useState<GalgameAssetStatus | null>(null);
  const [lastGeneratedAssets, setLastGeneratedAssets] = useState<Record<string, GalgameAssetReference>>({});
  const [clusterOverview, setClusterOverview] = useState<ClusterOverview | null>(null);
  const [vectorFailures, setVectorFailures] = useState<VectorSyncFailure[]>([]);
  const [preview, setPreview] = useState<RewritePreviewBundle | null>(null);
  const [similarHits, setSimilarHits] = useState<VectorSearchHit[]>([]);
  const [similarSessionHits, setSimilarSessionHits] = useState<VectorSearchHit[]>([]);
  const [similarTurnHits, setSimilarTurnHits] = useState<VectorSearchHit[]>([]);
  const [lastReindex, setLastReindex] = useState<VectorReindexResponse | null>(null);
  const [feedback, setFeedback] = useState("");

  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [similarTemplateId, setSimilarTemplateId] = useState("");
  const [similarSessionId, setSimilarSessionId] = useState("");
  const [similarPrompt, setSimilarPrompt] = useState("");
  const [selectedUserId, setSelectedUserId] = useState("");
  const [inviteForm, setInviteForm] = useState({ created_by_user_id: "", label: "Campus batch", max_uses: "10" });
  const [vectorScope, setVectorScope] = useState<"templates" | "instances" | "sessions" | "galgame_turns" | "all">("all");
  const [similarTurnPrompt, setSimilarTurnPrompt] = useState("");
  const [assetForce, setAssetForce] = useState(false);
  const [assetIncludeCharacter, setAssetIncludeCharacter] = useState(false);
  const [storyTemplateForm, setStoryTemplateForm] = useState({
    template_id: "",
    name: "雨天后的社团活动室",
    description: "更接近 AI-GAL 的自由续写：校园群像、突发事件、关系张力和分支选择。",
    location: "雨刚停的社团活动室",
    speaker: "同桌",
    character_key: "desk_mate",
    background_key: "rainy_clubroom",
    background_prompt: "rainy campus clubroom after class, warm lamps, visual novel background",
    character_prompt: "classmate in casual school outfit, expressive eyes, visual novel portrait",
    style_prompt: "像可玩的 galgame，允许悬疑、轻喜剧、暧昧和突发事件；不要写成问卷。",
    scenario_tags: "campus,relationship,team_mode",
    active: true,
  });

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
  const selectedUser = useMemo(
    () => users.find((item) => item.user_id === selectedUserId),
    [users, selectedUserId]
  );

  async function fetchAdminState() {
    const [
      sessionPayload,
      userPayload,
      invitePayload,
      relationshipPayload,
      templatePayload,
      instancePayload,
      clusterPayload,
      aiStatusPayload,
      failurePayload,
      storyTemplatePayload,
      assetStatusPayload,
    ] =
      await Promise.all([
        listAdminSessions(),
        listUsers(),
        listInvites(),
        listUserRelationships(),
        listTemplates(),
        listItemInstances(),
        getClusterOverview(),
        getAIConfigStatus(),
        listVectorSyncFailures(),
        listGalgameStoryTemplates(true),
        getGalgameAssetStatus(),
      ]);
    return {
      sessionPayload,
      userPayload,
      invitePayload,
      relationshipPayload,
      templatePayload,
      instancePayload,
      clusterPayload,
      aiStatusPayload,
      failurePayload,
      storyTemplatePayload,
      assetStatusPayload,
    };
  }

  const applyAdminState = useCallback((payload: Awaited<ReturnType<typeof fetchAdminState>>) => {
    const {
      sessionPayload,
      userPayload,
      invitePayload,
      relationshipPayload,
      templatePayload,
      instancePayload,
      clusterPayload,
      aiStatusPayload,
      failurePayload,
      storyTemplatePayload,
      assetStatusPayload,
    } = payload;
    setSessions(sessionPayload.sessions);
    setUsers(userPayload.items);
    setInvites(invitePayload.items);
    setRelationships(relationshipPayload.items);
    setTemplates(templatePayload.items);
    setInstances(instancePayload.items);
    setStoryTemplates(storyTemplatePayload.items);
    setAssetStatus(assetStatusPayload);
    setClusterOverview(clusterPayload);
    setAiStatus(aiStatusPayload);
    setVectorFailures(failurePayload.items);
    setSelectedSessionId((current) => current || sessionPayload.sessions[0]?.session_id || "");
    setSimilarSessionId((current) => current || sessionPayload.sessions[0]?.session_id || "");
    setSelectedUserId((current) => current || userPayload.items[0]?.user_id || "");
    setSelectedTemplateId((current) => current || templatePayload.items[0]?.id || "");
    setSimilarTemplateId((current) => current || templatePayload.items[0]?.id || "");
  }, []);

  async function load() {
    applyAdminState(await fetchAdminState());
  }

  useEffect(() => {
    let cancelled = false;
    void fetchAdminState().then((payload) => {
      if (cancelled) return;
      applyAdminState(payload);
    });
    return () => {
      cancelled = true;
    };
  }, [applyAdminState]);

  async function handleConfigureAI() {
    const response = await configureAI(aiConfig);
    setFeedback(response.message);
    setAiConfig((current) => ({ ...current, api_key: "" }));
    await load();
  }

  async function handleCreateInvite() {
    const invite = await createInvite({
      created_by_user_id: inviteForm.created_by_user_id || null,
      label: inviteForm.label,
      max_uses: Number(inviteForm.max_uses),
    });
    setFeedback(`Created invite ${invite.code}`);
    await load();
  }

  async function handleRecommendations() {
    if (!selectedUserId) return;
    const response = await getUserRecommendations(selectedUserId, 6);
    setRecommendationsEnabled(response.enabled);
    setRecommendations(response.items);
    setFeedback(response.enabled ? `Loaded ${response.items.length} hidden recommendations` : "Recommendation feature flag is disabled");
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

  async function handleSimilarTurnSearch() {
    const prompt = similarTurnPrompt.trim();
    if (!prompt) return;
    const response = await searchSimilarGalgameTurns({ prompt, topK: 6 });
    setSimilarTurnHits(response.hits);
    setFeedback(response.hits.length ? `Found ${response.hits.length} similar story-turn hits` : "No similar story-turns above threshold");
  }

  function storyTemplatePayload() {
    return {
      name: storyTemplateForm.name,
      description: storyTemplateForm.description,
      location: storyTemplateForm.location,
      speaker: storyTemplateForm.speaker,
      character_key: storyTemplateForm.character_key,
      background_key: storyTemplateForm.background_key,
      background_prompt: storyTemplateForm.background_prompt,
      character_prompt: storyTemplateForm.character_prompt,
      style_prompt: storyTemplateForm.style_prompt,
      scenario_tags: storyTemplateForm.scenario_tags.split(",").map((item) => item.trim()).filter(Boolean),
      active: storyTemplateForm.active,
    };
  }

  async function handleCreateStoryTemplate() {
    const template = await createGalgameStoryTemplate(storyTemplatePayload());
    setStoryTemplateForm((current) => ({ ...current, template_id: template.template_id }));
    setFeedback(`Created story template ${template.template_id}`);
    await load();
  }

  async function handleUpdateStoryTemplate() {
    if (!storyTemplateForm.template_id) return;
    const template = await updateGalgameStoryTemplate(storyTemplateForm.template_id, storyTemplatePayload());
    setFeedback(`Updated story template ${template.template_id}`);
    await load();
  }

  async function handleDeleteStoryTemplate(templateId: string) {
    await deleteGalgameStoryTemplate(templateId);
    setFeedback(`Deleted story template ${templateId}`);
    await load();
  }

  async function handleGenerateAsset(kind: "background" | "character") {
    const key = kind === "background" ? storyTemplateForm.background_key : storyTemplateForm.character_key;
    const prompt = kind === "background" ? storyTemplateForm.background_prompt : storyTemplateForm.character_prompt;
    const response = await generateGalgameAsset({
      kind,
      key,
      prompt,
      force: assetForce,
    });
    setLastGeneratedAssets(response.assets);
    setFeedback(`Generated ${Object.keys(response.assets).join(", ") || kind} asset`);
    await load();
  }

  async function handleGenerateStoryTemplateAssets() {
    if (!storyTemplateForm.template_id) return;
    const response = await generateGalgameStoryTemplateAssets(storyTemplateForm.template_id, {
      include_character: assetIncludeCharacter,
      force: assetForce,
    });
    setLastGeneratedAssets(response.assets);
    setFeedback(`Generated assets for ${storyTemplateForm.template_id}: ${Object.keys(response.assets).join(", ")}`);
    await load();
  }

  async function handleCleanupAssets() {
    const response = await cleanupGalgameAssets();
    setFeedback(`Cleaned ${response.deleted_count} generated assets; ${response.remaining_count} files remain`);
    await load();
  }

  function loadStoryTemplate(template: GalgameStoryTemplate) {
    setStoryTemplateForm({
      template_id: template.template_id,
      name: template.name,
      description: template.description,
      location: template.location,
      speaker: template.speaker,
      character_key: template.character_key,
      background_key: template.background_key,
      background_prompt: template.background_prompt,
      character_prompt: template.character_prompt,
      style_prompt: template.style_prompt,
      scenario_tags: template.scenario_tags.join(","),
      active: template.active,
    });
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
      return <p className="num mt-2 text-[0.78rem] text-[color:var(--ink-faint)]">No hits</p>;
    }
    return (
      <div className="mt-2 space-y-1.5">
        {hits.map((hit) => (
          <div
            key={`${hit.object_id}-${hit.object_type}`}
            className="rounded-[var(--r-sm)] border border-[color:var(--line-soft)] bg-[color:var(--bg-sunken)] p-2.5"
          >
            <div className="num flex items-center justify-between gap-2 text-[0.7rem] text-[color:var(--ink-muted)]">
              <span>
                {hit.object_type} / {hit.score.toFixed(3)}
                {typeof hit.snapshot_milestone === "number" ? ` / m${hit.snapshot_milestone}` : ""}
              </span>
              <span className="truncate">{hit.session_id ?? hit.template_id ?? hit.instance_id ?? hit.object_id}</span>
            </div>
            <p className="mt-1.5 text-[0.82rem] leading-5 text-[color:var(--ink-body)]">{hit.prompt_excerpt}</p>
            {typeof hit.rerank_score === "number" ? (
              <p className="num mt-1 text-[0.7rem] text-[color:var(--ink-faint)]">rerank {hit.rerank_score.toFixed(3)}</p>
            ) : null}
          </div>
        ))}
      </div>
    );
  }

  return (
    <main className="cockpit-shell">
      <section className="relative z-10 mx-auto max-w-7xl space-y-5">
        <header className="panel fade-rise p-6 md:p-8">
          <p className="label-mini">Admin</p>
          <h1 className="mt-2 text-3xl md:text-4xl">Question and Vector Console</h1>
          {feedback ? (
            <p className="num mt-3 rounded-[var(--r-md)] border border-[color:var(--accent-soft)] bg-[color:var(--accent-soft)]/55 px-3.5 py-2.5 text-sm text-[color:var(--accent-ink)]">
              {feedback}
            </p>
          ) : null}
        </header>

        <section className="grid gap-5 xl:grid-cols-2">
          {/* === LEFT COLUMN === */}
          <div className="space-y-5">
            {/* AI */}
            <div className="panel fade-rise space-y-3 p-5 md:p-6">
              <p className="label-mini">AI</p>
              <input className="field" value={aiConfig.provider} onChange={(event) => setAiConfig((current) => ({ ...current, provider: event.target.value }))} placeholder="provider" />
              <input className="field" value={aiConfig.model} onChange={(event) => setAiConfig((current) => ({ ...current, model: event.target.value }))} placeholder="model" />
              <input className="field" value={aiConfig.base_url} onChange={(event) => setAiConfig((current) => ({ ...current, base_url: event.target.value }))} placeholder="base url" />
              <input className="field" type="password" value={aiConfig.api_key} onChange={(event) => setAiConfig((current) => ({ ...current, api_key: event.target.value }))} placeholder="api key" />
              <p className="num text-[0.82rem] text-[color:var(--ink-muted)]">
                {aiStatus.configured ? `${aiStatus.provider} / ${aiStatus.model} / ${aiStatus.base_url}` : "AI is not configured yet"}
              </p>
              <button className="btn btn-primary" onClick={() => void handleConfigureAI()}>
                Save and test AI config
              </button>
            </div>

            {/* Story engine */}
            <div className="panel fade-rise space-y-3 p-5 md:p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="label-mini">Story Engine</p>
                  <h2 className="mt-1.5 text-xl">AI-GAL style templates</h2>
                </div>
                <span className="chip">{storyTemplates.length} templates</span>
              </div>
              <p className="text-[0.82rem] leading-5 text-[color:var(--ink-muted)]">
                这里控制剧情主题、角色和背景素材提示。测量题只作为隐藏种子，剧情生成不应写成问卷。
              </p>
              <div className="grid gap-2.5">
                <input className="field" value={storyTemplateForm.template_id} onChange={(event) => setStoryTemplateForm((current) => ({ ...current, template_id: event.target.value }))} placeholder="template id for update" />
                <input className="field" value={storyTemplateForm.name} onChange={(event) => setStoryTemplateForm((current) => ({ ...current, name: event.target.value }))} placeholder="story name" />
                <textarea className="field min-h-20" value={storyTemplateForm.description} onChange={(event) => setStoryTemplateForm((current) => ({ ...current, description: event.target.value }))} placeholder="outline / premise" />
                <div className="grid gap-2.5 md:grid-cols-2">
                  <input className="field" value={storyTemplateForm.location} onChange={(event) => setStoryTemplateForm((current) => ({ ...current, location: event.target.value }))} placeholder="location" />
                  <input className="field" value={storyTemplateForm.speaker} onChange={(event) => setStoryTemplateForm((current) => ({ ...current, speaker: event.target.value }))} placeholder="speaker" />
                </div>
                <div className="grid gap-2.5 md:grid-cols-2">
                  <input className="field" value={storyTemplateForm.background_key} onChange={(event) => setStoryTemplateForm((current) => ({ ...current, background_key: event.target.value }))} placeholder="background key" />
                  <input className="field" value={storyTemplateForm.character_key} onChange={(event) => setStoryTemplateForm((current) => ({ ...current, character_key: event.target.value }))} placeholder="character key" />
                </div>
                <textarea className="field min-h-20" value={storyTemplateForm.background_prompt} onChange={(event) => setStoryTemplateForm((current) => ({ ...current, background_prompt: event.target.value }))} placeholder="background prompt" />
                <textarea className="field min-h-20" value={storyTemplateForm.character_prompt} onChange={(event) => setStoryTemplateForm((current) => ({ ...current, character_prompt: event.target.value }))} placeholder="character prompt" />
                <textarea className="field min-h-24" value={storyTemplateForm.style_prompt} onChange={(event) => setStoryTemplateForm((current) => ({ ...current, style_prompt: event.target.value }))} placeholder="generation style" />
                <input className="field" value={storyTemplateForm.scenario_tags} onChange={(event) => setStoryTemplateForm((current) => ({ ...current, scenario_tags: event.target.value }))} placeholder="scenario tags, comma separated" />
                <label className="flex items-center gap-2 text-sm text-[color:var(--ink-muted)]">
                  <input
                    type="checkbox"
                    checked={storyTemplateForm.active}
                    onChange={(event) => setStoryTemplateForm((current) => ({ ...current, active: event.target.checked }))}
                  />
                  active
                </label>
                <div className="flex flex-wrap gap-2.5">
                  <button className="btn btn-primary" onClick={() => void handleCreateStoryTemplate()}>
                    Create story template
                  </button>
                  <button className="btn btn-ghost" onClick={() => void handleUpdateStoryTemplate()}>
                    Update selected
                  </button>
                </div>
              </div>
              <div className="surface-sunken p-3.5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="label-mini">Asset Pipeline</p>
                    <p className="mt-1 text-[0.82rem] leading-5 text-[color:var(--ink-muted)]">
                      真实体验应走 SD WebUI 或兼容图片 API。Fallback SVG 只用于无模型时兜底。
                    </p>
                  </div>
                  <span className="chip">
                    {assetStatus?.backend ?? "unknown"} / {assetStatus?.sdwebui_available ? "SD online" : "SD offline"}
                  </span>
                </div>
                <p className="num mt-2 text-[0.76rem] text-[color:var(--ink-faint)]">
                  enabled {String(assetStatus?.generation_enabled ?? false)} · bg {assetStatus?.background_count ?? 0} · char {assetStatus?.character_count ?? 0} · {assetStatus?.base_url ?? "-"}
                </p>
                <p className="num mt-1 text-[0.76rem] text-[color:var(--ink-faint)]">
                  cache {assetStatus?.cache_total_count ?? 0}/{assetStatus?.cache_max_files ?? 0} files · {(((assetStatus?.cache_total_bytes ?? 0) / 1024 / 1024)).toFixed(1)} MB · max age {assetStatus?.cache_max_age_days ?? 0}d
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <button className="btn btn-ghost px-3 py-1.5 text-xs" onClick={() => void handleGenerateAsset("background")}>
                    Generate BG from form
                  </button>
                  <button className="btn btn-ghost px-3 py-1.5 text-xs" onClick={() => void handleGenerateAsset("character")}>
                    Generate Sprite from form
                  </button>
                  <button className="btn btn-primary px-3 py-1.5 text-xs" disabled={!storyTemplateForm.template_id} onClick={() => void handleGenerateStoryTemplateAssets()}>
                    Pre-generate selected template
                  </button>
                  <button className="btn btn-ghost px-3 py-1.5 text-xs" onClick={() => void handleCleanupAssets()}>
                    Cleanup cache
                  </button>
                </div>
                <div className="mt-3 flex flex-wrap gap-4 text-xs text-[color:var(--ink-muted)]">
                  <label className="flex items-center gap-1.5">
                    <input type="checkbox" checked={assetForce} onChange={(event) => setAssetForce(event.target.checked)} />
                    force overwrite
                  </label>
                  <label className="flex items-center gap-1.5">
                    <input type="checkbox" checked={assetIncludeCharacter} onChange={(event) => setAssetIncludeCharacter(event.target.checked)} />
                    include character on template batch
                  </label>
                </div>
                {Object.keys(lastGeneratedAssets).length ? (
                  <div className="mt-3 grid gap-2 md:grid-cols-2">
                    {Object.entries(lastGeneratedAssets).map(([kind, asset]) => (
                      <div key={`${kind}-${asset.key}`} className="rounded-[var(--r-md)] bg-[color:var(--bg-paper)] p-2.5">
                        <p className="num text-[0.72rem] text-[color:var(--ink-muted)]">{kind} / {asset.status} / {asset.source}</p>
                        <p className="mt-1 truncate text-xs text-[color:var(--ink-body)]">{asset.url ?? "no url"}</p>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
              <div className="space-y-2">
                {storyTemplates.map((template) => (
                  <div key={template.template_id} className="surface-sunken p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="num text-[0.72rem] text-[color:var(--ink-muted)]">
                        {template.template_id} / {template.active ? "active" : "inactive"}
                      </p>
                      <span className="chip">{template.background_key} · {template.character_key}</span>
                    </div>
                    <p className="mt-1.5 text-sm font-medium text-[color:var(--ink-strong)]">{template.name}</p>
                    <p className="mt-1 text-[0.82rem] leading-5 text-[color:var(--ink-muted)]">{template.description}</p>
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      <button className="btn btn-ghost px-3 py-1 text-xs" onClick={() => loadStoryTemplate(template)}>
                        Load
                      </button>
                      <button className="btn btn-danger px-3 py-1 text-xs" onClick={() => void handleDeleteStoryTemplate(template.template_id)}>
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Users and invites */}
            <div className="panel fade-rise space-y-3 p-5 md:p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="label-mini">Users / Invites</p>
                  <h2 className="mt-1.5 text-xl">Anonymous relationship graph</h2>
                </div>
                <span className="chip">{users.length} users</span>
              </div>
              <div className="surface-sunken p-3.5">
                <p className="label-mini">Create Invite</p>
                <div className="mt-2.5 grid gap-2">
                  <select
                    className="field"
                    value={inviteForm.created_by_user_id}
                    onChange={(event) => setInviteForm((current) => ({ ...current, created_by_user_id: event.target.value }))}
                  >
                    <option value="">root invite</option>
                    {users.map((user) => (
                      <option key={user.user_id} value={user.user_id}>
                        {user.handle}
                      </option>
                    ))}
                  </select>
                  <input
                    className="field"
                    value={inviteForm.label}
                    onChange={(event) => setInviteForm((current) => ({ ...current, label: event.target.value }))}
                    placeholder="label"
                  />
                  <input
                    className="field"
                    value={inviteForm.max_uses}
                    onChange={(event) => setInviteForm((current) => ({ ...current, max_uses: event.target.value }))}
                    placeholder="max uses"
                  />
                  <button className="btn btn-primary" onClick={() => void handleCreateInvite()}>
                    Create invite
                  </button>
                </div>
                <div className="mt-3 space-y-1.5">
                  {invites.slice(0, 6).map((invite) => (
                    <p key={invite.code} className="num text-[0.76rem] text-[color:var(--ink-muted)]">
                      {invite.code} / {invite.use_count}/{invite.max_uses} / {invite.label}
                    </p>
                  ))}
                </div>
              </div>

              <div className="surface-sunken p-3.5">
                <p className="label-mini">Hidden Recommendations</p>
                <select className="field mt-2.5" value={selectedUserId} onChange={(event) => setSelectedUserId(event.target.value)}>
                  <option value="">select user</option>
                  {users.map((user) => (
                    <option key={user.user_id} value={user.user_id}>
                      {user.handle}
                    </option>
                  ))}
                </select>
                <button className="btn btn-ghost mt-2.5" onClick={() => void handleRecommendations()}>
                  Load hidden candidates
                </button>
                <p className="mt-2 text-[0.78rem] text-[color:var(--ink-faint)]">
                  Feature flag: {recommendationsEnabled ? "enabled" : "disabled"} · Selected: {selectedUser?.handle ?? "none"}
                </p>
                {recommendations.length ? (
                  <div className="mt-2 space-y-1.5">
                    {recommendations.map((item) => (
                      <p key={item.candidate_user_id} className="num text-[0.76rem] text-[color:var(--ink-body)]">
                        {item.candidate_handle} / {item.score.toFixed(3)} / {item.shared_cluster_name ?? "cross-cluster"}
                      </p>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-[0.78rem] text-[color:var(--ink-faint)]">
                    No candidates shown. Public UI remains disabled.
                  </p>
                )}
              </div>

              <div className="surface-sunken p-3.5">
                <p className="label-mini">Relationship Edges</p>
                {relationships.length ? (
                  relationships.slice(0, 8).map((edge) => (
                    <p key={edge.relationship_id} className="num mt-1.5 text-[0.72rem] text-[color:var(--ink-muted)]">
                      {edge.relationship_type}: {edge.source_user_id.slice(0, 12)} → {edge.target_user_id.slice(0, 12)}
                    </p>
                  ))
                ) : (
                  <p className="mt-1.5 text-[0.82rem] text-[color:var(--ink-faint)]">No relationship edges yet</p>
                )}
              </div>
            </div>

            {/* Vectors */}
            <div className="panel fade-rise space-y-3 p-5 md:p-6">
              <p className="label-mini">Vectors</p>
              <div className="flex gap-2.5">
                <select className="field" value={vectorScope} onChange={(event) => setVectorScope(event.target.value as "templates" | "instances" | "sessions" | "galgame_turns" | "all")}>
                  <option value="all">all</option>
                  <option value="templates">templates</option>
                  <option value="instances">instances</option>
                  <option value="sessions">sessions</option>
                  <option value="galgame_turns">galgame turns</option>
                </select>
                <button className="btn btn-primary shrink-0" onClick={() => void handleVectorReindex()}>
                  Reindex
                </button>
              </div>
              {lastReindex ? (
                <p className="num text-[0.82rem] text-[color:var(--ink-muted)]">
                  {lastReindex.scope} / indexed {lastReindex.indexed_count} / failed {lastReindex.failed_count}
                </p>
              ) : null}

              <div className="surface-sunken p-3.5">
                <p className="label-mini">Similar Templates</p>
                <select className="field mt-2.5" value={similarTemplateId} onChange={(event) => setSimilarTemplateId(event.target.value)}>
                  <option value="">search by template id</option>
                  {templates.slice(0, 80).map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.id}
                    </option>
                  ))}
                </select>
                <textarea className="field mt-2.5 min-h-24" value={similarPrompt} onChange={(event) => setSimilarPrompt(event.target.value)} placeholder="or type a raw prompt" />
                <button className="btn btn-ghost mt-2.5" onClick={() => void handleSimilarTemplateSearch()}>
                  Search similar templates
                </button>
                {renderHits(similarHits)}
              </div>

              <div className="surface-sunken p-3.5">
                <p className="label-mini">Similar Sessions</p>
                <select className="field mt-2.5" value={similarSessionId} onChange={(event) => setSimilarSessionId(event.target.value)}>
                  <option value="">search by session id</option>
                  {sessions.map((session) => (
                    <option key={session.session_id} value={session.session_id}>
                      {session.session_id} / {session.question_count} questions
                    </option>
                  ))}
                </select>
                <button className="btn btn-ghost mt-2.5" onClick={() => void handleSimilarSessionSearch()}>
                  Search similar sessions
                </button>
                {renderHits(similarSessionHits)}
              </div>

              <div className="surface-sunken p-3.5">
                <p className="label-mini">Similar Story Turns</p>
                <textarea
                  className="field mt-2.5 min-h-24"
                  value={similarTurnPrompt}
                  onChange={(event) => setSimilarTurnPrompt(event.target.value)}
                  placeholder="输入一段玩家自由台词或剧情片段，检索相近的 galgame_turns"
                />
                <button className="btn btn-ghost mt-2.5" onClick={() => void handleSimilarTurnSearch()}>
                  Search similar story turns
                </button>
                {renderHits(similarTurnHits)}
              </div>

              <div className="surface-sunken p-3.5">
                <p className="label-mini">Sync Failures</p>
                {vectorFailures.length ? (
                  vectorFailures.map((failure) => (
                    <p key={failure.failure_id} className="num mt-1.5 text-[0.78rem] text-[color:var(--ink-body)]">
                      {failure.object_type} / {failure.operation} / {failure.error_message}
                    </p>
                  ))
                ) : (
                  <p className="mt-1.5 text-[0.82rem] text-[color:var(--ink-faint)]">No failure records</p>
                )}
              </div>
            </div>

            {/* Rewrite */}
            <div className="panel fade-rise space-y-3 p-5 md:p-6">
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
              <button className="btn btn-primary" onClick={() => void handlePreview()}>
                Generate rewrite preview
              </button>
              {preview ? (
                <div className="rounded-[var(--r-md)] border border-[color:var(--accent-soft)] bg-[color:var(--accent-soft)]/40 p-3.5">
                  <p className="text-[0.88rem] leading-6 text-[color:var(--ink-body)]">{preview.selected.rewritten_prompt}</p>
                  <p className="num mt-2 text-[0.72rem] text-[color:var(--ink-muted)]">
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
              {selectedSession ? (
                <p className="num text-[0.72rem] text-[color:var(--ink-faint)]">
                  Current session: {selectedSession.session_id} / {selectedSession.narrative_label ?? "unnamed"}
                </p>
              ) : null}
            </div>
          </div>

          {/* === RIGHT COLUMN === */}
          <div className="space-y-5">
            {/* Templates */}
            <div className="panel fade-rise space-y-3 p-5 md:p-6">
              <p className="label-mini">Templates</p>
              <textarea className="field min-h-32" value={form.prompt} onChange={(event) => setForm((current) => ({ ...current, prompt: event.target.value }))} placeholder="prompt" />
              <input className="field" value={form.template_id} onChange={(event) => setForm((current) => ({ ...current, template_id: event.target.value }))} placeholder="template id for update" />
              <input className="field" value={form.layer} onChange={(event) => setForm((current) => ({ ...current, layer: event.target.value }))} placeholder="layer" />
              <input className="field" value={form.dimension_weights} onChange={(event) => setForm((current) => ({ ...current, dimension_weights: event.target.value }))} />
              <input className="field" value={form.subdimension_weights} onChange={(event) => setForm((current) => ({ ...current, subdimension_weights: event.target.value }))} />
              <input className="field" value={form.module_affinities} onChange={(event) => setForm((current) => ({ ...current, module_affinities: event.target.value }))} />
              <input className="field" value={form.scenario_tags} onChange={(event) => setForm((current) => ({ ...current, scenario_tags: event.target.value }))} />
              <div className="grid grid-cols-2 gap-2.5">
                <input className="field" value={form.discrimination} onChange={(event) => setForm((current) => ({ ...current, discrimination: event.target.value }))} />
                <input className="field" value={form.difficulty} onChange={(event) => setForm((current) => ({ ...current, difficulty: event.target.value }))} />
              </div>
              <div className="flex gap-2.5">
                <button className="btn btn-primary" onClick={() => void handleCreateTemplate()}>
                  Create
                </button>
                <button className="btn btn-ghost" onClick={() => void handleUpdateTemplate()}>
                  Update
                </button>
              </div>
              <div className="space-y-2">
                {templates.map((template) => (
                  <div key={template.id} className="surface-sunken p-3">
                    <p className="num text-[0.72rem] text-[color:var(--ink-muted)]">
                      {template.id} / {template.layer}
                      {template.archived ? " / archived" : ""}
                    </p>
                    <p className="mt-1.5 text-[0.85rem] leading-6 text-[color:var(--ink-body)]">{template.prompt}</p>
                    <div className="mt-2.5 flex flex-wrap gap-1.5">
                      <button
                        className="btn btn-ghost px-3 py-1 text-xs"
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
                      <button
                        className="btn px-3 py-1 text-xs"
                        style={{
                          background: "var(--warn-soft)",
                          color: "var(--warn-ink)",
                          borderColor: "rgba(184,128,31,0.25)",
                        }}
                        onClick={() => void handleArchiveTemplate(template.id)}
                      >
                        Archive
                      </button>
                      <button
                        className="btn btn-danger px-3 py-1 text-xs"
                        onClick={() => void handleDeleteTemplate(template.id)}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Clusters */}
            <div className="panel fade-rise space-y-3 p-5 md:p-6">
              <p className="label-mini">Clusters</p>
              <p className="num text-[0.85rem] text-[color:var(--ink-body)]">
                {clusterOverview ? `${clusterOverview.current_version} / samples ${clusterOverview.sample_size}` : "No cluster data"}
              </p>
              <div className="grid gap-2.5 md:grid-cols-3">
                <input className="field" value={overrideForm.cluster_index} onChange={(event) => setOverrideForm((current) => ({ ...current, cluster_index: event.target.value }))} placeholder="cluster index" />
                <input className="field" value={overrideForm.name} onChange={(event) => setOverrideForm((current) => ({ ...current, name: event.target.value }))} placeholder="display name" />
                <input className="field" value={overrideForm.narrative_label} onChange={(event) => setOverrideForm((current) => ({ ...current, narrative_label: event.target.value }))} placeholder="narrative label" />
              </div>
              <button className="btn btn-primary" onClick={() => void handleSaveOverride()}>
                Save cluster override
              </button>
              <div className="space-y-1.5">
                {clusterOverview?.training_history.map((item) => (
                  <p key={item.version} className="num text-[0.82rem] text-[color:var(--ink-muted)]">
                    {item.version} / {item.sample_size} samples
                  </p>
                ))}
              </div>
            </div>

            {/* Instances */}
            <div className="panel fade-rise space-y-2 p-5 md:p-6">
              <p className="label-mini">Instances</p>
              {instances.map((item) => (
                <div
                  key={item.id}
                  className="rounded-[var(--r-md)] border border-[color:var(--accent-soft)] bg-[color:var(--accent-soft)]/35 p-3"
                >
                  <p className="num text-[0.72rem] text-[color:var(--ink-muted)]">
                    {item.id} / {item.generation_mode} / {item.layer}
                  </p>
                  <p className="mt-1.5 text-[0.85rem] leading-6 text-[color:var(--ink-body)]">{item.prompt}</p>
                </div>
              ))}
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}
