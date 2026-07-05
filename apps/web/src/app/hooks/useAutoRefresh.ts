import { useEffect, useState } from "react";

import { CHANNEL_REFRESH_MS, MONITOR_REFRESH_MS, type ViewName } from "../radarModel";

interface AutoRefreshDeps {
  view: ViewName;
  /** True when any modal is open — channel auto-refresh pauses while editing. */
  blockChannelRefresh: boolean;
  loadRadar: (options?: { quiet?: boolean }) => Promise<void>;
  refreshMonitorRoom: (options?: { quiet?: boolean }) => Promise<void>;
  notify: (text: string) => void;
}

/**
 * Owns the 1s clock and the monitor/channel auto-refresh scheduling. The
 * effects intentionally re-run every tick (via `now`) so they capture the
 * latest callbacks; trigger deps mirror the original controller exactly.
 */
export function useAutoRefresh({ view, blockChannelRefresh, loadRadar, refreshMonitorRoom, notify }: AutoRefreshDeps) {
  const [monitorRefreshInFlight, setMonitorRefreshInFlight] = useState(false);
  const [channelRefreshInFlight, setChannelRefreshInFlight] = useState(false);
  const [nextMonitorRefreshAt, setNextMonitorRefreshAt] = useState(Date.now() + MONITOR_REFRESH_MS);
  const [nextChannelRefreshAt, setNextChannelRefreshAt] = useState(Date.now() + CHANNEL_REFRESH_MS);
  const [now, setNow] = useState(Date.now());

  async function refreshMonitorFromHeader() {
    setMonitorRefreshInFlight(true);
    try {
      await refreshMonitorRoom({ quiet: true });
      setNextMonitorRefreshAt(Date.now() + MONITOR_REFRESH_MS);
    } catch (error) {
      notify((error as Error).message);
    } finally {
      setMonitorRefreshInFlight(false);
    }
  }

  /** Reset the monitor countdown, e.g. when navigating into the monitor view. */
  function scheduleMonitorRefresh() {
    setNextMonitorRefreshAt(Date.now() + MONITOR_REFRESH_MS);
  }

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (view !== "monitor" || document.hidden) return;
    if (monitorRefreshInFlight || now < nextMonitorRefreshAt) return;
    void refreshMonitorFromHeader();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, now, nextMonitorRefreshAt, monitorRefreshInFlight]);

  useEffect(() => {
    if (view !== "channels" || document.hidden) return;
    if (blockChannelRefresh) return;
    if (channelRefreshInFlight || now < nextChannelRefreshAt) return;
    setChannelRefreshInFlight(true);
    loadRadar({ quiet: true })
      .then(() => setNextChannelRefreshAt(Date.now() + CHANNEL_REFRESH_MS))
      .catch((error) => notify((error as Error).message))
      .finally(() => setChannelRefreshInFlight(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, now, nextChannelRefreshAt, channelRefreshInFlight, blockChannelRefresh]);

  const monitorRefreshSeconds = Math.max(0, Math.ceil((nextMonitorRefreshAt - now) / 1000));

  return {
    monitorRefreshInFlight,
    monitorRefreshSeconds,
    refreshMonitorFromHeader,
    scheduleMonitorRefresh,
  };
}
