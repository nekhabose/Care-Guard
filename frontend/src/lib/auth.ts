// Lightweight client-side session store. The backend issues JWTs (HS256) and
// expects them as a Bearer token; there is no login endpoint yet, so the
// coordinator pastes a token (or flips on Demo Mode to explore with sample data).

const TOKEN_KEY = "careguard.token";
const BASE_KEY = "careguard.apiBase";
const DEMO_KEY = "careguard.demo";

export interface JwtClaims {
  sub?: string;
  name?: string;
  email?: string;
  role?: string;
  exp?: number;
  [k: string]: unknown;
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token.trim());
}
export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function getApiBase(): string {
  return (
    localStorage.getItem(BASE_KEY) ??
    (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
    ""
  );
}
export function setApiBase(base: string): void {
  localStorage.setItem(BASE_KEY, base.replace(/\/$/, ""));
}

export function isDemoMode(): boolean {
  return localStorage.getItem(DEMO_KEY) === "1";
}
export function setDemoMode(on: boolean): void {
  if (on) localStorage.setItem(DEMO_KEY, "1");
  else localStorage.removeItem(DEMO_KEY);
}

export function isAuthenticated(): boolean {
  return isDemoMode() || !!getToken();
}

/** Best-effort decode of a JWT payload (no signature check — display only). */
export function decodeClaims(token: string | null): JwtClaims | null {
  if (!token) return null;
  try {
    const part = token.split(".")[1];
    if (!part) return null;
    const json = atob(part.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json) as JwtClaims;
  } catch {
    return null;
  }
}

export function logout(): void {
  clearToken();
  setDemoMode(false);
}
