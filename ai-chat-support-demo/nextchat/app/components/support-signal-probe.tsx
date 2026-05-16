"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import type { ChatMessage } from "../store";
import { getMessageTextContent, safeLocalStorage } from "../utils";

type DistilledRole = "user" | "assistant" | "system" | "tool";

type SupportSignalProbeProps = {
  conversationId: string;
  topic: string;
  messages: ChatMessage[];
};

const USER_ID_STORAGE_KEY = "distilled-ti-nextchat-user-id";
const ANALYZE_DEBOUNCE_MS = 1200;
const MAX_CONTEXT_MESSAGES = 30;
const storage = safeLocalStorage();

function getOrCreateUserId() {
  const existing = storage.getItem(USER_ID_STORAGE_KEY);
  if (existing) {
    return existing;
  }
  const generated =
    typeof crypto !== "undefined" && "randomUUID" in crypto
      ? crypto.randomUUID()
      : `user-${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const userId = `nextchat-${generated}`;
  storage.setItem(USER_ID_STORAGE_KEY, userId);
  return userId;
}

function normalizeRole(role: string): DistilledRole {
  if (role === "assistant" || role === "system" || role === "tool") {
    return role;
  }
  return "user";
}

export function SupportSignalProbe(props: SupportSignalProbeProps) {
  const lastSignatureRef = useRef("");
  const [lastRisk, setLastRisk] = useState<string | null>(null);
  const showBadge =
    process.env.NEXT_PUBLIC_DISTILLED_TI_SHOW_SIGNAL_BADGE === "true";

  const distilledMessages = useMemo(() => {
    return props.messages
      .map((message) => ({
        role: normalizeRole(message.role),
        content: getMessageTextContent(message).trim(),
      }))
      .filter((message) => message.content.length > 0)
      .slice(-MAX_CONTEXT_MESSAGES);
  }, [props.messages]);

  const signature = useMemo(
    () =>
      JSON.stringify(
        distilledMessages.map((message) => [
          message.role,
          message.content.slice(0, 280),
        ]),
      ),
    [distilledMessages],
  );

  useEffect(() => {
    if (
      distilledMessages.length < 2 ||
      signature === lastSignatureRef.current
    ) {
      return;
    }

    const timer = window.setTimeout(async () => {
      lastSignatureRef.current = signature;
      try {
        const response = await fetch("/api/distilled/context", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            external_user_id: getOrCreateUserId(),
            conversation_id: props.conversationId,
            messages: distilledMessages,
            metadata: {
              topic: props.topic,
              message_count: props.messages.length,
              source: "nextchat",
            },
          }),
        });
        if (!response.ok) {
          throw new Error(`context_analysis_failed_${response.status}`);
        }
        const payload = await response.json();
        setLastRisk(payload.risk_level || null);
        if (payload.human_review_recommended) {
          console.warn("[Distilled TI] support signal", payload);
        }
      } catch (error) {
        console.warn("[Distilled TI] context analysis unavailable", error);
      }
    }, ANALYZE_DEBOUNCE_MS);

    return () => window.clearTimeout(timer);
  }, [
    distilledMessages,
    props.conversationId,
    props.messages.length,
    props.topic,
    signature,
  ]);

  if (!showBadge) {
    return null;
  }

  return (
    <div
      style={{
        position: "absolute",
        right: 16,
        bottom: 16,
        zIndex: 20,
        borderRadius: 999,
        padding: "6px 10px",
        background: "rgba(17, 24, 39, 0.82)",
        color: "#f9fafb",
        fontSize: 12,
        pointerEvents: "none",
      }}
    >
      Context: {lastRisk || "idle"}
    </div>
  );
}
