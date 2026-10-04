"""データの型定義。

利用者が書くのは SiteEntry（Wikidata ID と一言メモ）だけで、
寺社の名称・座標などは Wikidata から取得した WikidataInfo を使う。
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field

SiteType = Literal["temple", "shrine"]


class Visit(BaseModel):
    # 日付は年月まで
    date: str = Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")
    memo: str = ""
    goshuin: bool = False


class SiteEntry(BaseModel):
    """data/sites.yaml の 1 件分。"""

    wikidata: str = Field(pattern=r"^Q\d+$")
    type: SiteType | None = None
    tags: list[str] = []
    photos: list[str] = []
    visits: list[Visit] = []


class SitesFile(BaseModel):
    sites: list[SiteEntry] = []


class Coordinate(BaseModel):
    lat: float
    lng: float


class CommonsImage(BaseModel):
    file: str
    thumb_url: str
    page_url: str
    artist: str = ""
    license: str = ""


class WikidataInfo(BaseModel):
    """Wikidata から取得した寺社の情報（キャッシュに保存する形）。"""

    id: str
    label: str
    description: str = ""
    coordinate: Coordinate | None = None
    instance_of: list[str] = []
    located_in: str = ""
    image: str | None = None
    official_website: str | None = None
    jawiki_url: str | None = None
    jawiki_title: str | None = None


class WikipediaExtract(BaseModel):
    """日本語版 Wikipedia 記事の冒頭部分。"""

    title: str
    extract: str
    revid: int

    @property
    def permalink(self) -> str:
        # 取得した時点の版へのリンク（記事が更新されても、転記元を正確に示せる）
        return f"https://ja.wikipedia.org/w/index.php?oldid={self.revid}"


def load_sites(path: Path) -> list[SiteEntry]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return SitesFile.model_validate(raw).sites
