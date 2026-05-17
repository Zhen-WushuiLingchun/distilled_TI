"use client";

/* eslint-disable @next/next/no-img-element */

import type { SenrenGameScreenProps } from "./types";
import { SenrenModal } from "./SenrenModal";

const FALLBACK_BACKGROUND = "/generated/galgame/background/old_school_building_corridor.png";
const FALLBACK_CHARACTER = "/generated/galgame/character/classmate_androgynous_calm.png";
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000/api";
const API_ORIGIN = API_BASE_URL.replace(/\/api\/?$/, "");

function resolveAssetUrl(url: string) {
  if (url.startsWith("/api/")) {
    return `${API_ORIGIN}${url}`;
  }
  return url;
}

export function SenrenGameScreen({
  scene,
  liveState,
  mode,
  gamePath,
  localGameInfo,
  personas,
  displayedText,
  typing,
  autoMode,
  hidden,
  submitting,
  error,
  showLog,
  showSkills,
  showWorkbench,
  onFinishTyping,
  onSubmitChoice,
  onToggleAuto,
  onSetHidden,
  onSetShowLog,
  onSetShowSkills,
  onSetShowWorkbench,
  onExit,
  onReport,
}: SenrenGameScreenProps) {
  const mergedPersonas = {
    ...personas,
    ...(scene.skill_enrichment || {}),
  };
  const currentPersona = scene.speaker
    ? Object.values(mergedPersonas).find(
        (persona) => persona.display_name === scene.speaker || scene.speaker.includes(persona.display_name)
      )
    : undefined;
  const logItems = scene.recent_choices?.length ? scene.recent_choices : liveState?.recent_choices || [];
  const backgroundUrl = resolveAssetUrl(scene.background_asset?.url || FALLBACK_BACKGROUND);
  const characterUrl = resolveAssetUrl(scene.character_asset?.url || FALLBACK_CHARACTER);
  const currentCount = liveState?.question_count ?? 0;

  return (
    <div className={`senren-vn-stage ${hidden ? "is-senren-hidden" : ""}`} onClick={() => typing && onFinishTyping()}>
      <div className="senren-vn-bg" style={{ backgroundImage: `url(${backgroundUrl})` }} />
      <div className="senren-vn-vignette" />

      {!hidden && (
        <>
          <header className="senren-vn-header">
            <div>
              <p>{scene.location || "织守町"}</p>
              <h1>{scene.title || scene.chapter || "千恋万花"}</h1>
              <span>{scene.mood || "visual novel scene"}</span>
            </div>
            <div className="senren-vn-tags">
              <span>{scene.ai_generated ? "DeepSeek Scene" : "Fallback Scene"}</span>
              <span>{mode === "local" ? "Local Game" : mode === "story" ? "Story" : "Monitor"}</span>
              <span>{currentCount} / 8</span>
            </div>
          </header>

          <div className="senren-vn-character" key={characterUrl}>
            <img src={characterUrl} alt={scene.character_asset?.alt || scene.speaker || "character"} />
          </div>

          {!scene.completed && (
            <div className="senren-vn-choice-stack">
              {scene.choices.map((choice, index) => (
                <button
                  key={choice.option_key}
                  onClick={(event) => {
                    event.stopPropagation();
                    void onSubmitChoice(choice);
                  }}
                  disabled={submitting}
                  style={{ animationDelay: `${index * 70}ms` }}
                >
                  <span>{choice.text}</span>
                  {choice.affection_target !== "none" && <em>{choice.affection_target}</em>}
                </button>
              ))}
            </div>
          )}

          <section className="senren-vn-dialogue" onClick={(event) => event.stopPropagation()}>
            <div className="senren-vn-nameplate">{scene.speaker || "旁白"}</div>
            <p className="senren-vn-narrator">{scene.narrator_text}</p>
            <p className="senren-vn-line">
              {displayedText}
              {typing && <span className="senren-vn-caret" />}
            </p>
            {scene.completed && (
              <button className="senren-vn-report-button" onClick={onReport}>
                查看这条路线的报告
              </button>
            )}
            {error && <p className="senren-vn-error-line">{error}</p>}
          </section>

          <nav className="senren-vn-controls" onClick={(event) => event.stopPropagation()}>
            <button className={autoMode ? "is-active" : ""} onClick={onToggleAuto}>
              Auto
            </button>
            <button onClick={() => onSetShowLog(true)}>Log</button>
            <button onClick={() => onSetHidden(true)}>Hide</button>
            <button onClick={() => onSetShowSkills(true)}>Skills</button>
            <button onClick={() => onSetShowWorkbench(true)}>Workbench</button>
            {liveState?.can_generate_report && <button onClick={onReport}>Report</button>}
            <button onClick={onExit}>Exit</button>
          </nav>

          {mode === "local" && (
            <aside className="senren-vn-local-card">
              <span>LOCAL GAME LINK</span>
              <strong>{localGameInfo?.game_info?.valid ? "目录已验证" : "网页伴随模式"}</strong>
              <p>{localGameInfo?.game_path || gamePath || "当前只记录网页 VN 选择，不 hook 原游戏进程。"}</p>
            </aside>
          )}
        </>
      )}

      {hidden && (
        <button
          className="senren-vn-restore"
          onClick={(event) => {
            event.stopPropagation();
            onSetHidden(false);
          }}
        >
          Show UI
        </button>
      )}

      {submitting && (
        <div className="senren-vn-busy">
          <strong>记录选择中</strong>
          <span>正在推进下一幕</span>
        </div>
      )}

      {showLog && (
        <SenrenModal title="Dialogue Log" onClose={() => onSetShowLog(false)}>
          <div className="senren-vn-log-list">
            {logItems.length ? (
              [...logItems].reverse().map((item, index) => (
                <article key={`${item.context}-${index}`}>
                  <span>{item.location || "Recent"}</span>
                  <p>{item.context}</p>
                  {item.option_text && <strong>→ {item.option_text}</strong>}
                </article>
              ))
            ) : (
              <p className="senren-vn-empty">还没有历史选择。</p>
            )}
          </div>
        </SenrenModal>
      )}

      {showSkills && (
        <SenrenModal title="Character Skills" onClose={() => onSetShowSkills(false)}>
          <div className="senren-vn-skill-grid">
            {Object.values(mergedPersonas).length ? (
              Object.values(mergedPersonas).map((persona) => (
                <article key={persona.display_name}>
                  <span>{persona.profile?.role || "Persona"}</span>
                  <h3>{persona.display_name}</h3>
                  <p>{persona.impression || persona.layer2?.voice_sample}</p>
                  {persona.layer2?.tone && <em>语气：{persona.layer2.tone}</em>}
                  {persona.layer0?.length > 0 && (
                    <ul>
                      {persona.layer0.slice(0, 3).map((rule) => (
                        <li key={rule}>{rule}</li>
                      ))}
                    </ul>
                  )}
                </article>
              ))
            ) : (
              <p className="senren-vn-empty">没有加载到角色 skill。</p>
            )}
          </div>
        </SenrenModal>
      )}

      {showWorkbench && (
        <SenrenModal title="Hidden Workbench" onClose={() => onSetShowWorkbench(false)}>
          <div className="senren-vn-workbench">
            <section>
              <span>Current Persona</span>
              <h3>{currentPersona?.display_name || scene.speaker || "Unknown"}</h3>
              <p>{currentPersona?.layer2?.voice_sample || currentPersona?.impression || "当前场景没有匹配到 persona。"}</p>
            </section>
            <section>
              <span>Top Dimensions</span>
              {liveState?.top_dimensions?.length ? (
                liveState.top_dimensions.map((dim) => (
                  <div key={dim.key} className="senren-vn-meter">
                    <strong>{dim.label}</strong>
                    <em>
                      {dim.score > 0 ? "+" : ""}
                      {dim.score.toFixed(2)}
                    </em>
                  </div>
                ))
              ) : (
                <p>还没有足够选择。</p>
              )}
            </section>
            <section>
              <span>Character Affinity</span>
              {liveState?.character_affinity &&
                Object.entries(liveState.character_affinity)
                  .sort(([, a], [, b]) => b - a)
                  .slice(0, 5)
                  .map(([name, score]) => (
                    <div key={name} className="senren-vn-meter">
                      <strong>{name}</strong>
                      <em>{score.toFixed(1)}%</em>
                    </div>
                  ))}
            </section>
          </div>
        </SenrenModal>
      )}
    </div>
  );
}

export function SenrenGameLoading() {
  return (
    <div className="senren-vn-stage">
      <div className="senren-vn-bg" style={{ backgroundImage: `url(${FALLBACK_BACKGROUND})` }} />
      <div className="senren-vn-loading">
        <span>Loading</span>
        <strong>正在加载本地 VN 场景</strong>
        <p>读取路线、角色 skill 与当前会话状态。</p>
      </div>
    </div>
  );
}

export function SenrenGameError({ error, onExit }: { error: string; onExit: () => void }) {
  return (
    <div className="senren-vn-stage">
      <div className="senren-vn-bg" style={{ backgroundImage: `url(${FALLBACK_BACKGROUND})` }} />
      <button className="senren-vn-pill senren-vn-exit" onClick={onExit}>
        返回
      </button>
      <div className="senren-vn-loading">
        <span>Error</span>
        <strong>场景加载失败</strong>
        <p>{error || "请检查后端服务是否已启动。"}</p>
      </div>
    </div>
  );
}
