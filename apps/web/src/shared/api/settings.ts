import { http } from "./http";

type ApiPayload = Record<string, any>;

/** Notification/scan settings endpoints. */
export const settingsApi = {
  update: (payload: ApiPayload) => http<ApiPayload>("/api/settings", { method: "PATCH", body: JSON.stringify(payload) }),
  testNotification: (payload: ApiPayload) =>
    http<ApiPayload>("/api/settings/test-notification", { method: "POST", body: JSON.stringify(payload) }),
};
