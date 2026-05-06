"use client";

import { useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";

import {
  getReportViewPreferences,
  saveReportViewPreferences,
  type NamingStyle,
  type ProjectionMode,
} from "@/lib/runtime-store";

export function LandingClient() {
  const router = useRouter();
  const [projectionMode, setProjectionMode] = useState<ProjectionMode>(() => getReportViewPreferences().projectionMode);
  const [namingStyle, setNamingStyle] = useState<NamingStyle>(() => getReportViewPreferences().namingStyle);
  const [showBrandModal, setShowBrandModal] = useState(false);

  return (
    <main className="cockpit-shell">
      <div className="relative z-10 mx-auto grid min-h-[calc(100vh-4rem)] max-w-[1240px] gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        {/* ===== LEFT: Brand + Headline ===== */}
        <section className="panel fade-rise flex flex-col justify-between p-6 md:p-9">
          <div>
            <div className="flex items-center gap-3">
              <span className="eyebrow">Distilled TI</span>
              <span className="hairline-strong h-px w-8" aria-hidden />
              <span className="eyebrow">Trait Cartography</span>
            </div>

            <button
              type="button"
              className="brand-plate mt-6 w-full text-left"
              onClick={() => setShowBrandModal(true)}
              aria-label="查看品牌图"
            >
              <Image
                src="/brand/hero-logo.png"
                alt="Distilled TI 品牌图"
                width={1024}
                height={576}
                className="brand-hero-image"
                priority
              />
            </button>

            <h1 className="mt-7 max-w-3xl text-[2.5rem] leading-[1.05] text-[color:var(--ink-strong)] md:text-[3.6rem]">
              把人格从静态类型，
              <br />
              <span className="text-[color:var(--accent)]">拉回连续结构空间。</span>
            </h1>
            <p className="mt-5 max-w-xl text-[1rem] leading-7 text-[color:var(--ink-muted)] measure">
              这不是一次性的类型贴标，而是一场可以持续推进的行为倾向测绘。答到 20 题后即可先看报告，
              之后也可以继续补题，把画像压得更细。
            </p>
          </div>

          <div className="mt-9 grid gap-3 md:grid-cols-3">
            {[
              ["连续作答", "支持随时中断与续答，20 题后即可先看结构化报告。"],
              ["会话隔离", "每次测试都会下发独立访问令牌，删除后立即失效，1 小时后自动过期。"],
              ["本地管理", "AI 配置与题库管理已移到独立 localhost 管理端，不再暴露在普通入口。"],
            ].map(([title, description]) => (
              <div key={title} className="surface-sunken p-4">
                <p className="label-mini">{title}</p>
                <p className="mt-2 text-[0.85rem] leading-6 text-[color:var(--ink-body)]">{description}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ===== RIGHT: Launch panel ===== */}
        <section className="panel-paper fade-rise flex flex-col p-6 md:p-9" style={{ animationDelay: "80ms" }}>
          <div className="flex items-center justify-between">
            <div>
              <p className="label-mini">Launch</p>
              <h2 className="mt-1.5 text-2xl md:text-3xl">开始一次会话</h2>
            </div>
            <span className="chip chip-accent">20 题可出报告</span>
          </div>

          <div className="hairline mt-6" />

          <div className="mt-6 grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="label-mini mb-2 block">默认投影模式</span>
              <select
                className="field"
                value={projectionMode}
                onChange={(event) => setProjectionMode(event.target.value as ProjectionMode)}
              >
                <option value="auto">自动投影</option>
                <option value="structure">结构轴投影</option>
                <option value="core">核心维度投影</option>
              </select>
            </label>
            <label className="block">
              <span className="label-mini mb-2 block">默认命名风格</span>
              <select
                className="field"
                value={namingStyle}
                onChange={(event) => setNamingStyle(event.target.value as NamingStyle)}
              >
                <option value="auto">自动</option>
                <option value="object">物体 / 器件</option>
                <option value="creature">生物 / 怪物</option>
                <option value="role">职业 / 角色</option>
                <option value="apparatus">抽象装置</option>
              </select>
            </label>
          </div>

          <div className="mt-6 space-y-2.5">
            <p className="surface-sunken p-3.5 text-[0.85rem] leading-6 text-[color:var(--ink-body)]">
              AI 增强现在由本地管理端统一配置。普通入口不再提交或持久化 API Key，报告会自动使用当前管理员已启用的模型，
              如果没有启用就回退到后端本地摘要。
            </p>
            <p className="rounded-[var(--r-md)] border border-[color:var(--accent-soft)] bg-[color:var(--accent-soft)]/55 p-3.5 text-[0.85rem] leading-6 text-[color:var(--ink-body)]">
              当前版本会为每次测试分配独立的会话密钥与删除令牌。刷新页面仍可续答；主动删除后立即失效，超过 1 小时也会自动清理。
            </p>
            <p className="rounded-[var(--r-md)] border border-[color:var(--warn-soft)] bg-[color:var(--warn-soft)]/55 p-3.5 text-[0.85rem] leading-6 text-[color:var(--warn-ink)]">
              提示：此项目仍属于娱乐与结构化自测，不构成专业诊断、人格定论或现实决策建议。
            </p>
          </div>

          <div className="mt-auto flex flex-col gap-3 pt-7 sm:flex-row">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => {
                saveReportViewPreferences({ projectionMode, namingStyle });
                router.push("/session");
              }}
            >
              开始测试
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => router.push("/history")}
            >
              查看本地历史
            </button>
          </div>
        </section>
      </div>

      {showBrandModal ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[color:var(--bg-ink)]/55 px-6 py-8 backdrop-blur-sm"
          onClick={() => setShowBrandModal(false)}
        >
          <div
            className="relative w-full max-w-5xl overflow-hidden rounded-[var(--r-xl)] border border-[color:var(--line-mid)] bg-[color:var(--bg-paper)] p-5 shadow-[0_30px_120px_rgba(26,24,22,0.35)]"
            onClick={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="absolute right-4 top-4 z-10 flex h-10 w-10 items-center justify-center rounded-full border border-[color:var(--line-mid)] bg-[color:var(--bg-paper)] text-lg text-[color:var(--ink-strong)] shadow-sm transition hover:bg-[color:var(--bg-sunken)]"
              onClick={() => setShowBrandModal(false)}
              aria-label="关闭品牌图预览"
            >
              ×
            </button>
            <div className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
              <div className="rounded-[var(--r-lg)] bg-[color:var(--bg-sunken)] p-3">
                <Image
                  src="/brand/hero-logo.png"
                  alt="Distilled TI 品牌图放大预览"
                  width={1024}
                  height={576}
                  className="h-auto w-full rounded-[var(--r-md)]"
                />
              </div>
              <div className="px-2 py-3 lg:px-4">
                <p className="label-mini">Distilled TI</p>
                <h2 className="mt-3 text-3xl leading-tight text-[color:var(--ink-strong)] md:text-4xl">
                  Distilled TI
                  <br />
                  Not a type. A structure.
                </h2>
                <div className="mt-6 space-y-2 text-[1rem] leading-7 text-[color:var(--ink-body)]">
                  <p>从回答中提纯轮廓，</p>
                  <p>从轮廓中析出结构。</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </main>
  );
}
