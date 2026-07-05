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
import { type ViewName, viewMeta } from "./radarModel";
import { useRadarController } from "./useRadarController";

export function RadarApp() {
  const {
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
    closeChannelModal,
    closeKeyModal,
    closeMonitorLog,
  } = useRadarController();

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
              <button className={isMonitor ? "primary-button is-refresh" : "primary-button"} id="createChannelButton" type="button" onClick={() => (isMonitor ? void refreshMonitorFromHeader() : openCreateChannel())}>
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
            onToggleExpand={toggleExpandedId}
            onProbe={(id) => probeChannel(id, "/probe")}
            onSyncKeys={syncKeys}
            onEditChannel={openEditChannel}
            onDeleteChannel={deleteChannel}
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
            onOpenLog={openMonitorLog}
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
            onDraft={updateSettingsDraft}
            onSubmit={submitSettings}
            onTest={testNotification}
          />
        </main>
      </div>

      {channelModal ? <ChannelModal channelModal={channelModal} message={formMessage} onClose={closeChannelModal} onSubmit={submitChannel} /> : null}
      {keyModal ? <KeyModal keyModal={keyModal} message={keyMessage} onClose={closeKeyModal} onDraft={updateKeyDraft} onSubmit={submitKeyForm} /> : null}
      {monitorLog ? <MonitorLogModal channel={monitorLog} message={monitorLogMessage} onClose={closeMonitorLog} /> : null}
      {toast ? <div id="toastMessage" className="toast-message show">{toast}</div> : null}
    </>
  );
}
