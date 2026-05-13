import type { NamingStyle, ProjectionMode, SessionAccessBundle, UserAccessBundle } from "@/lib/runtime-store";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api";
const ADMIN_API_BASE_URL = process.env.NEXT_PUBLIC_ADMIN_API_BASE_URL ?? "http://127.0.0.1:8001/api";

export type QuestionOption = {
  key: string;
  text: string;
  score: number;
};

export type Question = {
  id: string;
  template_id?: string | null;
  prompt: string;
  question_type: string;
  layer: string;
  scenario_tags: string[];
  options: QuestionOption[];
  generation_mode?: string;
  validator_passed?: boolean;
  archived?: boolean;
  quality_score?: number | null;
  similarity_penalty?: number | null;
};

export type SessionState = {
  core_mu: Record<string, number>;
  core_sigma: Record<string, number>;
  sub_mu: Record<string, number>;
  sub_sigma: Record<string, number>;
  sub_counts: Record<string, number>;
  module_scores: Record<string, number>;
  module_counts: Record<string, number>;
  zeta: Record<string, number>;
  recent_item_ids: string[];
  dimension_counts: Record<string, number>;
  unlocked_subdimensions: string[];
  active_modules: string[];
  answers: Array<{
    item_id: string;
    option_key: string;
    mapped_score: number;
    predicted_score: number;
    residual: number;
    latency_ms: number | null;
  }>;
  question_count: number;
};

export type WorkbenchSignal = {
  key: string;
  label: string;
  value: number;
  confidence_percent: number;
  sample_count: number;
  detail?: string | null;
};

export type WorkbenchMilestone = {
  milestone: number;
  status: "completed" | "current" | "upcoming";
  question_delta: number;
  progress_percent: number;
  snapshot_expected: boolean;
};

export type WorkbenchCheckpoint = {
  question_count: number;
  report_ready: boolean;
  report_target: number;
  remaining_until_report: number;
  report_progress_percent: number;
  previous_milestone?: number | null;
  next_milestone?: number | null;
  milestone_progress_percent: number;
  snapshot_due_now: boolean;
  narrative: string;
  top_core_signals: WorkbenchSignal[];
  uncertainty_queue: WorkbenchSignal[];
  active_modules: WorkbenchSignal[];
  unlocked_subdimensions: WorkbenchSignal[];
  milestones: WorkbenchMilestone[];
};

export type WorkbenchEvidenceItem = {
  reference_key: string;
  object_type: "template" | "rewrite_candidate" | "item_instance" | "session_snapshot" | "galgame_turn";
  label: string;
  relationship: string;
  prompt_excerpt: string;
  confidence_tier: "high" | "medium" | "low";
  scenario_tags: string[];
  snapshot_milestone?: number | null;
};

export type WorkbenchEvidence = {
  enabled: boolean;
  current_question_id?: string | null;
  current_template_id?: string | null;
  vector_available: boolean;
  reranker_applied: boolean;
  item_evidence: WorkbenchEvidenceItem[];
  session_evidence: WorkbenchEvidenceItem[];
  notes: string[];
};

export type GalgameChoice = {
  key: string;
  text: string;
  option_key: string;
  score: number;
  tone: "direct" | "guarded" | "ambivalent" | string;
};

export type GalgameScene = {
  scene_id: string;
  session_id: string;
  item_id: string;
  template_id: string;
  title: string;
  location: string;
  mood: string;
  speaker: string;
  narrator_text: string;
  character_text: string;
  prompt_shadow: string;
  choices: GalgameChoice[];
  memory_fragments: string[];
  background_key: string;
  background_prompt: string;
  character_key: string;
  character_prompt: string;
  background_asset?: GalgameAssetReference | null;
  character_asset?: GalgameAssetReference | null;
  audio_asset?: GalgameAssetReference | null;
  story_template_id?: string | null;
  ai_generated: boolean;
  custom_input_enabled: boolean;
};

export type GalgameAssetReference = {
  kind: "background" | "character" | "audio";
  key: string;
  prompt: string;
  url?: string | null;
  source: "generated" | "fallback" | "external" | "none";
  status: "ready" | "disabled" | "failed" | "missing";
};

export type GalgameAssetStatus = {
  generation_enabled: boolean;
  backend: string;
  base_url: string;
  model: string;
  public_url_prefix: string;
  background_count: number;
  character_count: number;
  sdwebui_available: boolean;
  comfyui_available: boolean;
};

export type GalgameTextInference = {
  inferred_option_key?: string | null;
  confidence: number;
  reason: string;
  source: "none" | "rule" | "embedding" | "pairwise" | "llm" | "hybrid";
  option_scores: Array<{
    option_key: string;
    llm_score?: number | null;
    embedding_score?: number | null;
    pairwise_score?: number | null;
    fused_score: number;
    reason: string;
  }>;
  embedding_available: boolean;
  pairwise_available: boolean;
  llm_available: boolean;
  method_version: string;
};

export type GalgameSceneResult = {
  session_id: string;
  state: SessionState;
  can_generate_report: boolean;
  remaining_until_report: number;
  scene: GalgameScene | null;
  text_inference?: GalgameTextInference | null;
  workbench_checkpoint?: WorkbenchCheckpoint | null;
};

export type GalgameStoryTemplate = {
  template_id: string;
  owner_user_id?: string | null;
  name: string;
  description: string;
  location: string;
  speaker: string;
  character_key: string;
  background_key: string;
  background_prompt: string;
  character_prompt: string;
  style_prompt: string;
  scenario_tags: string[];
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type SessionSummary = {
  session_id: string;
  question_count: number;
  min_questions_for_report: number;
  max_questions_per_session: number;
  can_generate_report: boolean;
  remaining_until_report: number;
  current_item_id: string | null;
  current_template_id?: string | null;
  current_question?: Question | null;
  state: SessionState;
  workbench_checkpoint?: WorkbenchCheckpoint | null;
};

export type SessionStartResponse = SessionAccessBundle & {
  state: SessionState;
  question: Question;
  min_questions_for_report: number;
  max_questions_per_session: number;
  workbench_checkpoint?: WorkbenchCheckpoint | null;
};

export type SubmitResponse = {
  session_id: string;
  state: SessionState;
  can_generate_report: boolean;
  remaining_until_report: number;
  next_question: Question | null;
  workbench_checkpoint?: WorkbenchCheckpoint | null;
};

export type SessionReport = {
  session_id: string;
  question_count: number;
  can_exit_with_report: boolean;
  structural_labels: Array<{
    dimension: string;
    label: string;
    score: number;
  }>;
  narrative_label: string;
  ai_aliases: string[];
  ai_summary: string;
  uncertainty_summary: Record<string, number>;
  module_bars: Record<string, number>;
  core_bars: Record<string, number>;
  sub_bars: Record<string, number>;
  cluster_name: string;
  cluster_confidence: number;
  cluster_mix: Array<{
    cluster_index: number;
    cluster_name: string;
    narrative_label: string;
    weight: number;
    distance: number;
  }>;
  salient_subdimensions: string[];
  active_module_labels: string[];
  sub_insights: Array<{
    key: string;
    label: string;
    parent_dimension: string;
    parent_label: string;
    score: number;
    percent: number;
    sigma: number;
    sample_count: number;
    confidence_percent: number;
    confidence_label: string;
    direction_label: string;
    strength_label: string;
    evaluation: string;
    metaphor: string;
  }>;
  module_insights: Array<{
    key: string;
    label: string;
    score: number;
    percent: number;
    sample_count: number;
    confidence_percent: number;
    confidence_label: string;
    strength_label: string;
    evaluation: string;
    metaphor: string;
  }>;
  support_risk_flags: Array<{
    key: string;
    severity: "low" | "medium" | "high";
    label: string;
    evidence: string[];
    suggested_action: string;
    diagnostic: boolean;
  }>;
  current_state: SessionState;
};

export type SessionMap = {
  session_id: string;
  point: {
    x: number;
    y: number;
    dimensions: Record<string, number>;
    label?: string | null;
    kind?: string | null;
    cluster_name?: string | null;
  };
  confidence: number;
  answer_points: Array<{
    x: number;
    y: number;
    dimensions: Record<string, number>;
    label?: string | null;
    kind?: string | null;
    cluster_name?: string | null;
  }>;
  trajectory_points: Array<{
    x: number;
    y: number;
    dimensions: Record<string, number>;
    label?: string | null;
    kind?: string | null;
    cluster_name?: string | null;
  }>;
  cluster_centers: Array<{
    x: number;
    y: number;
    dimensions: Record<string, number>;
    label?: string | null;
    kind?: string | null;
    cluster_name?: string | null;
  }>;
  cluster_regions: Array<{
    cluster_index: number;
    cluster_name: string;
    x: number;
    y: number;
    rx: number;
    ry: number;
    angle: number;
  }>;
};

export type RuntimeAIConfig = {
  provider: string;
  model: string;
  base_url: string;
  api_key: string;
};

export type SessionHistoryEntry = {
  session_id: string;
  user_id?: string | null;
  user_handle?: string | null;
  status: string;
  question_count: number;
  can_generate_report: boolean;
  created_at: string;
  updated_at: string;
  cluster_name: string | null;
  narrative_label: string | null;
};

export type UserEvolutionEntry = {
  session_id: string;
  question_count: number;
  can_generate_report: boolean;
  cluster_name: string | null;
  narrative_label: string | null;
  core_mu: Record<string, number>;
  zeta: Record<string, number>;
  active_modules: string[];
  updated_at: string;
  core_delta_from_previous: Record<string, number>;
};

export type RewritePreview = {
  template_id: string;
  rewritten_prompt: string;
  generation_mode: "template" | "llm_rewrite" | "anchor" | "probe";
  validator_passed: boolean;
  score: number;
  reasons: string[];
  embedding_score_breakdown?: EmbeddingScoreBreakdown | null;
};

export type RewritePreviewBundle = {
  template_id: string;
  selected: RewritePreview;
  candidates: RewritePreview[];
  retrieval_context?: RewriteRetrievalContext | null;
};

export type EmbeddingScoreBreakdown = {
  enabled: boolean;
  source_similarity: number;
  source_distance_score: number;
  duplicate_similarity: number;
  duplicate_penalty: number;
  alignment_similarity: number;
  alignment_bonus: number;
  total: number;
};

export type VectorSearchHit = {
  object_id: string;
  object_type: "template" | "rewrite_candidate" | "item_instance" | "session_snapshot" | "galgame_turn";
  template_id?: string | null;
  instance_id?: string | null;
  session_id?: string | null;
  snapshot_milestone?: number | null;
  layer: string;
  generation_mode: string;
  prompt_excerpt: string;
  score: number;
  rerank_score?: number | null;
  scenario_tags: string[];
};

export type RewriteRetrievalContext = {
  enabled: boolean;
  reranker_applied: boolean;
  template_hits: VectorSearchHit[];
  item_instance_hits: VectorSearchHit[];
  rewrite_candidate_hits: VectorSearchHit[];
};

export type VectorReindexResponse = {
  scope: "templates" | "instances" | "sessions" | "galgame_turns" | "all";
  enabled: boolean;
  indexed_count: number;
  failed_count: number;
  failure_ids: string[];
};

export type VectorSearchResponse = {
  enabled: boolean;
  hits: VectorSearchHit[];
};

export type VectorSyncFailure = {
  failure_id: string;
  object_type: string;
  object_id: string;
  operation: string;
  error_message: string;
  payload_json: string;
  created_at: string;
};

export type ClusterVersionInfo = {
  version: string;
  sample_size: number;
  cluster_count: number;
  labels: string[];
  dataset_signature: string;
  created_at: string;
};

export type ClusterOverview = {
  current_version: string;
  sample_size: number;
  cluster_count: number;
  labels: string[];
  training_history: ClusterVersionInfo[];
  scatter_points: Array<{
    session_id: string;
    x: number;
    y: number;
    question_count: number;
    cluster_name: string;
    confidence: number;
  }>;
  label_overrides: Array<{
    version: string;
    cluster_index: number;
    name: string;
    narrative_label: string;
    updated_at: string;
  }>;
};

type JsonBody = Record<string, unknown>;
type RequestAuth = {
  sessionSecret?: string;
  deleteToken?: string;
  user?: UserAccessBundle;
};

async function request<T>(
  baseUrl: string,
  path: string,
  init?: RequestInit & { json?: JsonBody },
  auth?: RequestAuth
) {
  const headers = new Headers(init?.headers);
  if (init?.json) {
    headers.set("Content-Type", "application/json");
  }
  if (auth?.sessionSecret) {
    headers.set("X-Session-Secret", auth.sessionSecret);
  }
  if (auth?.deleteToken) {
    headers.set("X-Delete-Token", auth.deleteToken);
  }
  if (auth?.user) {
    headers.set("X-User-Id", auth.user.user_id);
    headers.set("X-User-Secret", auth.user.user_secret);
  }

  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers,
    body: init?.json ? JSON.stringify(init.json) : init?.body,
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const errorPayload = (await response.json()) as { detail?: string };
      detail = errorPayload.detail ?? detail;
    } catch {}
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

function publicRequest<T>(path: string, init?: RequestInit & { json?: JsonBody }, auth?: RequestAuth) {
  return request<T>(API_BASE_URL, path, init, auth);
}

function adminRequest<T>(path: string, init?: RequestInit & { json?: JsonBody }, auth?: RequestAuth) {
  return request<T>(ADMIN_API_BASE_URL, path, init, auth);
}

export type UserProfile = {
  user_id: string;
  handle: string;
  invite_code: string;
  invited_by_user_id?: string | null;
  email_registered: boolean;
  relationship_opt_in: boolean;
  recommendation_opt_in: boolean;
  created_at: string;
  updated_at: string;
};

export type InviteCode = {
  code: string;
  created_by_user_id?: string | null;
  label: string;
  max_uses: number;
  use_count: number;
  active: boolean;
  created_at: string;
  expires_at?: string | null;
};

export type UserRecommendation = {
  subject_user_id: string;
  candidate_user_id: string;
  candidate_handle: string;
  score: number;
  reason: string;
  shared_cluster_name?: string | null;
  via_relationship?: string | null;
};

export function redeemInvite(inviteCode: string, email: string) {
  return publicRequest<UserAccessBundle>("/invite/redeem", {
    method: "POST",
    json: { invite_code: inviteCode, email },
  });
}

export function claimInvite(user: UserAccessBundle, inviteCode: string) {
  return publicRequest<UserProfile>(
    "/user/invite/claim",
    {
      method: "POST",
      json: { invite_code: inviteCode },
    },
    { user }
  );
}

export function getCurrentUser(user: UserAccessBundle) {
  return publicRequest<UserProfile>("/user/me", undefined, { user });
}

export function updateCurrentUser(user: UserAccessBundle, payload: {
  relationship_opt_in?: boolean;
  recommendation_opt_in?: boolean;
}) {
  return publicRequest<UserProfile>(
    "/user/me",
    {
      method: "PATCH",
      json: payload,
    },
    { user }
  );
}

export function listUserSessions(user: UserAccessBundle) {
  return publicRequest<{ user: UserProfile; sessions: SessionHistoryEntry[] }>("/user/sessions", undefined, { user });
}

export function getUserEvolution(user: UserAccessBundle) {
  return publicRequest<{ user: UserProfile; items: UserEvolutionEntry[] }>("/user/evolution", undefined, { user });
}

export function listCurrentUserRecommendations(user: UserAccessBundle, limit = 5) {
  return publicRequest<{ enabled: boolean; items: UserRecommendation[] }>(
    `/user/recommendations?limit=${encodeURIComponent(String(limit))}`,
    undefined,
    { user }
  );
}

export function issueUserSessionAccess(user: UserAccessBundle, sessionId: string) {
  return publicRequest<SessionAccessBundle>(
    `/user/session/${sessionId}/access`,
    {
      method: "POST",
      json: {},
    },
    { user }
  );
}

export function listUserGalgameStoryTemplates(user: UserAccessBundle) {
  return publicRequest<{ items: GalgameStoryTemplate[] }>("/user/galgame/story-templates", undefined, { user });
}

export type GalgameStoryTemplatePayload = {
  name: string;
  description: string;
  location: string;
  speaker: string;
  character_key: string;
  background_key: string;
  background_prompt: string;
  character_prompt: string;
  style_prompt: string;
  scenario_tags: string[];
  active: boolean;
};

export function createUserGalgameStoryTemplate(user: UserAccessBundle, payload: GalgameStoryTemplatePayload) {
  return publicRequest<GalgameStoryTemplate>(
    "/user/galgame/story-templates",
    {
      method: "POST",
      json: payload,
    },
    { user }
  );
}

export function updateUserGalgameStoryTemplate(user: UserAccessBundle, templateId: string, payload: GalgameStoryTemplatePayload) {
  return publicRequest<GalgameStoryTemplate>(
    `/user/galgame/story-templates/${templateId}`,
    {
      method: "PUT",
      json: payload,
    },
    { user }
  );
}

export function deleteUserGalgameStoryTemplate(user: UserAccessBundle, templateId: string) {
  return publicRequest<{ deleted: boolean }>(
    `/user/galgame/story-templates/${templateId}`,
    {
      method: "DELETE",
    },
    { user }
  );
}

export function startSession(user?: UserAccessBundle | null) {
  return publicRequest<SessionStartResponse>("/session/start", {
    method: "POST",
    json: { mode: "core" },
  }, user ? { user } : undefined);
}

export function submitAnswer(access: SessionAccessBundle, itemId: string, optionKey: string, latencyMs: number) {
  return publicRequest<SubmitResponse>(
    "/response/submit",
    {
      method: "POST",
      json: {
        session_id: access.session_id,
        item_id: itemId,
        option_key: optionKey,
        latency_ms: latencyMs,
      },
    },
    { sessionSecret: access.session_secret }
  );
}

export function getNextQuestion(access: SessionAccessBundle) {
  return publicRequest<Question>(
    "/question/next",
    {
      method: "POST",
      json: { session_id: access.session_id },
    },
    { sessionSecret: access.session_secret }
  );
}

export function getSessionSummary(access: SessionAccessBundle) {
  return publicRequest<SessionSummary>(`/session/${access.session_id}/summary`, undefined, {
    sessionSecret: access.session_secret,
  });
}

export function getWorkbenchEvidence(access: SessionAccessBundle) {
  return publicRequest<WorkbenchEvidence>(`/session/${access.session_id}/workbench/evidence`, undefined, {
    sessionSecret: access.session_secret,
  });
}

export function getGalgameScene(access: SessionAccessBundle) {
  return publicRequest<GalgameScene>(`/session/${access.session_id}/galgame/scene`, undefined, {
    sessionSecret: access.session_secret,
  });
}

export function respondGalgameScene(
  access: SessionAccessBundle,
  payload: {
    item_id: string;
    scene_id: string;
    option_key: string;
    choice_text?: string;
    custom_text?: string;
    latency_ms?: number;
  }
) {
  return publicRequest<GalgameSceneResult>(
    `/session/${access.session_id}/galgame/respond`,
    {
      method: "POST",
      json: payload,
    },
    { sessionSecret: access.session_secret }
  );
}

export function getSessionReport(access: SessionAccessBundle) {
  return publicRequest<SessionReport>(`/session/${access.session_id}/report`, undefined, {
    sessionSecret: access.session_secret,
  });
}

export function generateSessionReport(access: SessionAccessBundle, namingStyle?: NamingStyle) {
  return publicRequest<SessionReport>(
    `/session/${access.session_id}/report`,
    {
      method: "POST",
      json: {
        naming_style: namingStyle ?? "auto",
      },
    },
    { sessionSecret: access.session_secret }
  );
}

export function getSessionMap(access: SessionAccessBundle, projectionMode: ProjectionMode = "auto") {
  return publicRequest<SessionMap>(
    `/session/${access.session_id}/map?projection_mode=${encodeURIComponent(projectionMode)}`,
    undefined,
    { sessionSecret: access.session_secret }
  );
}

export function deleteSession(access: SessionAccessBundle) {
  return publicRequest<{ deleted: boolean }>(`/session/${access.session_id}`, { method: "DELETE" }, {
    deleteToken: access.delete_token,
  });
}

export function configureAI(payload: RuntimeAIConfig) {
  return adminRequest<{ configured: boolean; tested: boolean; message: string; provider: string; model: string; base_url: string }>(
    "/ai/config",
    {
      method: "POST",
      json: payload,
    }
  );
}

export function getAIConfigStatus() {
  return adminRequest<{ configured: boolean; provider?: string | null; model?: string | null; base_url?: string | null }>(
    "/ai/config"
  );
}

export function issueAdminSessionAccess(sessionId: string) {
  return adminRequest<SessionAccessBundle>(`/session/${sessionId}/access`, {
    method: "POST",
    json: {},
  });
}

export function listAdminSessions() {
  return adminRequest<{ sessions: SessionHistoryEntry[] }>("/admin/sessions");
}

export function createInvite(payload: { created_by_user_id?: string | null; label?: string; max_uses?: number }) {
  return adminRequest<InviteCode>("/admin/invites", {
    method: "POST",
    json: payload,
  });
}

export function listGalgameStoryTemplates(includeInactive = true) {
  return adminRequest<{ items: GalgameStoryTemplate[] }>(
    `/admin/galgame/story-templates?include_inactive=${encodeURIComponent(String(includeInactive))}`
  );
}

export function createGalgameStoryTemplate(payload: Omit<GalgameStoryTemplate, "template_id" | "created_at" | "updated_at">) {
  return adminRequest<GalgameStoryTemplate>("/admin/galgame/story-templates", {
    method: "POST",
    json: payload as JsonBody,
  });
}

export function updateGalgameStoryTemplate(
  templateId: string,
  payload: Omit<GalgameStoryTemplate, "template_id" | "created_at" | "updated_at">
) {
  return adminRequest<GalgameStoryTemplate>(`/admin/galgame/story-templates/${encodeURIComponent(templateId)}`, {
    method: "PUT",
    json: payload as JsonBody,
  });
}

export function deleteGalgameStoryTemplate(templateId: string) {
  return adminRequest<{ deleted: boolean }>(`/admin/galgame/story-templates/${encodeURIComponent(templateId)}`, {
    method: "DELETE",
  });
}

export function getGalgameAssetStatus() {
  return adminRequest<GalgameAssetStatus>("/admin/galgame/assets/status");
}

export function generateGalgameAsset(payload: {
  kind: "background" | "character";
  key: string;
  prompt: string;
  force?: boolean;
}) {
  return adminRequest<{ assets: Record<string, GalgameAssetReference> }>("/admin/galgame/assets/generate", {
    method: "POST",
    json: payload,
  });
}

export function generateGalgameStoryTemplateAssets(
  templateId: string,
  payload: { include_character?: boolean; force?: boolean } = {}
) {
  return adminRequest<{ assets: Record<string, GalgameAssetReference> }>(
    `/admin/galgame/story-templates/${encodeURIComponent(templateId)}/assets`,
    {
      method: "POST",
      json: payload,
    }
  );
}

export function listInvites(limit = 100) {
  return adminRequest<{ items: InviteCode[] }>(`/admin/invites?limit=${encodeURIComponent(String(limit))}`);
}

export function listUsers(limit = 100) {
  return adminRequest<{ items: UserProfile[] }>(`/admin/users?limit=${encodeURIComponent(String(limit))}`);
}

export function listUserRelationships(payload?: { userId?: string; limit?: number }) {
  const params = new URLSearchParams();
  if (payload?.userId) params.set("user_id", payload.userId);
  if (payload?.limit) params.set("limit", String(payload.limit));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return adminRequest<{ items: Array<{ relationship_id: string; source_user_id: string; target_user_id: string; relationship_type: string; created_at: string }> }>(
    `/admin/users/relationships${suffix}`
  );
}

export function getUserRecommendations(userId: string, limit = 5) {
  return adminRequest<{ enabled: boolean; items: UserRecommendation[] }>(
    `/admin/users/${encodeURIComponent(userId)}/recommendations?limit=${encodeURIComponent(String(limit))}`
  );
}

export function listTemplates() {
  return adminRequest<{ items: Question[] }>("/admin/templates?include_archived=true");
}

export function listItemInstances(sessionId?: string) {
  const suffix = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  return adminRequest<{ items: Question[] }>(`/admin/item-instances${suffix}`);
}

export function previewRewrite(payload: {
  session_id: string;
  item_id: string;
  style_hint?: string;
}) {
  return adminRequest<{ enabled: boolean; message: string; preview: RewritePreviewBundle }>(
    "/ai/rewrite-question",
    {
      method: "POST",
      json: payload,
    }
  );
}

export function cleanupExpiredSessions() {
  return adminRequest<{ removed: number }>("/admin/cleanup", {
    method: "POST",
    json: {},
  });
}

export function createTemplate(payload: {
  prompt: string;
  question_type: string;
  layer: string;
  dimension_weights: Record<string, number>;
  subdimension_weights: Record<string, number>;
  module_affinities: Record<string, number>;
  discrimination: number;
  difficulty: number;
  scenario_tags: string[];
  is_anchor: boolean;
  allow_rewrite: boolean;
  options: QuestionOption[];
}) {
  return adminRequest<{ item: Question }>("/admin/item-template/create", {
    method: "POST",
    json: payload as JsonBody,
  });
}

export function updateTemplate(
  templateId: string,
  payload: {
    prompt: string;
    question_type: string;
    layer: string;
    dimension_weights: Record<string, number>;
    subdimension_weights: Record<string, number>;
    module_affinities: Record<string, number>;
    discrimination: number;
    difficulty: number;
    scenario_tags: string[];
    is_anchor: boolean;
    allow_rewrite: boolean;
    options: QuestionOption[];
  }
) {
  return adminRequest<{ item: Question }>(`/admin/item-template/${templateId}`, {
    method: "PUT",
    json: payload as JsonBody,
  });
}

export function getClusterOverview() {
  return adminRequest<ClusterOverview>("/admin/clusters/overview");
}

export function saveClusterLabelOverride(payload: {
  version: string;
  cluster_index: number;
  name: string;
  narrative_label: string;
}) {
  return adminRequest<{ saved: boolean }>("/admin/clusters/label-override", {
    method: "POST",
    json: payload,
  });
}

export function archiveTemplate(templateId: string) {
  return adminRequest<{ item: Question }>(`/admin/item-template/${templateId}/archive`, {
    method: "POST",
    json: {},
  });
}

export function deleteTemplate(templateId: string) {
  return adminRequest<{ deleted: boolean }>(`/admin/item-template/${templateId}`, {
    method: "DELETE",
  });
}

export function reindexVectors(scope: "templates" | "instances" | "sessions" | "galgame_turns" | "all") {
  return adminRequest<VectorReindexResponse>("/admin/vector/reindex", {
    method: "POST",
    json: { scope },
  });
}

export function searchSimilarGalgameTurns(payload: { prompt: string; topK?: number }) {
  const params = new URLSearchParams();
  params.set("prompt", payload.prompt);
  if (typeof payload.topK === "number") params.set("top_k", String(payload.topK));
  return adminRequest<VectorSearchResponse>(`/admin/vector/galgame-turns/similar?${params.toString()}`);
}

export function searchSimilarTemplates(payload: { templateId?: string; prompt?: string; topK?: number }) {
  const params = new URLSearchParams();
  if (payload.templateId) params.set("template_id", payload.templateId);
  if (payload.prompt) params.set("prompt", payload.prompt);
  if (typeof payload.topK === "number") params.set("top_k", String(payload.topK));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return adminRequest<VectorSearchResponse>(`/admin/vector/templates/similar${suffix}`);
}

export function searchSimilarSessions(payload: { sessionId: string; topK?: number }) {
  const params = new URLSearchParams();
  params.set("session_id", payload.sessionId);
  if (typeof payload.topK === "number") params.set("top_k", String(payload.topK));
  return adminRequest<VectorSearchResponse>(`/admin/vector/sessions/similar?${params.toString()}`);
}

export function listVectorSyncFailures(limit = 25) {
  return adminRequest<{ items: VectorSyncFailure[] }>(`/admin/vector/sync-failures?limit=${encodeURIComponent(String(limit))}`);
}
