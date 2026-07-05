import { type Dispatch, type FormEvent, type SetStateAction } from "react";

import { channelsApi } from "../../shared/api/channels";
import { eventsApi } from "../../shared/api/events";
import {
  type AnyRecord,
  boolField,
  initialRadarState,
  providerDefaultModels,
  splitModels,
} from "../radarModel";
import { type ModalsController } from "./useModals";

type RadarState = typeof initialRadarState;

interface RadarActionDeps {
  radar: RadarState;
  loadRadar: (options?: { quiet?: boolean }) => Promise<void>;
  notify: (text: string) => void;
  setLoadingIds: Dispatch<SetStateAction<Set<number>>>;
  setSyncingRates: Dispatch<SetStateAction<boolean>>;
  modals: ModalsController;
}

/**
 * Async orchestration for channel and event operations. Each action mutates
 * upstream state via the API layer then refreshes the radar snapshot, routing
 * failures through `notify`. State ownership stays in the composing hooks.
 */
export function useRadarActions({ radar, loadRadar, notify, setLoadingIds, setSyncingRates, modals }: RadarActionDeps) {
  const addLoading = (id: number) => setLoadingIds((previous) => new Set(previous).add(id));
  const clearLoading = (id: number) =>
    setLoadingIds((previous) => {
      const next = new Set(previous);
      next.delete(id);
      return next;
    });

  async function probeChannel(id: number, suffix: string) {
    addLoading(id);
    try {
      await channelsApi.probe(id, suffix);
      await loadRadar({ quiet: true });
      return true;
    } catch (error) {
      notify((error as Error).message);
      await loadRadar({ quiet: true }).catch(() => {});
      return false;
    } finally {
      clearLoading(id);
    }
  }

  async function syncKeys(id: number) {
    addLoading(id);
    try {
      await channelsApi.syncKeys(id);
      await loadRadar({ quiet: true });
    } catch (error) {
      notify((error as Error).message);
    } finally {
      clearLoading(id);
    }
  }

  async function toggleMonitor(channel: AnyRecord) {
    try {
      await channelsApi.update(channel.id, { is_monitoring: !boolField(channel, "is_monitoring", "isMonitoring") });
      await loadRadar({ quiet: true });
    } catch (error) {
      notify((error as Error).message);
    }
  }

  async function setDefaultKey(id: number) {
    try {
      await channelsApi.setDefault(id);
      await loadRadar({ quiet: true });
    } catch (error) {
      notify((error as Error).message);
    }
  }

  async function probeModelChannel(id: number) {
    addLoading(id);
    try {
      await channelsApi.probeModel(id);
      await loadRadar({ quiet: true });
    } catch (error) {
      notify((error as Error).message);
    } finally {
      clearLoading(id);
    }
  }

  async function ackEvent(id: number) {
    try {
      await eventsApi.ack(id);
      await loadRadar({ quiet: true });
    } catch (error) {
      notify((error as Error).message);
    }
  }

  async function ackAllEvents() {
    try {
      await eventsApi.ackAll();
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
        addLoading(id);
        try {
          await channelsApi.probeGroups(id);
        } catch (error) {
          notify((error as Error).message);
        } finally {
          clearLoading(id);
        }
      }
      await loadRadar({ quiet: true });
    } finally {
      setSyncingRates(false);
    }
  }

  async function submitKeyForm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const keyModal = modals.keyModal;
    if (!keyModal) return;
    const id = Number(keyModal.channel.id);
    const provider = keyModal.draft.key_provider || null;
    const payload = {
      name: String(keyModal.draft.name || "").trim(),
      key_provider: provider,
      monitor_models: splitModels(keyModal.draft.monitor_models || providerDefaultModels(provider).join(",")),
      monitor_interval_seconds: Number(keyModal.draft.monitor_interval_seconds || 60),
      is_enabled: Boolean(keyModal.draft.is_enabled),
      is_monitoring: Boolean(keyModal.draft.is_monitoring),
      disable_on_rate_multiplier_change: Boolean(keyModal.draft.disable_on_rate_multiplier_change),
      disable_on_model_sync_failure: Boolean(keyModal.draft.disable_on_model_sync_failure),
    };
    if (!payload.name) {
      modals.setKeyMessage("Key 名称不能为空");
      return;
    }
    modals.setKeyMessage("保存中...");
    try {
      await channelsApi.update(id, payload);
      if (keyModal.draft.is_default_key && !keyModal.wasDefault) {
        await channelsApi.setDefault(id);
      }
      await loadRadar({ quiet: true });
      modals.setKeyModal(null);
    } catch (error) {
      modals.setKeyMessage((error as Error).message);
    }
  }

  async function submitChannel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const formData = new FormData(form);
    const payload: AnyRecord = Object.fromEntries(formData.entries());
    payload.threshold = Number(payload.threshold || 10);
    payload.is_enabled = formData.get("is_enabled") === "on";
    payload.is_demo = formData.get("is_demo") === "on";
    payload.disable_on_rate_multiplier_change = formData.get("disable_on_rate_multiplier_change") === "on";
    payload.disable_on_model_sync_failure = formData.get("disable_on_model_sync_failure") === "on";
    if (!String(payload.source_channel_id || "").trim()) delete payload.source_channel_id;
    const channelModal = modals.channelModal;
    if (channelModal?.mode === "edit") {
      ["api_key", "access_token", "refresh_token", "password", "turnstile_token"].forEach((key) => {
        if (!String(payload[key] || "").trim()) delete payload[key];
      });
      modals.setFormMessage("保存中...");
      try {
        await channelsApi.update(channelModal.channel.id, payload);
        await loadRadar({ quiet: true });
        modals.setChannelModal(null);
      } catch (error) {
        modals.setFormMessage((error as Error).message);
      }
      return;
    }
    modals.setFormMessage("保存中...");
    try {
      const created = await channelsApi.create(payload);
      modals.setFormMessage("已保存，正在同步 Key 和分组...");
      try {
        const syncPayload = payload.turnstile_token ? { turnstile_token: payload.turnstile_token } : {};
        await channelsApi.syncKeys(created.channel.id, syncPayload);
      } catch (error) {
        notify(`Key 同步失败: ${(error as Error).message}`);
      }
      await loadRadar({ quiet: true });
      if (payload.is_demo || payload.api_key) {
        modals.setFormMessage("已保存，正在首次探测...");
        await probeChannel(created.channel.id, "/probe");
      }
      modals.setChannelModal(null);
      form.reset();
    } catch (error) {
      modals.setFormMessage((error as Error).message);
    }
  }

  async function deleteChannel(channel: AnyRecord) {
    const id = Number(channel.id);
    if (!id) return;
    const children = channel.children || [];
    const suffix = children.length ? `及 ${children.length} 个子 Key` : "";
    if (!window.confirm(`确定删除渠道「${channel.name || id}」${suffix} 吗？`)) return;
    addLoading(id);
    try {
      await channelsApi.remove(id);
      await loadRadar({ quiet: true });
    } catch (error) {
      notify((error as Error).message);
    } finally {
      clearLoading(id);
    }
  }

  return {
    probeChannel,
    syncKeys,
    toggleMonitor,
    setDefaultKey,
    probeModelChannel,
    ackEvent,
    ackAllEvents,
    syncAllRates,
    submitKeyForm,
    submitChannel,
    deleteChannel,
  };
}
