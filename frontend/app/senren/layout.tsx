import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "千恋万花 · 人格监视器",
  description: "追踪你在千恋万花中的每一个选择，实时映射深层人格画像。",
};

export default function SenrenLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="senren-theme senren-bg relative">
      {/* 装饰性粒子/樱花效果占位 */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-10 left-[15%] w-1 h-1 rounded-full bg-[var(--senren-sakura)] opacity-20 animate-pulse" />
        <div className="absolute top-[30%] right-[10%] w-1 h-1 rounded-full bg-[var(--senren-gold)] opacity-15" style={{ animationDelay: '1.2s' }} />
        <div className="absolute bottom-[20%] left-[25%] w-0.5 h-0.5 rounded-full bg-[var(--senren-sakura)] opacity-15" style={{ animationDelay: '2.1s' }} />
      </div>

      {/* 顶部导航条 */}
      <nav className="relative z-10 border-b border-[var(--senren-line-soft)] bg-[var(--senren-bg-deep)]/60 backdrop-blur-sm">
        <div className="max-w-6xl mx-auto px-4 py-2.5 flex items-center justify-between">
          <Link
            href="/senren"
            className="text-[var(--senren-gold)] text-sm font-semibold tracking-[0.08em] hover:text-[var(--senren-sakura)] transition-colors"
          >
            千恋＊万花 人格监视器
          </Link>
          <div className="flex items-center gap-4 text-xs text-[var(--senren-ink-muted)]">
            <Link href="/senren/monitor" className="hover:text-[var(--senren-ink-body)] transition-colors">仪表盘</Link>
            <Link href="/senren/report" className="hover:text-[var(--senren-ink-body)] transition-colors">报告</Link>
            <Link href="/senren/history" className="hover:text-[var(--senren-ink-body)] transition-colors">历史</Link>
            <span className="text-[var(--senren-line-mid)]">|</span>
            <Link href="/" className="hover:text-[var(--senren-ink-body)] transition-colors">← TI</Link>
          </div>
        </div>
      </nav>

      <div className="relative z-10">{children}</div>
    </div>
  );
}
