import { http } from "./http";

type ApiPayload = Record<string, any>;

/** Channel resource endpoints. Bodies and methods mirror the backend contract exactly. */
export const channelsApi = {
  list: () => http<ApiPayload>("/api/channels"),
  create: (payload: ApiPayload) => http<ApiPayload>("/api/channels", { method: "POST", body: JSON.stringify(payload) }),
  update: (id: number, payload: ApiPayload) => http(`/api/channels/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),
  remove: (id: number) => http(`/api/channels/${id}`, { method: "DELETE" }),
  setDefault: (id: number) => http(`/api/channels/${id}/set-default`, { method: "POST", body: "{}" }),
  syncKeys: (id: number, payload?: ApiPayload) =>
    http(`/api/channels/${id}/sync-keys`, { method: "POST", body: payload ? JSON.stringify(payload) : "{}" }),
  probe: (id: number, suffix: string) => http(`/api/channels/${id}${suffix}`, { method: "POST", body: "{}" }),
  probeGroups: (id: number) => http(`/api/channels/${id}/probe-groups`, { method: "POST", body: "{}" }),
  probeModel: (id: number) => http(`/api/channels/${id}/monitor/probe`, { method: "POST", body: "{}" }),
};
