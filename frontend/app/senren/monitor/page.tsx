"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import SenrenMonitorClient from "@/components/SenrenMonitorClient";

export default function SenrenMonitorPage() {
  const router = useRouter();

  useEffect(() => {
    const sid = sessionStorage.getItem("senren_session_id");
    const secret = sessionStorage.getItem("senren_session_secret");
    if (!sid || !secret) {
      router.push("/senren");
    }
  }, [router]);

  return <SenrenMonitorClient />;
}
