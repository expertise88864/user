"""Data-only settings validation shared by trusted generators and delivery gates.

Read this module from the trusted base, never import Python from a CMS branch.
Settings select existing public articles and fixed fonts; no code or CSS input.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
CONTRACT = json.loads((ROOT / "_site_settings_contract.json").read_text(encoding="utf-8"))
SHA = re.compile(r"(?!0{40}$)[a-f0-9]{40}\Z")


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate settings JSON key")
        result[key] = value
    return result


def parse_json(text: str | bytes, limit: int = 32_000):
    if isinstance(text, bytes):
        if len(text) > limit:
            raise ValueError("Settings JSON exceeds byte limit")
        text = text.decode("utf-8", errors="strict")
    elif not isinstance(text, str) or len(text.encode("utf-8")) > limit:
        raise ValueError("Invalid or oversized settings JSON")
    return json.loads(text, object_pairs_hook=unique_object,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite settings JSON")))


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("Invalid settings fields")


def catalog_of(value):
    exact(value, ("version", "articles"))
    rows = value["articles"]
    if type(value["version"]) not in (int, float) or value["version"] != 1 or not isinstance(rows, list) or not 1 <= len(rows) <= CONTRACT["maxArticles"]:
        raise ValueError("Invalid settings catalogue")
    seen = set()
    for row in rows:
        exact(row, ("slug", "title", "title_en"))
        slug = row["slug"]
        if not isinstance(slug, str) or len(slug) > 100 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or slug in seen:
            raise ValueError("Invalid or duplicate settings article")
        for key in ("title", "title_en"):
            text = row[key]
            if not isinstance(text, str) or not text.strip() or len(text.encode("utf-16-le")) // 2 > 500:
                raise ValueError("Invalid settings article title")
        seen.add(slug)
    return [dict(row) for row in rows]


def settings_record(value):
    """Validate stored source without assuming its original catalogue is current.

    Delivery still binds approved source to its immutable original catalogue.
    Projection never approves a new author selection or rewrites that source.
    """
    exact(value, ("version", "font", "order", "picks", "legacyPicks"))
    if type(value["version"]) not in (int, float) or value["version"] != 1 or type(value["legacyPicks"]) is not bool:
        raise ValueError("Invalid settings version")
    exact(value["font"], CONTRACT["fonts"])
    if any(not isinstance(value["font"][key], str) or value["font"][key] not in choices for key, choices in CONTRACT["fonts"].items()):
        raise ValueError("Invalid settings font")
    for key, limit in (("order", CONTRACT["maxArticles"]), ("picks", CONTRACT["maxPicks"])):
        values = value[key]
        if not isinstance(values, list) or len(values) > limit or any(
                not isinstance(slug, str) or len(slug) > 100 or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug)
                for slug in values):
            raise ValueError("Invalid settings article selection")
        if len(values) != len(set(values)):
            raise ValueError("Duplicate settings article selection")
    if not value["picks"]:
        raise ValueError("Incomplete settings article selection")
    return {"version": 1, "legacyPicks": value["legacyPicks"], "font": dict(value["font"]), "order": list(value["order"]), "picks": list(value["picks"])}


def settings_of(value, articles):
    """New author input must select only the current public catalogue."""
    result = settings_record(value)
    slugs = {item["slug"] for item in articles}
    if any(slug not in slugs for key in ("order", "picks") for slug in result[key]):
        raise ValueError("Invalid settings article selection")
    if result["order"] and len(result["order"]) != len(articles):
        raise ValueError("Incomplete settings article selection")
    return result


def public_settings_of(value, articles):
    """Keep visible approved priorities; append new articles in default order.

    Withdrawn picks disappear. An empty projected recommendation list does not
    invent replacement recommendations that the author never selected.
    """
    result = settings_record(value)
    current = [item["slug"] for item in articles]
    visible = set(current)
    if result["order"]:
        retained = [slug for slug in result["order"] if slug in visible]
        retained_set = set(retained)
        result["order"] = retained + [slug for slug in current if slug not in retained_set]
    result["picks"] = [slug for slug in result["picks"] if slug in visible]
    return result


def public_settings_catalog(root: Path = ROOT):
    # Uses only the trusted site's article source and visibility declarations.
    from _sync_hub_catalog import CardList, load_catalog, public_catalog
    rows = public_catalog(load_catalog(root), root)
    # The default UI order must match the homepage's authored visible dates,
    # including existing editorial date overrides and catalogue tie-breaking.
    home = root / 'index.html'
    dates = CardList(home.read_text(encoding='utf-8'), 'dn-article-list').dates if home.is_file() else {}
    rank = {item['slug']: (dates.get(item['slug']) or item.get('date') or '', index) for index, item in enumerate(rows)}
    rows = sorted(rows, key=lambda item: rank[item['slug']], reverse=True)
    return {"version": 1, "articles": catalog_of({"version": 1, "articles": [
        {key: item[key] for key in ("slug", "title", "title_en")} for item in rows]})}


def load_settings(root: Path = ROOT):
    catalog = public_settings_catalog(root)
    settings = public_settings_of(parse_json((root / CONTRACT["source"]).read_bytes()), catalog["articles"])
    return settings, catalog
