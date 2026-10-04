"""Wikidata / Wikimedia Commons から寺社情報を取得してキャッシュする。

キャッシュ（data/wikidata_cache.json）をリポジトリに置くことで、
ビルドのたびに API へアクセスせずに済み、Wikidata 側の変更も差分で確認できる。

使い方:
    python -m jisha_memo.wikidata            # 未取得の項目だけ取得
    python -m jisha_memo.wikidata --refresh  # すべて取り直す
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any, Iterable

import requests

from .models import CommonsImage, Coordinate, WikidataInfo, load_sites

WIKIDATA_API = "https://www.wikidata.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
# Wikimedia の利用規約で、連絡先のわかる User-Agent が求められている
USER_AGENT = "jisha-memo/0.1 (https://github.com/Karintou83/jisha-memo)"
BATCH_SIZE = 50  # wbgetentities が一度に受け付ける上限
THUMB_WIDTH = 640

ROOT = Path(__file__).resolve().parents[2]
SITES_PATH = ROOT / "data" / "sites.yaml"
CACHE_PATH = ROOT / "data" / "wikidata_cache.json"


def _chunks(items: list[str], size: int) -> Iterable[list[str]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def _get(session: requests.Session, url: str, params: dict[str, str]) -> dict[str, Any]:
    resp = session.get(url, params={**params, "format": "json"}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _label(entity: dict[str, Any]) -> str:
    labels = entity.get("labels", {})
    for lang in ("ja", "en"):
        if lang in labels:
            return labels[lang]["value"]
    return entity.get("id", "")


def _claim_values(entity: dict[str, Any], prop: str) -> list[Any]:
    """指定プロパティの値を、優先度の高い順（preferred → normal）に返す。"""
    claims = [
        c
        for c in entity.get("claims", {}).get(prop, [])
        if c.get("rank") != "deprecated" and c["mainsnak"].get("snaktype") == "value"
    ]
    claims.sort(key=lambda c: c.get("rank") != "preferred")
    return [c["mainsnak"]["datavalue"]["value"] for c in claims]


def _item_ids(entity: dict[str, Any], prop: str) -> list[str]:
    return [v["id"] for v in _claim_values(entity, prop)]


def parse_entity(entity: dict[str, Any], labels: dict[str, str]) -> WikidataInfo:
    """wbgetentities の 1 項目を WikidataInfo に変換する。

    labels は P31・P131 が指す項目の ID → 日本語名の対応表。
    """
    coords = _claim_values(entity, "P625")
    images = _claim_values(entity, "P18")
    websites = _claim_values(entity, "P856")
    located = _item_ids(entity, "P131")
    jawiki = entity.get("sitelinks", {}).get("jawiki")

    return WikidataInfo(
        id=entity["id"],
        label=_label(entity),
        description=entity.get("descriptions", {}).get("ja", {}).get("value", ""),
        coordinate=Coordinate(lat=coords[0]["latitude"], lng=coords[0]["longitude"]) if coords else None,
        instance_of=[labels.get(q, q) for q in _item_ids(entity, "P31")],
        located_in=labels.get(located[0], located[0]) if located else "",
        image=images[0] if images else None,
        official_website=websites[0] if websites else None,
        jawiki_url=jawiki.get("url") if jawiki else None,
    )


def fetch_entities(session: requests.Session, ids: list[str]) -> dict[str, dict[str, Any]]:
    entities: dict[str, dict[str, Any]] = {}
    for chunk in _chunks(ids, BATCH_SIZE):
        data = _get(
            session,
            WIKIDATA_API,
            {
                "action": "wbgetentities",
                "ids": "|".join(chunk),
                "props": "labels|descriptions|claims|sitelinks/urls",
                "languages": "ja|en",
                "sitefilter": "jawiki",
            },
        )
        entities.update(data.get("entities", {}))
    return entities


def fetch_labels(session: requests.Session, ids: list[str]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for chunk in _chunks(ids, BATCH_SIZE):
        data = _get(
            session,
            WIKIDATA_API,
            {"action": "wbgetentities", "ids": "|".join(chunk), "props": "labels", "languages": "ja|en"},
        )
        for qid, entity in data.get("entities", {}).items():
            labels[qid] = _label(entity)
    return labels


def _strip_tags(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text)).strip()


def parse_imageinfo(file: str, page: dict[str, Any]) -> CommonsImage | None:
    info = (page.get("imageinfo") or [None])[0]
    if info is None:
        return None
    meta = info.get("extmetadata", {})
    return CommonsImage(
        file=file,
        thumb_url=info.get("thumburl") or info["url"],
        page_url=info["descriptionurl"],
        artist=_strip_tags(meta.get("Artist", {}).get("value", "")),
        license=meta.get("LicenseShortName", {}).get("value", ""),
    )


def fetch_commons(session: requests.Session, files: list[str]) -> dict[str, CommonsImage]:
    """Commons のファイル名から、サムネイル URL と作者・ライセンス情報を取得する。"""
    result: dict[str, CommonsImage] = {}
    for chunk in _chunks(files, BATCH_SIZE):
        data = _get(
            session,
            COMMONS_API,
            {
                "action": "query",
                "titles": "|".join(f"File:{f}" for f in chunk),
                "prop": "imageinfo",
                "iiprop": "url|extmetadata",
                "iiurlwidth": str(THUMB_WIDTH),
                "iiextmetadatafilter": "Artist|LicenseShortName",
            },
        )
        query = data.get("query", {})
        # API はファイル名を正規化（_ → 空白など）して返すので、元の名前に戻す
        normalized = {n["to"]: n["from"] for n in query.get("normalized", [])}
        for page in query.get("pages", {}).values():
            title = normalized.get(page["title"], page["title"])
            file = title.removeprefix("File:")
            image = parse_imageinfo(file, page)
            if image:
                result[file] = image
    return result


def _normalize_file(name: str) -> str:
    return name.removeprefix("File:").strip()


def update_cache(refresh: bool = False) -> dict[str, Any]:
    sites = load_sites(SITES_PATH)
    cache: dict[str, Any] = {} if refresh else json.loads(CACHE_PATH.read_text(encoding="utf-8") or "{}")
    cached_sites: dict[str, Any] = cache.get("sites", {})
    cached_images: dict[str, Any] = cache.get("images", {})

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    missing = sorted({s.wikidata for s in sites} - cached_sites.keys())
    if missing:
        entities = fetch_entities(session, missing)
        ref_ids = sorted(
            {q for e in entities.values() for p in ("P31", "P131") for q in _item_ids(e, p)}
        )
        labels = fetch_labels(session, ref_ids) if ref_ids else {}
        for qid, entity in entities.items():
            if "missing" in entity:
                print(f"警告: {qid} は Wikidata に存在しません")
                continue
            cached_sites[qid] = parse_entity(entity, labels).model_dump()

    wanted_files: set[str] = set()
    for s in sites:
        if s.photos:
            wanted_files.update(_normalize_file(p) for p in s.photos)
        elif (info := cached_sites.get(s.wikidata)) and info.get("image"):
            wanted_files.add(info["image"])
    missing_files = sorted(wanted_files - cached_images.keys())
    if missing_files:
        for file, image in fetch_commons(session, missing_files).items():
            cached_images[file] = image.model_dump()

    cache = {"sites": dict(sorted(cached_sites.items())), "images": dict(sorted(cached_images.items()))}
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"寺社 {len(cached_sites)} 件・画像 {len(cached_images)} 件をキャッシュしました")
    return cache


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="キャッシュを無視してすべて取り直す")
    update_cache(refresh=parser.parse_args().refresh)


if __name__ == "__main__":
    main()
