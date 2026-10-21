#!/usr/bin/env python3
"""Remote-first delivery gate. CI evidence is never inferred from local tests."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
SHA = re.compile(r"^[0-9a-f]{40}$")
ZERO = "0" * 40


class Blocked(RuntimeError):
    """Missing or unsuccessful evidence; do not publish."""


class Final(Blocked):
    """Blocked, and the awaited evidence can no longer appear by waiting.

    Only raised on positive evidence that nothing is still building or can
    still change the outcome; anything uncertain stays an ordinary Blocked.
    """


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def policy() -> dict:
    cfg = json.loads((ROOT / "_delivery_policy.json").read_text(encoding="utf-8"))
    validate_policy(cfg)
    return cfg


def validate_policy(cfg: dict) -> None:
    if cfg.get("cms_author_intent", False) not in (True, False) or ("cms_author_intent" in cfg and type(cfg["cms_author_intent"]) is not bool):
        raise Blocked("Invalid CMS author-intent policy")
    if cfg.get("repository") == "expertise88864/user" and cfg.get("cms_author_intent") is not True:
        raise Blocked("This website requires live CMS author-intent verification")
    if cfg.get("repository") == "expertise88864/user" and cfg.get("site_settings_author_intent") is not True:
        raise Blocked("This website requires live site-settings author-intent verification")
    entries = cfg.get("workflows")
    if not isinstance(entries, list) or not entries:
        raise Blocked("A nonempty workflow contract is required")
    paths = set()
    for entry in entries:
        path = entry.get("path", "")
        if not re.fullmatch(r"\.github/workflows/[A-Za-z0-9_-]+\.yml", path) or path in paths:
            raise Blocked("Invalid or duplicate required workflow")
        paths.add(path)
        jobs = entry.get("jobs")
        if not isinstance(jobs, list) or not jobs or any(not isinstance(j, str) or not j for j in jobs):
            raise Blocked("Each workflow needs named required jobs")
        if any(not entry.get("steps", {}).get(job, {}).get("required") for job in jobs):
            raise Blocked("Required jobs need explicit validation step contracts")
        if cfg.get("require_pr"):
            contract = entry.get("pull_request")
            if not isinstance(contract, dict):
                raise Blocked("PR workflows need explicit applicability contracts")
            skips = contract.get("skips", [])
            patterns = contract.get("paths")
            if (not isinstance(skips, list) or any(not isinstance(j, str) for j in skips)
                    or len(set(skips)) != len(skips) or not set(skips) < set(jobs)):
                raise Blocked("Invalid PR conditional jobs")
            if patterns is not None and (not isinstance(patterns, list) or not patterns
                    or any(not isinstance(p, str) or not re.fullmatch(r"[A-Za-z0-9_./*\-]+", p) for p in patterns)):
                raise Blocked("Invalid positive PR path filters")
    if cfg.get("allow_dispatch", False) not in (True, False):
        raise Blocked("Invalid dispatch policy")
    if cfg.get("pr_review", False) not in (True, False):
        raise Blocked("Invalid pr_review policy")


def check_sha(sha: str) -> str:
    if not SHA.fullmatch(sha) or sha == ZERO:
        raise Blocked("A full, nonzero commit SHA is required")
    return sha


def clean(sha: str) -> None:
    check_sha(sha)
    if git("rev-parse", "HEAD") != sha or git("status", "--porcelain", "--untracked-files=all"):
        raise Blocked("Use the clean, exact candidate revision; preserve other work separately")


def token() -> str:
    value = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if value:
        return value
    # Use the already configured Git credential helper. Never print/store credentials.
    result = subprocess.run(
        ["git", "credential", "fill"], cwd=ROOT,
        input="protocol=https\nhost=github.com\n\n", text=True,
        capture_output=True, timeout=15,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "Never"},
    )
    if result.returncode == 0:
        return dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line).get("password", "")
    return ""


class API:
    def __init__(self, repo: str):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
            raise Blocked("Invalid GitHub repository")
        self.base = "https://api.github.com/repos/" + repo
        self.auth = token()

    def get(self, path: str):
        if not path.startswith("/") or "://" in path:
            raise Blocked("Only relative repository API paths are accepted")
        headers = {"User-Agent": "remote-ci-delivery", "Accept": "application/vnd.github+json", "Cache-Control": "no-cache"}
        if path.startswith("/contents/"):
            headers["Accept"] = "application/vnd.github.object+json"
        if self.auth:
            headers["Authorization"] = "Bearer " + self.auth
        request = urllib.request.Request(self.base + path, headers=headers)
        # A redirected API URL must never carry the user's credential elsewhere.
        opener = urllib.request.build_opener(NoRedirect)
        with opener.open(request, timeout=30) as response:
            raw = response.read(10_000_001)
            if len(raw) > 10_000_000:
                raise Blocked("GitHub evidence response exceeds its byte limit")
            return json.loads(raw)

    def pages(self, path: str, key: str | None = None) -> list:
        rows = []
        for page in range(1, 21):
            data = self.get(path + ("&" if "?" in path else "?") + f"per_page=100&page={page}")
            items = data[key] if key else data
            if not isinstance(items, list) or any(not isinstance(x, dict) for x in items):
                raise Blocked("Invalid GitHub API response")
            rows.extend(items)
            if len(items) < 100:
                return rows
        raise Blocked("API pagination exceeded bound; evidence is incomplete")


def assess_jobs(jobs: list, required: list, allowed_skips: list,
                contracts: dict | None = None, phase: str = "candidate") -> None:
    if not jobs or not set(required).issubset({j.get("name") for j in jobs}):
        raise Blocked("Required jobs are absent")
    for job in jobs:
        name = job.get("name")
        conclusion = job.get("conclusion")
        if job.get("status") != "completed":
            raise Blocked(f"Job not complete: {name}")
        if conclusion == "skipped" and name in allowed_skips:
            continue
        if conclusion != "success":
            raise Blocked(f"Job not successful: {name}: {conclusion}")
        if contracts is not None:
            contract = contracts.get(name)
            if not contract or not contract.get("required"):
                raise Blocked(f"Missing step contract: {name}")
            needed = contract["required"] + contract.get(phase + "_required", [])
            steps = job.get("steps")
            if not isinstance(steps, list) or not steps:
                raise Blocked(f"Missing step evidence: {name}")
            for step_name in needed:
                matches = [s for s in steps if s.get("name") == step_name]
                if (len(matches) != 1 or matches[0].get("status") != "completed"
                        or matches[0].get("conclusion") != "success"):
                    raise Blocked(f"Required step absent/incomplete/not successful: {name} / {step_name}")
        # continue-on-error must not hide a failed executed step.
        for step in job.get("steps", []):
            if step.get("conclusion") in ("failure", "cancelled", "timed_out", "action_required"):
                raise Blocked(f"Failed step: {name} / {step.get('name')}")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Blocked("GitHub API redirects are not accepted")


def select_run(runs: list, path: str, sha: str, phase: str, allow_dispatch: bool = False) -> dict:
    matches = [
        r for r in runs
        if r.get("head_sha") == sha and r.get("path") == path
        and ((r.get("head_branch") == "main") if phase == "main"
             else str(r.get("head_branch", "")).startswith("codex/"))
    ]
    push_runs = [r for r in matches if r.get("event") == "push"]
    if push_runs:
        matches = push_runs  # A later dispatch must never mask a failed/pending push.
    else:
        matches = [r for r in matches if allow_dispatch and r.get("event") == "workflow_dispatch"
                   and r.get("actor", {}).get("login") == "github-actions[bot]"
                   and (phase == "main" or str(r.get("head_branch", "")).startswith("codex/scheduled-"))]
    if not matches:
        raise Blocked(f"No exact-SHA {phase} push run for {path}")
    run = max(matches, key=lambda r: (r["id"], r.get("run_attempt", 1)))
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        raise Blocked(f"{path}: {run.get('status')}/{run.get('conclusion')} ({run.get('html_url')})")
    return run


def verify(sha: str, phase: str, cfg: dict, api: API) -> list:
    check_sha(sha)
    validate_policy(cfg)
    runs = api.pages(f"/actions/runs?head_sha={sha}", "workflow_runs")
    evidence = []
    for entry in cfg["workflows"]:
        run = select_run(runs, entry["path"], sha, phase, cfg.get("allow_dispatch", False))
        jobs = api.pages(f"/actions/runs/{run['id']}/attempts/{run.get('run_attempt', 1)}/jobs", "jobs")
        assess_jobs(jobs, entry["jobs"], entry.get(phase + "_skips", []), entry["steps"], phase)
        evidence.append({"sha": sha, "event": run["event"], "run_id": run["id"], "url": run["html_url"],
                         "jobs": [{"name": j["name"], "id": j["id"],
                                   "conclusion": j["conclusion"]} for j in jobs]})
    if phase == "candidate" and cfg.get("require_pr"):
        prs = api.pages(f"/commits/{sha}/pulls")
        matching = [p for p in prs if p.get("state") == "open" and p.get("head", {}).get("sha") == sha
                   and p.get("base", {}).get("ref") == "main"
                   and p.get("head", {}).get("repo", {}).get("full_name") == cfg["repository"]]
        if len(matching) != 1:
            raise Blocked("One open, same-repository PR for this exact candidate is required")
        evidence.extend(verify_pr_checks(sha, cfg, api, runs, matching[0]))
    if phase == "candidate" and cfg.get("morning_dry_run"):
        base = check_sha(api.get("/git/ref/heads/main")["object"]["sha"])
        changed = git("diff", "--name-only", base, sha).splitlines()
        if needs_morning_preview(changed):
            candidates = [r for r in runs if r.get("head_sha") == sha
                          and r.get("path") == ".github/workflows/ci.yml"
                          and r.get("event") == "workflow_dispatch"
                          and str(r.get("head_branch", "")).startswith("codex/")]
            if not candidates:
                raise Blocked("Production pipeline changed: dispatch CI dry-run-preview on this candidate")
            run = max(candidates, key=lambda r: r["id"])
            if run.get("status") != "completed" or run.get("conclusion") != "success":
                raise Blocked("Required morning dry-run-preview has not succeeded")
            jobs = api.pages(f"/actions/runs/{run['id']}/attempts/{run.get('run_attempt', 1)}/jobs", "jobs")
            ci = next(e for e in cfg["workflows"] if e["path"] == ".github/workflows/ci.yml")
            assess_jobs(jobs, ["test", "dry-run-preview"], [], ci["steps"])
            evidence.append({"sha": sha, "dry_run_id": run["id"], "url": run["html_url"]})
    if cfg.get("cms_author_intent"):
        from _cms_delivery import verify as verify_author_intent
        try:
            evidence.append({"cms": verify_author_intent(sha, api)})
        except (ValueError, KeyError, TypeError) as error:
            raise Blocked("CMS author intent / approved payload is no longer valid") from error
    if cfg.get("site_settings_author_intent"):
        from _site_settings_delivery import verify as verify_settings_intent
        try:
            evidence.append({"siteSettings": verify_settings_intent(sha, api)})
        except (ValueError, KeyError, TypeError) as error:
            raise Blocked("Site settings author intent / approved payload is no longer valid") from error
    return evidence


def pr_identity(pr: dict, sha: str, repo: str) -> tuple:
    """Bind all API reads to one source head, main base and complete file census."""
    number, count = pr.get("number"), pr.get("changed_files")
    head, base = pr.get("head", {}), pr.get("base", {})
    if (type(number) is not int or number <= 0 or type(count) is not int or not 0 <= count < 2000
            or pr.get("state") != "open" or head.get("sha") != sha
            or not isinstance(head.get("ref"), str) or not head["ref"].startswith("codex/")
            or base.get("ref") != "main"
            or any(node.get("repo", {}).get("full_name") != repo for node in (head, base))):
        raise Blocked("Incomplete or foreign candidate PR identity")
    return number, head["ref"], check_sha(base.get("sha", "")), count


def pr_path_matches(filename: str, pattern: str) -> bool:
    # Only the positive * / ** syntax used by our declared GitHub path filters.
    expression = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?")
    expression = expression.replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
    return re.fullmatch(expression, filename) is not None


def verify_pr_checks(sha: str, cfg: dict, api: API, runs: list, candidate: dict) -> list:
    number = candidate.get("number")
    if type(number) is not int or number <= 0:
        raise Blocked("Candidate PR number is absent")
    detail = api.get(f"/pulls/{number}")
    identity = pr_identity(detail, sha, cfg["repository"])
    if identity[0] != number:
        raise Blocked("Candidate PR identity changed")
    files = api.pages(f"/pulls/{number}/files")
    names = [f.get("filename") for f in files]
    if (len(files) != identity[3] or any(not isinstance(n, str) or not n for n in names)
            or len(set(names)) != len(names)):
        raise Blocked("PR file evidence is incomplete")
    names += [f["previous_filename"] for f in files if "previous_filename" in f]
    if any(not isinstance(n, str) or not n or n.startswith("/") or ".." in n.split("/") for n in names):
        raise Blocked("Invalid PR file path")
    evidence = []
    for entry in cfg["workflows"]:
        contract = entry["pull_request"]
        observed = [r for r in runs if r.get("head_sha") == sha and r.get("path") == entry["path"]
                    and r.get("event") == "pull_request"]
        applicable = "paths" not in contract or any(pr_path_matches(n, p) for n in names for p in contract["paths"])
        if not applicable and not observed:
            continue  # Existing workflow filter; never discard a run that actually exists.
        matches = [r for r in observed if r.get("head_branch") == identity[1]]
        if not matches:
            raise Blocked(f"No exact-SHA PR run for {entry['path']}")
        run = max(matches, key=lambda r: (r["id"], r.get("run_attempt", 1)))
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            raise Blocked(f"PR {entry['path']}: {run.get('status')}/{run.get('conclusion')} ({run.get('html_url')})")
        jobs = api.pages(f"/actions/runs/{run['id']}/attempts/{run.get('run_attempt', 1)}/jobs", "jobs")
        assess_jobs(jobs, entry["jobs"], contract.get("skips", []), entry["steps"], "pull_request")
        evidence.append({"sha": sha, "event": "pull_request", "pr": number, "base_sha": identity[2],
                         "run_id": run["id"], "url": run["html_url"],
                         "jobs": [{"name": j["name"], "id": j["id"], "conclusion": j["conclusion"]} for j in jobs]})
    if pr_identity(api.get(f"/pulls/{number}"), sha, cfg["repository"]) != identity:
        raise Blocked("Candidate PR advanced during verification")
    return evidence


REVIEW_CONTEXT = "codex-review/gpt-6.1-sol"
# tools/pr_review.py: "<verdict> base=<sha> [prev=<sha>] [s=<session prefix>]". A status
# with prev= reviewed only prev..head and continues an earlier verdict of the same
# session; one without reviewed base..head whole (also every status older tools wrote).
REVIEW_DESCRIPTION = re.compile(r"(APPROVE|REQUEST_CHANGES|quota-pending) base=([0-9a-f]{40})"
                                r"(?: prev=([0-9a-f]{40}))?(?: s=([0-9a-f]{8}))?")
REVIEW_HEAD_STATES = (("APPROVE", "success"), ("quota-pending", "pending"))
REVIEW_LINK_STATES = (("APPROVE", "success"), ("REQUEST_CHANGES", "failure"))
MAX_REVIEW_CHAIN = 100


def requires_pr_review(cfg: dict, base_cfg: dict | None) -> bool:
    """A candidate cannot switch off the whole-PR review its base policy requires."""
    return bool(cfg.get("pr_review")) or bool((base_cfg or {}).get("pr_review"))


def review_statuses(api: API, owner: str, sha: str) -> list:
    check_sha(sha)
    rows = [s for s in api.pages(f"/commits/{sha}/statuses")
            if s.get("context") == REVIEW_CONTEXT
            and str((s.get("creator") or {}).get("login", "")).lower() == owner]
    return sorted(rows, key=lambda s: s.get("id", 0), reverse=True)


def is_ancestor(older: str, newer: str) -> bool:
    return subprocess.run(["git", "merge-base", "--is-ancestor", older, newer], cwd=ROOT).returncode == 0


def pr_review(api: API, cfg: dict, sha: str, previous: str) -> dict:
    """One review per PR (user decision 2026-10-15), recorded by tools/pr_review.py as
    the owner's commit status on the exact head. Its reviewed range must cover every
    commit being promoted. Quota pending may publish but is reported, never approval.

    An incremental resume reviews only prev..head, so the head's status is followed
    back through prev= links: each link needs a completed verdict (APPROVE or
    REQUEST_CHANGES) of the same session on the same base, on an ancestor commit,
    until a status without prev (a review of the whole range base..link)."""
    check_sha(sha)
    owner = cfg["repository"].split("/")[0].lower()
    rows = review_statuses(api, owner, sha)
    if not rows:
        raise Blocked("No PR review for this exact head: run python tools/pr_review.py")
    latest = rows[0]
    match = REVIEW_DESCRIPTION.fullmatch(str(latest.get("description", "")))
    state = latest.get("state")
    if not match or (match.group(1), state) not in REVIEW_HEAD_STATES:
        raise Blocked(f"PR review not approved: {state} {latest.get('description')!r}")
    verdict, reviewed_base, link, session = match.groups()
    chain = [sha]
    while link:
        if link in chain or len(chain) >= MAX_REVIEW_CHAIN:
            raise Blocked("PR review chain loops or is too long; review the PR again")
        if not is_ancestor(link, chain[-1]):
            raise Blocked(f"PR review chain link {link[:12]} is not an ancestor of "
                          f"{chain[-1][:12]}; review the PR again")
        found = None
        for row in review_statuses(api, owner, link):
            step = REVIEW_DESCRIPTION.fullmatch(str(row.get("description", "")))
            if step and (step.group(1), row.get("state")) in REVIEW_LINK_STATES \
                    and step.group(2) == reviewed_base and step.group(4) == session:
                found = step
                break
        if found is None:
            raise Blocked(f"No completed review of {link[:12]} in the same session and base; "
                          "the incremental review chain does not reach a whole-range review")
        chain.append(link)
        link = found.group(3)
    if not is_ancestor(reviewed_base, previous):
        raise Blocked("The reviewed range does not cover main..head; review the PR again")
    if verdict == "quota-pending":
        print("WARNING: PR review is quota-pending (not approved); backfill with "
              "python tools/pr_review.py --pending", file=sys.stderr)
    return {"sha": sha, "pr_review": verdict, "reviewed_base": reviewed_base,
            "chain": chain, "url": latest.get("target_url", "")}


def needs_morning_preview(paths: list[str]) -> bool:
    """Conservative production-change routing; docs/tests/gate-only need no paid LLM run."""
    for path in paths:
        if path.startswith(("tests/", "docs/", ".githooks/")) or path in ("_delivery.py", "_test_delivery.py"):
            continue
        if path.startswith("tools/claude_"):
            continue
        if path.endswith(".py") or path.startswith("requirements"):
            return True
        if path.startswith(".github/workflows/") and path != ".github/workflows/delivery.yml":
            return True
    return False


def deployment_url(api: API, sha: str, environment: str = "preview") -> str:
    check_sha(sha)
    deployments = api.pages(f"/deployments?sha={sha}")
    matching = []
    for deployment in sorted(deployments, key=lambda d: d["id"], reverse=True):
        if (deployment.get("sha") != sha
                or str(deployment.get("environment", "")).lower() != environment
                or (environment == "preview" and deployment.get("production_environment") is not False)):
            continue
        if str(deployment.get("creator", {}).get("login", "")).lower() not in ("vercel[bot]", "vercel"):
            continue
        statuses = api.pages(f"/deployments/{deployment['id']}/statuses")
        matching.append(statuses)
        if not statuses or statuses[0].get("state") != "success":
            continue
        url = statuses[0].get("environment_url", "")
        parsed = urllib.parse.urlparse(url)
        if (parsed.scheme == "https" and parsed.hostname
                and parsed.hostname.endswith(".vercel.app")
                and not parsed.username and not parsed.password and parsed.port is None
                and parsed.path in ("", "/") and not parsed.query and not parsed.fragment):
            return url.rstrip("/")
    message = f"No successful Vercel {environment} deployment bound to this SHA"
    reason = vercel_outcome_final(api, sha, environment, matching, deployments)
    if reason:
        raise Final(f"{message}; {reason}")
    raise Blocked(message)


VERCEL_CONTEXT = "Vercel"
VERCEL_LOGINS = ("vercel[bot]", "vercel")
DEPLOYMENT_TERMINAL = ("success", "failure", "error", "inactive")


def vercel_outcome_final(api: API, sha: str, environment: str, matching: list, deployments: list) -> str:
    """Why no exact-SHA `environment` deployment can still succeed, or "" to keep waiting.

    Vercel posts one `pending` commit status when it starts a build of this SHA
    and one terminal status when that build ends; the GitHub deployment record
    only appears when a build completes. Commit statuses are not bound to an
    environment, so they only prove that nothing is still building; the failure
    itself must be bound to the requested environment:
      * the newest matching deployment of that environment ended in failure or
        error (its own attempt, not another environment's), or
      * for production only, the latest build was canceled by the Ignored Build
        Step: this repository's gate never cancels Preview builds, and a
        production build of a SHA is only started by promoting that SHA.
    Every build must have ended, no matching deployment may still be running,
    and every successful build (any environment, possibly ending out of order)
    must already be matched by a published successful deployment; otherwise a
    success may still be publishing. Missing or unreadable evidence, anything
    still building, and every other combination keep the caller waiting exactly
    as before.
    """
    try:
        builds = [
            status for status in api.pages(f"/commits/{sha}/statuses")
            if status.get("context") == VERCEL_CONTEXT
            and str((status.get("creator") or {}).get("login", "")).lower() in VERCEL_LOGINS
        ]
        if not builds:
            return ""
        builds.sort(key=lambda status: (str(status["created_at"]), int(status["id"])))
        started = sum(status.get("state") == "pending" for status in builds)
        ended = sum(status.get("state") in ("success", "failure", "error") for status in builds)
        if started == 0 or started > ended:
            return ""
        for statuses in matching:
            if not statuses or statuses[0].get("state") not in DEPLOYMENT_TERMINAL:
                return ""
        succeeded = sum(status.get("state") == "success"
                        and "ignored build step" not in str(status.get("description") or "").lower()
                        for status in builds)
        published = 0
        for deployment in deployments:
            if (deployment.get("sha") != sha
                    or str((deployment.get("creator") or {}).get("login", "")).lower() not in VERCEL_LOGINS):
                continue
            history = api.pages(f"/deployments/{deployment['id']}/statuses")
            published += any(status.get("state") == "success" for status in history)
        if succeeded > published:
            return ""
        if matching and matching[0][0].get("state") in ("failure", "error"):
            return (f"the newest exact-SHA {environment} deployment ended with "
                    f"{matching[0][0]['state']} and nothing is still building")
        latest = builds[-1]
        if (environment == "production" and latest.get("state") == "success"
                and "ignored build step" in str(latest.get("description") or "").lower()):
            return "Vercel canceled the production build of this SHA by its Ignored Build Step and nothing is still building"
        return ""
    except Exception:  # Unproven finality never ends a wait early.
        return ""


def preview_url(api: API, sha: str) -> str:
    return deployment_url(api, sha, "preview")


def main_advanced_past(api: API, sha: str) -> bool:
    """True only when production main is a strict fast-forward descendant of `sha`.

    Main only moves forward (fast-forward promotions; force pushes are refused),
    so a smoke of `sha` can then never see main == sha again. Behind, diverged,
    equal or unreadable all return False and keep the caller waiting.
    """
    try:
        head = check_sha(api.get('/branches/main')['commit']['sha'])
        if head == sha:
            return False
        comparison = api.get(f'/compare/{sha}...{head}')
        return (comparison.get('status') == 'ahead' and comparison.get('behind_by') == 0
                and isinstance(comparison.get('ahead_by'), int) and comparison['ahead_by'] > 0)
    except Exception:  # Unproven finality never ends a wait early.
        return False


MAIN_ADVANCED = 'production main has advanced past the delivery revision, so this smoke can never pass'


def production_smoke(api: API, sha: str, cfg: dict) -> dict:
    try:
        deployment = deployment_url(api, sha, "production")
    except Final:
        raise
    except Blocked as exc:
        if main_advanced_past(api, sha):
            raise Final(f"{exc}; {MAIN_ADVANCED}") from exc
        raise
    if api.get('/branches/main')['commit']['sha'] != sha:
        if main_advanced_past(api, sha):
            raise Final(f'Production main no longer matches the delivery revision; {MAIN_ADVANCED}')
        raise Blocked('Production main no longer matches the delivery revision')
    origin = 'https://chendermatologist.com'
    checked = []
    for route in [*cfg['preview_paths'], '/blog/blog-shared.min.js',
                  '/assets/search-index.json', '/sw.js', '/pagefind/pagefind.js']:
        request = urllib.request.Request(origin + route, headers={'User-Agent': 'DermNotes-release-smoke'})
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status != 200 or urllib.parse.urlsplit(response.url).netloc != 'chendermatologist.com':
                raise Blocked(f'Production route did not return the site: {route}')
            body = response.read()
            if route in cfg['preview_paths']:
                if not re.search(rb'<main\b', body, re.I) or not re.search(rb'<title>[^<]+</title>', body, re.I):
                    raise Blocked(f'Production page is missing its content: {route}')
                if 'noindex' in response.headers.get('X-Robots-Tag', '').lower():
                    raise Blocked(f'Production page is unexpectedly noindex: {route}')
            elif route != '/pagefind/pagefind.js':
                expected = subprocess.check_output(['git', 'show', sha + ':' + route.lstrip('/')], cwd=ROOT)
                if body.replace(b'\r\n', b'\n') != expected.replace(b'\r\n', b'\n'):
                    raise Blocked(f'Production asset does not match the delivered SHA: {route}')
            elif not body or 'javascript' not in response.headers.get('Content-Type', '').lower():
                raise Blocked('Production search bundle is missing')
        checked.append(route)
    return {'sha': sha, 'deployment': deployment, 'origin': origin, 'smoke_routes': checked}


def pre_push(lines: list[str], remote: str, cfg: dict) -> None:
    expected = "https://github.com/" + cfg["repository"] + ".git"
    if remote != "origin" or git("remote", "get-url", "--push", remote) != expected:
        raise Blocked("Unexpected push destination")
    for line in lines:
        fields = line.split()
        if len(fields) != 4:
            raise Blocked("Malformed pre-push ref update")
        _, sha, target, previous = fields
        check_sha(sha)
        clean(sha)
        if target == "refs/heads/main":
            if not SHA.fullmatch(previous) or previous == ZERO:
                raise Blocked("Refuse creating/replacing production main")
            # The advertised remote SHA must be present AND an ancestor.
            subprocess.run(["git", "fetch", "--no-tags", remote, "main"], cwd=ROOT, check=True)
            if git("rev-parse", "FETCH_HEAD") != previous:
                raise Blocked("Main advanced while preparing publication; fetch/integrate/retest")
            subprocess.run(["git", "merge-base", "--is-ancestor", previous, sha], cwd=ROOT, check=True)
            api = API(cfg["repository"])
            evidence = verify(sha, "candidate", cfg, api)
            try:
                base_cfg = json.loads(git("show", f"{previous}:_delivery_policy.json"))
            except (json.JSONDecodeError, subprocess.SubprocessError) as exc:
                raise Blocked(f"Cannot read production delivery policy: {exc}") from exc
            if requires_pr_review(cfg, base_cfg):
                evidence.append(pr_review(api, cfg, sha, previous))
            clean(sha)
            print(json.dumps(evidence, ensure_ascii=True))
        elif target.startswith("refs/heads/codex/"):
            if previous != ZERO:
                check_sha(previous)
                subprocess.run(["git", "fetch", "--no-tags", remote, target], cwd=ROOT, check=True)
                if git("rev-parse", "FETCH_HEAD") != previous:
                    raise Blocked("Candidate advanced; integrate and revalidate")
                subprocess.run(["git", "merge-base", "--is-ancestor", previous, sha], cwd=ROOT, check=True)
            # Exact committed candidate only; no full local CI requirement.
            subprocess.run([sys.executable, "-m", "unittest", "_test_delivery"], cwd=ROOT, check=True)
            subprocess.run(["git", "diff", "--check", sha + "^", sha], cwd=ROOT, check=True)
            clean(sha)
        else:
            raise Blocked("Only codex/* candidates and verified main promotions are supported")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("pre-push", "verify", "preview", "production", "smoke"))
    parser.add_argument("sha", nargs="?")
    parser.add_argument("--phase", choices=("candidate", "main"), default="candidate")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--wait", type=int, default=0, help="Bounded seconds; emits only changed state")
    args = parser.parse_args()
    try:
        cfg = policy()
        if args.command == "pre-push":
            lines = list(sys.stdin)
            pre_push(lines, args.remote, cfg)
            if cfg.get("claude_hook"):
                review_code = subprocess.run(
                    [sys.executable, "tools/claude_diff_review.py", "push", "--remote-name", args.remote],
                    cwd=ROOT, input="".join(lines), text=True, encoding="utf-8",
                ).returncode
                if review_code:
                    return review_code
            # A model review can take long enough for the author to withdraw a
            # request. Recheck main delivery immediately after the review too.
            if cfg.get("cms_author_intent"):
                from _cms_delivery import verify as verify_author_intent
                for line in lines:
                    fields = line.split()
                    if fields[2] == "refs/heads/main":
                        verify_author_intent(fields[1], API(cfg["repository"]))
                        clean(fields[1])
            if cfg.get("site_settings_author_intent"):
                from _site_settings_delivery import verify as verify_settings_intent
                for line in lines:
                    fields = line.split()
                    if fields[2] == "refs/heads/main":
                        verify_settings_intent(fields[1], API(cfg["repository"]))
                        clean(fields[1])
            return 0
        sha = check_sha(args.sha or git("rev-parse", "HEAD"))
        api = API(cfg["repository"])
        deadline = time.monotonic() + min(max(args.wait, 0), 3600)
        previous = ""
        final = ""
        while True:
            try:
                if args.command == "smoke":
                    print(json.dumps(production_smoke(api, sha, cfg), ensure_ascii=True))
                elif args.command in ("preview", "production"):
                    print(deployment_url(api, sha, args.command))
                else:
                    print(json.dumps(verify(sha, args.phase, cfg, api), ensure_ascii=True))
                return 0
            except Blocked as exc:
                message = str(exc)
                if message != previous:
                    print(message, file=sys.stderr)
                    previous = message
                # A final outcome must be observed on two consecutive polls (30 s
                # apart) before ending early, so a status GitHub has not yet
                # published (e.g. a just-started build) cannot cut a wait short.
                if isinstance(exc, Final) and message == final:
                    print("Stopped waiting early: this outcome can no longer change.", file=sys.stderr)
                    return 1
                final = message if isinstance(exc, Final) else ""
                if time.monotonic() >= deadline:
                    return 1
                time.sleep(min(30, max(0, deadline - time.monotonic())))
    except (Blocked, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(f"DELIVERY BLOCKED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
