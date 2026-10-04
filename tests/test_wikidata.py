from jisha_memo.wikidata import clean_extract, parse_entity, parse_extracts, parse_imageinfo


def _claim(prop_value, rank="normal"):
    return {"rank": rank, "mainsnak": {"snaktype": "value", "datavalue": {"value": prop_value}}}


ENTITY = {
    "id": "Q1",
    "labels": {"ja": {"value": "テスト寺"}, "en": {"value": "Test-ji"}},
    "descriptions": {"ja": {"value": "京都の寺院"}},
    "claims": {
        "P31": [_claim({"id": "Q100"})],
        "P131": [_claim({"id": "Q200"}, rank="deprecated"), _claim({"id": "Q201"})],
        "P625": [_claim({"latitude": 35.0, "longitude": 135.7})],
        "P18": [_claim("Old.jpg"), _claim("Best.jpg", rank="preferred")],
        "P856": [_claim("https://example.org/")],
    },
    "sitelinks": {"jawiki": {"url": "https://ja.wikipedia.org/wiki/テスト寺"}},
}


def test_parse_entity():
    info = parse_entity(ENTITY, {"Q100": "仏教寺院", "Q201": "東山区"})
    assert info.label == "テスト寺"
    assert info.instance_of == ["仏教寺院"]
    assert info.located_in == "東山区"  # deprecated の値は使わない
    assert info.image == "Best.jpg"  # preferred を優先する
    assert info.coordinate.lat == 35.0
    assert info.jawiki_url.endswith("テスト寺")


def test_parse_entity_minimal():
    info = parse_entity({"id": "Q2", "labels": {"en": {"value": "Only English"}}}, {})
    assert info.label == "Only English"
    assert info.coordinate is None and info.image is None


def test_parse_imageinfo_strips_html():
    page = {
        "imageinfo": [
            {
                "url": "https://upload.wikimedia.org/a.jpg",
                "thumburl": "https://upload.wikimedia.org/thumb/a.jpg",
                "descriptionurl": "https://commons.wikimedia.org/wiki/File:A.jpg",
                "extmetadata": {
                    "Artist": {"value": '<a href="//commons.wikimedia.org/wiki/User:X">X &amp; Y</a>'},
                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                },
            }
        ]
    }
    image = parse_imageinfo("A.jpg", page)
    assert image.artist == "X & Y"
    assert image.license == "CC BY-SA 4.0"
    assert parse_imageinfo("Missing.jpg", {"missing": ""}) is None


def test_parse_extracts_follows_normalization_and_redirects():
    query = {
        "normalized": [{"from": "テスト_寺", "to": "テスト 寺"}],
        "redirects": [{"from": "テスト 寺", "to": "テスト寺"}],
        "pages": {
            "1": {"title": "テスト寺", "lastrevid": 123, "extract": "テスト寺（てすとでら、）は寺院。\n\n境内は広い。"},
            "-1": {"title": "存在しない", "missing": ""},
        },
    }
    result = parse_extracts(query, ["テスト_寺", "存在しない"])
    assert list(result) == ["テスト_寺"]
    extract = result["テスト_寺"]
    assert extract.title == "テスト寺"
    assert extract.extract == "テスト寺（てすとでら、）は寺院。\n境内は広い。"
    assert extract.permalink == "https://ja.wikipedia.org/w/index.php?oldid=123"


def test_clean_extract_removes_empty_parentheses():
    assert clean_extract("伏見稲荷大社（ 、）は神社。") == "伏見稲荷大社は神社。"
