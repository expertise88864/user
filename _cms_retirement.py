"""Immutable, separately delivered retirement of already published CMS receipts.

Never writes Git refs, edits patient content or treats saved drafts as published.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import re
from urllib.parse import urlsplit

from _cms_delivery import FILE, REPO, ImmutableBlobs, ancestor, github_file, parse, receipts, revision, utc

PREFIX = ".cms-retirements/"
ARCHIVE = re.compile(r"\.cms-retirements/([a-f0-9]{40})\.json")
FIELDS = {"version", "repository", "publishedSha", "receiptBlobSha", "requests", "evidence", "preparedAt"}


def pages(api, path, key=None):
    result = []
    for page in range(1, 4):
        data = api.get(path + ("&" if "?" in path else "?") + f"per_page=100&page={page}")
        rows = data.get(key) if key and isinstance(data, dict) else data if not key else None
        if not isinstance(rows, list) or len(rows) > 100 or any(not isinstance(r, dict) for r in rows):
            raise ValueError("Incomplete retirement repository evidence")
        result.extend(rows)
        if len(rows) < 100:
            return result
    raise ValueError("Retirement repository evidence exceeds its bound")


def main_sha(api):
    ref = api.get("/git/ref/heads/main")
    if not isinstance(ref, dict) or ref.get("ref") != "refs/heads/main" or ref.get("object", {}).get("type") != "commit":
        raise ValueError("Retirement main reference unavailable")
    return revision(ref["object"].get("sha"))


def main_runs(api, sha):
    return [r for r in pages(api, "/actions/runs?head_sha=" + sha, "workflow_runs")
            if r.get("head_sha") == sha and r.get("event") == "push" and r.get("head_branch") == "main"
            and r.get("head_repository", {}).get("full_name") == REPO]


def baseline(api, candidate, current):
    if current != candidate:
        ancestor(api, current, candidate)
        return current
    parent = candidate
    for _ in range(20):
        commit = api.get("/git/commits/" + parent)
        if not isinstance(commit, dict) or commit.get("sha") != parent or len(commit.get("parents", [])) != 1:
            raise ValueError("Retirement needs an unambiguous previous main revision")
        parent = revision(commit["parents"][0].get("sha"))
        if any(r.get("path") == ".github/workflows/delivery.yml" for r in main_runs(api, parent)):
            return parent
    raise ValueError("Retirement previous main exceeds its history bound")


def optional_blob(api, path, commit):
    if path not in api.entries(commit):
        return None
    return github_file(api, path, commit)


def archive_paths(tree):
    paths = {}
    for path, entry in tree.items():
        if path == PREFIX[:-1] and (entry.get("type") != "tree" or entry.get("mode") != "040000"):
            raise ValueError("Malformed retirement archive root")
        if not path.startswith(PREFIX) or entry.get("type") == "tree":
            continue
        match = ARCHIVE.fullmatch(path)
        if not match or entry.get("type") != "blob" or entry.get("mode") != "100644":
            raise ValueError("Malformed retirement archive path or Git mode")
        revision(match[1]); revision(entry.get("sha"))
        paths[path] = entry["sha"]
    return paths


def selected_runs(api, sha, policy):
    rows = main_runs(api, sha)
    selected = []
    for entry in policy["workflows"]:
        matches = [r for r in rows if r.get("path") == entry["path"]]
        if not matches or any(type(r.get("id")) is not int or r["id"] <= 0 or type(r.get("run_attempt")) is not int or r["run_attempt"] <= 0 for r in matches):
            raise ValueError("Retirement formal CI identity missing")
        run = max(matches, key=lambda r: (r["id"], r["run_attempt"]))
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            raise ValueError("Retirement formal CI not successful")
        selected.append({"workflow": entry["path"], "runId": run["id"], "attempt": run["run_attempt"]})
    return selected


def production(api):
    rows = [d for d in pages(api, "/deployments") if str(d.get("environment", "")).lower() == "production"
            and type(d.get("production_environment")) is bool and d.get("creator", {}).get("login") in {"vercel[bot]", "vercel"}]
    if not rows or any(type(d.get("id")) is not int or d["id"] <= 0 for d in rows):
        raise ValueError("Retirement trusted production deployment missing")
    result = max(rows, key=lambda d: d["id"])
    revision(result.get("sha"))
    return result


def valid_status(status):
    if status.get("state") != "success" or status.get("creator", {}).get("login") not in {"vercel[bot]", "vercel"}:
        return False
    url = urlsplit(status.get("environment_url", ""))
    return (url.scheme == "https" and url.hostname is not None and url.hostname.startswith("chendermatologist-")
            and url.hostname.endswith(".vercel.app") and not url.username and not url.password and not url.port
            and url.path in {"", "/"} and not url.query and not url.fragment)


def historical_status_valid(latest, success, current_sha, published):
    if latest == success:
        return True
    return (current_sha != published and latest.get("state") == "inactive"
            and latest.get("environment_url") == success.get("environment_url")
            and valid_status({**latest, "state": "success"}))


def publication_evidence(api, published, candidate, claimed=None):
    """Re-read exact formal attempts/jobs/steps; historical success is not live intent."""
    _, raw = github_file(api, "_delivery_policy.json", published, 32_000)
    policy = parse(raw)
    if (not isinstance(policy, dict) or policy.get("repository") != REPO or policy.get("require_pr") is not True
            or policy.get("allow_dispatch") is not False or policy.get("cms_author_intent") is not True
            or not isinstance(policy.get("workflows"), list) or len(policy["workflows"]) < 6
            or any(not isinstance(w, dict) or not isinstance(w.get("path"), str)
                   or not isinstance(w.get("jobs"), list) or not w["jobs"]
                   or any(not isinstance(n, str) for n in w["jobs"]) for w in policy["workflows"])
            or len({w.get("path") for w in policy["workflows"]}) != len(policy["workflows"])):
        raise ValueError("Retirement formal policy unavailable")
    from _delivery import assess_jobs
    selected = selected_runs(api, published, policy)
    for record, entry in zip(selected, policy["workflows"]):
        jobs = pages(api, f'/actions/runs/{record["runId"]}/attempts/{record["attempt"]}/jobs', "jobs")
        if any(j.get("head_sha") != published for j in jobs) or any(sum(j.get("name") == n for j in jobs) != 1 for n in entry["jobs"]):
            raise ValueError("Retirement formal job SHA or identity invalid")
        assess_jobs(jobs, entry["jobs"], entry.get("main_skips", []), entry.get("steps"), "main")
    if selected_runs(api, published, policy) != selected:
        raise ValueError("Retirement formal CI changed")
    deployment = production(api)
    if deployment["sha"] not in {published, candidate}:
        raise ValueError("Retirement production rolled back or changed")
    deployment_id = claimed["deploymentId"] if claimed else deployment["id"]
    if type(deployment_id) is not int or deployment_id <= 0:
        raise ValueError("Retirement deployment identity invalid")
    original = api.get("/deployments/" + str(deployment_id))
    if (original.get("id") != deployment_id or original.get("sha") != published
            or str(original.get("environment", "")).lower() != "production"
            or type(original.get("production_environment")) is not bool
            or original.get("creator", {}).get("login") not in {"vercel[bot]", "vercel"}):
        raise ValueError("Retirement deployment does not bind the published revision")
    statuses = pages(api, "/deployments/" + str(deployment_id) + "/statuses")
    if not statuses or any(type(s.get("id")) is not int or s["id"] <= 0 for s in statuses):
        raise ValueError("Retirement deployment statuses incomplete")
    status = next((s for s in statuses if s["id"] == claimed["statusId"]), None) if claimed else max(statuses, key=lambda s: s["id"])
    if not status or not valid_status(status):
        raise ValueError("Retirement lacks trusted successful deployment evidence")
    # Before promotion the latest publication must still be the observed one.
    # After promotion, a newer deployment of the retirement-only candidate is
    # expected; the prior success may now be marked inactive, but is not erased.
    if ((deployment["sha"] == published and deployment["id"] != deployment_id)
            or not historical_status_valid(max(statuses, key=lambda s: s["id"]), status, deployment["sha"], published)):
        raise ValueError("Retirement publication changed since preparation")
    result = {"workflows": selected, "deploymentId": deployment_id, "statusId": status["id"]}
    if claimed is not None and claimed != result:
        raise ValueError("Retirement evidence does not match exact formal publication")
    fresh = production(api)
    if fresh["id"] != deployment["id"] or fresh["sha"] != deployment["sha"]:
        raise ValueError("Retirement deployment changed during validation")
    fresh_statuses = pages(api, "/deployments/" + str(deployment_id) + "/statuses")
    if (not fresh_statuses or any(type(s.get("id")) is not int or s["id"] <= 0 for s in fresh_statuses)
            or not any(s == status for s in fresh_statuses)
            or not historical_status_valid(max(fresh_statuses, key=lambda s: s["id"]), status, fresh["sha"], published)):
        raise ValueError("Retirement deployment status changed during validation")
    return result


def verify_transition(candidate, api, current_items, *, now=None):
    current = main_sha(api); base = baseline(api, candidate, current)
    before = optional_blob(api, FILE, base)
    old_items = receipts(before[1], now=now) if before else []
    old_archives = archive_paths(api.entries(base)); new_archives = archive_paths(api.entries(candidate))
    if any(new_archives.get(path) != blob for path, blob in old_archives.items()):
        raise ValueError("Immutable retirement history was modified or removed")
    added = set(new_archives) - set(old_archives)
    old = {r["file"]: r for r in old_items}; new = {r["file"]: r for r in current_items}
    if any(new[file] != old[file] for file in set(old) & set(new)):
        raise ValueError("Existing published receipt requires separate retirement before replacement")
    removed = set(old) - set(new)
    if added or removed:
        path = PREFIX + base + ".json"
        if not removed or added != {path} or any(old.get(file) != value for file, value in new.items()):
            raise ValueError("Receipt removal requires a separate exact retirement candidate")
        before_files = {p: (e.get("mode"), e.get("type"), e.get("sha")) for p, e in api.entries(base).items() if e.get("type") != "tree"}
        after_files = {p: (e.get("mode"), e.get("type"), e.get("sha")) for p, e in api.entries(candidate).items() if e.get("type") != "tree"}
        changed = {p for p in set(before_files) | set(after_files) if before_files.get(p) != after_files.get(p)}
        if changed != {FILE, path}:
            raise ValueError("Retirement must not change patient content or other source files")
        _, raw = github_file(api, path, candidate, 256_000)
        record = parse(raw, canonical=True, limit=256_000)
        if (not isinstance(record, dict) or set(record) != FIELDS or type(record["version"]) is not int or record["version"] != 1
                or record["repository"] != REPO or record["publishedSha"] != base or record["receiptBlobSha"] != before[0]
                or record["requests"] != [old[f] for f in sorted(removed)]):
            raise ValueError("Retirement does not preserve the exact published receipt")
        stamp = utc(record["preparedAt"])
        if stamp > (now or datetime.now(timezone.utc)):
            raise ValueError("Retirement preparation timestamp is in the future")
        claimed = record["evidence"]
        if not isinstance(claimed, dict) or set(claimed) != {"workflows", "deploymentId", "statusId"}:
            raise ValueError("Retirement publication evidence incomplete")
        publication_evidence(api, base, candidate, claimed)
    if main_sha(api) != current:
        raise ValueError("Retirement main changed during validation")
    return {"retiredRequests": len(removed), "baseline": base}


def prepare(api, expected_main, *, now=None):
    """Return reviewable source bytes only; no branch, draft or production writes."""
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("Retirement preparation clock requires a timezone")
    now = now.astimezone(timezone.utc)
    api = ImmutableBlobs(api); expected_main = revision(expected_main)
    if main_sha(api) != expected_main:
        raise ValueError("Retirement preparation main changed")
    receipt_sha, raw = github_file(api, FILE, expected_main)
    items = receipts(raw, now=now)
    if not items:
        if main_sha(api) != expected_main:
            raise ValueError("Retirement preparation main changed")
        return {}
    path = PREFIX + expected_main + ".json"
    if path in api.entries(expected_main):
        raise ValueError("Retirement archive already exists")
    evidence = publication_evidence(api, expected_main, expected_main)
    record = {"version": 1, "repository": REPO, "publishedSha": expected_main, "receiptBlobSha": receipt_sha,
              "requests": sorted(items, key=lambda item: item["file"]), "evidence": evidence,
              "preparedAt": (now or datetime.now(timezone.utc)).isoformat(timespec="milliseconds").replace("+00:00", "Z")}
    if main_sha(api) != expected_main:
        raise ValueError("Retirement preparation main changed")
    encode = lambda value: (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return {FILE: encode({"version": 1, "requests": []}), path: encode(record)}
