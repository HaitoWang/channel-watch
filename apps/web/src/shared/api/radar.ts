import { http } from "./http";

type ApiPayload = Record<string, any>;

/** Aggregate radar reads used by the dashboard loaders. */
export const radarApi = {
  /** Full dashboard snapshot; tuple order is consumed positionally by the loader. */
  snapshot: () =>
    Promise.all([
      http<ApiPayload>("/api/channels"),
      http<ApiPayload>("/api/events"),
      http<ApiPayload>("/api/events?ack=all"),
      http<ApiPayload>("/api/history?limit=160"),
      http<ApiPayload>("/api/usage"),
      http<ApiPayload>("/api/rates"),
      http<ApiPayload>("/api/monitor"),
      http<ApiPayload>("/api/settings"),
    ]),
  monitor: () => http<ApiPayload>("/api/monitor"),
  history: () => http<ApiPayload>("/api/history?limit=160"),
  /** Monitor room refresh: monitor + history in parallel. */
  monitorRoom: () => Promise.all([http<ApiPayload>("/api/monitor"), http<ApiPayload>("/api/history?limit=160")]),
};
