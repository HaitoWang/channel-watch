from __future__ import annotations

from typing import Any

from apps.api.app.core.errors import ApiError
from apps.api.app.core.utils import bool_value, mask_secret, normalize_base_url


class Sub2apiConfigMixin:
    sub2api_defaults = {
        "sub2api_enabled": "0",
        "sub2api_base_url": "",
        "sub2api_email": "",
        "sub2api_password": "",
        "sub2api_access_token": "",
        "sub2api_refresh_token": "",
        "sub2api_user_id": "",
        "sub2api_turnstile_token": "",
        "sub2api_disable_on_rate_multiplier_change": "0",
        "sub2api_disable_on_model_sync_failure": "0",
    }

    def sub2api_settings(self, *, include_secret: bool = False) -> dict[str, Any]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT key, value, updated_at
                FROM app_settings
                WHERE key IN (
                  'sub2api_enabled',
                  'sub2api_base_url',
                  'sub2api_email',
                  'sub2api_password',
                  'sub2api_access_token',
                  'sub2api_refresh_token',
                  'sub2api_user_id',
                  'sub2api_turnstile_token',
                  'sub2api_disable_on_rate_multiplier_change',
                  'sub2api_disable_on_model_sync_failure'
                )
                """
            ).fetchall()
        values = self.sub2api_defaults.copy()
        updated_at = None
        for row in rows:
            values[row["key"]] = row["value"] or ""
            updated_at = max(updated_at or row["updated_at"], row["updated_at"])

        base_url = normalize_base_url(values["sub2api_base_url"])
        email = values["sub2api_email"].strip()
        password = values["sub2api_password"].strip()
        access_token = values["sub2api_access_token"].strip()
        refresh_token = values["sub2api_refresh_token"].strip()
        user_id = values["sub2api_user_id"].strip()
        turnstile_token = values["sub2api_turnstile_token"].strip()
        configured = bool(base_url and (access_token or refresh_token or (email and password)))
        result = {
            "sub2api_enabled": bool_value(values["sub2api_enabled"]),
            "sub2apiEnabled": bool_value(values["sub2api_enabled"]),
            "sub2api_configured": configured,
            "sub2apiConfigured": configured,
            "sub2api_base_url": base_url,
            "sub2apiBaseUrl": base_url,
            "sub2api_email": email,
            "sub2apiEmail": email,
            "sub2api_password_masked": mask_secret(password),
            "sub2apiPasswordMasked": mask_secret(password),
            "sub2api_access_token_masked": mask_secret(access_token),
            "sub2apiAccessTokenMasked": mask_secret(access_token),
            "sub2api_refresh_token_masked": mask_secret(refresh_token),
            "sub2apiRefreshTokenMasked": mask_secret(refresh_token),
            "sub2api_user_id": user_id,
            "sub2apiUserId": user_id,
            "sub2api_turnstile_token_masked": mask_secret(turnstile_token),
            "sub2apiTurnstileTokenMasked": mask_secret(turnstile_token),
            "sub2api_disable_on_rate_multiplier_change": bool_value(values["sub2api_disable_on_rate_multiplier_change"]),
            "sub2apiDisableOnRateMultiplierChange": bool_value(values["sub2api_disable_on_rate_multiplier_change"]),
            "sub2api_disable_on_model_sync_failure": bool_value(values["sub2api_disable_on_model_sync_failure"]),
            "sub2apiDisableOnModelSyncFailure": bool_value(values["sub2api_disable_on_model_sync_failure"]),
            "sub2api_updated_at": updated_at,
            "sub2apiUpdatedAt": updated_at,
        }
        if include_secret:
            result["sub2api_password"] = password
            result["sub2apiPassword"] = password
            result["sub2api_access_token"] = access_token
            result["sub2apiAccessToken"] = access_token
            result["sub2api_refresh_token"] = refresh_token
            result["sub2apiRefreshToken"] = refresh_token
            result["sub2api_turnstile_token"] = turnstile_token
            result["sub2apiTurnstileToken"] = turnstile_token
        return result

    def update_sub2api_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        current = self.sub2api_settings(include_secret=True)
        updates: dict[str, str] = {}
        bool_fields = {
            "sub2api_enabled": ("sub2api_enabled", "sub2apiEnabled"),
            "sub2api_disable_on_rate_multiplier_change": (
                "sub2api_disable_on_rate_multiplier_change",
                "sub2apiDisableOnRateMultiplierChange",
            ),
            "sub2api_disable_on_model_sync_failure": (
                "sub2api_disable_on_model_sync_failure",
                "sub2apiDisableOnModelSyncFailure",
            ),
        }
        for target, keys in bool_fields.items():
            value = self.payload_value(payload, *keys)
            if value is not None:
                updates[target] = "1" if bool_value(value) else "0"

        base_url = self.payload_value(payload, "sub2api_base_url", "sub2apiBaseUrl")
        if base_url is not None:
            updates["sub2api_base_url"] = normalize_base_url(base_url)

        email = self.payload_value(payload, "sub2api_email", "sub2apiEmail")
        if email is not None:
            updates["sub2api_email"] = str(email or "").strip()

        user_id = self.payload_value(payload, "sub2api_user_id", "sub2apiUserId")
        if user_id is not None:
            updates["sub2api_user_id"] = str(user_id or "").strip()

        password = self.payload_value(payload, "sub2api_password", "sub2apiPassword")
        if password is not None and str(password).strip():
            updates["sub2api_password"] = str(password).strip()
        if bool_value(self.payload_value(payload, "clear_sub2api_password", "clearSub2apiPassword")):
            updates["sub2api_password"] = ""

        access_token = self.payload_value(payload, "sub2api_access_token", "sub2apiAccessToken")
        if access_token is not None and str(access_token).strip():
            updates["sub2api_access_token"] = str(access_token).strip()

        refresh_token = self.payload_value(payload, "sub2api_refresh_token", "sub2apiRefreshToken")
        if refresh_token is not None and str(refresh_token).strip():
            updates["sub2api_refresh_token"] = str(refresh_token).strip()
        if bool_value(self.payload_value(payload, "clear_sub2api_tokens", "clearSub2apiTokens")):
            updates["sub2api_access_token"] = ""
            updates["sub2api_refresh_token"] = ""

        turnstile_token = self.payload_value(payload, "sub2api_turnstile_token", "sub2apiTurnstileToken")
        if turnstile_token is not None and str(turnstile_token).strip():
            updates["sub2api_turnstile_token"] = str(turnstile_token).strip()
        if bool_value(self.payload_value(payload, "clear_sub2api_turnstile_token", "clearSub2apiTurnstileToken")):
            updates["sub2api_turnstile_token"] = ""

        next_values = {key: str(current.get(key) or "") for key in self.sub2api_defaults}
        next_values.update(updates)
        next_enabled = bool_value(next_values["sub2api_enabled"])
        next_base_url = normalize_base_url(next_values["sub2api_base_url"])
        next_email = next_values["sub2api_email"].strip()
        next_password = next_values["sub2api_password"].strip()
        next_access_token = next_values["sub2api_access_token"].strip()
        next_refresh_token = next_values["sub2api_refresh_token"].strip()
        if next_enabled and not next_base_url:
            raise ApiError(400, "启用 sub2Api 默认配置前请填写 Base URL")
        if next_enabled and not (next_access_token or next_refresh_token or (next_email and next_password)):
            raise ApiError(400, "启用 sub2Api 默认配置前请填写 token 或 email/password")

        if updates:
            self.save_app_settings(updates)
        return {"ok": True, "settings": self.sub2api_settings()}
