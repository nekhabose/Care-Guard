// Lightweight client-side session store. The coordinator signs in with email +
// password at POST /auth/login; the backend returns a short-lived JWT (HS256)
// we send as a Bearer token. Demo Mode bypasses the backend with sample data.

const TOKEN_KEY = "careguard.token";
const BASE_KEY = "careguard.apiBase";
const DEMO_KEY = "careguard.demo";
const USER_KEY = "careguard.user";

export interface JwtClaims {
  sub?: string;
  name?: string;
  email?: string;
  role?: string;
  exp?: number;
  [k: string]: unknown;
}

export interface SessionUser {
  id: string;
  email: string;
  name: string;
  role: string;
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

export function getUser(): SessionUser | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as SessionUser;
  } catch {
    return null;
  }
}
export function setUser(user: SessionUser): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

/** Persist a successful login: token + identity. */
export function setSession(token: string, user: SessionUser): void {
  setToken(token);
  setUser(user);
  setDemoMode(false);
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
  localStorage.removeItem(USER_KEY);
  setDemoMode(false);
}
