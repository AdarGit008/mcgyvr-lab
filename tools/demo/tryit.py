#!/usr/bin/env python3
"""Sign in as the requester, show the plan for the demo model, send a prompt
through the pool page's Try-it box and screenshot the page, dark and light.

  PLAYWRIGHT_BROWSERS_PATH=... tryit.py <outdir> [ctx]
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

from playwright.sync_api import sync_playwright

HUB = os.environ.get("HUB", "http://127.0.0.1:18765")
TOKEN = os.environ["REQ_TOKEN"]
MODEL = os.environ.get("MODEL", "Qwen2.5-Coder-32B-Instruct-Q5_K_M.gguf")
PROMPT = os.environ.get(
    "PROMPT", "In one sentence: why split a model's layers across several GPUs?"
)


def run(out: str, ctx: str, scheme: str, send: bool) -> dict[str, Any]:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.emulate_media(color_scheme=scheme)
        page.goto(f"{HUB}/signin")
        page.fill("#token", TOKEN)
        page.click("form button[type=submit]")
        page.wait_for_load_state("networkidle")
        page.goto(f"{HUB}/pool")
        page.select_option("#plan-model", MODEL)
        page.fill("#plan-ctx", ctx)
        page.dispatch_event("#plan-ctx", "change")
        page.wait_for_selector("#plan table.plan, #plan .errors", timeout=20000)
        time.sleep(1)
        result: dict[str, Any] = {
            "scheme": scheme,
            "plan_text": page.inner_text("#plan"),
        }
        if send:
            page.select_option("#try-model", MODEL)
            page.fill("#prompt", PROMPT)
            t0 = time.monotonic()
            page.click("#try-it button.primary")
            # (the page's CSP forbids eval, so poll from here)
            while not page.inner_text("#try-output").strip():
                if time.monotonic() - t0 > 600:
                    raise TimeoutError("no output from the Try-it box")
                page.wait_for_timeout(50)
            result["first_text_s"] = round(time.monotonic() - t0, 2)
            # done when the Stop button hides again
            page.wait_for_selector(
                "#try-it button[data-stop]", state="hidden", timeout=600000
            )
            result["done_s"] = round(time.monotonic() - t0, 2)
            result["answer"] = page.inner_text("#try-output")
            result["failed"] = "failed" in (
                page.get_attribute("#try-output", "class") or ""
            )
        page.wait_for_timeout(5500)  # one sessions poll
        result["sessions_text"] = page.inner_text("#sessions")
        page.screenshot(path=os.path.join(out, f"pool-{scheme}.png"), full_page=True)
        browser.close()
        return result


def main() -> None:
    out = sys.argv[1]
    ctx = sys.argv[2] if len(sys.argv) > 2 else "12288"
    os.makedirs(out, exist_ok=True)
    results = [run(out, ctx, "dark", True), run(out, ctx, "light", True)]
    print(json.dumps(results, indent=1))


if __name__ == "__main__":
    main()
