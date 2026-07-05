from __future__ import annotations

from typing import Any

from apps.api.app.core.utils import optional_float


class AnalyticsMixin:
    def balance_channels(self) -> list[dict[str, Any]]:
        return self.list_channel_accounts()

    def overview(self) -> dict[str, Any]:
        channels = self.balance_channels()
        events = self.list_events(acknowledged=False)
        healthy = sum(1 for item in channels if item["status"] == "healthy")
        warning = sum(1 for item in channels if item["status"] == "warning")
        offline = sum(1 for item in channels if item["status"] == "offline")
        total_balance = sum(float(item["balance"] or 0) for item in channels)
        total_quota = sum(float(item["quota_total"] or 0) for item in channels)
        total_used = sum(self.channel_used(item) for item in channels)
        rates = [optional_float(item.get("rate_multiplier")) for item in channels]
        known_rates = [item for item in rates if item is not None]
        low_balance = sum(
            1
            for item in channels
            if optional_float(item.get("balance")) is not None
            and optional_float(item.get("threshold")) is not None
            and float(item["balance"] or 0) < float(item["threshold"] or 0)
        )
        last_success = max(
            [item["last_checked_at"] for item in channels if item.get("last_checked_at") and item["status"] != "offline"],
            default=None,
        )
        return {
            "total_channels": len(channels),
            "totalChannels": len(channels),
            "healthy_channels": healthy,
            "healthyChannels": healthy,
            "warning_channels": warning,
            "warningChannels": warning,
            "offline_channels": offline,
            "offlineChannels": offline,
            "open_events": len(events),
            "openEvents": len(events),
            "balance_total": round(total_balance, 2),
            "balanceTotal": round(total_balance, 2),
            "quota_total": round(total_quota, 2),
            "quotaTotal": round(total_quota, 2),
            "used_total": round(total_used, 2),
            "usedTotal": round(total_used, 2),
            "low_balance_channels": low_balance,
            "lowBalanceChannels": low_balance,
            "average_rate": round(sum(known_rates) / len(known_rates), 4) if known_rates else None,
            "averageRate": round(sum(known_rates) / len(known_rates), 4) if known_rates else None,
            "unknown_rate_channels": len(channels) - len(known_rates),
            "unknownRateChannels": len(channels) - len(known_rates),
            "last_success_at": last_success,
            "lastSuccessAt": last_success,
        }

    def channel_used(self, channel: dict[str, Any]) -> float:
        used = optional_float(channel.get("used"))
        if used is not None:
            return max(0, used)
        quota_total = optional_float(channel.get("quota_total") or channel.get("quotaTotal"))
        balance = optional_float(channel.get("balance"))
        if quota_total is not None and balance is not None:
            return max(0, quota_total - balance)
        return 0

    def usage_summary(self) -> dict[str, Any]:
        channels = self.balance_channels()
        rows: list[dict[str, Any]] = []
        total_balance = 0.0
        total_quota = 0.0
        total_used = 0.0
        low_count = 0
        for item in channels:
            balance = optional_float(item.get("balance"))
            quota_total = optional_float(item.get("quota_total") or item.get("quotaTotal"))
            used = self.channel_used(item)
            threshold = optional_float(item.get("threshold")) or 0
            if balance is not None:
                total_balance += balance
            if quota_total is not None:
                total_quota += quota_total
            total_used += used
            is_low = balance is not None and threshold > 0 and balance < threshold
            if is_low:
                low_count += 1
            rows.append(
                {
                    "channel_id": item["id"],
                    "channelId": item["id"],
                    "name": item["name"],
                    "platform": item["platform"],
                    "status": item["status"],
                    "unit": item.get("unit") or "USD",
                    "balance": balance,
                    "threshold": threshold,
                    "quota_total": quota_total,
                    "quotaTotal": quota_total,
                    "used": round(used, 2),
                    "used_percent": round((used / quota_total * 100), 2) if quota_total else 0,
                    "usedPercent": round((used / quota_total * 100), 2) if quota_total else 0,
                    "remaining_percent": item.get("remaining_percent"),
                    "remainingPercent": item.get("remaining_percent"),
                    "is_low": is_low,
                    "isLow": is_low,
                    "last_checked_at": item.get("last_checked_at"),
                    "lastCheckedAt": item.get("last_checked_at"),
                }
            )
        rows.sort(key=lambda item: (not item["is_low"], -(item["used"] or 0), item["name"]))
        burn_rate = round((total_used / total_quota * 100), 2) if total_quota else 0
        return {
            "summary": {
                "balance_total": round(total_balance, 2),
                "balanceTotal": round(total_balance, 2),
                "quota_total": round(total_quota, 2),
                "quotaTotal": round(total_quota, 2),
                "used_total": round(total_used, 2),
                "usedTotal": round(total_used, 2),
                "low_count": low_count,
                "lowCount": low_count,
                "burn_rate": burn_rate,
                "burnRate": burn_rate,
            },
            "channels": rows,
            "history": self.list_history(kind="balance", limit=30),
        }

    def rate_summary(self) -> dict[str, Any]:
        channels = self.list_channels()
        group_history = self.list_history(kind="group", limit=80)
        latest_by_channel: dict[int, dict[str, Any]] = {}
        for item in group_history:
            channel_id = item.get("channel_id")
            if channel_id is not None and channel_id not in latest_by_channel:
                latest_by_channel[int(channel_id)] = item
        rates = [optional_float(item.get("rate_multiplier")) for item in channels]
        known_rates = [item for item in rates if item is not None]
        return {
            "summary": {
                "known": len(known_rates),
                "unknown": len(channels) - len(known_rates),
                "average_rate": round(sum(known_rates) / len(known_rates), 4) if known_rates else None,
                "averageRate": round(sum(known_rates) / len(known_rates), 4) if known_rates else None,
            },
            "channels": [
                {
                    **item,
                    "last_rate_probe": latest_by_channel.get(int(item["id"])),
                    "lastRateProbe": latest_by_channel.get(int(item["id"])),
                }
                for item in channels
            ],
            "history": group_history,
        }
