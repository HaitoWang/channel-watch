import { http } from "./http";

/** Alert/event acknowledgement endpoints. */
export const eventsApi = {
  ack: (id: number) => http(`/api/events/${id}/ack`, { method: "POST", body: "{}" }),
  ackAll: () => http("/api/events/ack-all", { method: "POST", body: "{}" }),
};
