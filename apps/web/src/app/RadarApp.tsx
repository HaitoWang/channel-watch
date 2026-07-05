import { type FormEvent, useEffect, useRef, useState } from "react";

import { http } from "../shared/api/http";
import {
  AlertsPanel,
  ChannelModal,
  ChannelsPanel,
  KeyModal,
  LogsPanel,
  MonitorLogModal,
  MonitorPanel,
  OverviewPanel,
  RadarCanvas,
  RatesPanel,
  SceneOrbit,
  SettingsPanel,
  UsagePanel,
} from "../features/radar/RadarPanels";

type ViewName = "overview" | "channels" | "monitor" | "alerts" | "rates" | "usage" | "logs" | "settings";
type AnyRecord = Record<string, any>;

const viewMeta: Record<ViewName, { title: string; subtitle: string }> = {
  overview: { title: "渠道雷达", subtitle: "newApi / sub2Api 状态概览" },
  channels: { title: "渠道管理", subtitle: "Base URL、凭证、阈值和探测状态" },
  monitor: { title: "监控室", subtitle: "已启动监控的 Key 和模型探测结果" },
  alerts: { title: "告警中心", subtitle: "余额阈值、探测失败和倍率变化" },
  rates: { title: "分组倍率", subtitle: "分组、模型范围和有效倍率" },
  usage: { title: "消耗分析", subtitle: "余额、消耗和低余额风险" },
  logs: { title: "探测日志", subtitle: "余额、倍率和告警时间线" },
  settings: { title: "通知设置", subtitle: "pushplus / Server酱 / QQBot 通知" },
};

const MONITOR_REFRESH_MS = 5000;
const CHANNEL_REFRESH_MS = 30000;

const initialRadarState = {
  channels: [] as AnyRecord[],
  accounts: [] as AnyRecord[],
  events: [] as AnyRecord[],
  allEvents: [] as AnyRecord[],
  history: [] as AnyRecord[],
  usage: { summary: {}, channels: [], history: [] } as AnyRecord,
  rates: { summary: {}, channels: [], history: [] } as AnyRecord,
  monitor: { summary: {}, channels: [] } as AnyRecord,
  settings: {} as AnyRecord,
  overview: {} as AnyRecord,
};

function initialView(): ViewName {
  const hash = window.location.hash.slice(1) as ViewName;
  return viewMeta[hash] ? hash : "overview";
}

function field(item: AnyRecord, snake: string, camel?: string) {
  return item[snake] ?? item[camel || snake];
}

function boolField(item: AnyRecord, snake: string, camel?: string) {
  return Boolean(field(item, snake, camel));
}

function providerDefaultModels(provider: string | null | undefined) {
  if (provider === "openai") return ["gpt-5.5"];
  if (provider === "anthropic") return ["claude-sonnet-4-5"];
  return ["gpt-5.5", "claude-sonnet-4-5"];
}

function splitModels(value: string) {
  return String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function isDefaultModelList(value: string) {
  const normalized = splitModels(value).join(",");
  return ["", "gpt-5.5", "claude-sonnet-4-5", "gpt-5.5,claude-sonnet-4-5"].includes(normalized);
}

function settingsFromBackend(settings: AnyRecord) {
  return {
    notification_enabled: Boolean(settings.notification_enabled ?? settings.notificationEnabled),
    notification_channel: settings.notification_channel || settings.notificationChannel || "pushplus",
    pushplus_channel: settings.pushplus_channel || settings.pushplusChannel || "wechat",
    pushplus_template: settings.pushplus_template || settings.pushplusTemplate || "markdown",
    qqbot_app_id: settings.qqbot_app_id || settings.qqbotAppId || "",
    qqbot_target_type: settings.qqbot_target_type || settings.qqbotTargetType || "subscribers",
    qqbot_target_id: settings.qqbot_target_id || settings.qqbotTargetId || "",
    notify_low_balance: settings.notify_low_balance ?? settings.notifyLowBalance ?? true,
    notify_rate_change: settings.notify_rate_change ?? settings.notifyRateChange ?? true,
    notify_model_failure: settings.notify_model_failure ?? settings.notifyModelFailure ?? true,
    pushplus_token: "",
    serverchan_send_key: "",
    qqbot_secret: "",
    clear_pushplus_token: false,
    clear_serverchan_send_key: false,
    clear_qqbot_secret: false,
  };
}

function settingsPayloadFromDraft(draft: AnyRecord) {
  const payload = { ...draft };
  const pushplusToken = String(payload.pushplus_token || "").trim();
  const serverchanSendKey = String(payload.serverchan_send_key || "").trim();
  const qqbotSecret = String(payload.qqbot_secret || "").trim();
  if (pushplusToken) payload.pushplus_token = pushplusToken;
  else delete payload.pushplus_token;
  if (serverchanSendKey) payload.serverchan_send_key = serverchanSendKey;
  else delete payload.serverchan_send_key;
  if (qqbotSecret) payload.qqbot_secret = qqbotSecret;
  else delete payload.qqbot_secret;
  payload.qqbot_app_id = String(payload.qqbot_app_id || "").trim();
  payload.qqbot_target_id = String(payload.qqbot_target_id || "").trim();
  if ((payload.qqbot_target_type || "subscribers") === "subscribers") payload.qqbot_target_id = "";
  return payload;
}

export function RadarApp() {
  const [radar, setRadar] = useState(initialRadarState);
  const [view, setViewState] = useState<ViewName>(initialView);
  const [filter, setFilter] = useState("all");
  const [alertFilter, setAlertFilter] = useState("open");
  const [logKind, setLogKind] = useState("all");
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [loadingIds, setLoadingIds] = useState<Set<number>>(new Set());
  const [syncingRates, setSyncingRates] = useState(false);
  const [toast, setToast] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
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
    if (modalOpen) {
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
      setModalOpen(false);
      form.reset();
    } catch (error) {
      setFormMessage((error as Error).message);
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
    if (modalOpen || keyModal || monitorLog) return;
    if (channelRefreshInFlight || now < nextChannelRefreshAt) return;
    setChannelRefreshInFlight(true);
    loadRadar({ quiet: true })
      .then(() => setNextChannelRefreshAt(Date.now() + CHANNEL_REFRESH_MS))
      .catch((error) => notify((error as Error).message))
      .finally(() => setChannelRefreshInFlight(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, now, nextChannelRefreshAt, channelRefreshInFlight, modalOpen, keyModal, monitorLog]);

  const monitorRefreshSeconds = Math.max(0, Math.ceil((nextMonitorRefreshAt - now) / 1000));

  return (
    <>
      <RadarCanvas />
      <SceneOrbit />
      <div className="app-shell">
        <header className="topbar">
          <a className="brand" href="#" aria-label="渠道雷达首页" onClick={(event) => event.preventDefault()}>
            <span className="brand-mark">R</span>
            <span>
              <strong>Channel Radar</strong>
              <small>AI GATEWAY WATCH</small>
            </span>
          </a>
          <nav className="nav-tabs" aria-label="主导航">
            {(Object.keys(viewMeta) as ViewName[]).map((item) => (
              <button className={item === view ? "nav-tab active" : "nav-tab"} key={item} type="button" data-view={item} onClick={() => setView(item)}>
                {viewMeta[item].title.replace("渠道雷达", "总览").replace("渠道管理", "渠道").replace("告警中心", "告警").replace("分组倍率", "倍率").replace("消耗分析", "消耗").replace("探测日志", "日志").replace("通知设置", "设置")}
              </button>
            ))}
          </nav>
          <div className="top-actions">
            <button className="pill-button" type="button" aria-label="切换语言">
              <span className="icon icon-globe" aria-hidden="true"></span>
              ZH
            </button>
            <button className="account-button" type="button">
              <span className="icon icon-user" aria-hidden="true"></span>
              退出
            </button>
          </div>
        </header>

        <main>
          <section className="hero-strip" aria-labelledby="pageTitle">
            <div>
              <h1 id="pageTitle">{meta.title}</h1>
              <p id="pageSubtitle">{meta.subtitle}</p>
            </div>
            {["overview", "channels", "monitor"].includes(view) ? (
              <button className={isMonitor ? "primary-button is-refresh" : "primary-button"} id="createChannelButton" type="button" onClick={() => (isMonitor ? void refreshMonitorFromHeader() : (setFormMessage(""), setModalOpen(true)))}>
                <span className={`icon ${isMonitor ? "icon-radar" : "icon-plus"}`} aria-hidden="true"></span>
                <span id="createChannelButtonText">{isMonitor ? "刷新" : "新建渠道"}</span>
                {isMonitor ? <small id="createChannelButtonSub">{monitorRefreshInFlight ? "刷新中" : `${monitorRefreshSeconds}s`}</small> : null}
              </button>
            ) : null}
          </section>

          <OverviewPanel active={view === "overview"} radar={radar} onAck={ackEvent} />
          <ChannelsPanel
            active={view === "channels"}
            accounts={radar.accounts}
            filter={filter}
            expandedIds={expandedIds}
            loadingIds={loadingIds}
            onFilter={setFilter}
            onToggleExpand={(id) =>
              setExpandedIds((previous) => {
                const next = new Set(previous);
                if (next.has(id)) next.delete(id);
                else next.add(id);
                return next;
              })
            }
            onProbe={(id) => probeChannel(id, "/probe")}
            onSyncKeys={syncKeys}
            onToggleMonitor={toggleMonitor}
            onEditKey={openKeyModal}
            onSetDefault={setDefaultKey}
            onProbeModels={probeModelChannel}
          />
          <MonitorPanel
            active={view === "monitor"}
            channels={radar.monitor.channels || []}
            history={radar.history}
            loadingIds={loadingIds}
            onProbeModels={probeModelChannel}
            onOpenLog={(channel) => {
              setMonitorLogMessage("");
              setMonitorLog(channel);
            }}
            onEditKey={openKeyModal}
            onToggleMonitor={toggleMonitor}
          />
          <AlertsPanel active={view === "alerts"} events={radar.allEvents} openEvents={radar.events} alertFilter={alertFilter} onFilter={setAlertFilter} onAck={ackEvent} onAckAll={ackAllEvents} />
          <RatesPanel active={view === "rates"} channels={(radar.rates.channels?.length ? radar.rates.channels : radar.channels) || []} loadingIds={loadingIds} syncingRates={syncingRates} onSyncAll={syncAllRates} onProbe={(id) => probeChannel(id, "/probe-groups")} />
          <UsagePanel active={view === "usage"} usage={radar.usage} onProbe={(id) => probeChannel(id, "/probe")} />
          <LogsPanel active={view === "logs"} history={radar.history} events={radar.allEvents} logKind={logKind} onLogKind={setLogKind} />
          <SettingsPanel
            active={view === "settings"}
            settings={radar.settings}
            draft={settingsDraft}
            message={settingsMessage}
            onDraft={(patch) => setSettingsDraft((current) => ({ ...current, ...patch }))}
            onSubmit={submitSettings}
            onTest={testNotification}
          />
        </main>
      </div>

      {modalOpen ? <ChannelModal message={formMessage} onClose={() => setModalOpen(false)} onSubmit={submitChannel} /> : null}
      {keyModal ? <KeyModal keyModal={keyModal} message={keyMessage} onClose={() => setKeyModal(null)} onDraft={updateKeyDraft} onSubmit={submitKeyForm} /> : null}
      {monitorLog ? <MonitorLogModal channel={monitorLog} message={monitorLogMessage} onClose={() => setMonitorLog(null)} /> : null}
      {toast ? <div id="toastMessage" className="toast-message show">{toast}</div> : null}
    </>
  );
}
