# Channel Radar Architecture

目标是前后端分离，同时保持现有功能可用。

```text
channel-watc/
  apps/
    web/                  React + Vite 前端
      src/
        app/              应用入口、状态编排、API 动作
        features/radar/   雷达页面展示组件、卡片、弹窗
        shared/           API client、布局、通用 UI、配置
    api/                  后端 API 目标结构
      app/
        api/routes/       HTTP 路由
        core/             配置、启动、调度器
        domain/           业务用例
        infrastructure/   数据库、上游 API、通知适配器
  packages/
    contracts/            OpenAPI 和前后端类型契约
  backups/                旧实现备份包
```

## Current Migration State

`apps/web` 是 React + Vite 项目，React 入口不再挂载旧 DOM：

- `src/app/App.tsx`：只负责挂载 `RadarApp`。
- `src/app/RadarApp.tsx`：负责页面状态、API 调用、定时刷新和表单动作。
- `src/features/radar/RadarPanels.tsx`：雷达页面组件导出入口。
- `src/features/radar/*Panel.tsx`：按视图拆分的总览、渠道、监控室、告警、倍率、消耗、日志和设置面板。
- `src/features/radar/Modals.tsx`：渠道、Key 和监控日志弹窗。
- `src/features/radar/visuals.tsx`：雷达背景和场景装饰。
- `src/features/radar/layout.tsx` / `utils.ts`：面板布局和雷达展示辅助函数。
- `src/shared/api/http.ts`：前端 API client。
- `src/shared/formatters.ts`：展示格式化工具。
- `src/styles.css`：原主题样式原样沿用，页面视觉保持不变。

`apps/api` 是后端 API 入口，不再通过旧 `channel_watch.web` 提供 HTTP 路由，旧兼容入口已经移入 `backups/legacy-code-20260705.tar.gz`：

- `app/api/handler.py`：HTTP JSON handler。
- `app/api/routes/*`：按资源拆分 API 路由。
- `app/core/scheduler.py`：余额/倍率统一扫描、模型监控定时任务。
- `app/domain/store/*`：渠道、监控、告警、用量和设置的数据/领域服务。
- `app/domain/store/notification_*.py`：通知配置、监控汇总、推送发送、QQBot 回调和通知文案。
- `app/infrastructure/integrations`：上游 newApi / sub2Api / 模型探测适配。
- `app/main.py`：API 服务启动入口。

旧根目录静态入口、旧 `channel_watch` 包和根目录 `server.py` 已经移除，前端统一从 `apps/web` 构建和运行。

## Migration Order

1. 继续细化 API 契约：把现有 `/api/*` 请求/响应补全到 `packages/contracts/openapi.yaml`。
2. 前端继续抽 hooks：把 `src/app/RadarApp.tsx` 中的 API 动作、定时刷新和表单状态移到按业务域组织的 hooks。
3. 后端继续细拆：把 `domain/store/channels.py` 的渠道仓储、Key 同步和账号聚合拆成更小的 repository/use case。

## Run Targets

后端 API：

```bash
npm run api:dev
```

React 前端：

```bash
npm install
npm run web:dev
```

React dev server 会把 `/api` 代理到 `http://127.0.0.1:4176`。

后台任务默认间隔：

- 余额和倍率统一扫描：20 秒。
- 模型监控：60 秒。
