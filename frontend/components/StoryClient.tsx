"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import {
  createUserGalgameStoryTemplate,
  deleteUserGalgameStoryTemplate,
  generateSessionReport,
  getGalgameScene,
  getSessionMap,
  listUserGalgameStoryTemplates,
  respondGalgameScene,
  startSession,
  updateUserGalgameStoryTemplate,
  type GalgameScene,
  type GalgameStoryTemplate,
  type GalgameStoryTemplatePayload,
  type GalgameTextInference,
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
  type UserAccessBundle,
} from "@/lib/runtime-store";

type DialogueLogEntry = {
  id: string;
  speaker: string;
  text: string;
  meta: string;
};

type TemplateFormState = {
  name: string;
  description: string;
  location: string;
  speaker: string;
  characterKey: string;
  backgroundKey: string;
  backgroundPrompt: string;
  characterPrompt: string;
  stylePrompt: string;
  scenarioTags: string;
};

const EMPTY_TEMPLATE_FORM: TemplateFormState = {
  name: "我的校园分支",
  description: "围绕一次关系、社团或学习场景展开，允许角色主动制造分歧。",
  location: "黄昏后的旧社团楼",
  speaker: "临时同伴",
  characterKey: "custom_companion",
  backgroundKey: "custom_evening_clubroom",
  backgroundPrompt: "evening school clubroom, warm window light, visual novel background",
  characterPrompt: "visual novel companion portrait, expressive, non sexualized, campus style",
  stylePrompt: "更像可玩的 galgame；台词可以有悬疑、玩笑和关系张力，角色可以主动改变局面。",
  scenarioTags: "campus, relationship, team_mode",
};

function moodLabel(mood: string) {
  if (mood === "追问") return "Probe";
  if (mood === "低电量") return "Low Battery";
  if (mood === "分岔") return "Branch";
  if (mood === "校准") return "Calibration";
  return "Opening";
}

function splitTags(value: string) {
  return value
    .split(/[,，\s]+/)
    .map((item) => item.trim())
    .filter(Boolean)
    .slice(0, 12);
}

function templateToForm(template: GalgameStoryTemplate): TemplateFormState {
  return {
    name: template.name,
    description: template.description,
    location: template.location,
    speaker: template.speaker,
    characterKey: template.character_key,
    backgroundKey: template.background_key,
    backgroundPrompt: template.background_prompt,
    characterPrompt: template.character_prompt,
    stylePrompt: template.style_prompt,
    scenarioTags: template.scenario_tags.join(", "),
  };
}

function formToPayload(form: TemplateFormState): GalgameStoryTemplatePayload {
  return {
    name: form.name.trim() || EMPTY_TEMPLATE_FORM.name,
    description: form.description.trim(),
    location: form.location.trim() || EMPTY_TEMPLATE_FORM.location,
    speaker: form.speaker.trim() || EMPTY_TEMPLATE_FORM.speaker,
    character_key: form.characterKey.trim() || EMPTY_TEMPLATE_FORM.characterKey,
    background_key: form.backgroundKey.trim() || EMPTY_TEMPLATE_FORM.backgroundKey,
    background_prompt: form.backgroundPrompt.trim(),
    character_prompt: form.characterPrompt.trim(),
    style_prompt: form.stylePrompt.trim(),
    scenario_tags: splitTags(form.scenarioTags),
    active: true,
  };
}

function sceneLogEntry(scene: GalgameScene): DialogueLogEntry {
  return {
    id: scene.scene_id,
    speaker: scene.speaker,
    text: `${scene.narrator_text}\n${scene.character_text}`,
    meta: `${scene.location} / ${scene.mood}`,
  };
}

export function StoryClient() {
  const router = useRouter();
  const [access, setAccess] = useState<SessionAccessBundle | null>(null);
  const [user, setUser] = useState<UserAccessBundle | null>(null);
  const [scene, setScene] = useState<GalgameScene | null>(null);
  const [state, setState] = useState<SessionState | null>(null);
  const [lastInference, setLastInference] = useState<GalgameTextInference | null>(null);
  const [customText, setCustomText] = useState("");
  const [selectedOptionKey, setSelectedOptionKey] = useState("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [remainingUntilReport, setRemainingUntilReport] = useState(20);
  const [canGenerateReport, setCanGenerateReport] = useState(false);
  const [typedText, setTypedText] = useState("");
  const [typedDone, setTypedDone] = useState(false);
  const [hideUI, setHideUI] = useState(false);
  const [showLog, setShowLog] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [showDebug, setShowDebug] = useState(false);
  const [templates, setTemplates] = useState<GalgameStoryTemplate[]>([]);
  const [editingTemplateId, setEditingTemplateId] = useState<string | null>(null);
  const [templateForm, setTemplateForm] = useState<TemplateFormState>(EMPTY_TEMPLATE_FORM);
  const [templateStatus, setTemplateStatus] = useState("");
  const [dialogueLog, setDialogueLog] = useState<DialogueLogEntry[]>([]);
  const startedAtRef = useRef<number>(Date.now());
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        setBusy(true);
        const currentUser = getUserAccess();
        setUser(currentUser);
        let currentAccess = getActiveSessionAccess();
        if (!currentAccess) {
          clearFinalReportSnapshot();
          const started = await startSession(currentUser, "story");
          currentAccess = {
            session_id: started.session_id,
            session_secret: started.session_secret,
            delete_token: started.delete_token,
          };
          saveActiveSessionAccess(currentAccess);
          setState(started.state);
          setRemainingUntilReport(started.min_questions_for_report);
        }
        const [nextScene, templatePayload] = await Promise.all([
          getGalgameScene(currentAccess),
          currentUser ? listUserGalgameStoryTemplates(currentUser).catch(() => ({ items: [] })) : Promise.resolve({ items: [] }),
        ]);
        if (cancelled) return;
        setAccess(currentAccess);
        setScene(nextScene);
        setTemplates(templatePayload.items);
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

  useEffect(() => {
    if (!scene) return;
    setDialogueLog((current) => {
      if (current.some((entry) => entry.id === scene.scene_id)) return current;
      return [...current, sceneLogEntry(scene)].slice(-18);
    });
  }, [scene]);

  useEffect(() => {
    const line = scene?.character_text ?? "";
    setTypedText("");
    setTypedDone(false);
    if (!line) return;
    let cursor = 0;
    const step = 2;
    const interval = window.setInterval(() => {
      cursor += step;
      if (cursor >= line.length) {
        setTypedText(line);
        setTypedDone(true);
        window.clearInterval(interval);
      } else {
        setTypedText(line.slice(0, cursor));
      }
    }, 26);
    return () => window.clearInterval(interval);
  }, [scene?.scene_id, scene?.character_text]);

  useEffect(() => {
    const player = audioRef.current;
    if (!player || !scene?.audio_asset?.url) return;
    player.volume = 0.18;
    void player.play().catch(() => {
      // Browser autoplay policies can block ambient audio until the user clicks.
    });
  }, [scene?.audio_asset?.url]);

  useEffect(() => {
    if (!hideUI) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setHideUI(false);
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [hideUI]);

  async function refreshTemplates(currentUser = user) {
    if (!currentUser) return;
    const payload = await listUserGalgameStoryTemplates(currentUser);
    setTemplates(payload.items);
  }

  async function handleChoice(optionKey: string, textOverride?: string) {
    if (!access || !scene) return;
    try {
      setBusy(true);
      const choiceText = scene.choices.find((choice) => choice.option_key === optionKey)?.text ?? optionKey;
      setDialogueLog((current) => [
        ...current,
        {
          id: `${scene.scene_id}:player:${Date.now()}`,
          speaker: "你",
          text: textOverride?.trim() || choiceText,
          meta: "player branch",
        },
      ].slice(-18));
      const latencyMs = Math.round(performance.now() - startedAtRef.current);
      const response = await respondGalgameScene(access, {
        item_id: scene.item_id,
        scene_id: scene.scene_id,
        option_key: optionKey,
        choice_text: choiceText,
        custom_text: textOverride?.trim() || undefined,
        latency_ms: latencyMs,
      });
      setState(response.state);
      setScene(response.scene);
      setLastInference(response.text_inference ?? null);
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

  async function handleSaveTemplate() {
    if (!user) {
      setTemplateStatus("需要先通过邀请码进入，才能保存个人剧情模板。");
      return;
    }
    try {
      setTemplateStatus("正在保存模板…");
      if (editingTemplateId) {
        await updateUserGalgameStoryTemplate(user, editingTemplateId, formToPayload(templateForm));
      } else {
        await createUserGalgameStoryTemplate(user, formToPayload(templateForm));
      }
      await refreshTemplates(user);
      setEditingTemplateId(null);
      setTemplateForm(EMPTY_TEMPLATE_FORM);
      setTemplateStatus("模板已保存。下一幕或新会话会按标签自动参与匹配。");
    } catch (reason) {
      setTemplateStatus(reason instanceof Error ? reason.message : "模板保存失败。");
    }
  }

  async function handleDeleteTemplate(templateId: string) {
    if (!user) return;
    try {
      setTemplateStatus("正在删除模板…");
      await deleteUserGalgameStoryTemplate(user, templateId);
      await refreshTemplates(user);
      if (editingTemplateId === templateId) {
        setEditingTemplateId(null);
        setTemplateForm(EMPTY_TEMPLATE_FORM);
      }
      setTemplateStatus("模板已删除。");
    } catch (reason) {
      setTemplateStatus(reason instanceof Error ? reason.message : "模板删除失败。");
    }
  }

  function revealLine() {
    if (!scene) return;
    if (!typedDone) {
      setTypedText(scene.character_text);
      setTypedDone(true);
    }
  }

  const backgroundUrl = scene?.background_asset?.url ?? "/galgame-assets/backgrounds/campus_courtyard.svg";
  const characterUrl = scene?.character_asset?.url ?? "/galgame-assets/sprites/desk_mate.svg";
  const selectedChoice =
    scene?.choices.find((choice) => choice.option_key === selectedOptionKey) ??
    scene?.choices[0] ??
    null;

  if (busy && !scene) {
    return (
      <main className="story-shell story-shell-vn">
        <section className="story-loading-card">
          <p className="eyebrow">Distilled TI / Story Mode</p>
          <h1 className="mt-4 text-4xl">正在生成第一幕</h1>
          <p className="mt-3 text-[color:var(--ink-muted)]">正在为你生成一个可推进的校园分支。</p>
        </section>
      </main>
    );
  }

  return (
    <main className={`story-shell story-shell-vn ${hideUI ? "is-ui-hidden" : ""}`}>
      <section className="story-vn-frame">
        <div className="story-vn-bg" data-background-key={scene?.background_key ?? "campus_window"}>
          <img className="story-vn-bg-image" src={backgroundUrl} alt="" />
        </div>
        <div className="story-vn-atmosphere" />
        <div className="story-vn-character" data-character-key={scene?.character_key ?? "desk_mate"} aria-hidden>
          <img className="story-vn-sprite-image" src={characterUrl} alt="" />
        </div>
        {scene?.audio_asset?.url ? <audio ref={audioRef} src={scene.audio_asset.url} loop /> : null}

        <header className="story-vn-hud">
          <div>
            <p className="label-mini">{scene?.location ?? "Unknown"}</p>
            <h1>{scene?.title ?? "Story Mode"}</h1>
          </div>
          <div className="story-vn-pills">
            <span>{scene ? moodLabel(scene.mood) : "Loading"}</span>
            <span>Ch.{String((state?.question_count ?? 0) + 1).padStart(2, "0")}</span>
            {user ? <span>{user.handle}</span> : <span>Guest</span>}
          </div>
        </header>

        <div className="story-vn-controls">
          <button type="button" onClick={() => setShowLog(true)}>Log</button>
          <button type="button" onClick={() => setHideUI((value) => !value)}>{hideUI ? "Show" : "Hide"}</button>
          <button type="button" onClick={() => setShowTemplates(true)}>Template</button>
          <button type="button" onClick={() => setShowDebug((value) => !value)}>Debug</button>
          <button type="button" disabled={!canGenerateReport || busy} onClick={() => void handleReport()}>
            {canGenerateReport ? "Report" : `Report ${remainingUntilReport}`}
          </button>
          <button type="button" onClick={() => router.push("/session")}>Workbench</button>
        </div>

        {hideUI ? (
          <button
            type="button"
            className="story-vn-restore-control"
            onClick={() => setHideUI(false)}
            aria-label="恢复剧情界面"
          >
            Show UI
          </button>
        ) : null}

        {!hideUI ? (
          <>
            <section className="story-vn-choice-board" aria-label="剧情选项">
              {scene?.choices.map((choice, index) => {
                const isSelected = choice.option_key === selectedChoice?.option_key;
                return (
                  <button
                    key={choice.key}
                    className={`story-choice story-choice-vn ${choice.tone} ${isSelected ? "is-selected" : ""}`}
                    disabled={busy}
                    aria-pressed={isSelected}
                    style={{ animationDelay: `${120 + index * 70}ms` }}
                    onClick={() => setSelectedOptionKey(choice.option_key)}
                  >
                    <span>{choice.text}</span>
                    {isSelected ? <em>当前</em> : null}
                  </button>
                );
              })}
            </section>

            <section className="story-vn-dialogue" onClick={revealLine}>
              <div className="story-vn-nameplate">{scene?.speaker ?? "同桌"}</div>
              <p className="story-vn-narrator">{scene?.narrator_text}</p>
              <p className="story-vn-line">
                {typedText || scene?.character_text}
                {!typedDone ? <span className="type-caret" /> : null}
              </p>
              <div className="story-vn-free-line">
                <textarea
                  value={customText}
                  onChange={(event) => setCustomText(event.target.value)}
                  placeholder="自己写一句台词，例如：我低声问，那封信是谁放在这里的？"
                />
                <div className="story-vn-free-actions">
                  <div className="story-vn-current-choice">
                    <span>当前选择</span>
                    <strong>{selectedChoice?.text ?? "请选择左侧选项"}</strong>
                  </div>
                  <button
                    type="button"
                    disabled={busy || !selectedChoice}
                    onClick={() => {
                      if (!selectedChoice) return;
                      void handleChoice(selectedChoice.option_key, customText);
                    }}
                  >
                    {customText.trim() ? "以这句推进" : "以当前选择推进"}
                  </button>
                </div>
              </div>
            </section>
          </>
        ) : null}

        {showDebug ? (
          <section className="story-vn-debug">
            <p className="label-mini">Asset / Classifier Debug</p>
            <div className="mt-3 grid gap-2 md:grid-cols-2">
              <div>
                <p className="num text-[0.72rem] text-[color:var(--ink-faint)]">BG / CHAR</p>
                <p>{scene?.background_key ?? "-"} / {scene?.character_key ?? "-"}</p>
                <p className="mt-1 text-xs text-[color:var(--ink-muted)]">
                  {scene?.background_asset?.source ?? "fallback"} / {scene?.character_asset?.source ?? "fallback"}
                </p>
              </div>
              <div>
                <p className="num text-[0.72rem] text-[color:var(--ink-faint)]">Template</p>
                <p>{scene?.story_template_id ?? "none"}</p>
              </div>
            </div>
            {lastInference ? (
              <div className="mt-3">
                <p className="num text-[0.75rem] text-[color:var(--ink-muted)]">
                  {lastInference.source} / {lastInference.inferred_option_key ?? "uncertain"} / confidence {lastInference.confidence.toFixed(2)}
                </p>
                <p className="mt-1 text-xs leading-5 text-[color:var(--ink-muted)]">{lastInference.reason}</p>
                <div className="mt-2 space-y-1.5">
                  {lastInference.option_scores.slice(0, 4).map((score) => (
                    <div key={score.option_key} className="story-score-row">
                      <span>{score.option_key}</span>
                      <span>
                        F {score.fused_score.toFixed(2)} / L {score.llm_score?.toFixed(2) ?? "-"} / E {score.embedding_score?.toFixed(2) ?? "-"} / P {score.pairwise_score?.toFixed(2) ?? "-"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <p className="mt-3 text-xs text-[color:var(--ink-muted)]">提交自由台词后会显示 LLM / embedding / pairwise 分类证据。</p>
            )}
            {scene?.memory_fragments.length ? (
              <div className="mt-3">
                <p className="label-mini">Memory</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {scene.memory_fragments.map((fragment, index) => (
                    <span key={`${fragment}-${index}`} className="chip">{fragment}</span>
                  ))}
                </div>
              </div>
            ) : null}
          </section>
        ) : null}

        {error ? <div className="story-vn-error">{error}</div> : null}
        {busy ? <div className="story-vn-busy">处理中…</div> : null}
      </section>

      {showLog ? (
        <div className="story-overlay">
          <section className="story-modal story-log-modal">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="label-mini">Backlog</p>
                <h2>剧情记录</h2>
              </div>
              <button type="button" className="btn btn-ghost" onClick={() => setShowLog(false)}>关闭</button>
            </div>
            <div className="mt-5 space-y-3">
              {dialogueLog.map((entry) => (
                <article key={entry.id} className="story-log-entry">
                  <div className="flex items-center justify-between gap-3">
                    <strong>{entry.speaker}</strong>
                    <span>{entry.meta}</span>
                  </div>
                  <p>{entry.text}</p>
                </article>
              ))}
            </div>
          </section>
        </div>
      ) : null}

      {showTemplates ? (
        <div className="story-overlay">
          <section className="story-modal story-template-drawer">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <p className="label-mini">Scenario Templates</p>
                <h2>自定义剧情模板</h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-[color:var(--ink-muted)]">
                  用户模板只绑定随机匿名 ID，不包含真实身份。保存后会和系统模板一起按标签匹配后续剧情。
                </p>
              </div>
              <button type="button" className="btn btn-ghost" onClick={() => setShowTemplates(false)}>关闭</button>
            </div>

            {!user ? (
              <div className="surface-sunken mt-5 p-4 text-sm text-[color:var(--ink-muted)]">
                需要先通过邀请码进入，才能长期保存个人剧情模板。未注册访客仍可正常游玩当前剧情。
              </div>
            ) : null}

            <div className="mt-5 grid gap-5 lg:grid-cols-[0.9fr_1.1fr]">
              <div className="space-y-2.5">
                {templates.map((template) => {
                  const owned = Boolean(user && template.owner_user_id === user.user_id);
                  return (
                    <article key={template.template_id} className="story-template-row">
                      <div>
                        <div className="flex flex-wrap items-center gap-2">
                          <strong>{template.name}</strong>
                          <span>{owned ? "Mine" : "System"}</span>
                        </div>
                        <p>{template.location} / {template.speaker}</p>
                      </div>
                      {owned ? (
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              setEditingTemplateId(template.template_id);
                              setTemplateForm(templateToForm(template));
                            }}
                          >
                            编辑
                          </button>
                          <button type="button" onClick={() => void handleDeleteTemplate(template.template_id)}>删除</button>
                        </div>
                      ) : null}
                    </article>
                  );
                })}
                {!templates.length ? <p className="text-sm text-[color:var(--ink-muted)]">还没有可显示模板。</p> : null}
              </div>

              <form className="story-template-form" onSubmit={(event) => { event.preventDefault(); void handleSaveTemplate(); }}>
                <div className="grid gap-3 md:grid-cols-2">
                  <label>
                    <span>名称</span>
                    <input value={templateForm.name} onChange={(event) => setTemplateForm((form) => ({ ...form, name: event.target.value }))} />
                  </label>
                  <label>
                    <span>地点</span>
                    <input value={templateForm.location} onChange={(event) => setTemplateForm((form) => ({ ...form, location: event.target.value }))} />
                  </label>
                  <label>
                    <span>说话角色</span>
                    <input value={templateForm.speaker} onChange={(event) => setTemplateForm((form) => ({ ...form, speaker: event.target.value }))} />
                  </label>
                  <label>
                    <span>标签</span>
                    <input value={templateForm.scenarioTags} onChange={(event) => setTemplateForm((form) => ({ ...form, scenarioTags: event.target.value }))} />
                  </label>
                  <label>
                    <span>角色 Key</span>
                    <input value={templateForm.characterKey} onChange={(event) => setTemplateForm((form) => ({ ...form, characterKey: event.target.value }))} />
                  </label>
                  <label>
                    <span>背景 Key</span>
                    <input value={templateForm.backgroundKey} onChange={(event) => setTemplateForm((form) => ({ ...form, backgroundKey: event.target.value }))} />
                  </label>
                </div>
                <label>
                  <span>剧情简介</span>
                  <textarea value={templateForm.description} onChange={(event) => setTemplateForm((form) => ({ ...form, description: event.target.value }))} />
                </label>
                <label>
                  <span>风格提示词</span>
                  <textarea value={templateForm.stylePrompt} onChange={(event) => setTemplateForm((form) => ({ ...form, stylePrompt: event.target.value }))} />
                </label>
                <label>
                  <span>背景素材提示</span>
                  <textarea value={templateForm.backgroundPrompt} onChange={(event) => setTemplateForm((form) => ({ ...form, backgroundPrompt: event.target.value }))} />
                </label>
                <label>
                  <span>角色素材提示</span>
                  <textarea value={templateForm.characterPrompt} onChange={(event) => setTemplateForm((form) => ({ ...form, characterPrompt: event.target.value }))} />
                </label>
                <div className="flex flex-wrap items-center gap-2">
                  <button type="submit" className="btn btn-primary" disabled={!user}>
                    {editingTemplateId ? "保存修改" : "创建个人模板"}
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={() => {
                      setEditingTemplateId(null);
                      setTemplateForm(EMPTY_TEMPLATE_FORM);
                    }}
                  >
                    新建草稿
                  </button>
                  {templateStatus ? <span className="text-sm text-[color:var(--ink-muted)]">{templateStatus}</span> : null}
                </div>
              </form>
            </div>
          </section>
        </div>
      ) : null}
    </main>
  );
}
