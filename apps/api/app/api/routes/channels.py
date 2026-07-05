from __future__ import annotations

from typing import Optional

from apps.api.app.api.request import ApiRequest, RouteResult, channel_id_from, ok


def handle(request: ApiRequest) -> Optional[RouteResult]:
    method = request.method
    path = request.path
    parts = request.parts

    if method == "GET" and path == "/api/channels":
        status = (request.query.get("status") or [""])[0]
        return ok(
            {
                "channels": request.store.list_channels(status=status or None),
                "accounts": request.store.list_channel_accounts(status=status or None),
                "overview": request.store.overview(),
            }
        )

    if method == "POST" and path == "/api/channels":
        channel = request.store.create_channel(request.json())
        return ok({"ok": True, "channel": channel, "overview": request.store.overview()}, status=201)

    if len(parts) >= 3 and parts[1] == "channels":
        channel_id = channel_id_from(parts)
        if method == "PATCH" and len(parts) == 3:
            channel = request.store.update_channel(channel_id, request.json())
            return ok({"ok": True, "channel": channel, "overview": request.store.overview()})
        if method == "DELETE" and len(parts) == 3:
            request.store.delete_channel(channel_id)
            return ok({"ok": True, "overview": request.store.overview()})
        if method == "POST" and len(parts) == 4 and parts[3] == "probe":
            return ok(request.store.probe_balance(channel_id))
        if method == "POST" and len(parts) == 4 and parts[3] == "probe-groups":
            return ok(request.store.probe_groups(channel_id))
        if method == "POST" and len(parts) == 4 and parts[3] == "sync-keys":
            return ok(request.store.sync_user_keys(channel_id, request.json()))
        if method == "POST" and len(parts) == 4 and parts[3] == "set-default":
            request.store.set_default_key(channel_id)
            return ok(
                {
                    "ok": True,
                    "channel": request.store.public_channel(request.store.get_channel_row(channel_id)),
                    "accounts": request.store.list_channel_accounts(),
                }
            )

    return None
