import type { AnyRecord } from "../types";

/** "号池调度" tab: 我方 sub2api 号池连接、下发开关、恢复防抖与全局倍率阈值。 */
export function PoolSchedulerSettingsTab({
  settings,
  draft,
  onDraft,
}: {
  settings: AnyRecord;
  draft: AnyRecord;
  onDraft: (patch: AnyRecord) => void;
}) {
  const poolEnabled = Boolean(settings.pool_enabled ?? settings.poolEnabled);
  const poolConfigured = Boolean(settings.pool_configured ?? settings.poolConfigured);
  const poolAutoSchedule = Boolean(settings.pool_auto_schedule ?? settings.poolAutoSchedule);
  const poolBaseUrl = settings.pool_base_url || settings.poolBaseUrl || "";
  const poolAdminKeyMasked = settings.pool_admin_api_key_masked || settings.poolAdminApiKeyMasked;

  return (
    <>
      <div className="settings-callout span-2">
        <strong>账号映射在哪里配？</strong>
        每个上游 <b>Key</b> 对应哪些「我方号池账号 ID」，是在 <b>渠道</b> 页 → 展开账号 → 点某个 Key 的「编辑」→ 弹窗底部「号池自动调度」区块里填写。本页只配置全局的号池连接与调度参数。
      </div>
      <section className="settings-card span-2">
        <header className="settings-card-head">
          <div>
            <h3>号池自动调度</h3>
            <p>根据上游倍率 / 余额 / 模型可用性，自动开关我方 sub2api 号池账号</p>
          </div>
          <div className="settings-status">
            <span className={`badge ${poolEnabled ? "good" : "warn"}`}>{poolEnabled ? "已启用" : "未启用"}</span>
            <span className={`badge ${poolConfigured ? "good" : "warn"}`}>{poolConfigured ? "连接已配置" : "连接未配置"}</span>
            <span className={`badge ${poolAutoSchedule ? "good" : "warn"}`}>{poolAutoSchedule ? "实时下发" : "仅预览"}</span>
            {poolBaseUrl ? <span className="badge">{poolBaseUrl}</span> : null}
          </div>
        </header>
        <div className="settings-grid">
          <label className="settings-toggle-row span-2">
            <input
              name="pool_enabled"
              type="checkbox"
              checked={Boolean(draft.pool_enabled)}
              onChange={(event) => onDraft({ pool_enabled: event.target.checked })}
            />
            <span>启用号池自动调度（总开关）</span>
          </label>
          <label className="settings-toggle-row span-2">
            <input
              name="pool_auto_schedule"
              type="checkbox"
              checked={Boolean(draft.pool_auto_schedule)}
              onChange={(event) => onDraft({ pool_auto_schedule: event.target.checked })}
            />
            <span>实际下发开关（关闭则仅记录期望态，不调用号池接口）</span>
          </label>
          <label className="span-2">
            <span>号池 Base URL</span>
            <input
              name="pool_base_url"
              placeholder="https://our-sub2api.example.com"
              autoComplete="off"
              value={draft.pool_base_url || ""}
              onChange={(event) => onDraft({ pool_base_url: event.target.value })}
            />
          </label>
          <label className="span-2">
            <span>号池 Admin API Key</span>
            <input
              name="pool_admin_api_key"
              type="password"
              autoComplete="off"
              placeholder={poolAdminKeyMasked ? `已配置: ${poolAdminKeyMasked}` : "sub2api 管理端 x-api-key"}
              value={draft.pool_admin_api_key || ""}
              onChange={(event) => onDraft({ pool_admin_api_key: event.target.value })}
            />
          </label>
          <label>
            <span>恢复稳定轮数</span>
            <input
              name="pool_recover_stable_rounds"
              type="number"
              min="1"
              step="1"
              value={draft.pool_recover_stable_rounds ?? 2}
              onChange={(event) => onDraft({ pool_recover_stable_rounds: event.target.value })}
            />
          </label>
          <label>
            <span>调度周期（秒）</span>
            <input
              name="pool_scan_interval"
              type="number"
              min="0"
              step="1"
              placeholder="默认 120，0 表示暂停轮询"
              value={draft.pool_scan_interval ?? 120}
              onChange={(event) => onDraft({ pool_scan_interval: event.target.value })}
            />
          </label>
          <label>
            <span>全局默认倍率阈值</span>
            <input
              name="pool_rate_threshold_default"
              type="number"
              step="0.0001"
              min="0"
              placeholder="留空表示不按倍率禁用"
              value={draft.pool_rate_threshold_default ?? ""}
              onChange={(event) => onDraft({ pool_rate_threshold_default: event.target.value })}
            />
          </label>
        </div>
        <p className="settings-hint">
          禁用即时生效；恢复启用需上游指标连续 N 轮全部正常。定时器按「调度周期」自动巡检全部已映射渠道，改动开关/周期后无需重启即时生效；也可在渠道卡片手动「立即调度」。渠道未单独设置倍率阈值时回落到此全局默认值。
        </p>
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
              name="clear_pool_admin_api_key"
              type="checkbox"
              checked={Boolean(draft.clear_pool_admin_api_key)}
              onChange={(event) => onDraft({ clear_pool_admin_api_key: event.target.checked })}
            />
            <span>清空号池 Admin API Key</span>
          </label>
        </div>
      </section>
    </>
  );
}
