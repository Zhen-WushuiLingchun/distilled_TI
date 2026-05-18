export type SessionAccessBundle = {
  session_id: string;
  session_secret: string;
  delete_token: string;
};

export type SessionMode = "core" | "story";

export type UserAccessBundle = {
  user_id: string;
  user_secret: string;
  handle: string;
  relationship_opt_in?: boolean;
  recommendation_opt_in?: boolean;
};

export type ProjectionMode = "auto" | "structure" | "core";
export type NamingStyle = "auto" | "object" | "creature" | "role" | "apparatus";

export type ReportViewPreferences = {
  projectionMode: ProjectionMode;
  namingStyle: NamingStyle;
};

const SESSION_ACCESS_KEY = "distilled-ti-active-session-access";
const SESSION_ACCESS_BY_MODE_KEY = "distilled-ti-active-session-access-by-mode";
const USER_ACCESS_KEY = "distilled-ti-user-access";
const FINAL_REPORT_KEY = "distilled-ti-final-report-snapshot";
const REPORT_PREFS_KEY = "distilled-ti-report-view-preferences";

type SessionAccessByMode = Partial<Record<SessionMode, SessionAccessBundle>>;

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.sessionStorage !== "undefined";
}

function getSessionAccessByMode(): SessionAccessByMode {
  if (!canUseStorage()) return {};
  const raw = window.sessionStorage.getItem(SESSION_ACCESS_BY_MODE_KEY);
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw) as SessionAccessByMode;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function saveSessionAccessByMode(accessByMode: SessionAccessByMode) {
  if (!canUseStorage()) return;
  if (!Object.values(accessByMode).some(Boolean)) {
    window.sessionStorage.removeItem(SESSION_ACCESS_BY_MODE_KEY);
    return;
  }
  window.sessionStorage.setItem(SESSION_ACCESS_BY_MODE_KEY, JSON.stringify(accessByMode));
}

function readLegacyActiveSessionAccess(): SessionAccessBundle | null {
  if (!canUseStorage()) return null;
  const raw = window.sessionStorage.getItem(SESSION_ACCESS_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionAccessBundle;
  } catch {
    return null;
  }
}

export function saveActiveSessionAccess(access: SessionAccessBundle, mode: SessionMode = "core") {
  if (!canUseStorage()) return;
  const accessByMode = getSessionAccessByMode();
  accessByMode[mode] = access;
  saveSessionAccessByMode(accessByMode);
  if (mode === "core") {
    window.sessionStorage.setItem(SESSION_ACCESS_KEY, JSON.stringify(access));
  }
}

export function getActiveSessionAccess(mode?: SessionMode): SessionAccessBundle | null {
  if (!canUseStorage()) return null;
  if (mode) {
    const accessByMode = getSessionAccessByMode();
    const scopedAccess = accessByMode[mode];
    if (scopedAccess) return scopedAccess;
    if (mode !== "core") return null;
  }
  return readLegacyActiveSessionAccess();
}

export function clearActiveSessionAccess(mode?: SessionMode) {
  if (!canUseStorage()) return;
  if (!mode) {
    window.sessionStorage.removeItem(SESSION_ACCESS_KEY);
    window.sessionStorage.removeItem(SESSION_ACCESS_BY_MODE_KEY);
    return;
  }
  const accessByMode = getSessionAccessByMode();
  const removedSessionId = accessByMode[mode]?.session_id;
  delete accessByMode[mode];
  saveSessionAccessByMode(accessByMode);
  if (mode === "core") {
    const legacyAccess = readLegacyActiveSessionAccess();
    if (!removedSessionId || legacyAccess?.session_id === removedSessionId) {
      window.sessionStorage.removeItem(SESSION_ACCESS_KEY);
    }
  }
}

export function saveUserAccess(access: UserAccessBundle) {
  if (!canUseStorage()) return;
  window.localStorage.setItem(USER_ACCESS_KEY, JSON.stringify(access));
}

export function getUserAccess(): UserAccessBundle | null {
  if (!canUseStorage()) return null;
  const raw = window.localStorage.getItem(USER_ACCESS_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as UserAccessBundle;
  } catch {
    return null;
  }
}

export function clearUserAccess() {
  if (!canUseStorage()) return;
  window.localStorage.removeItem(USER_ACCESS_KEY);
}

export function saveFinalReportSnapshot(snapshot: unknown) {
  if (!canUseStorage()) return;
  window.sessionStorage.setItem(FINAL_REPORT_KEY, JSON.stringify(snapshot));
}

export function getFinalReportSnapshot<T>() {
  if (!canUseStorage()) return null as T | null;
  const raw = window.sessionStorage.getItem(FINAL_REPORT_KEY);
  if (!raw) return null as T | null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null as T | null;
  }
}

export function clearFinalReportSnapshot() {
  if (!canUseStorage()) return;
  window.sessionStorage.removeItem(FINAL_REPORT_KEY);
}

export function saveReportViewPreferences(preferences: ReportViewPreferences) {
  if (!canUseStorage()) return;
  window.sessionStorage.setItem(REPORT_PREFS_KEY, JSON.stringify(preferences));
}

export function getReportViewPreferences(): ReportViewPreferences {
  if (!canUseStorage()) return { projectionMode: "auto", namingStyle: "auto" };
  const raw = window.sessionStorage.getItem(REPORT_PREFS_KEY);
  if (!raw) return { projectionMode: "auto", namingStyle: "auto" };
  try {
    return JSON.parse(raw) as ReportViewPreferences;
  } catch {
    return { projectionMode: "auto", namingStyle: "auto" };
  }
}
