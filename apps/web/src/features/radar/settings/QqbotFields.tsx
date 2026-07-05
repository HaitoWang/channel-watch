import { formatTime } from "../../../shared/formatters";
import type { AnyRecord } from "../types";
import { qqbotStatusLabel } from "./monitorStatus";

/** QQBot credentials, target selection, and gateway status. Hidden unless active. */
export function QqbotFields({
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
  const qqbotSecretMasked = settings.qqbot_secret_masked || settings.qqbotSecretMasked || settings.qqbot_client_secret_masked || settings.qqbotClientSecretMasked;
  const qqbotTargetMasked = settings.qqbot_target_id_masked || settings.qqbotTargetIdMasked;
  const qqbotTargetType = draft.qqbot_target_type || "subscribers";
  const qqbotSubscriberCount = Number(settings.qqbot_subscriber_count ?? settings.qqbotSubscriberCount ?? 0);
  const qqbotLastTargetMasked = settings.qqbot_last_target_id_masked || settings.qqbotLastTargetIdMasked;
  const qqbotLastEventType = settings.qqbot_last_event_type || settings.qqbotLastEventType;
  const qqbotLastEventAt = settings.qqbot_last_event_at || settings.qqbotLastEventAt;
  const qqbotGatewayStatus = settings.qqbot_gateway_status || settings.qqbotGatewayStatus || "stopped";
  const qqbotGatewayLastConnectedAt = settings.qqbot_gateway_last_connected_at || settings.qqbotGatewayLastConnectedAt;
  const qqbotGatewayLastError = settings.qqbot_gateway_last_error || settings.qqbotGatewayLastError;
  const qqbotGatewayStatusLabel = qqbotStatusLabel(qqbotGatewayStatus);

  return (
    <div className="settings-channel" id="qqbotSettings" hidden={channel !== "qqbot"}>
      <div className="settings-subhead">
        <strong>QQBot</strong>
      </div>
      <label>
        <span>AppID</span>
        <input name="qqbot_app_id" autoComplete="off" placeholder="填写 QQBot AppID" value={draft.qqbot_app_id || ""} onChange={(event) => onDraft({ qqbot_app_id: event.target.value })} />
      </label>
      <label>
        <span>Secret</span>
        <input
          name="qqbot_secret"
          type="password"
          autoComplete="off"
          placeholder={qqbotSecretMasked ? `已配置: ${qqbotSecretMasked}` : "填写 Secret"}
          value={draft.qqbot_secret || ""}
          onChange={(event) => onDraft({ qqbot_secret: event.target.value })}
        />
      </label>
      <label>
        <span>目标类型</span>
        <select name="qqbot_target_type" value={qqbotTargetType} onChange={(event) => onDraft({ qqbot_target_type: event.target.value })}>
          <option value="subscribers">自动订阅列表</option>
          <option value="group">QQ群</option>
          <option value="user">QQ单聊</option>
          <option value="channel">频道子频道</option>
          <option value="guild_dm">频道私信</option>
        </select>
      </label>
      {qqbotTargetType === "subscribers" ? (
        <label>
          <span>订阅对象</span>
          <input name="qqbot_subscriber_count" readOnly value={`${qqbotSubscriberCount} 个`} />
        </label>
      ) : (
        <label>
          <span>目标 ID</span>
          <input
            name="qqbot_target_id"
            autoComplete="off"
            placeholder={qqbotTargetMasked ? `已配置: ${qqbotTargetMasked}` : "填写 openid / group_openid / channel_id"}
            value={draft.qqbot_target_id || ""}
            onChange={(event) => onDraft({ qqbot_target_id: event.target.value })}
          />
        </label>
      )}
      <label>
        <span>连接方式</span>
        <input name="qqbot_transport" readOnly value="WebSocket 长连接" />
      </label>
      <label>
        <span>连接状态</span>
        <input name="qqbot_gateway_status" readOnly value={qqbotGatewayStatusLabel} />
      </label>
      <label>
        <span>测试指令</span>
        <input name="qqbot_test_command" readOnly value="测试" />
      </label>
      <label className="settings-toggle-row danger">
        <input
          name="clear_qqbot_secret"
          type="checkbox"
          checked={Boolean(draft.clear_qqbot_secret)}
          onChange={(event) => onDraft({ clear_qqbot_secret: event.target.checked })}
        />
        <span>清空当前 Secret</span>
      </label>
      {(qqbotGatewayStatus || qqbotGatewayLastConnectedAt || qqbotGatewayLastError || qqbotLastTargetMasked || qqbotLastEventType) && (
        <div className="settings-hints">
          <span className={`badge ${qqbotGatewayStatus === "connected" ? "good" : qqbotGatewayStatus === "error" ? "bad" : ""}`}>{qqbotGatewayStatusLabel}</span>
          {qqbotGatewayLastConnectedAt && <span className="badge">{formatTime(qqbotGatewayLastConnectedAt)}</span>}
          {qqbotLastEventType && <span className="badge">{qqbotLastEventType}</span>}
          {qqbotLastTargetMasked && <span className="badge">{qqbotLastTargetMasked}</span>}
          {qqbotLastEventAt && <span className="badge">{formatTime(qqbotLastEventAt)}</span>}
          {qqbotGatewayLastError && <span className="badge bad">{qqbotGatewayLastError}</span>}
        </div>
      )}
    </div>
  );
}
