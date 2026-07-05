import { type Dispatch, type FormEvent, type SetStateAction, useEffect, useRef, useState } from "react";

import { settingsApi } from "../../shared/api/settings";
import {
  type AnyRecord,
  initialRadarState,
  settingsFromBackend,
  settingsPayloadFromDraft,
} from "../radarModel";

type RadarState = typeof initialRadarState;

interface SettingsFormDeps {
  /** Latest backend settings; drives one-way sync into the draft. */
  settings: AnyRecord;
  setRadar: Dispatch<SetStateAction<RadarState>>;
  setSettingsMessage: Dispatch<SetStateAction<string>>;
}

/** Owns the settings draft, its sync-from-backend effect, and submit/test actions. */
export function useSettingsForm({ settings, setRadar, setSettingsMessage }: SettingsFormDeps) {
  const [settingsDraft, setSettingsDraft] = useState(settingsFromBackend({}));
  const lastSettingsUpdated = useRef<string | undefined>(undefined);

  useEffect(() => {
    const updatedAt = settings.updated_at || settings.updatedAt;
    if (updatedAt !== lastSettingsUpdated.current) {
      lastSettingsUpdated.current = updatedAt;
      setSettingsDraft(settingsFromBackend(settings));
    }
  }, [settings]);

  function updateSettingsDraft(patch: AnyRecord) {
    setSettingsDraft((current) => ({ ...current, ...patch }));
  }

  async function submitSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSettingsMessage("保存中...");
    try {
      const result = await settingsApi.update(settingsPayloadFromDraft(settingsDraft));
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
      const result = await settingsApi.testNotification(settingsPayloadFromDraft(settingsDraft));
      setSettingsMessage(result.message || "测试通知已发送");
    } catch (error) {
      setSettingsMessage((error as Error).message);
    }
  }

  return { settingsDraft, updateSettingsDraft, submitSettings, testNotification };
}
