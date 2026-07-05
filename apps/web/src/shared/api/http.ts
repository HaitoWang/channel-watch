import { AUTH_EXPIRED_EVENT, clearAuthSession, getAuthToken } from "./auth";

export type RequestOptions = RequestInit & {
  signal?: AbortSignal;
};

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function http<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const token = getAuthToken();
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) {
      clearAuthSession();
      window.dispatchEvent(new Event(AUTH_EXPIRED_EVENT));
    }
    throw new ApiError(response.status, payload.message || `HTTP ${response.status}`);
  }
  return payload as T;
}
