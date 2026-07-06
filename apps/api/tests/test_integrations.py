"""Regression tests for the split integration adapters.

Pure-function coverage that pins the behaviour preserved by the module split.
Run from the repo root:

    python3 -m unittest discover -s apps/api/tests -t .
"""

from __future__ import annotations

import unittest

from apps.api.app.infrastructure.integrations import (
    api_url,
    extract_access_token,
    extract_auth_tokens,
    extract_balance_result,
    extract_key_items,
    extract_model_rates,
    extract_sub2api_keys,
    find_group,
    find_model_rate,
    find_nested_number,
    find_nested_text,
    first_number,
    first_text,
    group_payload,
    history_payload_summary,
    imported_key_matches_channel,
    infer_model_key,
    key_identity,
    looks_like_api_secret,
    looks_masked_secret,
    normalize_key_provider,
    normalize_model_name,
    normalize_probe_model,
    payload_total_count,
    public_key_items,
)


class NormalizerTests(unittest.TestCase):
    def test_normalize_model_name_strips_symbols_and_lowercases(self):
        self.assertEqual(normalize_model_name("GPT-4o_v2!!"), "gpt4ov2")
        self.assertEqual(normalize_model_name("  Claude 3  "), "claude3")
        self.assertEqual(normalize_model_name(None), "")

    def test_normalize_model_name_keeps_cjk(self):
        self.assertEqual(normalize_model_name("测试abc"), "测试abc")

    def test_normalize_probe_model_canonicalizes_gpt55(self):
        self.assertEqual(normalize_probe_model("GPT 5.5"), "gpt-5.5")
        self.assertEqual(normalize_probe_model("gpt-5.5"), "gpt-5.5")
        self.assertEqual(normalize_probe_model("gpt-4o"), "gpt-4o")

    def test_normalize_key_provider(self):
        self.assertEqual(normalize_key_provider("anthropic/claude"), "anthropic")
        self.assertEqual(normalize_key_provider("openai gpt-4"), "openai")
        self.assertEqual(normalize_key_provider("ChatGPT"), "openai")
        self.assertIsNone(normalize_key_provider("random-provider"))


class ParserHelperTests(unittest.TestCase):
    def test_first_number_returns_first_numeric(self):
        self.assertEqual(first_number({"a": "x", "b": "2.5"}, "a", "b"), 2.5)
        self.assertIsNone(first_number({"a": "x"}, "a", "missing"))

    def test_first_text_trims_and_skips_blanks(self):
        self.assertEqual(first_text({"a": "  ", "b": " hi "}, "a", "b"), "hi")
        self.assertIsNone(first_text({"a": ""}, "a"))

    def test_find_nested_number_and_text(self):
        payload = {"data": {"inner": {"remaining": "12.5", "unit": "USD"}}}
        self.assertEqual(find_nested_number(payload, "remaining"), 12.5)
        self.assertEqual(find_nested_text(payload, "unit"), "USD")

    def test_group_payload_whitelists_keys(self):
        raw = '{"model_id": "x", "evil": 1, "group_rate_multiplier": 2}'
        self.assertEqual(group_payload(raw), {"model_id": "x", "group_rate_multiplier": 2})
        self.assertEqual(group_payload("not json"), {})
        self.assertEqual(group_payload(None), {})

    def test_api_url_dedupes_v1_prefix(self):
        self.assertEqual(api_url("https://a.com/v1", "/v1/messages"), "https://a.com/v1/messages")
        self.assertEqual(api_url("https://a.com", "/v1/responses"), "https://a.com/v1/responses")


class BalanceTests(unittest.TestCase):
    def test_extract_balance_result_direct_fields(self):
        result = extract_balance_result({"data": {"remaining": 12.5, "used": 3, "total": 15.5, "unit": "USD", "group": "vip"}})
        self.assertEqual(result["remaining"], 12.5)
        self.assertEqual(result["unit"], "USD")
        self.assertEqual(result["plan_name"], "vip")

    def test_extract_balance_result_derives_remaining(self):
        result = extract_balance_result({"available_quota": None, "total_quota": 20, "used_quota": 12})
        # remaining absent -> total - used
        self.assertEqual(result["remaining"], 8)

    def test_extract_balance_result_none_when_unrecognized(self):
        self.assertIsNone(extract_balance_result({"nothing": 1}))


class RateTests(unittest.TestCase):
    def test_extract_model_rates_from_list_and_map(self):
        models = extract_model_rates({"models": [{"model": "gpt-5.5", "rate": 2.5}, {"model_id": "claude-sonnet-5", "ratio": 3}]})
        ids = {item["model_id"] for item in models}
        # The primary model ids are surfaced (alongside quirky scalar-key entries).
        self.assertIn("gpt-5.5", ids)
        self.assertIn("claude-sonnet-5", ids)
        mapped = extract_model_rates({"data": {"pricing": {"gpt-5.5": 1.2, "codex": 0.8}}})
        self.assertEqual({item["model_id"] for item in mapped}, {"gpt-5.5", "codex"})

    def test_find_model_rate_exact_then_contains(self):
        models = [{"model_id": "gpt-5.5"}, {"model_id": "gpt-5.5-mini"}]
        self.assertEqual(find_model_rate(models, "gpt-5.5")["model_id"], "gpt-5.5")
        self.assertEqual(find_model_rate(models, "mini")["model_id"], "gpt-5.5-mini")
        self.assertIsNone(find_model_rate(models, "zzz"))

    def test_find_group_matches_by_string_id(self):
        groups = [{"group_id": "1"}, {"group_id": "2"}]
        self.assertEqual(find_group(groups, 2)["group_id"], "2")
        self.assertIsNone(find_group(groups, None))

    def test_infer_model_key_prefers_codex_then_last_token(self):
        self.assertEqual(infer_model_key({"model_scope": "codex, gpt-5.5", "name": "x"}), "codex")
        # Non-codex scopes fall back to the last token after splitting on separators.
        self.assertEqual(infer_model_key({"model_scope": "claude-sonnet-5", "name": ""}), "5")


class KeyTests(unittest.TestCase):
    def test_extract_key_items_walks_containers(self):
        payload = {"data": {"keys": [{"id": 1, "api_key": "sk-abcdefgh12345678"}]}}
        items = extract_key_items(payload)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], 1)

    def test_extract_sub2api_keys_masks_and_dual_cases(self):
        keys = extract_sub2api_keys({"items": [{"id": 7, "api_key": "sk-abcdefgh12345678", "name": "k1"}]})
        self.assertEqual(len(keys), 1)
        key = keys[0]
        self.assertEqual(key["external_key_id"], "7")
        self.assertEqual(key["externalKeyId"], "7")
        self.assertEqual(key["key_name"], "k1")
        self.assertTrue(key["api_key_masked"])  # auto-masked

    def test_key_identity_prefers_external_id(self):
        self.assertEqual(key_identity({"external_key_id": " 5 "}), "5")
        self.assertEqual(key_identity({"apiKey": "sk-x"}), "sk-x")
        self.assertIsNone(key_identity({}))

    def test_payload_total_count(self):
        self.assertEqual(payload_total_count({"data": {"meta": {"total": 42}}}), 42)
        self.assertIsNone(payload_total_count({"data": {}}))

    def test_secret_shape_detectors(self):
        self.assertTrue(looks_masked_secret("sk-****"))
        self.assertFalse(looks_masked_secret("sk-abcdefgh12345678"))
        self.assertTrue(looks_like_api_secret("sk-abcdefgh12345678"))
        self.assertFalse(looks_like_api_secret("short"))

    def test_public_key_items_drops_raw_secret(self):
        public = public_key_items([{"api_key": "sk-abcdefgh12345678", "key_name": "k", "external_key_id": "1"}])
        self.assertNotIn("api_key", public[0])
        self.assertIn("key_masked", public[0])

    def test_imported_key_matches_channel(self):
        row = {"api_key": "sk-abcdefgh12345678"}
        self.assertTrue(imported_key_matches_channel(row, {"api_key": "sk-abcdefgh12345678"}))
        self.assertFalse(imported_key_matches_channel(row, {"api_key": "different"}))


class AuthTokenTests(unittest.TestCase):
    def test_extract_auth_tokens(self):
        tokens = extract_auth_tokens({"data": {"access_token": "a", "refresh_token": "r", "user_id": "9"}})
        self.assertEqual(tokens["access_token"], "a")
        self.assertEqual(tokens["refresh_token"], "r")
        self.assertEqual(tokens["user_id"], "9")

    def test_extract_access_token_variants(self):
        self.assertEqual(extract_access_token({"data": {"accessToken": "tok"}}), "tok")
        self.assertEqual(extract_access_token({"token": "tok2"}), "tok2")
        self.assertIsNone(extract_access_token(123))


class HistorySummaryTests(unittest.TestCase):
    def test_balance_summary(self):
        self.assertEqual(history_payload_summary("balance", '{"unit": "USD"}', 12.5, None), "余额 12.5 USD")

    def test_group_summary_with_model_rate(self):
        payload = '{"group_name": "vip", "model_name": "gpt-4o", "model_rate_multiplier": 2, "group_rate_multiplier": 1.5}'
        summary = history_payload_summary("group", payload, 3.0, 3.0)
        self.assertIn("vip", summary)
        self.assertIn("有效倍率 3x", summary)

    def test_error_payload_wins(self):
        self.assertEqual(history_payload_summary("model", '{"error": "boom"}', None, None), "boom")


if __name__ == "__main__":
    unittest.main()
