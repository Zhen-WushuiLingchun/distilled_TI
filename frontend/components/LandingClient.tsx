"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";

import { getCurrentUser, redeemInvite } from "@/lib/api";
import {
  clearUserAccess,
  getUserAccess,
  getReportViewPreferences,
  saveReportViewPreferences,
  saveUserAccess,
  type NamingStyle,
  type ProjectionMode,
  type UserAccessBundle,
} from "@/lib/runtime-store";

export function LandingClient() {
  const router = useRouter();
  const [projectionMode, setProjectionMode] = useState<ProjectionMode>(() => getReportViewPreferences().projectionMode);
  const [namingStyle, setNamingStyle] = useState<NamingStyle>(() => getReportViewPreferences().namingStyle);
  const [showBrandModal, setShowBrandModal] = useState(false);
  const [userAccess, setUserAccess] = useState<UserAccessBundle | null>(null);
  const [inviteCode, setInviteCode] = useState("");
  const [registerEmail, setRegisterEmail] = useState("");
  const [inviteBusy, setInviteBusy] = useState(false);
  const [inviteError, setInviteError] = useState("");

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const invite = params.get("invite");
    if (invite) setInviteCode(invite);
    const stored = getUserAccess();
    if (!stored) return;
    setUserAccess(stored);
    getCurrentUser(stored)
      .then((profile) => {
        const refreshed = {
          ...stored,
          handle: profile.handle,
          relationship_opt_in: profile.relationship_opt_in,
          recommendation_opt_in: profile.recommendation_opt_in,
        };
        saveUserAccess(refreshed);
        setUserAccess(refreshed);
      })
      .catch(() => {
        clearUserAccess();
        setUserAccess(null);
      });
  }, []);

  async function handleRedeemInvite() {
    if (!inviteCode.trim()) {
      setInviteError("请输入邀请码。");
      return;
    }
    if (!registerEmail.trim()) {
      setInviteError("请输入注册邮箱。");
      return;
    }
    try {
      setInviteBusy(true);
      setInviteError("");
      const access = await redeemInvite(inviteCode.trim(), registerEmail.trim());
      saveUserAccess(access);
      setUserAccess(access);
      setInviteCode("");
      setRegisterEmail("");
    } catch (reason) {
      setInviteError(reason instanceof Error ? reason.message : "注册失败。");
    } finally {
      setInviteBusy(false);
    }
  }

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
              ["长期画像", "通过邀请码创建匿名 ID 后，历史报告会长期归属到同一用户档案。"],
              ["隐私关系网", "后台只看随机 handle 和邀请关系，不要求真实姓名、手机号或校园身份。"],
              ["Social Lab", "公开推荐入口只显示匿名 handle；结果仍要求双方 opt-in 且有足够历史样本。"],
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
            <div className="surface-sunken p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="label-mini">Invite Identity</p>
                  <h3 className="mt-1.5 text-lg text-[color:var(--ink-strong)]">
                    {userAccess ? `已进入：${userAccess.handle}` : "邀请码 + 邮箱注册，启用长期历史"}
                  </h3>
                </div>
                {userAccess ? <span className="chip chip-accent">匿名档案</span> : <span className="chip">Invite only</span>}
              </div>
              {userAccess ? (
                <p className="mt-3 text-[0.85rem] leading-6 text-[color:var(--ink-muted)]">
                  后续会话会绑定到这个随机 handle。你可以在历史页继续会话、查看报告档案，也可以清除本机凭证重新输入邀请码。
                </p>
              ) : (
                <div className="mt-4 grid gap-2">
                  <input
                    className="field"
                    value={inviteCode}
                    onChange={(event) => setInviteCode(event.target.value)}
                    placeholder="请输入邀请者发给你的一次性邀请码"
                  />
                  <input
                    className="field"
                    type="email"
                    value={registerEmail}
                    onChange={(event) => setRegisterEmail(event.target.value)}
                    placeholder="注册邮箱；一个邮箱只能注册一个匿名档案"
                  />
                  <button className="btn btn-primary" type="button" disabled={inviteBusy} onClick={() => void handleRedeemInvite()}>
                    {inviteBusy ? "注册中…" : "注册并进入"}
                  </button>
                </div>
              )}
              {inviteError ? <p className="mt-2 text-xs text-[color:var(--danger-ink)]">{inviteError}</p> : null}
              {userAccess ? (
                <button
                  className="mt-3 text-xs text-[color:var(--ink-faint)] underline underline-offset-4"
                  type="button"
                  onClick={() => {
                    clearUserAccess();
                    setUserAccess(null);
                  }}
                >
                  清除本机匿名凭证
                </button>
              ) : null}
            </div>
            <p className="surface-sunken p-3.5 text-[0.85rem] leading-6 text-[color:var(--ink-body)]">
              AI 增强现在由本地管理端统一配置。普通入口不再提交或持久化 API Key，报告会自动使用当前管理员已启用的模型，
              如果没有启用就回退到后端本地摘要。
            </p>
            <p className="rounded-[var(--r-md)] border border-[color:var(--accent-soft)] bg-[color:var(--accent-soft)]/55 p-3.5 text-[0.85rem] leading-6 text-[color:var(--ink-body)]">
              注册必须同时提供邀请码和邮箱；后端只保存标准化邮箱哈希用于去重，不在公开页面展示明文邮箱。
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
                router.push("/story");
              }}
            >
              剧情模式
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => {
                saveReportViewPreferences({ projectionMode, namingStyle });
                router.push("/session");
              }}
            >
              工作台模式
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              onClick={() => router.push("/history")}
            >
              查看历史与档案
            </button>
            {userAccess ? (
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => router.push("/profile")}
              >
                用户配置
              </button>
            ) : null}
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
