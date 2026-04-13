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
    <main className="relative overflow-hidden px-6 py-10 md:px-10">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.18),_transparent_32%),radial-gradient(circle_at_80%_20%,_rgba(129,140,248,0.18),_transparent_28%),linear-gradient(180deg,_rgba(10,14,29,0.96),_rgba(4,7,18,1))]" />
      <div className="relative mx-auto grid min-h-[calc(100vh-5rem)] max-w-7xl gap-8 lg:grid-cols-[1.1fr_0.9fr]">
        <section className="flex flex-col justify-between rounded-[2.5rem] border border-white/10 bg-white/6 p-8 shadow-[0_40px_140px_rgba(15,23,42,0.65)] backdrop-blur-2xl md:p-10">
          <div>
            <p className="text-xs uppercase tracking-[0.45em] text-cyan-200/70">Distilled TI</p>
            <button
              type="button"
              className="brand-plate mt-6 w-full text-left transition hover:-translate-y-0.5"
              onClick={() => setShowBrandModal(true)}
            >
              <div className="brand-plate-glow" />
              <Image
                src="/brand/hero-logo.png"
                alt="Distilled TI 品牌图"
                width={1024}
                height={576}
                className="brand-hero-image"
                priority
              />
            </button>
            <h1 className="mt-4 max-w-4xl text-5xl leading-[0.95] text-white md:text-7xl">
              把人格从静态类型，
              <span className="text-cyan-300">拉回连续结构空间。</span>
            </h1>
            <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
              这不是一次性的类型贴标，而是一场可以持续推进的行为倾向测绘。答到 20 题后就能先看报告，
              之后也可以继续补题，把画像压得更细。
            </p>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            {[
              ["连续作答", "支持随时中断与续答，20 题后即可先看结构化报告。"],
              ["会话隔离", "每次测试都会下发独立访问令牌，删除后立即失效，1 小时后自动过期。"],
              ["本地管理", "AI 配置与题库管理已移到独立 localhost 管理端，不再暴露在普通入口。"],
            ].map(([title, description]) => (
              <div key={title} className="rounded-[1.6rem] border border-white/10 bg-black/20 p-5">
                <p className="text-sm uppercase tracking-[0.25em] text-cyan-200/60">{title}</p>
                <p className="mt-3 text-sm leading-6 text-slate-300">{description}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-[2.5rem] border border-white/10 bg-black/25 p-8 shadow-[0_40px_140px_rgba(8,15,33,0.72)] backdrop-blur-2xl md:p-10">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs uppercase tracking-[0.4em] text-cyan-200/70">Launch</p>
              <h2 className="mt-3 text-3xl text-white">开始一次会话</h2>
            </div>
            <div className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-4 py-2 text-xs uppercase tracking-[0.3em] text-cyan-100">
              20 题可出报告
            </div>
          </div>

          <div className="mt-8 grid gap-4 md:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm text-slate-300">默认投影模式</span>
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
              <span className="mb-2 block text-sm text-slate-300">默认命名风格</span>
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

          <p className="mt-5 rounded-2xl border border-white/8 bg-white/5 px-4 py-3 text-sm leading-6 text-slate-300">
            AI 增强现在由本地管理端统一配置。普通用户入口不再提交或持久化 API Key，报告会自动使用当前管理员已启用的模型，
            如果没有启用，就安全地回退到后端本地摘要。
          </p>
          <p className="mt-4 rounded-2xl border border-cyan-300/10 bg-cyan-300/5 px-4 py-3 text-sm leading-6 text-slate-300">
            当前版本会为每次测试分配独立的会话密钥和删除令牌，刷新页面仍可续答；主动删除后立即失效，超过 1 小时也会自动清理。
          </p>
          <p className="mt-4 rounded-2xl border border-amber-300/10 bg-amber-300/5 px-4 py-3 text-sm leading-6 text-slate-300">
            提示：此项目仍属于娱乐与结构化自测，不构成专业诊断、人格定论或现实决策建议。
          </p>

          <div className="mt-8 flex flex-col gap-4 sm:flex-row">
            <button
              type="button"
              className="rounded-full bg-cyan-300 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200"
              onClick={() => {
                saveReportViewPreferences({ projectionMode, namingStyle });
                router.push("/session");
              }}
            >
              开始测试
            </button>
            <button
              type="button"
              className="rounded-full border border-white/15 bg-white/6 px-6 py-3 text-sm font-semibold text-white transition hover:bg-white/10"
              onClick={() => router.push("/history")}
            >
              查看本地历史
            </button>
          </div>
        </section>
      </div>

      {showBrandModal ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/82 px-6 py-8 backdrop-blur-md">
          <div className="relative w-full max-w-6xl overflow-hidden rounded-[2rem] border border-white/12 bg-[#e8ebef] p-4 shadow-[0_35px_140px_rgba(0,0,0,0.55)]">
            <button
              type="button"
              className="absolute right-4 top-4 z-10 flex h-11 w-11 items-center justify-center rounded-full border border-slate-900/10 bg-white/82 text-xl text-slate-900 shadow-sm transition hover:bg-white"
              onClick={() => setShowBrandModal(false)}
              aria-label="关闭品牌图预览"
            >
              X
            </button>
            <div className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr] lg:items-center">
              <div className="rounded-[1.6rem] bg-[linear-gradient(180deg,_rgba(255,255,255,0.92),_rgba(234,239,243,0.96))] p-4">
                <Image
                  src="/brand/hero-logo.png"
                  alt="Distilled TI 品牌图放大预览"
                  width={1024}
                  height={576}
                  className="h-auto w-full rounded-[1rem]"
                />
              </div>
              <div className="px-2 py-3 text-slate-900 lg:px-4">
                <p className="text-xs uppercase tracking-[0.4em] text-slate-500">Distilled TI</p>
                <h2 className="mt-4 text-4xl leading-tight text-slate-950 md:text-5xl">
                  Distilled TI
                  <br />
                  Not a type. A structure.
                </h2>
                <div className="mt-8 space-y-3 text-lg leading-8 text-slate-700">
                  <p>Distilled TI</p>
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
