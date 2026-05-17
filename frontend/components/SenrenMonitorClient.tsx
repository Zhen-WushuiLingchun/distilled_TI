"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import {
  SenrenGameError,
  SenrenGameLoading,
  SenrenGameScreen,
} from "@/components/senren-vn/SenrenGameScreen";
import type {
  ApiErrorPayload,
  LiveState,
  LocalGameInfo,
  PersonaData,
  SenrenMode,
  VnChoice,
  VnScene,
} from "@/components/senren-vn/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000/api";

export default function SenrenMonitorClient() {
  const router = useRouter();
  const [sessionId, setSessionId] = useState("");
  const [sessionSecret, setSessionSecret] = useState("");
  const [mode, setMode] = useState<SenrenMode>("");
  const [gamePath, setGamePath] = useState("");
  const [scene, setScene] = useState<VnScene | null>(null);
  const [liveState, setLiveState] = useState<LiveState | null>(null);
  const [allPersonas, setAllPersonas] = useState<Record<string, PersonaData>>({});
  const [localGameInfo, setLocalGameInfo] = useState<LocalGameInfo | null>(null);
  const [displayedText, setDisplayedText] = useState("");
  const [typing, setTyping] = useState(false);
  const [autoMode, setAutoMode] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [showLog, setShowLog] = useState(false);
  const [showSkills, setShowSkills] = useState(false);
  const [showWorkbench, setShowWorkbench] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    const sid = sessionStorage.getItem("senren_session_id") || "";
    const secret = sessionStorage.getItem("senren_session_secret") || "";
    const storedMode = normalizeMode(sessionStorage.getItem("senren_mode") || "");
    const storedPath = sessionStorage.getItem("senren_game_path") || "";

    if (!sid || !secret) {
      router.push("/senren");
      return;
    }

    setSessionId(sid);
    setSessionSecret(secret);
    setMode(storedMode);
    setGamePath(storedPath);
    void bootstrap(sid, secret, storedMode);
    // bootstrap intentionally runs once after sessionStorage is read.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router]);

  useEffect(() => {
    if (!scene) return;
    const line = scene.character_text || scene.narrator_text || "";
    setDisplayedText("");
    setTyping(true);
    let index = 0;

    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = window.setInterval(() => {
      index += 1;
      setDisplayedText(line.slice(0, index));
      if (index >= line.length) {
        setTyping(false);
        if (timerRef.current) window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }, 22);

    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      timerRef.current = null;
    };
    // scene is included through stable scalar fields to avoid restarting typing on unrelated object identity changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scene?.choice_id, scene?.character_text, scene?.narrator_text]);

  useEffect(() => {
    if (!autoMode || !typing || !scene) return;
    const timeout = window.setTimeout(() => finishTyping(scene), 900);
    return () => window.clearTimeout(timeout);
    // finishTyping is a local helper; including it would restart the auto timer every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoMode, typing, scene]);

  async function bootstrap(sid: string, secret: string, storedMode: SenrenMode) {
    setLoading(true);
    setError("");
    await Promise.all([
      fetchLiveState(sid, secret),
      fetchVnScene(sid, secret),
      fetchPersonas(),
      storedMode === "local" ? fetchLocalGameInfo(sid, secret) : Promise.resolve(),
    ]);
    setLoading(false);
  }

  async function fetchPersonas() {
    try {
      const res = await fetch(`${API_BASE}/senren/skills/personas`);
      if (res.ok) {
        const data = await res.json();
        setAllPersonas(data.personas || {});
      }
    } catch {
      // Skills are enrichment only; the VN remains playable without them.
    }
  }

  async function fetchLocalGameInfo(sid: string, secret: string) {
    try {
      const res = await fetch(`${API_BASE}/senren/local-game/${sid}/info`, {
        headers: { "X-Session-Secret": secret },
      });
      if (res.ok) setLocalGameInfo(await res.json());
    } catch {
      // Non-critical.
    }
  }

  async function fetchVnScene(sid: string, secret: string) {
    try {
      const res = await fetch(`${API_BASE}/senren/monitor/${sid}/vn-scene`, {
        headers: { "X-Session-Secret": secret },
      });
      if (!res.ok) {
        const detail = (await res.json().catch(() => ({}))) as ApiErrorPayload;
        throw new Error(detail.detail || "无法加载 VN 场景");
      }
      setScene(await res.json());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "无法加载 VN 场景");
    }
  }

  async function fetchLiveState(sid: string, secret: string) {
    try {
      const res = await fetch(`${API_BASE}/senren/monitor/${sid}/live-state`, {
        headers: { "X-Session-Secret": secret },
      });
      if (res.ok) setLiveState(await res.json());
    } catch {
      // The main VN scene is still playable without the side state.
    }
  }

  function finishTyping(activeScene = scene) {
    if (!activeScene) return;
    if (timerRef.current) window.clearInterval(timerRef.current);
    timerRef.current = null;
    setDisplayedText(activeScene.character_text || activeScene.narrator_text || "");
    setTyping(false);
  }

  async function submitChoice(choice: VnChoice) {
    if (!scene?.choice_id || !sessionId || !sessionSecret) return;
    setSubmitting(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/senren/monitor/choice`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Session-Secret": sessionSecret,
        },
        body: JSON.stringify({
          session_id: sessionId,
          choice_id: scene.choice_id,
          option_key: choice.option_key,
        }),
      });
      if (!res.ok) {
        const detail = (await res.json().catch(() => ({}))) as ApiErrorPayload;
        throw new Error(detail.detail || "选择提交失败");
      }
      await Promise.all([fetchLiveState(sessionId, sessionSecret), fetchVnScene(sessionId, sessionSecret)]);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "选择提交失败");
    } finally {
      setSubmitting(false);
    }
  }

  function leaveSession() {
    sessionStorage.removeItem("senren_session_id");
    sessionStorage.removeItem("senren_session_secret");
    sessionStorage.removeItem("senren_delete_token");
    sessionStorage.removeItem("senren_mode");
    sessionStorage.removeItem("senren_game_path");
    router.push("/senren");
  }

  function goToReport() {
    router.push("/senren/report");
  }

  if (loading) return <SenrenGameLoading />;
  if (!scene) return <SenrenGameError error={error} onExit={leaveSession} />;

  return (
    <SenrenGameScreen
      scene={scene}
      liveState={liveState}
      mode={mode}
      gamePath={gamePath}
      localGameInfo={localGameInfo}
      personas={allPersonas}
      displayedText={displayedText}
      typing={typing}
      autoMode={autoMode}
      hidden={hidden}
      submitting={submitting}
      error={error}
      showLog={showLog}
      showSkills={showSkills}
      showWorkbench={showWorkbench}
      onFinishTyping={() => finishTyping()}
      onSubmitChoice={submitChoice}
      onToggleAuto={() => setAutoMode((value) => !value)}
      onSetHidden={setHidden}
      onSetShowLog={setShowLog}
      onSetShowSkills={setShowSkills}
      onSetShowWorkbench={setShowWorkbench}
      onExit={leaveSession}
      onReport={goToReport}
    />
  );
}

function normalizeMode(value: string): SenrenMode {
  if (value === "local" || value === "story" || value === "monitor") return value;
  return "";
}
