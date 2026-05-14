"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import SenrenMonitorClient from "@/components/SenrenMonitorClient";

export default function SenrenMonitorPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const sid = sessionStorage.getItem("senren_session_id");
    const secret = sessionStorage.getItem("senren_session_secret");
    if (!sid || !secret) {
      router.push("/senren");
      return;
    }
    setReady(true);
  }, [router]);

  if (!ready) {
    return (
      <div className="min-h-[calc(100vh-41px)] flex items-center justify-center">
        <p className="text-[var(--senren-ink-muted)] animate-pulse">加载监视器...</p>
      </div>
    );
  }

  return <SenrenMonitorClient />;
}
