#!/usr/bin/env python3
"""Item 7: walk the hub's pages as a browser would (stdlib only, cookies, CSRF,
Origin), signed out and signed in as each given user (by its personal key
through /signin). Saves each page's text (tags stripped, tokens and invite
codes redacted) under OUT/<user>/<page>.txt and prints one line per check.

    web_walk.py OUT user1 [user2 ...]
"""
from __future__ import annotations

import html
import http.cookiejar
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from hub import HUB, STATE, key, redact

CSRF = re.compile(r'name="csrf" value="([^"]+)"')
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".")
results: list[bool] = []


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # type: ignore[no-untyped-def]
        return None


class Browser:
    def __init__(self) -> None:
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()), _NoRedirect())

    def go(self, method: str, path: str, form: dict[str, str] | None = None) -> tuple[int, str, dict[str, str]]:
        data = urllib.parse.urlencode(form).encode() if form is not None else None
        req = urllib.request.Request(HUB + path, data=data, method=method)
        if data is not None:
            req.add_header("Content-Type", "application/x-www-form-urlencoded")
            req.add_header("Origin", HUB)
        try:
            with self.opener.open(req, timeout=30) as r:
                return r.status, r.read().decode(), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode(errors="replace"), dict(e.headers)

    def csrf(self, path: str) -> str:
        m = CSRF.search(self.go("GET", path)[1])
        assert m, f"no csrf on {path}"
        return m.group(1)


def text(page: str) -> str:
    page = re.sub(r"(?s)<(script|style)[^>]*>.*?</\1>", " ", page)
    page = re.sub(r"<[^>]+>", " ", page)
    page = html.unescape(page)
    page = re.sub(r"[ \t]+", " ", page)
    return redact(re.sub(r"\n\s*\n+", "\n", page)).strip()


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  | {redact(detail)[:300]}" if detail else ""), flush=True)


def save(who: str, name: str, body: str) -> str:
    d = OUT / who
    d.mkdir(parents=True, exist_ok=True)
    t = text(body)
    (d / f"{name}.txt").write_text(t + "\n")
    return t


def main() -> None:
    crew = json.loads((STATE / "live-b-crew.json").read_text())["id"]
    anon = Browser()
    st, body, _ = anon.go("GET", "/")
    t = save("signed-out", "landing", body)
    check("signed out: / is the landing page", st == 200 and "Four ways to share" in t, t[:200])
    for path in ("/profile", "/me/hitchhike", "/me/rigs", f"/me/crews/{crew}"):
        st, body, hdr = anon.go("GET", path)
        check(f"signed out: {path} is not shown", st in (303, 302, 401, 404), f"{st} {hdr.get('location', '')}")

    for who in sys.argv[2:]:
        b = Browser()
        st, body, hdr = b.go("POST", "/signin", {"csrf": b.csrf("/signin"), "token": key(who)})
        check(f"{who}: sign in with the personal key", st == 303 and hdr.get("location") == "/", f"{st} {hdr.get('location')}")
        for name, path in (("feed", "/"), ("feed-crews", "/feed?show=crews"), ("feed-hitchhike", "/feed?show=hitchhike"),
                           ("profile", "/profile"), ("hitchhike", "/me/hitchhike"), ("crew", f"/me/crews/{crew}"),
                           ("rigs", "/me/rigs"), ("network", "/network")):
            st, body, _ = b.go("GET", path)
            t = save(who, name, body)
            check(f"{who}: GET {path} -> {st}", st == 200, f"{len(t)} chars")
        print("DONE", sum(results), "/", len(results))


if __name__ == "__main__":
    main()
