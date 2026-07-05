import { useState, type FormEvent } from "react";

import type { AnyRecord } from "./types";
import { Panel } from "./layout";
import { MonitorSettingsTab } from "./settings/MonitorSettingsTab";
import { Sub2apiSettingsTab } from "./settings/Sub2apiSettingsTab";

type SettingsTab = "monitor" | "sub2api";

export function SettingsPanel({
  active,
  settings,
  draft,
  message,
  onDraft,
  onSubmit,
  onTest,
}: {
  active: boolean;
  settings: AnyRecord;
  draft: AnyRecord;
  message: string;
  onDraft: (patch: AnyRecord) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onTest: () => void;
}) {
  const [tab, setTab] = useState<SettingsTab>("monitor");

  return (
    <Panel active={active} viewName="settings">
      <section className="settings-panel" aria-label="系统设置">
        <form id="settingsForm" className="channel-form settings-form" onSubmit={onSubmit}>
          <div className="settings-tabs span-2" role="tablist" aria-label="设置分类">
            <button type="button" role="tab" aria-selected={tab === "monitor"} className={tab === "monitor" ? "active" : ""} onClick={() => setTab("monitor")}>
              渠道监控配置
            </button>
            <button type="button" role="tab" aria-selected={tab === "sub2api"} className={tab === "sub2api" ? "active" : ""} onClick={() => setTab("sub2api")}>
              sub2api配置
            </button>
          </div>

          {tab === "monitor" ? (
            <MonitorSettingsTab settings={settings} draft={draft} onDraft={onDraft} />
          ) : (
            <Sub2apiSettingsTab settings={settings} draft={draft} onDraft={onDraft} />
          )}

          <div className="settings-actions span-2">
            <span id="settingsMessage">{message}</span>
            {tab === "monitor" ? (
              <button className="ghost-button" type="button" onClick={onTest}>
                <span className="icon icon-bell" aria-hidden="true"></span>
                测试当前通道
              </button>
            ) : null}
            <button className="primary-button" type="submit">
              保存设置
            </button>
          </div>
        </form>
      </section>
    </Panel>
  );
}
