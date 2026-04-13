import { Suspense } from "react";

import { SessionClient } from "@/components/SessionClient";

export default function SessionPage() {
  return (
    <Suspense fallback={<main className="session-shell">正在准备会话...</main>}>
      <SessionClient />
    </Suspense>
  );
}
