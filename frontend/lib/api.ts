import type { NamingStyle, ProjectionMode, SessionAccessBundle } from "@/lib/runtime-store";

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
  status: string;
  question_count: number;
  can_generate_report: boolean;
  created_at: string;
  updated_at: string;
  cluster_name: string | null;
  narrative_label: string | null;
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
  object_type: "template" | "rewrite_candidate" | "item_instance" | "session_snapshot";
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
  scope: "templates" | "instances" | "sessions" | "all";
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

export function startSession() {
  return publicRequest<SessionStartResponse>("/session/start", {
    method: "POST",
    json: { mode: "core" },
  });
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

export function reindexVectors(scope: "templates" | "instances" | "sessions" | "all") {
  return adminRequest<VectorReindexResponse>("/admin/vector/reindex", {
    method: "POST",
    json: { scope },
  });
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
