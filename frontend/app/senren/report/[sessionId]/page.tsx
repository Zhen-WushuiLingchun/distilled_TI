"use client";

import { useParams } from "next/navigation";
import SenrenReportClient from "@/components/SenrenReportClient";

export default function SenrenHistoricalReportPage() {
  const params = useParams();
  const sessionId = params?.sessionId as string;

  // Pass sessionId context — the report client reads from sessionStorage
  // For historical reports, user would need to re-authenticate
  return (
    <div>
      <div className="senren-dashboard-panel text-center mx-4 mt-6 max-w-2xl md:mx-auto">
        <p className="text-sm text-[var(--senren-ink-muted)]">
          历史报告 · 会话 ID: {sessionId}
        </p>
        <p className="text-xs text-[var(--senren-ink-dim)] mt-2">
          请通过当前活动会话查看报告。如需查看历史报告，请在会话未过期时保存凭证。
        </p>
        <a
          href="/senren/report"
          className="inline-block mt-4 text-xs text-[var(--senren-gold)] hover:underline"
        >
          查看当前会话报告 →
        </a>
      </div>
    </div>
  );
}
