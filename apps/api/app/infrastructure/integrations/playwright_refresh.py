#!/usr/bin/env python3
"""用无头浏览器（Playwright）在「过 Seton/CF 盾的会话」里刷新 sub2api token。

背景：congmingai 等站对 /api/v1/auth/* 加了 Seton Edge V2 盾（PoW + 环境指纹检测）
和 Cloudflare。直连 refresh 会被 403 拦。但用「代理 + 反检测脚本」过盾后，在
已通过盾的浏览器会话里 fetch /api/v1/auth/refresh 可成功（已实测拿到新 at/rt）。

登录那道 Turnstile 无法自动过，但 refresh **不经过 Turnstile**，所以只要有一个
有效 refresh_token，即可靠本脚本无限自动续期（每次 refresh 轮换 rt）。

用法：
    python3 playwright_refresh.py <base_url> <refresh_token> [--proxy http://host:port] [--timeout 90]

stdout 输出一行 JSON：
    {"ok": true, "access_token": "...", "refresh_token": "...", "user_id": "..."}
    {"ok": false, "error": "..."}
"""

from __future__ import annotations

import argparse
import json
import sys

# 反检测 init 脚本：抹掉 webdriver、伪造 plugins / window.chrome，
# 骗过 Seton Edge 的环境检测（wd/plg0/... 项）。已实测能过盾。
_ANTIDETECT = (
    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
    "Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]});"
    "Object.defineProperty(navigator,'languages',{get:()=>['zh-CN','zh','en']});"
    "window.chrome={runtime:{}};"
)
_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def log(*args: object) -> None:
    print("[playwright-refresh]", *args, file=sys.stderr, flush=True)


def _extract(obj: object) -> dict[str, str]:
    found: dict[str, str] = {}

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                lk = str(k).lower().replace("-", "_")
                if isinstance(v, (str, int)) and str(v):
                    if lk in ("access_token", "accesstoken") and "access_token" not in found:
                        found["access_token"] = str(v)
                    elif lk in ("refresh_token", "refreshtoken") and "refresh_token" not in found:
                        found["refresh_token"] = str(v)
                    elif lk in ("user_id", "userid") and "user_id" not in found:
                        found["user_id"] = str(v)
                walk(v)
        elif isinstance(node, list):
            for it in node:
                walk(it)

    walk(obj)
    return found


def run(base_url: str, refresh_token: str, proxy: str | None, timeout: int) -> dict[str, object]:
    from playwright.sync_api import sync_playwright

    base = base_url.rstrip("/")
    launch_kwargs: dict[str, object] = {
        "headless": True,
        "args": ["--disable-blink-features=AutomationControlled"],
    }
    if proxy:
        launch_kwargs["proxy"] = {"server": proxy}

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(locale="zh-CN", ignore_https_errors=True, user_agent=_UA)
        context.add_init_script(_ANTIDETECT)
        page = context.new_page()

        # 先访问首页过盾（Seton PoW + 反检测）
        log("过盾中…")
        try:
            page.goto(base, wait_until="commit", timeout=min(60000, timeout * 1000))
        except Exception as exc:  # noqa: BLE001
            log(f"首页加载异常（继续）: {exc}")
        passed = False
        for _ in range(min(25, timeout // 2)):
            page.wait_for_timeout(2000)
            try:
                title = page.title()
            except Exception:  # noqa: BLE001
                continue
            if title and "Security Check" not in title and "Just a moment" not in title:
                passed = True
                log(f"已过盾（{title[:30]}）")
                break
        if not passed:
            log("警告：疑似未过盾，仍尝试 refresh")

        # 在已过盾会话里 fetch refresh
        result = page.evaluate(
            """async (args) => {
                const resp = await fetch(args.base + "/api/v1/auth/refresh", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({refresh_token: args.rt})
                });
                const raw = await resp.text();
                let body = raw;
                try { body = JSON.parse(raw); } catch (e) { /* 保留原始文本 */ }
                return {status: resp.status, body: body};
            }""",
            {"base": base, "rt": refresh_token},
        )
        browser.close()

    status = result.get("status")
    body = result.get("body")
    if status != 200 or not isinstance(body, dict):
        snippet = json.dumps(body, ensure_ascii=False)[:150] if isinstance(body, (dict, list)) else str(body)[:150]
        return {"ok": False, "error": f"refresh HTTP {status}: {snippet}"}
    tokens = _extract(body)
    if not tokens.get("access_token"):
        return {"ok": False, "error": "refresh 成功但未解析到 access_token"}
    return {
        "ok": True,
        "access_token": tokens.get("access_token"),
        "refresh_token": tokens.get("refresh_token", ""),
        "user_id": tokens.get("user_id", ""),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Playwright sub2api token 刷新")
    parser.add_argument("base_url")
    parser.add_argument("refresh_token")
    parser.add_argument("--proxy", default=None)
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()
    try:
        result = run(args.base_url, args.refresh_token, args.proxy, args.timeout)
    except Exception as exc:  # noqa: BLE001
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
