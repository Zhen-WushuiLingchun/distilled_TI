"use client";

interface ChoiceOption {
  key: string;
  text: string;
  affection_target: string;
}

interface SceneNode {
  choice_id: string;
  chapter: string;
  location: string;
  characters: string[];
  context: string;
  prompt: string;
  options: ChoiceOption[];
}

interface PersonaInfo {
  display_name: string;
  profile: Record<string, string>;
  impression: string;
  layer0: string[];
  layer2: {
    tone: string;
    patterns: string[];
    voice_sample: string;
    emotional_tells: string;
    speaking_pace: string;
  };
  layer3: {
    priorities: string;
    enthusiasm: string[];
    caution: string[];
  };
}

interface Props {
  scene: SceneNode;
  onSubmit: (choiceId: string, optionKey: string) => void;
  submitting: boolean;
  error: string;
  personas?: PersonaInfo[];
}

export default function SenrenChoicePanel({ scene, onSubmit, submitting, error, personas }: Props) {
  // Build character dialogue hints from persona data
  const characterHints = personas?.map((p) => {
    const patterns = p.layer2?.patterns?.slice(0, 2).join("、") || "";
    return `${p.display_name}（${p.layer2?.tone || "?"}${patterns ? `，习惯说"${patterns}"` : ""}）`;
  }).join("  ");

  return (
    <div className="fade-rise">
      {/* 场景信息条 */}
      <div className="flex items-center gap-3 mb-4 text-xs text-[var(--senren-ink-dim)]">
        <span>{scene.chapter}</span>
        <span className="text-[var(--senren-line-mid)]">|</span>
        <span>{scene.location}</span>
        {scene.characters.length > 0 && (
          <>
            <span className="text-[var(--senren-line-mid)]">|</span>
            <span className="text-[var(--senren-sakura)]">
              {scene.characters.join(" · ")}
            </span>
          </>
        )}
      </div>

      {/* 视觉小说对话框 */}
      <div className="senren-dialogue-box">
        {/* 角色名条（如果有 persona 数据） */}
        {scene.characters.length > 0 && (
          <div className="senren-character-name mb-4">
            {scene.characters.map((name, i) => {
              const p = personas?.find(
                (x) => x.display_name === name || name.includes(x.display_name)
              );
              return (
                <span key={i} className="inline-flex items-center gap-1.5 mr-4">
                  <span className="text-[var(--senren-gold)] text-sm">{name}</span>
                  {p?.layer2?.tone && (
                    <span className="text-[10px] text-[var(--senren-ink-dim)]">
                      · {p.layer2.tone}
                    </span>
                  )}
                </span>
              );
            })}
          </div>
        )}

        {/* 角色人设提示（skills 驱动） */}
        {characterHints && (
          <div className="mb-4 p-2.5 rounded bg-[var(--senren-bg-deep)] border border-[var(--senren-line-soft)]">
            <p className="text-[10px] text-[var(--senren-ink-dim)] leading-relaxed">
              🎭 {characterHints}
            </p>
          </div>
        )}

        {/* 场景描述 */}
        <p className="text-sm text-[var(--senren-ink-body)] leading-relaxed mb-6 whitespace-pre-line">
          {scene.context}
        </p>

        {/* 选择提示 */}
        <p className="senren-character-name">{scene.prompt || "你的选择是..."}</p>

        {/* 错误提示 */}
        {error && (
          <p className="text-xs text-[var(--senren-vermillion)] mb-3">{error}</p>
        )}

        {/* 选择按钮 */}
        <div className="space-y-2.5">
          {scene.options.map((option) => (
            <button
              key={option.key}
              onClick={() => onSubmit(scene.choice_id, option.key)}
              disabled={submitting}
              className={`senren-choice-btn ${submitting ? "opacity-50 cursor-wait" : ""}`}
            >
              <span className="text-sm">{option.text}</span>
              {option.affection_target !== "none" && (
                <span className="ml-2 text-xs text-[var(--senren-gold)] opacity-60">
                  [{option.affection_target} +好感]
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* 提交中指示 */}
      {submitting && (
        <p className="mt-3 text-xs text-[var(--senren-ink-muted)] animate-pulse text-center">
          记录中...
        </p>
      )}
    </div>
  );
}
