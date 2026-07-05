from __future__ import annotations

"""Upstream newApi / sub2Api integration adapters.

The implementation is split into cohesive modules; this package re-exports the
full public surface so existing imports keep working unchanged.
"""

from ._http import api_url, http_json, unwrap_data
from .balance import (
    demo_balance_result,
    extract_balance_result,
    query_real_balance,
    query_sub2api_account_balance,
)
from .groups import (
    apply_model_multiplier,
    apply_model_multiplier_to_groups,
    demo_group_result,
    extract_newapi_groups,
    extract_sub2api_groups,
    query_real_group,
    query_real_group_catalog,
)
from .history import history_payload_summary
from .keys import (
    extract_key_items,
    extract_sub2api_keys,
    imported_key_matches_channel,
    key_identity,
    looks_like_api_secret,
    looks_masked_secret,
    payload_total_count,
    public_key_items,
    query_sub2api_keys,
)
from .parsers import (
    find_nested_number,
    find_nested_text,
    first_number,
    first_text,
    group_payload,
    normalize_key_provider,
    normalize_model_name,
    normalize_probe_model,
)
from .probe import extract_probe_text, query_model_probe
from .rates import extract_model_rates, find_group, find_model_rate, infer_model_key
from .sub2api_auth import (
    extract_access_token,
    extract_auth_tokens,
    login_sub2api_credentials,
    refresh_sub2api_session,
    sub2api_access_token,
)

__all__ = [
    "api_url",
    "http_json",
    "unwrap_data",
    "demo_balance_result",
    "extract_balance_result",
    "query_real_balance",
    "query_sub2api_account_balance",
    "apply_model_multiplier",
    "apply_model_multiplier_to_groups",
    "demo_group_result",
    "extract_newapi_groups",
    "extract_sub2api_groups",
    "query_real_group",
    "query_real_group_catalog",
    "history_payload_summary",
    "extract_key_items",
    "extract_sub2api_keys",
    "imported_key_matches_channel",
    "key_identity",
    "looks_like_api_secret",
    "looks_masked_secret",
    "payload_total_count",
    "public_key_items",
    "query_sub2api_keys",
    "find_nested_number",
    "find_nested_text",
    "first_number",
    "first_text",
    "group_payload",
    "normalize_key_provider",
    "normalize_model_name",
    "normalize_probe_model",
    "extract_probe_text",
    "query_model_probe",
    "extract_model_rates",
    "find_group",
    "find_model_rate",
    "infer_model_key",
    "extract_access_token",
    "extract_auth_tokens",
    "login_sub2api_credentials",
    "refresh_sub2api_session",
    "sub2api_access_token",
]
