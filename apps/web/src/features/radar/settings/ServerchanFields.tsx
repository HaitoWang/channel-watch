import type { AnyRecord } from "../types";

/** Server酱 SendKey field. Rendered hidden unless active. */
export function ServerchanFields({
  channel,
  settings,
  draft,
  onDraft,
}: {
  channel: string;
  settings: AnyRecord;
  draft: AnyRecord;
  onDraft: (patch: AnyRecord) => void;
}) {
  const serverchanConfigured = Boolean(settings.serverchan_configured ?? settings.serverchanConfigured);
  const serverchanMasked = settings.serverchan_send_key_masked || settings.serverchanSendKeyMasked;

  return (
    <div className="settings-channel" id="serverchanSettings" hidden={channel !== "serverchan"}>
      <div className="settings-subhead">
        <strong>Server酱</strong>
      </div>
      <label>
        <span>SendKey</span>
        <input
          name="serverchan_send_key"
          type="password"
          autoComplete="off"
          placeholder={serverchanConfigured ? `已配置: ${serverchanMasked}` : "填写 Server酱 SendKey"}
          value={draft.serverchan_send_key || ""}
          onChange={(event) => onDraft({ serverchan_send_key: event.target.value })}
        />
      </label>
      <label className="settings-toggle-row danger">
        <input
          name="clear_serverchan_send_key"
          type="checkbox"
          checked={Boolean(draft.clear_serverchan_send_key)}
          onChange={(event) => onDraft({ clear_serverchan_send_key: event.target.checked })}
        />
        <span>清空当前 SendKey</span>
      </label>
    </div>
  );
}
