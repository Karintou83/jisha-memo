"""data/ の YAML とキャッシュから静的サイトを _site/ に生成する。

使い方:
    python -m jisha_memo.build
"""

from __future__ import annotations

import hashlib
import json
import re
from urllib.parse import quote, urlencode
import shutil
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import CommonsImage, SiteEntry, SiteType, Visit, WikidataInfo, WikipediaExtract, load_sites

ROOT = Path(__file__).resolve().parents[2]
SITES_PATH = ROOT / "data" / "sites.yaml"
CACHE_PATH = ROOT / "data" / "wikidata_cache.json"
TEMPLATES_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
OUTPUT_DIR = ROOT / "_site"

REPO_URL = "https://github.com/Karintou83/jisha-memo"
TYPE_LABELS: dict[str, str] = {"temple": "寺院", "shrine": "神社"}
EXCERPT_LENGTH = 80


def excerpt(text: str, limit: int = EXCERPT_LENGTH) -> str:
    """冒頭の段落から、なるべく文の切れ目（。）で区切った抜粋を作る。"""
    first = text.split("\n", 1)[0]
    if len(first) <= limit:
        return first
    cut = first.rfind("。", 0, limit)
    if cut != -1:
        return first[: cut + 1]
    return first[:limit] + "…"


@dataclass
class Site:
    """テンプレートに渡す、利用者のメモと Wikidata の情報を合わせたもの。"""

    entry: SiteEntry
    info: WikidataInfo
    images: list[CommonsImage]
    wikipedia: WikipediaExtract | None = None

    @property
    def id(self) -> str:
        return self.entry.wikidata

    @property
    def name(self) -> str:
        """表示名。日本語版 Wikipedia の記事名に揃え、末尾の曖昧さ回避の括弧は外す。"""
        if self.info.jawiki_title:
            return re.sub(r"\s*[(（][^()（）]*[)）]$", "", self.info.jawiki_title)
        return self.info.label

    @property
    def memo_url(self) -> str:
        """「一言メモを追加」の Issue フォームを、寺社と最新の参拝年月を入れた状態で開く URL。"""
        params = {"template": "memo.yml", "title": f"一言メモ: {self.name}", "wikidata": self.id}
        if self.last_visit:
            params["date"] = self.last_visit
        return f"{REPO_URL}/issues/new?{urlencode(params, quote_via=quote)}"

    @property
    def type(self) -> SiteType | None:
        if self.entry.type:
            return self.entry.type
        # Wikidata の「分類（P31）」の日本語名から推定する
        kinds = " ".join(self.info.instance_of)
        if "神社" in kinds or "神宮" in kinds:
            return "shrine"
        if "寺" in kinds:
            return "temple"
        return None

    @property
    def type_label(self) -> str:
        return TYPE_LABELS.get(self.type or "", "")

    @property
    def visits(self) -> list[Visit]:
        return sorted(self.entry.visits, key=lambda v: v.date or "", reverse=True)

    @property
    def excerpt(self) -> str:
        return excerpt(self.wikipedia.extract) if self.wikipedia else ""

    @property
    def last_visit(self) -> str:
        return (self.visits[0].date or "") if self.visits else ""


def load_site_models(sites_path: Path, cache_path: Path) -> list[Site]:
    entries = load_sites(sites_path)
    cache = json.loads(cache_path.read_text(encoding="utf-8") or "{}")
    cached_sites = cache.get("sites", {})
    cached_images = cache.get("images", {})
    cached_wikipedia = cache.get("wikipedia", {})

    sites: list[Site] = []
    for entry in entries:
        raw = cached_sites.get(entry.wikidata)
        if raw is None:
            raise SystemExit(
                f"{entry.wikidata} の情報がキャッシュにありません。"
                "先に `python -m jisha_memo.wikidata` を実行してください。"
            )
        info = WikidataInfo.model_validate(raw)
        files = [p.removeprefix("File:").strip() for p in entry.photos] or ([info.image] if info.image else [])
        images = [CommonsImage.model_validate(cached_images[f]) for f in files if f in cached_images]
        wiki = cached_wikipedia.get(entry.wikidata)
        wikipedia = WikipediaExtract.model_validate(wiki) if wiki else None
        sites.append(Site(entry=entry, info=info, images=images, wikipedia=wikipedia))

    sites.sort(key=lambda s: s.last_visit, reverse=True)
    return sites


def asset_version(static_dir: Path = STATIC_DIR) -> str:
    """static/ の中身から作る短いハッシュ。

    CSS・JS の URL に付けることで、更新後にブラウザが古いキャッシュを使い続けるのを防ぐ。
    """
    digest = hashlib.sha256()
    for path in sorted(static_dir.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(static_dir).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()[:10]


def map_points(sites: list[Site], prefix: str = "") -> list[dict[str, object]]:
    return [
        {
            "id": s.id,
            "name": s.name,
            "type": s.type,
            "type_label": s.type_label,
            "tags": s.entry.tags,
            "last_visit": s.last_visit,
            "excerpt": s.excerpt,
            "image": s.images[0].thumb_url if s.images else None,
            "lat": s.info.coordinate.lat,
            "lng": s.info.coordinate.lng,
            "url": f"{prefix}sites/{s.id}.html",
        }
        for s in sites
        if s.info.coordinate
    ]


def build(sites_path: Path = SITES_PATH, cache_path: Path = CACHE_PATH, output_dir: Path = OUTPUT_DIR) -> None:
    sites = load_site_models(sites_path, cache_path)
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=select_autoescape())
    env.globals["asset_version"] = asset_version()

    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "sites").mkdir(parents=True)
    shutil.copytree(STATIC_DIR, output_dir / "static")

    tags = sorted({t for s in sites for t in s.entry.tags})
    (output_dir / "index.html").write_text(
        env.get_template("index.html").render(
            root="",
            sites=sites,
            tags=tags,
            points=map_points(sites),
            visit_count=sum(len(s.entry.visits) for s in sites),
        ),
        encoding="utf-8",
    )
    for site in sites:
        (output_dir / "sites" / f"{site.id}.html").write_text(
            env.get_template("site.html").render(root="../", site=site, points=map_points([site], "../")),
            encoding="utf-8",
        )
    print(f"{len(sites)} 件の寺社ページを {output_dir} に生成しました")


def main() -> None:
    build()


if __name__ == "__main__":
    main()
