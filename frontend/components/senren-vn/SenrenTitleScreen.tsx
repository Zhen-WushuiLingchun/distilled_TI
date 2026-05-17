"use client";

/* eslint-disable @next/next/no-img-element */

import type { PersonaOverview, SenrenMode } from "./types";

interface SenrenTitleScreenProps {
  loading: boolean;
  error: string;
  personaOverview: PersonaOverview | null;
  onStartMode: (mode: Extract<SenrenMode, "monitor" | "story">) => void | Promise<void>;
  onOpenLocalSetup: () => void;
  onOpenCredits: () => void;
}

export function SenrenTitleScreen({
  loading,
  error,
  personaOverview,
  onStartMode,
  onOpenLocalSetup,
  onOpenCredits,
}: SenrenTitleScreenProps) {
  const personaNames = Object.values(personaOverview?.personas || {})
    .map((persona) => persona.display_name)
    .filter(Boolean)
    .slice(0, 6);

  return (
    <>
      <div
        className="senren-title-bg"
        style={{ backgroundImage: "url(/generated/galgame/background/old_school_building_hallway_sunset.png)" }}
      />
      <div className="senren-title-glow" />

      <section className="senren-title-hero">
        <div className="senren-title-copy">
          <p className="senren-title-kicker">SENREN BANKA LOCAL VN COMPANION</p>
          <h1>
            千恋
            <span>＊</span>
            万花
          </h1>
          <strong>Local Visual Novel Runtime</strong>
          <p>
            这里不是问卷皮肤，而是按 Paper2Gal 的单屏视觉小说结构重建：标题页、启动页、游戏屏、Log/Hide/Auto
            控制层和后端剧情 provider 分离。现阶段使用本仓库的千恋 choice tree、角色 skills、SD/本地资产和 DeepSeek
            场景润色，之后可直接把测量 API 嵌入容器回调。
          </p>
        </div>

        <div className="senren-title-sprite">
          <img src="/generated/galgame/character/classmate_androgynous_calm.png" alt="Senren local VN character" />
        </div>

        <nav className="senren-title-menu" aria-label="Senren mode menu">
          <button className="is-primary" onClick={onOpenLocalSetup} disabled={loading}>
            <span>Start</span>
            <strong>本地游戏模式</strong>
            <em>验证千恋万花目录后进入 VN Companion</em>
          </button>
          <button onClick={() => onStartMode("story")} disabled={loading}>
            <span>Story</span>
            <strong>独立故事模式</strong>
            <em>不需要本地游戏目录，直接网页游玩</em>
          </button>
          <button onClick={() => onStartMode("monitor")} disabled={loading}>
            <span>Monitor</span>
            <strong>实时记录模式</strong>
            <em>手动同步原作里的关键选择</em>
          </button>
          <button onClick={onOpenCredits}>
            <span>Config</span>
            <strong>资源与说明</strong>
            <em>查看 skills、资产、provider 和当前边界</em>
          </button>
        </nav>
      </section>

      <aside className="senren-title-status">
        <div>
          <span>Character Skills</span>
          <strong>{personaOverview?.count ?? "--"}</strong>
          <p>{personaNames.length ? personaNames.join(" / ") : "等待后端返回角色 skill"}</p>
        </div>
        <div>
          <span>Scene Provider</span>
          <strong>DeepSeek</strong>
          <p>沿用后台 AI 配置；不可用时自动 fallback。</p>
        </div>
        <div>
          <span>Measurement Boundary</span>
          <strong>Bridge</strong>
          <p>VN 只触发容器回调，心理测量 API 后续在 bridge 层接入。</p>
        </div>
      </aside>

      {loading && <div className="senren-title-toast">正在启动 VN Companion...</div>}
      {error && <div className="senren-title-toast is-error">{error}</div>}
    </>
  );
}
