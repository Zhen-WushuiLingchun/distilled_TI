"use client";

import { SenrenDisabledNotice } from "@/components/SenrenDisabledNotice";
import SenrenReportClient from "@/components/SenrenReportClient";
import { SENREN_ENABLED } from "@/lib/features";

export default function SenrenReportPage() {
  if (!SENREN_ENABLED) {
    return <SenrenDisabledNotice />;
  }

  return <SenrenReportClient />;
}
