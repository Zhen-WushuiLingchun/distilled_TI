export type SessionAccessBundle = {
  session_id: string;
  session_secret: string;
  delete_token: string;
};

export type ProjectionMode = "auto" | "structure" | "core";
export type NamingStyle = "auto" | "object" | "creature" | "role" | "apparatus";

export type ReportViewPreferences = {
  projectionMode: ProjectionMode;
  namingStyle: NamingStyle;
};

const SESSION_ACCESS_KEY = "distilled-ti-active-session-access";
const FINAL_REPORT_KEY = "distilled-ti-final-report-snapshot";
const REPORT_PREFS_KEY = "distilled-ti-report-view-preferences";

function canUseStorage() {
  return typeof window !== "undefined" && typeof window.sessionStorage !== "undefined";
}

export function saveActiveSessionAccess(access: SessionAccessBundle) {
  if (!canUseStorage()) return;
  window.sessionStorage.setItem(SESSION_ACCESS_KEY, JSON.stringify(access));
}

export function getActiveSessionAccess(): SessionAccessBundle | null {
  if (!canUseStorage()) return null;
  const raw = window.sessionStorage.getItem(SESSION_ACCESS_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionAccessBundle;
  } catch {
    return null;
  }
}

export function clearActiveSessionAccess() {
  if (!canUseStorage()) return;
  window.sessionStorage.removeItem(SESSION_ACCESS_KEY);
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
