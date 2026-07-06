import { describe, expect, it } from "vitest";

import { formatMoney, formatNumber, formatRate, maskBaseUrl } from "./formatters";

describe("formatNumber", () => {
  it("formats with thousands separators and caps fraction digits", () => {
    expect(formatNumber(1234.567)).toBe("1,234.57");
    expect(formatNumber(null)).toBe("0");
    expect(formatNumber("42")).toBe("42");
  });
});

describe("formatMoney", () => {
  it("prefixes USD with $ and renders placeholders for empties", () => {
    expect(formatMoney(12.5)).toBe("$12.5");
    expect(formatMoney(null)).toBe("$--");
    expect(formatMoney("")).toBe("$--");
  });

  it("appends non-USD unit as suffix", () => {
    expect(formatMoney(100, "CNY")).toBe("100 CNY");
    expect(formatMoney(null, "CNY")).toBe("--");
  });
});

describe("formatRate", () => {
  it("suffixes with x or shows 未知", () => {
    expect(formatRate(2.5)).toBe("2.5x");
    expect(formatRate(null)).toBe("未知");
    expect(formatRate("")).toBe("未知");
  });
});

describe("maskBaseUrl", () => {
  it("masks the host but keeps the protocol and tld", () => {
    expect(maskBaseUrl("https://api.example.com/v1")).toBe("https://*******.com");
    expect(maskBaseUrl("sub2api.example.com.cn")).toBe("https://*******.com.cn");
    expect(maskBaseUrl("")).toBe("");
  });
});
