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
            <h3>盈利护栏</h3>
            <p>只填卖价和目标毛利率，系统自动算倒挂阈值、按成本排序、预测余额燃尽</p>
          </div>
        </header>
        <div className="settings-grid">
          <label>
            <span>对外卖价倍率</span>
            <input
              name="pool_sell_rate"
              type="number"
              step="0.0001"
              min="0"
              placeholder="如 2.0（你对客户的计费倍率）"
              value={draft.pool_sell_rate ?? ""}
              onChange={(event) => onDraft({ pool_sell_rate: event.target.value })}
            />
          </label>
          <label>
            <span>目标毛利率 %</span>
            <input
              name="pool_target_margin"
              type="number"
              step="1"
              min="0"
              placeholder="如 20（低于此毛利即禁用）"
              value={draft.pool_target_margin ?? ""}
              onChange={(event) => onDraft({ pool_target_margin: event.target.value })}
            />
          </label>
          <label>
            <span>燃尽预警窗口（小时）</span>
            <input
              name="pool_burnout_warn_hours"
              type="number"
              step="0.5"
              min="0"
              placeholder="默认 6，0=关闭"
              value={draft.pool_burnout_warn_hours ?? 6}
              onChange={(event) => onDraft({ pool_burnout_warn_hours: event.target.value })}
            />
          </label>
          <label className="settings-toggle-row">
            <input
              name="pool_auto_priority"
              type="checkbox"
              checked={Boolean(draft.pool_auto_priority)}
              onChange={(event) => onDraft({ pool_auto_priority: event.target.checked })}
            />
            <span>自动按成本排序（流量往便宜上游倒）</span>
          </label>
        </div>
        <p className="settings-hint">
          倒挂阈值 = 卖价 ÷ (1 + 目标毛利率)，自动算，无需手填。上游倍率超过它即毛利跌破目标，自动禁用。开启「自动排序」后，监控会把便宜且正常的号池账号 priority 调最优先。渠道/Key 可单独覆盖卖价与毛利率。
        </p>
      </section>

      <section className="settings-card span-2">
        <header className="settings-card-head">
          <div>
            <h3>首 token 慢检测</h3>
            <p>能用但卡也是亏损——查号池账号最近的流式请求首 token 耗时，太慢就停调度</p>
          </div>
        </header>
        <div className="settings-grid">
          <label>
            <span>慢阈值（秒，0=关闭）</span>
            <input
              name="pool_slow_ttft_seconds"
              type="number"
              step="1"
              min="0"
              placeholder="默认 15，首 token 超此值算一次慢"
              value={draft.pool_slow_ttft_seconds ?? 15}
              onChange={(event) => onDraft({ pool_slow_ttft_seconds: event.target.value })}
            />
          </label>
          <label>
            <span>慢几次就停调度</span>
            <input
              name="pool_slow_count"
              type="number"
              step="1"
              min="1"
              placeholder="默认 5"
              value={draft.pool_slow_count ?? 5}
              onChange={(event) => onDraft({ pool_slow_count: event.target.value })}
            />
          </label>
          <label>
            <span>取最近几次样本</span>
            <input
              name="pool_slow_sample"
              type="number"
              step="1"
              min="1"
              placeholder="默认 10"
              value={draft.pool_slow_sample ?? 10}
              onChange={(event) => onDraft({ pool_slow_sample: event.target.value })}
            />
          </label>
          <label>
            <span>最少样本数（不足则跳过）</span>
            <input
              name="pool_slow_min_sample"
              type="number"
              step="1"
              min="1"
              placeholder="默认 5"
              value={draft.pool_slow_min_sample ?? 5}
              onChange={(event) => onDraft({ pool_slow_min_sample: event.target.value })}
            />
          </label>
        </div>
        <p className="settings-hint">
          只对已映射号池账号、且处于启用调度的 Key 生效。取最近 N 次<b>流式</b>请求的首 token 耗时，超阈值达到设定次数即判「慢」并停止调度；样本不足时跳过不判，避免误杀。
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
