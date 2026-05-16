import { NextRequest, NextResponse } from "next/server";

const DEFAULT_API_BASE = "http://127.0.0.1:8000";
const DEFAULT_APPLICATION_ID = "nextchat-support-demo";
const DEFAULT_CONSENT_BASIS =
  "user terms and local demo consent allow product safety support analysis";

function distilledApiBase() {
  return (process.env.DISTILLED_TI_API_BASE || DEFAULT_API_BASE).replace(
    /\/+$/,
    "",
  );
}

function backendHeaders() {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const apiKey = process.env.DISTILLED_TI_CONTEXT_API_KEY;
  if (apiKey) {
    headers["X-Context-API-Key"] = apiKey;
  }
  return headers;
}

export async function POST(request: NextRequest) {
  const payload = await request.json();
  const response = await fetch(`${distilledApiBase()}/api/context/analyze`, {
    method: "POST",
    headers: backendHeaders(),
    body: JSON.stringify({
      application_id:
        process.env.DISTILLED_TI_APPLICATION_ID || DEFAULT_APPLICATION_ID,
      consent_basis:
        process.env.DISTILLED_TI_CONSENT_BASIS || DEFAULT_CONSENT_BASIS,
      channel: "nextchat",
      locale: "zh-CN",
      persist: true,
      persist_messages: false,
      ...payload,
    }),
    cache: "no-store",
  });

  const body = await response.text();
  return new NextResponse(body, {
    status: response.status,
    headers: {
      "Content-Type":
        response.headers.get("Content-Type") || "application/json",
    },
  });
}

export const runtime = "nodejs";
