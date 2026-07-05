import type { AnyRecord } from "../types";

/** pushplus credential + delivery channel fields. Rendered hidden unless active. */
export function PushplusFields({
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
  const pushplusConfigured = Boolean(settings.pushplus_configured ?? settings.pushplusConfigured);
  const pushplusMasked = settings.pushplus_token_masked || settings.pushplusTokenMasked;

  return (
    <div className="settings-channel" id="pushplusSettings" hidden={channel !== "pushplus"}>
      <div className="settings-subhead">
        <strong>pushplus</strong>
      </div>
      <label>
        <span>Token</span>
        <input
          name="pushplus_token"
          type="password"
          autoComplete="off"
          placeholder={pushplusConfigured ? `已配置: ${pushplusMasked}` : "填写 pushplus token"}
          value={draft.pushplus_token || ""}
          onChange={(event) => onDraft({ pushplus_token: event.target.value })}
        />
      </label>
      <label>
        <span>发送通道</span>
        <select name="pushplus_channel" value={draft.pushplus_channel || "wechat"} onChange={(event) => onDraft({ pushplus_channel: event.target.value })}>
          <option value="wechat">wechat</option>
          <option value="webhook">webhook</option>
          <option value="cp">企业微信</option>
          <option value="mail">邮件</option>
          <option value="sms">短信</option>
          <option value="call">语音</option>
          <option value="app">App</option>
        </select>
      </label>
      <label>
        <span>消息模板</span>
        <select name="pushplus_template" value={draft.pushplus_template || "markdown"} onChange={(event) => onDraft({ pushplus_template: event.target.value })}>
          <option value="markdown">markdown</option>
          <option value="html">html</option>
          <option value="txt">txt</option>
          <option value="json">json</option>
        </select>
      </label>
      <label className="settings-toggle-row danger">
        <input
          name="clear_pushplus_token"
          type="checkbox"
          checked={Boolean(draft.clear_pushplus_token)}
          onChange={(event) => onDraft({ clear_pushplus_token: event.target.checked })}
        />
        <span>清空当前 Token</span>
      </label>
    </div>
  );
}
