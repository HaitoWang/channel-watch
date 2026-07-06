# 号池自动调度(Pool Auto Scheduler)实施计划

## 目标
channel-watc 监控**上游**(别人的 sub2api/newApi)的三类指标 —— 分组倍率、账号余额、模型可用性 —— 并据此**双向自动开关我方 sub2api 号池里对应的 account**:
- 上游便宜且正常(倍率低于阈值、余额充足、模型可用)→ 自动**启用**我方 account
- 上游倒挂/耗尽/异常(倍率超阈值、余额低于阈值、模型探测失败、探测请求失败)→ 自动**禁用**我方 account

价值:成本最低、API 速度优先、价格不倒挂、上游余额实时可见。

## 我方 sub2api 写接口(已核实)
- `POST {pool_base_url}/api/v1/admin/accounts/{account_id}/schedulable`
- body: `{"schedulable": true|false}`
- 鉴权 header: `x-api-key: <admin-api-key>`(`sub2api/backend/internal/server/middleware/admin_auth.go:48`,常量时间比对)
- handler: `SetSchedulable`(`account_handler.go:1958`)

## 触发方向决策(已与用户确认)
- 映射方式:channel 上手填我方 account id(支持一对多,逗号分隔)
- 调度方向:**双向自动**(开+关)
- 禁用触发条件(全选):倍率高于阈值 / 余额低于阈值或耗尽 / 上游模型探测异常 / 探测请求失败
- 防横跳:禁用即时生效;启用需连续 N 轮(默认 2)全绿才下发

---

## 后端改动(apps/api/app)

### 1. `domain/store/sub2api_config.py` — 扩展全局配置
仿现有 `Sub2apiConfigMixin` 模式,`sub2api_defaults` 新增号池调度相关键:
- `pool_enabled`("0") — 号池自动调度总开关
- `pool_base_url`("") — 我方 sub2api 地址
- `pool_admin_api_key`("") — admin api key(掩码存取,复用 `mask_secret`,新增 `clear_pool_admin_api_key` 清除标志)
- `pool_auto_schedule`("0") — 是否实际下发开关(关闭时仅记录期望态,dry-run)
- `pool_recover_stable_rounds`("2") — 恢复启用所需连续正常轮数
- `pool_rate_threshold_default`("") — 全局默认倍率阈值(channel 未单独设时回落)

对应 `sub2api_settings()` 输出(snake+camel 双写、`*_masked`)、`update_sub2api_settings()` 读取清洗、校验(启用时必须有 base_url + admin_api_key)。

### 2. `domain/store/schema.py` — channels 表加列(ensure_column 幂等)
- `pool_account_ids TEXT` — 逗号分隔的我方 account id 列表
- `pool_rate_threshold REAL` — 该 channel 的倍率阈值(超过则视为倒挂),空则回落全局默认
- `pool_auto_schedule INTEGER NOT NULL DEFAULT 1` — 该 channel 是否参与自动调度
- `pool_desired_state TEXT` — 上次计算的期望态(`enabled`/`disabled`),幂等去重
- `pool_last_pushed_state TEXT` — 上次成功下发我方的状态
- `pool_recover_streak INTEGER NOT NULL DEFAULT 0` — 连续正常轮数计数
- `pool_last_reason TEXT` — 最近一次调度原因
- `pool_last_error TEXT` — 最近一次下发失败信息
- `pool_last_pushed_at TEXT`

### 3. 新建 `infrastructure/integrations/pool_sub2api.py` — 写动作封装
```
set_account_schedulable(base_url, admin_api_key, account_id, enabled) -> dict
```
复用 `_http.py` 的 `http_json("POST", f"{base}/api/v1/admin/accounts/{id}/schedulable", {"x-api-key": key}, {"schedulable": enabled})`。不引第三方库。异常沿用 `ApiError`。

### 4. 新建 `domain/store/pool_scheduler.py` — 调度决策 Mixin(`PoolSchedulerMixin`)
核心方法:
- `pool_config()` — 读全局号池配置
- `evaluate_pool_schedule(channel_id, row=None, *, notify=True)` — 单渠道决策:
  1. 若 channel 未配 `pool_account_ids` 或 `pool_auto_schedule=0` 或全局 `pool_enabled=0` → 跳过
  2. 汇总信号:`rate_multiplier` vs `pool_rate_threshold`(倒挂)、`balance` vs `threshold`(低余额/耗尽)、`monitor_status`/`status`(模型异常/探测失败)、`last_error`
  3. 有任一红信号 → `target=disabled`(即时);全绿 → `recover_streak+1`,达到 `pool_recover_stable_rounds` → `target=enabled`,否则维持
  4. 仅当 `target != pool_last_pushed_state` 时对每个 account 调 `set_account_schedulable`(幂等,避免每轮打接口)
  5. 成功:更新 `pool_desired_state`/`pool_last_pushed_state`/`pool_last_pushed_at`/`pool_last_reason`;`ensure_event("pool_scheduled")` + `notify_event`
  6. 失败:写 `pool_last_error`,`ensure_event("pool_schedule_failed")`,保留下轮重试
- `schedule_all_pool_channels()` — 批量(供定时/手动全量触发)
- `pool_schedule_preview(channel_id)` — 只算不下发(dry-run 预览)

### 5. 挂接触发点
- `probes.py` `_apply_balance_result`(:357 收尾)→ `self.evaluate_pool_schedule(channel_id)`
- `probes.py` `probe_groups`(:159 倍率写入后)→ 同上
- `probes.py` `_record_probe_failure`(:413)→ 同上(探测失败即时触发)
- `monitoring.py` 模型探测收尾(:190 附近)→ 同上
统一入口 `evaluate_pool_schedule`,逻辑集中不散落。

### 6. `domain/store/__init__.py` — 注册 `PoolSchedulerMixin` 到 `RadarStore`

### 7. `channel_mutations.py`
- `update_channel` 的 `allowed` 白名单加:`pool_account_ids`/`poolAccountIds`、`pool_rate_threshold`/`poolRateThreshold`、`pool_auto_schedule`/`poolAutoSchedule`
- 类型处理:`pool_rate_threshold`→`optional_float`;`pool_auto_schedule`→bool→int;`pool_account_ids`→规整为逗号串(接受数组或字符串,过滤非数字)
- `create_channel` 同步支持这些字段(父账号维度)

### 8. `channel_presenters.py` `public_channel` — 输出新字段(snake+camel):
`pool_account_ids`(转数组回传)、`pool_rate_threshold`、`pool_auto_schedule`、`pool_desired_state`、`pool_last_pushed_state`、`pool_last_reason`、`pool_last_error`、`pool_last_pushed_at`

### 9. `api/routes/channels.py` — 新增手动端点
- `POST /api/channels/:id/pool-schedule` — 立即对该 channel 执行一次调度
- `GET  /api/channels/:id/pool-schedule/preview` — dry-run 预览目标态与原因
- `POST /api/channels/pool-schedule/run-all` — 全量触发一次

### 10. 事件类型
新增 `pool_scheduled`(info/warning)、`pool_schedule_failed`(critical),复用现有 `ensure_event`/`resolve_event`/`notify_event` 通知链路。可选在通知设置里加 `notify_pool_schedule` 开关。

---

## 前端改动(apps/web/src)

### 11. `app/radarModel.ts`
- `settingsFromBackend`:加 `pool_enabled`/`pool_base_url`/`pool_auto_schedule`/`pool_recover_stable_rounds`/`pool_rate_threshold_default` 默认值,`pool_admin_api_key: ""` + `clear_pool_admin_api_key: false`
- `settingsPayloadFromDraft`:`pool_admin_api_key` 空则 delete(仿 sub2api token 清洗)

### 12. 新建 `features/radar/settings/PoolSchedulerSettingsTab.tsx`
照抄 `Sub2apiSettingsTab.tsx`:总开关、base_url、admin_api_key(掩码占位 + 清除)、auto_schedule 下发开关、恢复轮数、全局默认倍率阈值。展示 `pool_configured` 状态。

### 13. `features/radar/SettingsPanel.tsx`
`SettingsTab` 联合类型加 `"pool"`;顶部加 tab 按钮;条件渲染 `<PoolSchedulerSettingsTab>`(共享 draft/onDraft)。

### 14. `features/radar/Modals.tsx`(ChannelModal,父渠道 FormData 表单)
新增字段输入:
- `pool_account_ids`(文本,逗号分隔我方 account id)
- `pool_rate_threshold`(number,倍率阈值)
- `pool_auto_schedule`(checkbox,参与自动调度)
`defaultValue`/`defaultChecked` 取 channel 现值。

### 15. `app/hooks/useRadarActions.ts`(`submitChannel`)
FormData 提取后手动转换:`pool_rate_threshold`→`Number`(空则删)、`pool_auto_schedule`→`=== "on"`、`pool_account_ids`→trim。

### 16. `features/radar/ChannelsPanel.tsx`
在渠道卡片展示调度状态:期望态徽章(启用/禁用)、`pool_last_reason`、映射的 account 数、失败提示。加「立即调度 / 预览」按钮(调新端点)。

### 17. `shared/api/channels.ts`
加 `poolSchedule(id)`、`poolSchedulePreview(id)`、`poolScheduleRunAll()` 封装。

---

## 安全 / 健壮性
- 全局 `pool_enabled` + `pool_auto_schedule` 双开关,默认关闭;配置齐全并手动开启后才真正下发
- 幂等:仅期望态翻转时调我方接口
- 防横跳:禁用即时、启用需连续 N 轮全绿
- 下发失败记录 `pool_last_error` + 事件,下一轮自动重试
- admin_api_key 掩码存储、掩码回显,明文仅在 `include_secret` 时取用
- dry-run 预览端点,便于配置期验证不误伤线上

## 验证
- `python3 -m compileall apps/api/app` 语法自检
- 前端 `npm run build`(tsc --noEmit + vite build)
- 手动:配 1 个上游 channel + 映射我方 account,调 preview 端点核对目标态与原因;开 auto_schedule 后触发一次真实开关并核对我方 sub2api account 状态变化
- 现有 `radarModel.test.ts` 回归

## 交付顺序
后端(1→10)→ 前端(11→17)→ 编译/构建自检 → 说明使用方式
