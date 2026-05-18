"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { SenrenDisabledNotice } from "@/components/SenrenDisabledNotice";
import SenrenMonitorClient from "@/components/SenrenMonitorClient";
import { SENREN_ENABLED } from "@/lib/features";

export default function SenrenMonitorPage() {
  const router = useRouter();

  useEffect(() => {
    if (!SENREN_ENABLED) return;
    const sid = sessionStorage.getItem("senren_session_id");
    const secret = sessionStorage.getItem("senren_session_secret");
    if (!sid || !secret) {
      router.push("/senren");
    }
  }, [router]);

  if (!SENREN_ENABLED) {
    return <SenrenDisabledNotice />;
  }

  return <SenrenMonitorClient />;
}
