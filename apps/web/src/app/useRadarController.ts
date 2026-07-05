import { type FormEvent, useEffect, useRef, useState } from "react";

import { http } from "../shared/api/http";
import {
  CHANNEL_REFRESH_MS,
  MONITOR_REFRESH_MS,
  type AnyRecord,
  boolField,
  initialRadarState,
  initialView,
  isDefaultModelList,
  providerDefaultModels,
  settingsFromBackend,
  settingsPayloadFromDraft,
  splitModels,
  viewMeta,
  type ViewName,
} from "./radarModel";

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
  const [channelModal, setChannelModal] = useState<{ mode: "create" } | { mode: "edit"; channel: AnyRecord } | null>(null);
  const [keyModal, setKeyModal] = useState<{ channel: AnyRecord; draft: AnyRecord; wasDefault: boolean } | null>(null);
  const [monitorLog, setMonitorLog] = useState<AnyRecord | null>(null);
  const [settingsDraft, setSettingsDraft] = useState(settingsFromBackend({}));
  const [formMessage, setFormMessage] = useState("");
  const [keyMessage, setKeyMessage] = useState("");
  const [settingsMessage, setSettingsMessage] = useState("");
  const [monitorLogMessage, setMonitorLogMessage] = useState("");
  const [monitorRefreshInFlight, setMonitorRefreshInFlight] = useState(false);
  const [channelRefreshInFlight, setChannelRefreshInFlight] = useState(false);
  const [nextMonitorRefreshAt, setNextMonitorRefreshAt] = useState(Date.now() + MONITOR_REFRESH_MS);
  const [nextChannelRefreshAt, setNextChannelRefreshAt] = useState(Date.now() + CHANNEL_REFRESH_MS);
  const [now, setNow] = useState(Date.now());
  const lastSettingsUpdated = useRef<string | undefined>(undefined);

  const meta = viewMeta[view] || viewMeta.overview;
  const isMonitor = view === "monitor";

  const notify = (text: string) => {
    if (!text) return;
    if (monitorLog) {
      setMonitorLogMessage(text);
      return;
    }
    if (keyModal) {
      setKeyMessage(text);
      return;
    }
    if (channelModal) {
      setFormMessage(text);
      return;
    }
    if (view === "settings") {
      setSettingsMessage(text);
      return;
    }
    setToast(text);
    window.setTimeout(() => setToast(""), 3600);
  };

  async function loadRadar({ quiet = false } = {}) {
    if (!quiet) {
      setFormMessage("");
    }
    const [channelsPayload, openEventsPayload, allEventsPayload, historyPayload, usagePayload, ratesPayload, monitorPayload, settingsPayload] =
      await Promise.all([
        http<AnyRecord>("/api/channels"),
        http<AnyRecord>("/api/events"),
        http<AnyRecord>("/api/events?ack=all"),
        http<AnyRecord>("/api/history?limit=160"),
        http<AnyRecord>("/api/usage"),
        http<AnyRecord>("/api/rates"),
        http<AnyRecord>("/api/monitor"),
        http<AnyRecord>("/api/settings"),
      ]);

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
    if (!quiet) setMonitorLogMessage("");
    const [monitorPayload, historyPayload] = await Promise.all([http<AnyRecord>("/api/monitor"), http<AnyRecord>("/api/history?limit=160")]);
    setRadar((previous) => ({
      ...previous,
      monitor: { summary: monitorPayload.summary || {}, channels: monitorPayload.channels || [] },
      history: historyPayload.history || [],
    }));
  }

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

  function setView(nextView: ViewName, push = true) {
    if (!viewMeta[nextView]) return;
    setViewState(nextView);
    if (push) window.location.hash = nextView;
    if (nextView === "monitor") {
      setNextMonitorRefreshAt(Date.now() + MONITOR_REFRESH_MS);
      void refreshMonitorFromHeader();
    }
  }

  async function probeChannel(id: number, suffix: string) {
    setLoadingIds((previous) => new Set(previous).add(id));
    try {
      await http(`/api/channels/${id}${suffix}`, { method: "POST", body: "{}" });
      await loadRadar({ quiet: true });
      return true;
    } catch (error) {
      notify((error as Error).message);
      await loadRadar({ quiet: true }).catch(() => {});
      return false;
    } finally {
      setLoadingIds((previous) => {
        const next = new Set(previous);
        next.delete(id);
        return next;
      });
    }
  }

  async function syncKeys(id: number) {
    setLoadingIds((previous) => new Set(previous).add(id));
    try {
      await http(`/api/channels/${id}/sync-keys`, { method: "POST", body: "{}" });
      await loadRadar({ quiet: true });
    } catch (error) {
      notify((error as Error).message);
    } finally {
      setLoadingIds((previous) => {
        const next = new Set(previous);
        next.delete(id);
        return next;
      });
    }
  }

  async function toggleMonitor(channel: AnyRecord) {
    try {
      await http(`/api/channels/${channel.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_monitoring: !boolField(channel, "is_monitoring", "isMonitoring") }),
      });
      await loadRadar({ quiet: true });
    } catch (error) {
      notify((error as Error).message);
    }
  }

  async function setDefaultKey(id: number) {
    try {
      await http(`/api/channels/${id}/set-default`, { method: "POST", body: "{}" });
      await loadRadar({ quiet: true });
    } catch (error) {
      notify((error as Error).message);
    }
  }

  async function probeModelChannel(id: number) {
    setLoadingIds((previous) => new Set(previous).add(id));
    try {
      await http(`/api/channels/${id}/monitor/probe`, { method: "POST", body: "{}" });
      await loadRadar({ quiet: true });
    } catch (error) {
      notify((error as Error).message);
    } finally {
      setLoadingIds((previous) => {
        const next = new Set(previous);
        next.delete(id);
        return next;
      });
    }
  }

  async function ackEvent(id: number) {
    try {
      await http(`/api/events/${id}/ack`, { method: "POST", body: "{}" });
      await loadRadar({ quiet: true });
    } catch (error) {
      notify((error as Error).message);
    }
  }

  async function ackAllEvents() {
    try {
      await http("/api/events/ack-all", { method: "POST", body: "{}" });
      await loadRadar({ quiet: true });
    } catch (error) {
      notify((error as Error).message);
    }
  }

  async function syncAllRates() {
    const ids = radar.channels.filter((channel) => channel.is_enabled ?? channel.isEnabled).map((channel) => Number(channel.id));
    if (!ids.length) return;
    setSyncingRates(true);
    try {
      for (const id of ids) {
        setLoadingIds((previous) => new Set(previous).add(id));
        try {
          await http(`/api/channels/${id}/probe-groups`, { method: "POST", body: "{}" });
        } catch (error) {
          notify((error as Error).message);
        } finally {
          setLoadingIds((previous) => {
            const next = new Set(previous);
            next.delete(id);
            return next;
          });
        }
      }
      await loadRadar({ quiet: true });
    } finally {
      setSyncingRates(false);
    }
  }

  function openKeyModal(channel: AnyRecord) {
    const models = channel.monitor_models || channel.monitorModels || [];
    const provider = channel.key_provider || channel.keyProvider || "";
    setKeyMessage("");
    setKeyModal({
      channel,
      wasDefault: boolField(channel, "is_default_key", "isDefaultKey"),
      draft: {
        name: channel.name || "",
        key_provider: provider,
        monitor_interval_seconds: channel.monitor_interval_seconds || channel.monitorIntervalSeconds || 60,
        monitor_models: models.join(", ") || providerDefaultModels(provider).join(", "),
        is_monitoring: boolField(channel, "is_monitoring", "isMonitoring"),
        is_default_key: boolField(channel, "is_default_key", "isDefaultKey"),
      },
    });
  }

  function updateKeyDraft(patch: AnyRecord) {
    setKeyModal((current) => {
      if (!current) return current;
      const nextDraft = { ...current.draft, ...patch };
      if (patch.key_provider !== undefined && isDefaultModelList(current.draft.monitor_models)) {
        nextDraft.monitor_models = providerDefaultModels(patch.key_provider).join(", ");
      }
      return { ...current, draft: nextDraft };
    });
  }

  async function submitKeyForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!keyModal) return;
    const id = Number(keyModal.channel.id);
    const provider = keyModal.draft.key_provider || null;
    const payload = {
      name: String(keyModal.draft.name || "").trim(),
      key_provider: provider,
      monitor_models: splitModels(keyModal.draft.monitor_models || providerDefaultModels(provider).join(",")),
      monitor_interval_seconds: Number(keyModal.draft.monitor_interval_seconds || 60),
      is_monitoring: Boolean(keyModal.draft.is_monitoring),
    };
    if (!payload.name) {
      setKeyMessage("Key 名称不能为空");
      return;
    }
    setKeyMessage("保存中...");
    try {
      await http(`/api/channels/${id}`, { method: "PATCH", body: JSON.stringify(payload) });
      if (keyModal.draft.is_default_key && !keyModal.wasDefault) {
        await http(`/api/channels/${id}/set-default`, { method: "POST", body: "{}" });
      }
      await loadRadar({ quiet: true });
      setKeyModal(null);
    } catch (error) {
      setKeyMessage((error as Error).message);
    }
  }

  async function submitChannel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    const payload: AnyRecord = Object.fromEntries(formData.entries());
    payload.threshold = Number(payload.threshold || 10);
    payload.is_demo = formData.get("is_demo") === "on";
    if (channelModal?.mode === "edit") {
      ["api_key", "access_token", "refresh_token", "password", "turnstile_token"].forEach((key) => {
        if (!String(payload[key] || "").trim()) delete payload[key];
      });
      setFormMessage("保存中...");
      try {
        await http(`/api/channels/${channelModal.channel.id}`, { method: "PATCH", body: JSON.stringify(payload) });
        await loadRadar({ quiet: true });
        setChannelModal(null);
      } catch (error) {
        setFormMessage((error as Error).message);
      }
      return;
    }
    setFormMessage("保存中...");
    try {
      const created = await http<AnyRecord>("/api/channels", { method: "POST", body: JSON.stringify(payload) });
      setFormMessage("已保存，正在同步 Key 和分组...");
      try {
        const syncPayload = payload.turnstile_token ? { turnstile_token: payload.turnstile_token } : {};
        await http(`/api/channels/${created.channel.id}/sync-keys`, { method: "POST", body: JSON.stringify(syncPayload) });
      } catch (error) {
        notify(`Key 同步失败: ${(error as Error).message}`);
      }
      await loadRadar({ quiet: true });
      if (payload.is_demo || payload.api_key) {
        setFormMessage("已保存，正在首次探测...");
        await probeChannel(created.channel.id, "/probe");
      }
      setChannelModal(null);
      form.reset();
    } catch (error) {
      setFormMessage((error as Error).message);
    }
  }

  async function deleteChannel(channel: AnyRecord) {
    const id = Number(channel.id);
    if (!id) return;
    const children = channel.children || [];
    const suffix = children.length ? `及 ${children.length} 个子 Key` : "";
    if (!window.confirm(`确定删除渠道「${channel.name || id}」${suffix} 吗？`)) return;
    setLoadingIds((previous) => new Set(previous).add(id));
    try {
      await http(`/api/channels/${id}`, { method: "DELETE" });
      await loadRadar({ quiet: true });
    } catch (error) {
      notify((error as Error).message);
    } finally {
      setLoadingIds((previous) => {
        const next = new Set(previous);
        next.delete(id);
        return next;
      });
    }
  }

  async function submitSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSettingsMessage("保存中...");
    try {
      const result = await http<AnyRecord>("/api/settings", { method: "PATCH", body: JSON.stringify(settingsPayloadFromDraft(settingsDraft)) });
      setRadar((previous) => ({ ...previous, settings: result.settings || {} }));
      setSettingsDraft(settingsFromBackend(result.settings || {}));
      setSettingsMessage("已保存");
    } catch (error) {
      setSettingsMessage((error as Error).message);
    }
  }

  async function testNotification() {
    setSettingsMessage("发送中...");
    try {
      const result = await http<AnyRecord>("/api/settings/test-notification", { method: "POST", body: JSON.stringify(settingsPayloadFromDraft(settingsDraft)) });
      setSettingsMessage(result.message || "测试通知已发送");
    } catch (error) {
      setSettingsMessage((error as Error).message);
    }
  }

  function toggleExpandedId(id: number) {
    setExpandedIds((previous) => {
      const next = new Set(previous);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function openCreateChannel() {
    setFormMessage("");
    setChannelModal({ mode: "create" });
  }

  function openEditChannel(channel: AnyRecord) {
    setFormMessage("");
    setChannelModal({ mode: "edit", channel });
  }

  function openMonitorLog(channel: AnyRecord) {
    setMonitorLogMessage("");
    setMonitorLog(channel);
  }

  function updateSettingsDraft(patch: AnyRecord) {
    setSettingsDraft((current) => ({ ...current, ...patch }));
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

  useEffect(() => {
    const updatedAt = radar.settings.updated_at || radar.settings.updatedAt;
    if (updatedAt !== lastSettingsUpdated.current) {
      lastSettingsUpdated.current = updatedAt;
      setSettingsDraft(settingsFromBackend(radar.settings));
    }
  }, [radar.settings]);

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
    if (channelModal || keyModal || monitorLog) return;
    if (channelRefreshInFlight || now < nextChannelRefreshAt) return;
    setChannelRefreshInFlight(true);
    loadRadar({ quiet: true })
      .then(() => setNextChannelRefreshAt(Date.now() + CHANNEL_REFRESH_MS))
      .catch((error) => notify((error as Error).message))
      .finally(() => setChannelRefreshInFlight(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, now, nextChannelRefreshAt, channelRefreshInFlight, channelModal, keyModal, monitorLog]);

  const monitorRefreshSeconds = Math.max(0, Math.ceil((nextMonitorRefreshAt - now) / 1000));

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
    channelModal,
    keyModal,
    monitorLog,
    settingsDraft,
    formMessage,
    keyMessage,
    settingsMessage,
    monitorLogMessage,
    monitorRefreshInFlight,
    monitorRefreshSeconds,
    setView,
    setFilter,
    setAlertFilter,
    setLogKind,
    refreshMonitorFromHeader,
    probeChannel,
    syncKeys,
    toggleMonitor,
    setDefaultKey,
    probeModelChannel,
    ackEvent,
    ackAllEvents,
    syncAllRates,
    openKeyModal,
    updateKeyDraft,
    submitKeyForm,
    submitChannel,
    deleteChannel,
    submitSettings,
    testNotification,
    toggleExpandedId,
    openCreateChannel,
    openEditChannel,
    openMonitorLog,
    updateSettingsDraft,
    closeChannelModal: () => setChannelModal(null),
    closeKeyModal: () => setKeyModal(null),
    closeMonitorLog: () => setMonitorLog(null),
  };
}
