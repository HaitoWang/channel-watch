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
  relogin: (id: number, payload?: ApiPayload) =>
    http<ApiPayload>(`/api/channels/${id}/relogin`, { method: "POST", body: payload ? JSON.stringify(payload) : "{}" }),
  probe: (id: number, suffix: string) => http(`/api/channels/${id}${suffix}`, { method: "POST", body: "{}" }),
  probeGroups: (id: number) => http(`/api/channels/${id}/probe-groups`, { method: "POST", body: "{}" }),
  probeModel: (id: number) => http(`/api/channels/${id}/monitor/probe`, { method: "POST", body: "{}" }),
  poolSchedule: (id: number) => http<ApiPayload>(`/api/channels/${id}/pool-schedule`, { method: "POST", body: "{}" }),
  poolSchedulePreview: (id: number) => http<ApiPayload>(`/api/channels/${id}/pool-schedule/preview`),
  poolScheduleRunAll: () => http<ApiPayload>("/api/channels/pool-schedule/run-all", { method: "POST", body: "{}" }),
  poolEnableAll: () => http<ApiPayload>("/api/channels/pool-schedule/enable-all", { method: "POST", body: "{}" }),
};
