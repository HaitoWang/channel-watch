import { useState } from "react";

import {
  type AnyRecord,
  boolField,
  isDefaultModelList,
  providerDefaultModels,
} from "../radarModel";

export type ChannelModalState = { mode: "create" } | { mode: "edit"; channel: AnyRecord } | null;
export type KeyModalState = { channel: AnyRecord; draft: AnyRecord; wasDefault: boolean } | null;

/**
 * Owns modal state (channel/key/monitor-log) and the four panel message slots
 * that `notify` routes into. Pure UI state plus open/close/draft helpers; the
 * async submit orchestration lives in useRadarActions.
 */
export function useModals() {
  const [channelModal, setChannelModal] = useState<ChannelModalState>(null);
  const [keyModal, setKeyModal] = useState<KeyModalState>(null);
  const [monitorLog, setMonitorLog] = useState<AnyRecord | null>(null);
  const [formMessage, setFormMessage] = useState("");
  const [keyMessage, setKeyMessage] = useState("");
  const [settingsMessage, setSettingsMessage] = useState("");
  const [monitorLogMessage, setMonitorLogMessage] = useState("");

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
        is_enabled: boolField(channel, "is_enabled", "isEnabled"),
        is_monitoring: boolField(channel, "is_monitoring", "isMonitoring"),
        is_default_key: boolField(channel, "is_default_key", "isDefaultKey"),
        disable_on_rate_multiplier_change: boolField(channel, "disable_on_rate_multiplier_change", "disableOnRateMultiplierChange"),
        disable_on_model_sync_failure: boolField(channel, "disable_on_model_sync_failure", "disableOnModelSyncFailure"),
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

  return {
    channelModal,
    keyModal,
    monitorLog,
    formMessage,
    keyMessage,
    settingsMessage,
    monitorLogMessage,
    setChannelModal,
    setKeyModal,
    setMonitorLog,
    setFormMessage,
    setKeyMessage,
    setSettingsMessage,
    setMonitorLogMessage,
    openKeyModal,
    updateKeyDraft,
    openCreateChannel,
    openEditChannel,
    openMonitorLog,
    closeChannelModal: () => setChannelModal(null),
    closeKeyModal: () => setKeyModal(null),
    closeMonitorLog: () => setMonitorLog(null),
  };
}

export type ModalsController = ReturnType<typeof useModals>;
