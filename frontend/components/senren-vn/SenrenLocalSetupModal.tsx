"use client";

import type { PersonaOverview, ValidationResult } from "./types";

const VALIDATION_FILE_FALLBACK = 4;

interface SenrenLocalSetupModalProps {
  gamePath: string;
  validationResult: ValidationResult | null;
  personaOverview: PersonaOverview | null;
  validating: boolean;
  loading: boolean;
  onGamePathChange: (value: string) => void;
  onValidate: () => void | Promise<void>;
  onStartLocalGame: () => void | Promise<void>;
  onClose: () => void;
}

export function SenrenLocalSetupModal({
  gamePath,
  validationResult,
  personaOverview,
  validating,
  loading,
  onGamePathChange,
  onValidate,
  onStartLocalGame,
  onClose,
}: SenrenLocalSetupModalProps) {
  const foundFileCount = validationResult?.found_files?.length || 0;
  const missingFileCount = validationResult?.missing_files?.length || 0;
  const totalCheckedFileCount = foundFileCount + missingFileCount;

  return (
    <div className="senren-title-modal-backdrop" onClick={onClose}>
      <div className="senren-title-modal" onClick={(event) => event.stopPropagation()}>
        <header>
          <div>
            <span>Local Game Setup</span>
            <h2>指定千恋万花本地目录</h2>
          </div>
          <button onClick={onClose}>Close</button>
        </header>

        <p className="senren-title-modal-lead">
          这是 Paper2Gal 中 Upload/Setup 屏的本地游戏版本：先验证目录，再进入网页 VN Companion。当前实现不读取或修改原游戏存档，
          也不 hook 进程；它使用本仓库的 choice tree、角色 skills、AI 场景润色和本地资产完成可玩的分支体验。
        </p>

        <div className="senren-title-path-row">
          <input
            type="text"
            value={gamePath}
            onChange={(event) => onGamePathChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") void onValidate();
            }}
            placeholder={"例如：D:\\Games\\SenrenBanka 或 D:\\Games\\千恋＊万花"}
            autoFocus
          />
          <button onClick={() => void onValidate()} disabled={validating || !gamePath.trim()}>
            {validating ? "Checking" : "Validate"}
          </button>
        </div>

        {validationResult && (
          <div className={`senren-title-validation ${validationResult.valid ? "is-valid" : "is-invalid"}`}>
            <div>
              <span>{validationResult.valid ? "Directory Ready" : "Directory Not Ready"}</span>
              <strong>{validationResult.hint || (validationResult.valid ? "目录有效。" : "目录无效。")}</strong>
            </div>
            <div className="senren-title-validation-grid">
              <Metric label="关键文件" value={`${foundFileCount}/${totalCheckedFileCount || VALIDATION_FILE_FALLBACK}`} />
              <Metric label="角色 skills" value={String(validationResult.skill_count ?? personaOverview?.count ?? 0)} />
              <Metric label="背景资产" value={String(validationResult.asset_summary?.generated_backgrounds ?? "--")} />
              <Metric label="立绘资产" value={String(validationResult.asset_summary?.generated_characters ?? "--")} />
            </div>
            {validationResult.found_files?.length ? <p>找到：{validationResult.found_files.join(" / ")}</p> : null}
            {!validationResult.valid && validationResult.missing_files?.length ? (
              <p>缺失：{validationResult.missing_files.join(" / ")}</p>
            ) : null}
          </div>
        )}

        <footer>
          <button onClick={onClose} className="is-ghost">
            取消
          </button>
          <button onClick={() => void onStartLocalGame()} disabled={!validationResult?.valid || loading} className="is-primary">
            进入本地 VN 模式
          </button>
        </footer>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
