# 盈利护栏（Profit Guard）实施计划

在已有「号池自动调度」之上叠加三个防亏损能力，核心原则：**你只填卖价+毛利率，系统自动算一切**。

## 你需要填的（就这些）

**全局（设置页 · 号池调度 Tab，填一次做默认）**
- `对外卖价倍率`（如 2.0）
- `目标毛利率 %`（如 20）
- `自动 priority 排序`开关

**Key 级（可选，不同上游成本不同时才覆盖，不填就吃全局默认）**
- 该 Key 的卖价倍率 / 目标毛利率

系统**自动算**：倒挂阈值 = 卖价 ÷ (1+毛利率)、当前毛利率、priority 排序、余额燃尽小时数。你不用碰这些数字。

---

## 一、毛利护栏（自动算倒挂阈值）

**逻辑**：`有效阈值 = 卖价倍率 ÷ (1 + 目标毛利率)`。当上游倍率 > 有效阈值 → 毛利跌破目标 → 触发禁用（复用现有 pool 调度）。

**取值优先级**（每个 Key 决策时）：
1. Key 自己填的 `pool_rate_threshold`（若填了绝对阈值，最高优先，向后兼容）
2. Key 的卖价/毛利率算出的阈值
3. 全局卖价/毛利率算出的阈值
4. 全局 `pool_rate_threshold_default`（兜底）

**改动**
- `sub2api_config.py`：全局加 `pool_sell_rate` / `pool_target_margin`（默认卖价、目标毛利率%）
- `schema.py`：channels 加 `pool_sell_rate` / `pool_target_margin`（Key 级可选覆盖）
- `pool_scheduler.py`：`compute_pool_decision` 里 rate_threshold 计算加入护栏公式；决策结果附带 `current_margin`（当前毛利率）供展示
- `channel_presenters.py`：public_channel 输出 `pool_current_margin`（实时毛利），前端徽章显示
- `channel_mutations.py`：白名单加两个字段

## 二、动态 priority 排序（流量自动往便宜上游倒）

**逻辑**：每轮调度后，对「已映射、正常可用」的号池账号，按成本升序排 priority——最便宜且模型正常的排最前（priority 最小 = 最优先被 sub2api 调度）。倍率相同再按模型探测延迟排。

**成本分 = 倍率**（延迟作次要排序键）。禁用态的账号不参与排序（它们已被关停）。

**新增**
- `pool_sub2api.py`：`set_account_priority(base_url, admin_key, account_id, priority)` → `PUT /api/v1/admin/accounts/:id`，body `{"priority": N}`
- `pool_scheduler.py`：`reorder_pool_priority()` — 收集所有健康的映射账号 → 按倍率(+延迟)排序 → 依次下发 priority（步长 10：10,20,30…，留插入空间）；仅在排序变化时下发（幂等）
- 挂到 `schedule_all_pool_channels` 收尾 + 定时器；全局开关 `pool_auto_priority` 控制
- 幂等记录：channels 加 `pool_last_priority` 列，只在变化时调接口

**安全**：只动"已映射且启用"的账号 priority，不碰你手动设的其它账号；开关默认关。

## 三、余额燃尽预测（提前预警"X 小时后没钱"）

**逻辑**：用 `history` 表里该账号最近 N 条 `remaining`（余额）+ `created_at`，线性回归/最小二乘算下降速率（USD/小时）→ `预计耗尽 = 当前余额 ÷ 速率`。低于预警窗口（如 6 小时）时推送。

**改动**
- `pool_scheduler.py` 或新 `burn_rate.py`：`estimate_burn_hours(channel_id)` — 读 history 近 20 条余额点，滤掉充值（余额突增）导致的噪声，算净消耗速率 → 返回预计耗尽小时数
- 新事件类型 `balance_burnout`：`ensure_event` + 通知（复用现有通知层，emoji 格式）
- 触发点：`_apply_balance_result` 收尾，算一次燃尽，低于窗口则预警
- 全局配置 `pool_burnout_warn_hours`（默认 6，0=关闭）
- `channel_presenters.py`：输出 `pool_burn_hours`（预计耗尽小时），前端可显示

**通知文案**：`⏳ 渠道-账号: 余额预计 3.2 小时后耗尽（当前 $8.5，日耗 ~$60），建议充值`

---

## 前端（少配置原则）

- **号池调度 Tab** 加一个「盈利护栏」分区：卖价倍率、目标毛利率、自动排序开关、燃尽预警窗口。共 4 个输入。
- **Key 编辑弹窗**：号池区块加「卖价/毛利率（选填，覆盖全局）」，折叠次要，不填就继承。
- **渠道/Key 卡片**：显示实时毛利率徽章（绿=健康 / 黄=接近阈值 / 红=倒挂）、燃尽小时数。
- 阈值这类算出来的值**只读展示**，不让你手填（除非用旧的绝对阈值覆盖）。

## 健壮性

- 数据不足时降级：history 点太少 → 燃尽预测跳过（不误报）；倍率读不到 → 护栏不误禁用（保持现状）。
- 所有新动作幂等：priority/schedulable 只在变化时下发。
- 全部受开关控制，默认关闭，配齐再开。
- CF 上游数据读不到时，护栏对该 Key 静默跳过（不拿脏数据做决策）—— 并在卡片标「数据缺失」。

## 交付顺序

1. 毛利护栏（自动算阈值 + 实时毛利展示）—— 最直接防亏损
2. 燃尽预测（提前预警）
3. 动态 priority 排序（成本最优）
4. 前端整合 + 编译验证 + 重启

## 验证

- 后端 compile + 各能力单元测试（护栏公式、燃尽回归、priority 排序）
- 前端 tsc / build / vitest
- 桩测 priority 下发（不打真实上游）
