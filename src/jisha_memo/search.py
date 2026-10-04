"""寺社名から Wikidata の項目 ID を探し、data/sites.yaml に貼れる形で表示する。

使い方:
    python -m jisha_memo.search 伏見稲荷大社 清水寺
"""

from __future__ import annotations

import argparse
from typing import Any

import requests

from .wikidata import USER_AGENT, WIKIDATA_API

LIMIT = 5


def parse_results(data: dict[str, Any]) -> list[tuple[str, str, str]]:
    """wbsearchentities の結果を (ID, 名称, 説明) のリストにする。"""
    return [
        (item["id"], item.get("label", ""), item.get("description", ""))
        for item in data.get("search", [])
    ]


def search(session: requests.Session, name: str) -> list[tuple[str, str, str]]:
    resp = session.get(
        WIKIDATA_API,
        params={
            "action": "wbsearchentities",
            "search": name,
            "language": "ja",
            "uselang": "ja",
            "type": "item",
            "limit": str(LIMIT),
            "format": "json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return parse_results(resp.json())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="+", help="寺社名")
    args = parser.parse_args()

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    for name in args.names:
        print(f"# {name}")
        results = search(session, name)
        if not results:
            print("  見つかりませんでした")
        for qid, label, description in results:
            print(f"  - wikidata: {qid}  # {label}（{description}）")
        print()


if __name__ == "__main__":
    main()
