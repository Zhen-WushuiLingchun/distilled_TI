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

interface Props {
  scene: SceneNode;
  onSubmit: (choiceId: string, optionKey: string) => void;
  submitting: boolean;
  error: string;
}

export default function SenrenChoicePanel({ scene, onSubmit, submitting, error }: Props) {
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
