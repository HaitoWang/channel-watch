# API App

This folder is the target backend boundary for the separated architecture.

The HTTP API, scheduler entrypoint, data store, and upstream integrations now
live in `apps/api/app`. The old compatibility entrypoints were moved into
`backups/legacy-code-20260705.tar.gz`.

Suggested layers:

- `app/api/routes`: HTTP route handlers.
- `app/core`: config, scheduler, startup/shutdown.
- `app/domain`: business use cases for channels, monitoring, notifications.
- `app/infrastructure`: database repositories and upstream integrations.

Run it from the workspace root:

```bash
npm run api:dev
```

Default scheduler intervals:

- Balance/rate scan: 20 seconds.
- Model monitor: 60 seconds.
