import Link from "next/link";

export function SenrenDisabledNotice() {
  return (
    <main className="min-h-screen bg-[color:var(--bg-sunken)] px-6 py-12 text-[color:var(--ink-body)]">
      <section className="mx-auto max-w-2xl rounded-[var(--r-xl)] border border-[color:var(--line-mid)] bg-[color:var(--bg-paper)] p-8 shadow-sm">
        <p className="label-mini">Local VN Demo</p>
        <h1 className="mt-3 text-3xl text-[color:var(--ink-strong)]">Senren 本地模式已默认关闭</h1>
        <p className="mt-4 leading-7 text-[color:var(--ink-muted)]">
          这部分会迁移成独立本地 galgame demo，像 NextChat demo 一样只通过标准 API 接入测量后端。
          如需临时调试旧入口，可在前端环境变量中设置 <code>NEXT_PUBLIC_SENREN_ENABLED=true</code> 后重新构建。
        </p>
        <Link className="btn btn-primary mt-6 inline-flex" href="/">
          返回首页
        </Link>
      </section>
    </main>
  );
}
