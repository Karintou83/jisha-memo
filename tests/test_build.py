import json

import pytest

from jisha_memo.build import asset_version, build, excerpt

SITES_YAML = """
sites:
  - wikidata: Q1
    tags: [テスト札所]
    visits:
      - date: "2025-04"
        memo: 桜がきれいだった
        goshuin: true
      - date: "2026-09"
        memo: 二回目
  - wikidata: Q2
    type: shrine
    visits:
      - goshuin: true
      - date: "2024-01"
"""

CACHE = {
    "sites": {
        "Q1": {
            "id": "Q1",
            "label": "テスト寺",
            "coordinate": {"lat": 35.0, "lng": 135.7},
            "instance_of": ["仏教寺院"],
            "located_in": "東山区",
            "image": "A.jpg",
        },
        "Q2": {
            "id": "Q2",
            "label": "Test Shrine",
            "instance_of": ["建造物"],
            "jawiki_title": "テスト社 (千代田区)",
        },
    },
    "images": {
        "A.jpg": {
            "file": "A.jpg",
            "thumb_url": "https://upload.wikimedia.org/thumb/a.jpg",
            "page_url": "https://commons.wikimedia.org/wiki/File:A.jpg",
            "artist": "X",
            "license": "CC BY-SA 4.0",
        }
    },
    "wikipedia": {
        "Q1": {
            "title": "テスト寺",
            "extract": "テスト寺は京都にある寺院。" + "あ" * 100 + "\n二段落目。",
            "revid": 42,
        }
    },
}


@pytest.fixture
def built(tmp_path):
    sites = tmp_path / "sites.yaml"
    cache = tmp_path / "cache.json"
    sites.write_text(SITES_YAML, encoding="utf-8")
    cache.write_text(json.dumps(CACHE, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "_site"
    build(sites, cache, out)
    return out


def _map_points(html):
    start = html.index('id="map-points">') + len('id="map-points">')
    return json.loads(html[start : html.index("</script>", start)])


def test_index_is_map(built):
    html = (built / "index.html").read_text(encoding="utf-8")
    assert "2 寺社・4 回の参拝" in html
    points = _map_points(html)
    # 座標のない Q2 は地図に載らない
    assert [p["id"] for p in points] == ["Q1"]
    assert points[0]["url"] == "sites/Q1.html"
    assert points[0]["image"] == "https://upload.wikimedia.org/thumb/a.jpg"  # ホバー時の写真
    assert points[0]["last_visit"] == "2026-09"
    assert points[0]["excerpt"] == "テスト寺は京都にある寺院。"  # Wikipedia 冒頭の抜粋
    assert "二回目" not in html  # 一言メモはトップページに出さない


def test_site_page(built):
    html = (built / "sites" / "Q1.html").read_text(encoding="utf-8")
    assert "寺院" in html and "東山区" in html
    assert "御朱印" in html
    assert "CC BY-SA 4.0" in html  # Commons 画像のクレジット
    assert "https://www.wikidata.org/wiki/Q1" in html
    # Wikipedia の冒頭部分を段落ごとに転記し、版を指定して出典を示す
    assert "<p>二段落目。</p>" in html
    assert "https://ja.wikipedia.org/w/index.php?oldid=42" in html
    assert "CC BY-SA 4.0" in html


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("短い説明。", "短い説明。"),
        ("一文目。" + "い" * 100, "一文目。"),
        ("あ" * 100, "あ" * 80 + "…"),  # 句点がなければ文字数で切る
        ("一段落目。\n二段落目。", "一段落目。"),
    ],
)
def test_excerpt(text, expected):
    assert excerpt(text) == expected


def test_type_override_and_missing_coordinate(built):
    html = (built / "sites" / "Q2.html").read_text(encoding="utf-8")
    # 表示名は Wikipedia の記事名から曖昧さ回避の括弧を外したもの
    assert "<h1>テスト社</h1>" in html
    assert "神社" in html
    assert 'id="map"' not in html


def test_missing_cache_entry(tmp_path):
    sites = tmp_path / "sites.yaml"
    cache = tmp_path / "cache.json"
    sites.write_text("sites: [{wikidata: Q9}]", encoding="utf-8")
    cache.write_text("{}", encoding="utf-8")
    with pytest.raises(SystemExit, match="Q9"):
        build(sites, cache, tmp_path / "_site")


def test_static_assets_are_versioned(built):
    # 更新後に古い CSS・JS がキャッシュから使われないよう、URL に版を付ける
    version = asset_version()
    index = (built / "index.html").read_text(encoding="utf-8")
    page = (built / "sites" / "Q1.html").read_text(encoding="utf-8")
    assert f'static/app.js?v={version}"' in index
    assert f'static/style.css?v={version}"' in index
    assert f'../static/app.js?v={version}"' in page


def test_asset_version_changes_with_content(tmp_path):
    (tmp_path / "app.js").write_text("a", encoding="utf-8")
    before = asset_version(tmp_path)
    (tmp_path / "app.js").write_text("b", encoding="utf-8")
    assert asset_version(tmp_path) != before


def test_memo_button(built):
    from urllib.parse import parse_qs, urlparse
    import html as html_lib

    page = (built / "sites" / "Q1.html").read_text(encoding="utf-8")
    href = html_lib.unescape(page.split('class="memo-button" href="', 1)[1].split('"', 1)[0])
    url = urlparse(href)
    assert url.path == "/Karintou83/jisha-memo/issues/new"
    query = parse_qs(url.query)
    assert query["template"] == ["memo.yml"]
    assert query["wikidata"] == ["Q1"]
    assert query["date"] == ["2026-09"]  # 最新の参拝年月を入れておく
    assert query["title"][0].startswith("一言メモ")  # Actions はこの題名で処理対象を判定する
