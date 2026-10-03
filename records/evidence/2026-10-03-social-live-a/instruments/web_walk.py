#!/usr/bin/env python3
"""Walk the live hub's web pages as a browser would (stdlib only).

Signs up two users through the /signup form (one normal, one listed in
MCGYVR_HUB_ADMIN_HANDLES), checks landing vs home, makes a key on the home
page, and checks /network, the absence of Try-it, and /pool/plan.
Prints one line per check, every token redacted; the plaintext keys go to
$STATE/live-a-keys.json (0600) for the API checks that follow.

    STATE=... HUB=http://host:port web_walk.py <user-handle> <admin-handle>
"""

from __future__ import annotations

import http.cookiejar
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HUB = os.environ["HUB"].rstrip("/")
STATE = Path(os.environ["STATE"])
# a full plaintext token: kind_hexid_secret (the home page shows only "mhu_<id>_…")
TOKEN = re.compile(r"mh[a-z]_[0-9a-f]{8,}_[A-Za-z0-9_\-]{16,}")
CSRF = re.compile(r'name="csrf" value="([^"]+)"')
results: list[tuple[str, bool, str]] = []


def redact(text: str) -> str:
    return TOKEN.sub(lambda m: m.group(0)[:4] + "<redacted>", text)


class Browser:
    def __init__(self) -> None:
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar), _NoRedirect()
        )

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
        _, body, _ = self.go("GET", path)
        m = CSRF.search(body)
        assert m, f"no csrf on {path}"
        return m.group(1)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # type: ignore[no-untyped-def]
        return None


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  | {redact(detail)}" if detail else ""))


def signup(b: Browser, handle: str) -> tuple[int, str]:
    csrf = b.csrf("/signup")
    status, body, _ = b.go("POST", "/signup", {"csrf": csrf, "handle": handle, "display_name": handle})
    return status, body


def main() -> int:
    user, admin = sys.argv[1], sys.argv[2]
    keys: dict[str, str] = {}

    anon = Browser()
    s, body, _ = anon.go("GET", "/")
    check("logged-out / is the landing page", s == 200 and "Pool your GPUs. Use the whole pool." in body and 'id="endpoint"' not in body, f"HTTP {s}")
    s, body, _ = anon.go("GET", "/pool/plan")
    check("logged-out /pool/plan is 404", s == 404, f"HTTP {s}")

    b = Browser()
    s, body = signup(b, user)
    tokens = TOKEN.findall(body)
    check("web sign-up (normal user) 201, token shown once-warning", s == 201 and "It is shown only once" in body and len(set(tokens)) == 1, f"HTTP {s}, tokens on page: {len(set(tokens))}")
    keys["user_signup"] = tokens[0] if tokens else ""
    s, body, _ = b.go("GET", "/")
    m = re.search(r'id="endpoint-url" type="text" readonly value="([^"]+)"', body)
    check("logged-in / is home (not landing)", s == 200 and 'id="endpoint"' in body and "Pool your GPUs. Use the whole pool." not in body, f"HTTP {s}")
    check("home shows the endpoint URL", bool(m) and m.group(1) == HUB + "/v1", f"endpoint={m.group(1) if m else None}")
    check("home page shows no plaintext token", not TOKEN.findall(body), "")
    csrf = CSRF.search(body).group(1)  # type: ignore[union-attr]
    s, body, _ = b.go("POST", "/me/tokens", {"csrf": csrf, "name": "live-a-laptop"})
    made = TOKEN.findall(body)
    check("key creation 201, key shown with 'Save this key now'", s == 201 and "Save this key now" in body and len(set(made)) == 1, f"HTTP {s}, keys on page: {len(set(made))}")
    keys["user_key"] = made[0] if made else ""
    s, body, _ = b.go("GET", "/")
    check("key not shown again on reload; key listed by name", s == 200 and keys["user_key"] not in body and "live-a-laptop" in body, f"HTTP {s}")
    s, body, _ = b.go("GET", "/network")
    check("/network directory 200, lists the new user", s == 200 and "<h1>The network</h1>" in body and f"/u/{user}" in body, f"HTTP {s}")
    s, body, _ = anon.go("GET", "/network")
    check("/network for logged-out visitor 200", s == 200 and "<h1>The network</h1>" in body, f"HTTP {s}")
    pages = {p: b.go("GET", p) for p in ("/", "/pool", "/network")}
    tryit = [p for p, (_, body, _) in pages.items() if re.search(r"pool/try|Try it|try-it", body, re.I)]
    check("no Try-it box on /, /pool, /network", not tryit, f"found on: {tryit}" if tryit else "pool HTTP %d" % pages["/pool"][0])
    s, _, _ = b.go("POST", "/pool/try", {"csrf": csrf, "model": "x", "prompt": "hi"})
    check("POST /pool/try is gone (404/405)", s in (404, 405), f"HTTP {s}")
    s, body, _ = b.go("GET", "/pool/plan")
    check("/pool/plan 404 for a normal user", s == 404, f"HTTP {s}")

    a = Browser()
    s, body = signup(a, admin)
    t = TOKEN.findall(body)
    keys["admin_signup"] = t[0] if t else ""
    check("web sign-up (admin handle) 201", s == 201, f"HTTP {s}")
    s, body, _ = a.go("GET", "/pool/plan")
    check("/pool/plan 200 for an admin handle", s == 200 and "Pick a model" in body, f"HTTP {s}, body: {re.sub(r'<[^>]+>|\\s+', ' ', body).strip()[:120]}")

    csrf = CSRF.search(b.go("GET", "/")[1]).group(1)  # type: ignore[union-attr]
    s, _, h = b.go("POST", "/signout", {"csrf": csrf})
    s2, body, _ = b.go("GET", "/")
    check("after sign-out / is the landing page again", s in (302, 303) and s2 == 200 and "Pool your GPUs" in body, f"signout HTTP {s}, / HTTP {s2}")

    old = os.umask(0o077)
    try:
        (STATE / "live-a-keys.json").write_text(json.dumps(keys))
    finally:
        os.umask(old)
    failed = [n for n, ok, _ in results if not ok]
    print(f"{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
