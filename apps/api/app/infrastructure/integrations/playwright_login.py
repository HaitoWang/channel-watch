#!/usr/bin/env python3
"""用无头浏览器（Playwright）登录 sub2api，绕过 Cloudflare + Turnstile，
拿到 access_token / refresh_token / user_id。

用法：
    python3 playwright_login.py <base_url> <email> <password> [--headful] [--timeout 60]

成功时向 stdout 打印一行 JSON：
    {"ok": true, "access_token": "...", "refresh_token": "...", "user_id": "..."}
失败时：
    {"ok": false, "error": "..."}

设计为被后端以 subprocess 方式调用，所有诊断信息走 stderr，stdout 只输出结果 JSON。
"""

from __future__ import annotations

import argparse
import json
import sys
import time


def log(*args: object) -> None:
    print("[playwright-login]", *args, file=sys.stderr, flush=True)


def extract_tokens(obj: object) -> dict[str, str]:
    """从任意嵌套结构里递归找 access_token / refresh_token / user_id。"""
    found: dict[str, str] = {}

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                lk = str(key).lower().replace("-", "_")
                if isinstance(value, (str, int)) and str(value):
                    if lk in ("access_token", "accesstoken", "token") and "access_token" not in found:
                        found["access_token"] = str(value)
                    elif lk in ("refresh_token", "refreshtoken") and "refresh_token" not in found:
                        found["refresh_token"] = str(value)
                    elif lk in ("user_id", "userid", "id") and "user_id" not in found:
                        found["user_id"] = str(value)
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(obj)
    return found


def run(base_url: str, email: str, password: str, headful: bool, timeout: int) -> dict[str, object]:
    from playwright.sync_api import sync_playwright

    base = base_url.rstrip("/")
    deadline = time.time() + timeout
    captured: dict[str, str] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headful)
        context = browser.new_context(locale="zh-CN")
        page = context.new_page()

        # 拦截登录接口响应，这是最可靠的 token 来源
        def on_response(response):  # type: ignore[no-untyped-def]
            url = response.url
            if "/auth/login" in url or "/auth/refresh" in url or "/auth/token" in url:
                try:
                    body = response.json()
                except Exception:
                    return
                tokens = extract_tokens(body)
                for k, v in tokens.items():
                    captured.setdefault(k, v)

        page.on("response", on_response)

        log(f"打开登录页 {base}/login")
        page.goto(f"{base}/login", wait_until="domcontentloaded", timeout=min(40000, timeout * 1000))
        page.wait_for_timeout(3500)  # 等 Cloudflare + 页面脚本

        # 关键：该站需先勾选「同意条款」，邮箱/密码框才会从 disabled 变为可用
        try:
            page.check("#login-agreement-consent", timeout=8000, force=True)
            log("已勾选同意条款")
        except Exception as exc:  # noqa: BLE001
            log(f"同意条款勾选跳过（可能无此项）: {exc}")

        # 等邮箱框变为可用
        log("等待登录表单就绪…")
        try:
            page.wait_for_function(
                """() => {
                    const el = document.querySelector('#email, input[type="email"], input[autocomplete="email"]');
                    return el && !el.disabled && el.offsetParent !== null;
                }""",
                timeout=max(15000, min(timeout * 1000 // 2, 40000)),
            )
        except Exception:  # noqa: BLE001
            log("警告：邮箱框迟迟未启用，仍尝试填写")

        # 填邮箱
        email_sel = '#email, input[type="email"], input[name*="mail" i], input[placeholder*="邮"], input[autocomplete="email"]'
        page.fill(email_sel, email, timeout=15000)
        # 填密码
        page.fill('#password, input[type="password"]', password, timeout=15000)
        log("已填入账号密码")

        # 等 Turnstile 自动生成 token（cf-turnstile-response 有值）
        log("等待 Turnstile 校验…")
        got_ts = False
        while time.time() < deadline:
            ts = page.evaluate(
                """() => {
                    const el = document.querySelector('[name="cf-turnstile-response"]');
                    return el ? (el.value || '') : '';
                }"""
            )
            if ts:
                got_ts = True
                log(f"Turnstile token 已生成（{len(ts)} 字符）")
                break
            page.wait_for_timeout(1000)
        if not got_ts:
            log("警告：未检测到 Turnstile token，仍尝试提交")

        # 点登录
        try:
            page.click('button[type="submit"]', timeout=8000)
        except Exception:
            page.keyboard.press("Enter")
        log("已提交登录")

        # 等待 token 被拦截，或页面跳转后从 storage 兜底读取
        while time.time() < deadline:
            if captured.get("access_token"):
                break
            page.wait_for_timeout(800)

        # 兜底：从 localStorage / sessionStorage 读取
        if not captured.get("access_token"):
            log("登录响应未直接拿到 token，尝试从 storage 读取")
            try:
                store = page.evaluate(
                    """() => {
                        const dump = {};
                        for (const s of [localStorage, sessionStorage]) {
                            for (let i = 0; i < s.length; i++) {
                                const k = s.key(i);
                                dump[k] = s.getItem(k);
                            }
                        }
                        return dump;
                    }"""
                )
                parsed: dict[str, object] = {}
                for k, v in store.items():
                    parsed[k] = v
                    try:
                        parsed[f"{k}__json"] = json.loads(v)
                    except Exception:
                        pass
                tokens = extract_tokens(parsed)
                for k, v in tokens.items():
                    captured.setdefault(k, v)
            except Exception as exc:  # noqa: BLE001
                log(f"storage 读取失败: {exc}")

        browser.close()

    if captured.get("access_token"):
        return {
            "ok": True,
            "access_token": captured.get("access_token"),
            "refresh_token": captured.get("refresh_token", ""),
            "user_id": captured.get("user_id", ""),
        }
    return {"ok": False, "error": "登录未拿到 access_token（可能账号密码错误、Turnstile 未通过或页面结构变化）"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Playwright sub2api 登录")
    parser.add_argument("base_url")
    parser.add_argument("email")
    parser.add_argument("password")
    parser.add_argument("--headful", action="store_true", help="显示浏览器窗口（调试用）")
    parser.add_argument("--timeout", type=int, default=60, help="总超时秒数")
    args = parser.parse_args()

    try:
        result = run(args.base_url, args.email, args.password, args.headful, args.timeout)
    except Exception as exc:  # noqa: BLE001
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
