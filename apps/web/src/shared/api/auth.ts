export type AuthUser = {
  username: string;
  display_name?: string;
  role?: string;
};

export type AuthSession = {
  access_token: string;
  expires_in: number;
  token_type: "Bearer";
  user: AuthUser;
};

export type AuthBootstrap = {
  username: string;
  password_file: string;
  created_at?: string;
  authenticated: boolean;
  user: AuthUser | null;
};

const TOKEN_KEY = "channel-watch-auth-token";
const USER_KEY = "channel-watch-auth-user";
const EXPIRES_KEY = "channel-watch-auth-expires-at";

export const AUTH_EXPIRED_EVENT = "channel-watch-auth-expired";

export function getAuthToken() {
  return window.localStorage.getItem(TOKEN_KEY) || "";
}

export function getStoredAuthUser(): AuthUser | null {
  const raw = window.localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (isRecord(parsed) && typeof parsed.username === "string") {
      return parsed as AuthUser;
    }
  } catch {
    return null;
  }
  return null;
}

export function saveAuthSession(session: AuthSession) {
  window.localStorage.setItem(TOKEN_KEY, session.access_token);
  window.localStorage.setItem(USER_KEY, JSON.stringify(session.user));
  window.localStorage.setItem(EXPIRES_KEY, String(Date.now() + session.expires_in * 1000));
}

export function clearAuthSession() {
  window.localStorage.removeItem(TOKEN_KEY);
  window.localStorage.removeItem(USER_KEY);
  window.localStorage.removeItem(EXPIRES_KEY);
}

export async function fetchAuthBootstrap(): Promise<AuthBootstrap> {
  return authRequest<AuthBootstrap>("/api/auth/bootstrap");
}

export async function login(username: string, password: string): Promise<AuthSession> {
  return authRequest<AuthSession>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function logout(): Promise<void> {
  await authRequest<{ ok: boolean }>("/api/auth/logout", { method: "POST", body: "{}" }).catch(() => null);
}

async function authRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAuthToken();
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(path, { ...options, headers });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(apiMessage(payload) || `HTTP ${response.status}`);
  }
  return payload as T;
}

function apiMessage(payload: unknown) {
  if (isRecord(payload) && typeof payload.message === "string") {
    return payload.message;
  }
  return "";
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
