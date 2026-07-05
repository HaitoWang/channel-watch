import { useEffect, useState } from "react";

import { radarApi } from "../shared/api/radar";
import { useAutoRefresh } from "./hooks/useAutoRefresh";
import { useModals } from "./hooks/useModals";
import { useRadarActions } from "./hooks/useRadarActions";
import { useSettingsForm } from "./hooks/useSettingsForm";
import {
  type AnyRecord,
  initialRadarState,
  initialView,
  viewMeta,
  type ViewName,
} from "./radarModel";

/**
 * Composition root for the radar dashboard: owns the core snapshot/filter/UI
 * state and the shared `notify`/`loadRadar` glue, then wires the focused hooks
 * (modals, auto-refresh, settings form, async actions) into a single view model.
 */
export function useRadarController() {
  const [radar, setRadar] = useState(initialRadarState);
  const [view, setViewState] = useState<ViewName>(initialView);
  const [filter, setFilter] = useState("all");
  const [alertFilter, setAlertFilter] = useState("open");
  const [logKind, setLogKind] = useState("all");
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [loadingIds, setLoadingIds] = useState<Set<number>>(new Set());
  const [syncingRates, setSyncingRates] = useState(false);
  const [toast, setToast] = useState("");

  const modals = useModals();

  const meta = viewMeta[view] || viewMeta.overview;
  const isMonitor = view === "monitor";

  const notify = (text: string) => {
    if (!text) return;
    if (modals.monitorLog) {
      modals.setMonitorLogMessage(text);
      return;
    }
    if (modals.keyModal) {
      modals.setKeyMessage(text);
      return;
    }
    if (modals.channelModal) {
      modals.setFormMessage(text);
      return;
    }
    if (view === "settings") {
      modals.setSettingsMessage(text);
      return;
    }
    setToast(text);
    window.setTimeout(() => setToast(""), 3600);
  };

  async function loadRadar({ quiet = false } = {}) {
    if (!quiet) {
      modals.setFormMessage("");
    }
    const [channelsPayload, openEventsPayload, allEventsPayload, historyPayload, usagePayload, ratesPayload, monitorPayload, settingsPayload] =
      await radarApi.snapshot();

    const nextState: typeof initialRadarState = {
      channels: channelsPayload.channels || [],
      accounts: channelsPayload.accounts || [],
      events: openEventsPayload.events || [],
      allEvents: allEventsPayload.events || openEventsPayload.events || [],
      history: historyPayload.history || [],
      usage: {
        summary: usagePayload.summary || {},
        channels: usagePayload.channels || [],
        history: usagePayload.history || [],
      },
      rates: {
        summary: ratesPayload.summary || {},
        channels: ratesPayload.channels || channelsPayload.channels || [],
        history: ratesPayload.history || [],
      },
      monitor: {
        summary: monitorPayload.summary || {},
        channels: monitorPayload.channels || [],
      },
      settings: settingsPayload.settings || {},
      overview: channelsPayload.overview || openEventsPayload.overview || {},
    };
    setRadar(nextState);
    setExpandedIds((previous) => {
      const ids = new Set([...nextState.channels.map((channel: AnyRecord) => Number(channel.id)), ...nextState.accounts.map((account: AnyRecord) => Number(account.id))]);
      return new Set([...previous].filter((id) => ids.has(id)));
    });
  }

  async function refreshMonitorRoom({ quiet = true } = {}) {
    if (!quiet) modals.setMonitorLogMessage("");
    const [monitorPayload, historyPayload] = await radarApi.monitorRoom();
    setRadar((previous) => ({
      ...previous,
      monitor: { summary: monitorPayload.summary || {}, channels: monitorPayload.channels || [] },
      history: historyPayload.history || [],
    }));
  }

  const autoRefresh = useAutoRefresh({
    view,
    blockChannelRefresh: Boolean(modals.channelModal || modals.keyModal || modals.monitorLog),
    loadRadar,
    refreshMonitorRoom,
    notify,
  });

  function setView(nextView: ViewName, push = true) {
    if (!viewMeta[nextView]) return;
    setViewState(nextView);
    if (push) window.location.hash = nextView;
    if (nextView === "monitor") {
      autoRefresh.scheduleMonitorRefresh();
      void autoRefresh.refreshMonitorFromHeader();
    }
  }

  const settingsForm = useSettingsForm({
    settings: radar.settings,
    setRadar,
    setSettingsMessage: modals.setSettingsMessage,
  });

  const actions = useRadarActions({
    radar,
    loadRadar,
    notify,
    setLoadingIds,
    setSyncingRates,
    modals,
  });

  function toggleExpandedId(id: number) {
    setExpandedIds((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  useEffect(() => {
    loadRadar().catch((error) => notify(`后端连接失败: ${(error as Error).message}`));
    const onHashChange = () => {
      const hash = window.location.hash.slice(1) as ViewName;
      if (viewMeta[hash]) setView(hash, false);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    radar,
    view,
    meta,
    isMonitor,
    filter,
    alertFilter,
    logKind,
    expandedIds,
    loadingIds,
    syncingRates,
    toast,
    channelModal: modals.channelModal,
    keyModal: modals.keyModal,
    monitorLog: modals.monitorLog,
    settingsDraft: settingsForm.settingsDraft,
    formMessage: modals.formMessage,
    keyMessage: modals.keyMessage,
    settingsMessage: modals.settingsMessage,
    monitorLogMessage: modals.monitorLogMessage,
    monitorRefreshInFlight: autoRefresh.monitorRefreshInFlight,
    monitorRefreshSeconds: autoRefresh.monitorRefreshSeconds,
    setView,
    setFilter,
    setAlertFilter,
    setLogKind,
    refreshMonitorFromHeader: autoRefresh.refreshMonitorFromHeader,
    probeChannel: actions.probeChannel,
    syncKeys: actions.syncKeys,
    toggleMonitor: actions.toggleMonitor,
    setDefaultKey: actions.setDefaultKey,
    probeModelChannel: actions.probeModelChannel,
    ackEvent: actions.ackEvent,
    ackAllEvents: actions.ackAllEvents,
    syncAllRates: actions.syncAllRates,
    openKeyModal: modals.openKeyModal,
    updateKeyDraft: modals.updateKeyDraft,
    submitKeyForm: actions.submitKeyForm,
    submitChannel: actions.submitChannel,
    deleteChannel: actions.deleteChannel,
    submitSettings: settingsForm.submitSettings,
    testNotification: settingsForm.testNotification,
    toggleExpandedId,
    openCreateChannel: modals.openCreateChannel,
    openEditChannel: modals.openEditChannel,
    openMonitorLog: modals.openMonitorLog,
    updateSettingsDraft: settingsForm.updateSettingsDraft,
    closeChannelModal: modals.closeChannelModal,
    closeKeyModal: modals.closeKeyModal,
    closeMonitorLog: modals.closeMonitorLog,
  };
}
