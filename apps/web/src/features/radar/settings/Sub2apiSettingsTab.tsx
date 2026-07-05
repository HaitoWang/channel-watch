import type { AnyRecord } from "../types";

/** "sub2api配置" tab: default credentials, default policy, and credential cleanup. */
export function Sub2apiSettingsTab({
  settings,
  draft,
  onDraft,
}: {
  settings: AnyRecord;
  draft: AnyRecord;
  onDraft: (patch: AnyRecord) => void;
}) {
  const sub2apiEnabled = Boolean(settings.sub2api_enabled ?? settings.sub2apiEnabled);
  const sub2apiConfigured = Boolean(settings.sub2api_configured ?? settings.sub2apiConfigured);
  const sub2apiBaseUrl = settings.sub2api_base_url || settings.sub2apiBaseUrl || "";
  const sub2apiPasswordMasked = settings.sub2api_password_masked || settings.sub2apiPasswordMasked;
  const sub2apiAccessTokenMasked = settings.sub2api_access_token_masked || settings.sub2apiAccessTokenMasked;
  const sub2apiRefreshTokenMasked = settings.sub2api_refresh_token_masked || settings.sub2apiRefreshTokenMasked;
  const sub2apiTurnstileTokenMasked = settings.sub2api_turnstile_token_masked || settings.sub2apiTurnstileTokenMasked;

  return (
    <>
      <section className="settings-card span-2">
        <header className="settings-card-head">
          <div>
            <h3>sub2api配置</h3>
            <p>新建 sub2Api 渠道时自动带入账号和默认策略</p>
          </div>
          <div className="settings-status">
            <span className={`badge ${sub2apiEnabled ? "good" : "warn"}`}>{sub2apiEnabled ? "已启用" : "未启用"}</span>
            <span className={`badge ${sub2apiConfigured ? "good" : "warn"}`}>{sub2apiConfigured ? "凭证已配置" : "凭证未配置"}</span>
            {sub2apiBaseUrl ? <span className="badge">{sub2apiBaseUrl}</span> : null}
          </div>
        </header>
        <div className="settings-grid">
          <label className="settings-toggle-row span-2">
            <input
              name="sub2api_enabled"
              type="checkbox"
              checked={Boolean(draft.sub2api_enabled)}
              onChange={(event) => onDraft({ sub2api_enabled: event.target.checked })}
            />
            <span>启用 sub2api 默认配置</span>
          </label>
          <label className="span-2">
            <span>Base URL</span>
            <input
              name="sub2api_base_url"
              placeholder="https://sub2api.example.com"
              autoComplete="off"
              value={draft.sub2api_base_url || ""}
              onChange={(event) => onDraft({ sub2api_base_url: event.target.value })}
            />
          </label>
          <label>
            <span>账号邮箱</span>
            <input
              name="sub2api_email"
              type="email"
              placeholder="sub2Api 登录邮箱"
              autoComplete="off"
              value={draft.sub2api_email || ""}
              onChange={(event) => onDraft({ sub2api_email: event.target.value })}
            />
          </label>
          <label>
            <span>登录密码</span>
            <input
              name="sub2api_password"
              type="password"
              autoComplete="off"
              placeholder={sub2apiPasswordMasked ? `已配置: ${sub2apiPasswordMasked}` : "填写登录密码"}
              value={draft.sub2api_password || ""}
              onChange={(event) => onDraft({ sub2api_password: event.target.value })}
            />
          </label>
          <label>
            <span>accessToken</span>
            <input
              name="sub2api_access_token"
              type="password"
              autoComplete="off"
              placeholder={sub2apiAccessTokenMasked ? `已配置: ${sub2apiAccessTokenMasked}` : "可选，优先使用"}
              value={draft.sub2api_access_token || ""}
              onChange={(event) => onDraft({ sub2api_access_token: event.target.value })}
            />
          </label>
          <label>
            <span>refreshToken</span>
            <input
              name="sub2api_refresh_token"
              type="password"
              autoComplete="off"
              placeholder={sub2apiRefreshTokenMasked ? `已配置: ${sub2apiRefreshTokenMasked}` : "可选，用于刷新登录"}
              value={draft.sub2api_refresh_token || ""}
              onChange={(event) => onDraft({ sub2api_refresh_token: event.target.value })}
            />
          </label>
          <label>
            <span>userId</span>
            <input name="sub2api_user_id" placeholder="可选" autoComplete="off" value={draft.sub2api_user_id || ""} onChange={(event) => onDraft({ sub2api_user_id: event.target.value })} />
          </label>
          <label>
            <span>登录校验 Token</span>
            <input
              name="sub2api_turnstile_token"
              type="password"
              autoComplete="off"
              placeholder={sub2apiTurnstileTokenMasked ? `已配置: ${sub2apiTurnstileTokenMasked}` : "可选"}
              value={draft.sub2api_turnstile_token || ""}
              onChange={(event) => onDraft({ sub2api_turnstile_token: event.target.value })}
            />
          </label>
        </div>
      </section>

      <section className="settings-card span-2">
        <header className="settings-card-head">
          <div>
            <h3>默认策略</h3>
            <p>创建新渠道或关联 Key 时使用</p>
          </div>
        </header>
        <div className="settings-event-grid">
          <label className="settings-toggle-row">
            <input
              name="sub2api_disable_on_rate_multiplier_change"
              type="checkbox"
              checked={Boolean(draft.sub2api_disable_on_rate_multiplier_change)}
              onChange={(event) => onDraft({ sub2api_disable_on_rate_multiplier_change: event.target.checked })}
            />
            <span>倍率变动停止调度</span>
          </label>
          <label className="settings-toggle-row">
            <input
              name="sub2api_disable_on_model_sync_failure"
              type="checkbox"
              checked={Boolean(draft.sub2api_disable_on_model_sync_failure)}
              onChange={(event) => onDraft({ sub2api_disable_on_model_sync_failure: event.target.checked })}
            />
            <span>模型检测失败停止调度</span>
          </label>
        </div>
      </section>

      <section className="settings-card span-2">
        <header className="settings-card-head">
          <div>
            <h3>清理凭证</h3>
            <p>勾选后保存生效</p>
          </div>
        </header>
        <div className="settings-event-grid">
          <label className="settings-toggle-row danger">
            <input
              name="clear_sub2api_password"
              type="checkbox"
              checked={Boolean(draft.clear_sub2api_password)}
              onChange={(event) => onDraft({ clear_sub2api_password: event.target.checked })}
            />
            <span>清空当前密码</span>
          </label>
          <label className="settings-toggle-row danger">
            <input
              name="clear_sub2api_tokens"
              type="checkbox"
              checked={Boolean(draft.clear_sub2api_tokens)}
              onChange={(event) => onDraft({ clear_sub2api_tokens: event.target.checked })}
            />
            <span>清空当前 Token</span>
          </label>
          <label className="settings-toggle-row danger">
            <input
              name="clear_sub2api_turnstile_token"
              type="checkbox"
              checked={Boolean(draft.clear_sub2api_turnstile_token)}
              onChange={(event) => onDraft({ clear_sub2api_turnstile_token: event.target.checked })}
            />
            <span>清空登录校验 Token</span>
          </label>
        </div>
      </section>
    </>
  );
}
