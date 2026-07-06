import { describe, expect, it } from "vitest";

import { boolField, field, isDefaultModelList, providerDefaultModels, settingsPayloadFromDraft, splitModels } from "./radarModel";

describe("splitModels", () => {
  it("splits, trims, and drops blanks", () => {
    expect(splitModels("gpt-5.5, claude-sonnet-5 ,")).toEqual(["gpt-5.5", "claude-sonnet-5"]);
    expect(splitModels("")).toEqual([]);
  });
});

describe("providerDefaultModels", () => {
  it("returns provider-specific defaults", () => {
    expect(providerDefaultModels("openai")).toEqual(["gpt-5.5"]);
    expect(providerDefaultModels("anthropic")).toEqual(["claude-sonnet-4-5"]);
    expect(providerDefaultModels(null)).toEqual(["gpt-5.5", "claude-sonnet-4-5"]);
  });
});

describe("isDefaultModelList", () => {
  it("recognizes the untouched default lists", () => {
    expect(isDefaultModelList("gpt-5.5")).toBe(true);
    expect(isDefaultModelList("gpt-5.5, claude-sonnet-4-5")).toBe(true);
    expect(isDefaultModelList("")).toBe(true);
    expect(isDefaultModelList("gpt-5.5, claude-sonnet-5")).toBe(false);
  });
});

describe("field / boolField", () => {
  it("reads snake_case then camelCase fallback", () => {
    expect(field({ is_default_key: 1 }, "is_default_key", "isDefaultKey")).toBe(1);
    expect(field({ isDefaultKey: 2 }, "is_default_key", "isDefaultKey")).toBe(2);
    expect(boolField({ isMonitoring: 1 }, "is_monitoring", "isMonitoring")).toBe(true);
    expect(boolField({}, "is_monitoring", "isMonitoring")).toBe(false);
  });
});

describe("settingsPayloadFromDraft", () => {
  it("drops empty secrets and clears target id for subscriber mode", () => {
    const payload = settingsPayloadFromDraft({
      sub2api_password: "  ",
      pushplus_token: " tok ",
      qqbot_secret: "",
      qqbot_target_type: "subscribers",
      qqbot_target_id: "123",
    });
    expect(payload).not.toHaveProperty("sub2api_password");
    expect(payload).not.toHaveProperty("qqbot_secret");
    expect(payload.pushplus_token).toBe("tok");
    expect(payload.qqbot_target_id).toBe("");
  });

  it("keeps target id when a concrete target type is chosen", () => {
    const payload = settingsPayloadFromDraft({ qqbot_target_type: "group", qqbot_target_id: " 42 " });
    expect(payload.qqbot_target_id).toBe("42");
  });
});
