import { NextRequest, NextResponse } from "next/server";

const DEFAULT_API_BASE = "http://127.0.0.1:8000";
const DEFAULT_APPLICATION_ID = "nextchat-support-demo";

function distilledApiBase() {
  return (process.env.DISTILLED_TI_API_BASE || DEFAULT_API_BASE).replace(
    /\/+$/,
    "",
  );
}

function backendHeaders() {
  const headers: Record<string, string> = {};
  const apiKey = process.env.DISTILLED_TI_CONTEXT_API_KEY;
  if (apiKey) {
    headers["X-Context-API-Key"] = apiKey;
  }
  return headers;
}

function adminTokenAllowed(request: NextRequest) {
  const expected = process.env.DISTILLED_TI_ADMIN_TOKEN;
  if (!expected) {
    return true;
  }
  return request.headers.get("X-Distilled-Admin-Token") === expected;
}

export async function GET(request: NextRequest) {
  if (!adminTokenAllowed(request)) {
    return NextResponse.json(
      { detail: "admin_token_required" },
      { status: 401 },
    );
  }

  const url = new URL(request.url);
  const params = new URLSearchParams();
  params.set(
    "application_id",
    url.searchParams.get("application_id") ||
      process.env.DISTILLED_TI_APPLICATION_ID ||
      DEFAULT_APPLICATION_ID,
  );
  params.set("min_risk", url.searchParams.get("min_risk") || "medium");
  params.set("limit", url.searchParams.get("limit") || "50");

  const response = await fetch(
    `${distilledApiBase()}/api/context/alerts?${params.toString()}`,
    {
      method: "GET",
      headers: backendHeaders(),
      cache: "no-store",
    },
  );
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
