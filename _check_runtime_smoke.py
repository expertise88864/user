from __future__ import annotations

import os
import http.client
import json
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DYNAMIC_BUNDLES = [
    "blog-hub",
    "blog-article-reading",
    "blog-diagrams",
    "blog-calculators",
    "blog-article-visuals",
    "blog-article-footer",
]


def asset_version() -> str:
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    match = re.search(r"/blog/blog-shared\.min\.js\?v=(\d+)", html)
    if not match:
        raise AssertionError("Could not find blog-shared asset version in index.html")
    return match.group(1)


def assert_dynamic_loader_versions_match_html(html_version: str) -> None:
    """Cross-file version-drift guard.

    All dynamic bundle URLs (?v=...) in HTML AND inside the JS sources that
    issue script tags for hub/article-reading/diagrams/etc. MUST share a single
    asset version. If they drift, the user can get fresh HTML + stale JS bundles
    (or the reverse) because the service worker keys cache by exact URL.

    This was a real outage on 2026-05-17 when HTML shipped v=202605170730 but
    blog-shared.js still had v=202605120530 hardcoded, so blog-hub.min.js was
    served from a stale cached URL and the spotlight + search + filter all
    disappeared at the same time.
    """
    pat = re.compile(
        r"/blog/blog-(?:shared|hub|article-reading|diagrams|calculators|article-visuals|article-footer)\.min\.js\?v=(\d+)"
    )
    drift: list[str] = []
    for src_name in ("blog/blog-shared.js", "blog/blog-article-reading.js",
                     "blog/blog-shared.min.js", "blog/blog-article-reading.min.js"):
        src_path = ROOT / src_name
        if not src_path.exists():
            continue
        src_text = src_path.read_text(encoding="utf-8")
        for found in set(pat.findall(src_text)):
            if found != html_version:
                drift.append(f"{src_name}: ?v={found} (HTML ships ?v={html_version})")
    if drift:
        raise AssertionError(
            "Asset-version drift between HTML and JS dynamic-loader URLs:\n  "
            + "\n  ".join(drift)
        )


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def fetch(base_url: str, path: str) -> tuple[str, str]:
    url = base_url + path
    # The local Windows HTTP transport can reset or truncate back-to-back
    # connections. Retry only transport failures, never HTTP errors or failed
    # content assertions. A fresh request must still pass every smoke check.
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                body = response.read().decode("utf-8", errors="replace")
                content_type = response.headers.get("content-type", "")
                return body, content_type
        except urllib.error.HTTPError as exc:
            raise AssertionError(f"{path} returned HTTP {exc.code}") from exc
        except (OSError, http.client.HTTPException) as exc:
            if attempt == 2:
                raise AssertionError(f"{path} failed after 3 attempts: {exc}") from exc
            time.sleep(0.1 * (attempt + 1))
    raise AssertionError("unreachable")


def wait_for_server(proc: subprocess.Popen[str], base_url: str) -> None:
    deadline = time.time() + 15
    last_error = ""
    while time.time() < deadline:
        if proc.poll() is not None:
            output = ""
            if proc.stdout:
                output = proc.stdout.read()
            raise AssertionError(f"Server exited early with code {proc.returncode}\n{output}")
        try:
            fetch(base_url, "/")
            return
        except AssertionError as exc:
            last_error = str(exc)
            time.sleep(0.25)
    raise AssertionError(f"Server did not become ready: {last_error}")


def assert_contains(label: str, body: str, needles: list[str]) -> list[str]:
    # 2026-05-25 — needles containing `|` are treated as OR-groups: the
    # body must contain AT LEAST ONE of the alternatives. (Used for the
    # post-extraction DN.initBlog needle that can be satisfied either by
    # the inline literal or by the external bootstrap file reference.)
    errors: list[str] = []
    for needle in needles:
        if "|" in needle:
            alts = needle.split("|")
            if not any(alt in body for alt in alts):
                errors.append(f"{label}: missing any of {alts}")
        elif needle not in body:
            errors.append(f"{label}: missing {needle}")
    return errors


def assert_no_eager_dynamic(label: str, body: str) -> list[str]:
    errors: list[str] = []
    for bundle in DYNAMIC_BUNDLES:
        needle = f"/blog/{bundle}.min.js"
        if needle in body:
            errors.append(f"{label}: eagerly references dynamic bundle {needle}")
    return errors


def run_smoke(base_url: str) -> list[str]:
    version = asset_version()
    shared = f"/blog/blog-shared.min.js?v={version}"
    errors: list[str] = []

    # Cross-file version-drift guard (see helper docstring for the outage story).
    try:
        assert_dynamic_loader_versions_match_html(version)
    except AssertionError as exc:
        errors.append(str(exc))

    # 2026-05-25 — audit follow-up E extracted the DN.initBlog bootstrap to
    # /assets/inline/dn-init.js. Pages can satisfy this smoke
    # check by either keeping the inline `DN.initBlog` literal OR by
    # referencing the external bootstrap file (both work identically at
    # runtime). The helper below collapses the two forms into one needle.
    dn_init = "DN.initBlog|/assets/inline/dn-init.js"

    pages = [
        ("/", "home", [dn_init, 'id="dn-hub"', shared]),
        ("/blog/", "blog index", [dn_init, shared]),
        ("/blog/acne-myths", "article", [dn_init, 'id="proseZh"', shared]),
        ("/about", "about", [dn_init, shared]),
        ("/tools", "tools", [dn_init, shared]),
    ]
    for path, label, needles in pages:
        body, content_type = fetch(base_url, path)
        if "text/html" not in content_type:
            errors.append(f"{label}: expected text/html, got {content_type!r}")
        errors.extend(assert_contains(label, body, needles))
        errors.extend(assert_no_eager_dynamic(label, body))

    admin_pages = [
        ("/admin.html", "full admin", ["/api/admin/login", "frame.setAttribute('sandbox', 'allow-same-origin');"]),
        ("/admin/", "clean-url full admin", ["/api/admin/login", "frame.setAttribute('sandbox', 'allow-same-origin');"]),
        ("/admin/edit.html", "simple editor", ["function sanitizeEditableHtml(html)", "anchor.textContent = url;"]),
    ]
    for path, label, needles in admin_pages:
        body, content_type = fetch(base_url, path)
        if "text/html" not in content_type:
            errors.append(f"{label}: expected text/html, got {content_type!r}")
        errors.extend(assert_contains(label, body, needles))
        if "Decap CMS" in body or "/api/auth" in body:
            errors.append(f"{label}: references retired Decap/OAuth workflow")

    json_body, content_type = fetch(base_url, "/assets/search-index.json")
    if "application/json" not in content_type:
        errors.append(f"search-index: expected application/json, got {content_type!r}")
    try:
        search_index = json.loads(json_body)
    except json.JSONDecodeError as exc:
        errors.append(f"search-index: invalid JSON: {exc}")
        search_index = []
    if not isinstance(search_index, list) or len(search_index) < 30:
        errors.append("search-index: expected at least 30 indexed public pages")
    elif not any(item.get("url") == "/blog/acne-myths" for item in search_index if isinstance(item, dict)):
        errors.append("search-index: missing /blog/acne-myths")

    sw_body, content_type = fetch(base_url, "/sw.js")
    if "javascript" not in content_type:
        errors.append(f"service-worker: expected JavaScript content-type, got {content_type!r}")
    errors.extend(assert_contains("service-worker", sw_body, [
        "const CACHE = 'cd-v163'",
        "const RUNTIME = 'cd-runtime-v161'",
        "/[?&]v=/",
        "url.pathname === '/assets/search-index.json'",
        "url.pathname.startsWith('/admin')",
        "url.pathname === '/reset-sw'",
        "Promise.allSettled(PRECACHE.map",
        "self.clients.claim",
    ]))
    precache_match = re.search(r"const\s+PRECACHE\s*=\s*\[([\s\S]*?)\];", sw_body)
    if not precache_match:
        errors.append("service-worker: missing PRECACHE list")
    elif "blog-shared.min.js" in precache_match.group(1) or re.search(r"\.js['\"]", precache_match.group(1)):
        errors.append("service-worker: JavaScript bundles should not be precached without versioning")

    js_checks = [
        (shared, "shared", ["ensureArticleReadingBundle", "ensureHubBundle", "ensureCalculatorBundle"]),
        (f"/blog/blog-hub.min.js?v={version}", "hub", ["DN.bindArticleHub", "DN.injectSpotlight"]),
        (f"/blog/blog-article-reading.min.js?v={version}", "article-reading", ["DN.addReadingMeta", "DN.injectMedDiagrams"]),
        (f"/blog/blog-diagrams.min.js?v={version}", "diagrams", ["DN.medDiagrams", "DN.MED_DIAGRAM_MAP"]),
        (f"/blog/blog-calculators.min.js?v={version}", "calculators", ["DN.injectSCORAD", "DN.injectGAGS"]),
        (f"/blog/blog-article-visuals.min.js?v={version}", "article-visuals", ["DN.injectArticleHero", "DN.enhanceArticleImages"]),
        (f"/blog/blog-article-footer.min.js?v={version}", "article-footer", ["DN.addRelatedArticles", "DN.addShareToolbar"]),
    ]
    for path, label, needles in js_checks:
        body, content_type = fetch(base_url, path)
        if "javascript" not in content_type:
            errors.append(f"{label}: expected JavaScript content-type, got {content_type!r}")
        if len(body) < 100:
            errors.append(f"{label}: bundle is unexpectedly small")
        errors.extend(assert_contains(label, body, needles))

    return errors


def main() -> int:
    port = int(os.environ.get("SMOKE_PORT") or free_port())
    base_url = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        ["node", str(ROOT / "_serve.mjs"), "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    try:
        wait_for_server(proc, base_url)
        errors = run_smoke(base_url)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    if errors:
        for error in errors:
            print(f"SMOKE  {error}")
        return 1
    print("Runtime smoke audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
