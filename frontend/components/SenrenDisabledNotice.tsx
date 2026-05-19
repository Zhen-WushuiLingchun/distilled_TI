"use client";

import Link from "next/link";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/api";
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || (typeof window !== "undefined" ? window.location.origin : "");
const COMPANION_SOURCE_URL =
  process.env.NEXT_PUBLIC_SENREN_COMPANION_DOWNLOAD_URL ||
  "https://github.com/Zhen-WushuiLingchun/distilled_TI/tree/embedding_insert/senren-local-companion";

export function SenrenDisabledNotice() {
  return (
    <main className="min-h-screen bg-[color:var(--bg-sunken)] px-6 py-12 text-[color:var(--ink-body)]">
      <section className="mx-auto max-w-3xl rounded-[var(--r-xl)] border border-[color:var(--line-mid)] bg-[color:var(--bg-paper)] p-8 shadow-sm">
        <p className="label-mini">Local Companion</p>
        <h1 className="mt-3 text-3xl text-[color:var(--ink-strong)]">Senren 本地游戏模式改为本机 Companion 接入</h1>
        <p className="mt-4 leading-7 text-[color:var(--ink-muted)]">
          网页端不能读取用户电脑里的游戏目录。请在本机运行 companion，它会读取本地游戏目录，然后用你的网站账号把选择和报告记录同步到服务器。
          如需临时调试旧网页入口，可在前端环境变量中设置 <code>NEXT_PUBLIC_SENREN_ENABLED=true</code> 后重新构建。
        </p>
        <div className="mt-6 grid gap-3 rounded-[var(--r-lg)] border border-[color:var(--line-soft)] bg-[color:var(--bg-sunken)] p-4 text-sm">
          <div>
            <p className="label-mini">网站地址</p>
            <code className="mt-1 block rounded bg-white/60 px-3 py-2 text-[color:var(--ink-strong)]">{SITE_URL || "部署后自动显示"}</code>
          </div>
          <div>
            <p className="label-mini">API 接入地址</p>
            <code className="mt-1 block rounded bg-white/60 px-3 py-2 text-[color:var(--ink-strong)]">{API_BASE}</code>
          </div>
          <div>
            <p className="label-mini">Companion 源码 / 下载入口</p>
            <a className="mt-1 block text-[color:var(--accent)] underline underline-offset-4" href={COMPANION_SOURCE_URL}>
              {COMPANION_SOURCE_URL}
            </a>
          </div>
        </div>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link className="btn btn-primary inline-flex" href="/">
            返回首页
          </Link>
          <Link className="btn btn-ghost inline-flex" href="/history">
            查看网站历史档案
          </Link>
        </div>
      </section>
    </main>
  );
}
