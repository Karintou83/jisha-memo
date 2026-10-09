import pytest
import yaml

from jisha_memo.add_memo import MemoError, add_memo, parse_issue_body, to_visit
from jisha_memo.models import SitesFile, Visit

SITES = """# コメントは残る
sites:
  - wikidata: Q1  # テスト寺
    tags: [世界遺産]
    visits:
      - date: "2025-04"
        goshuin: true
      - date: "2026-03"
        memo: |-
            一行目。
            二行目。
        goshuin: true
  - wikidata: Q2  # テスト社
    visits: []
"""


def _visits(text, qid):
    sites = SitesFile.model_validate(yaml.safe_load(text)).sites
    return next(s for s in sites if s.wikidata == qid).visits


def test_parse_issue_body():
    body = (
        "### Wikidata ID\n\nQ1\n\n### 参拝した年月\n\n_No response_\n\n"
        "### 一言メモ\n\n一行目\r\n二行目\n\n### 御朱印\n\nあり\n"
    )
    assert parse_issue_body(body) == {"wikidata": "Q1", "memo": "一行目\n二行目", "goshuin": "あり"}


def test_fills_memo_of_existing_visit_without_memo():
    result = add_memo(SITES, "Q1", Visit(date="2025-04", memo="新しいメモ", goshuin=True))
    visits = _visits(result, "Q1")
    assert [v.memo for v in visits] == ["新しいメモ", "一行目。\n二行目。"]
    assert result.startswith("# コメントは残る")  # ほかの部分は変えない


def test_appends_to_existing_memo():
    result = add_memo(SITES, "Q1", Visit(date="2026-03", memo="三行目。", goshuin=False))
    visit = _visits(result, "Q1")[1]
    assert visit.memo == "一行目。\n二行目。\n三行目。"
    assert visit.goshuin is False


def test_adds_new_visit_when_date_differs():
    result = add_memo(SITES, "Q1", Visit(date="2026-09", memo="再訪: 記号もOK # [x]", goshuin=True))
    visits = _visits(result, "Q1")
    assert [v.date for v in visits] == ["2025-04", "2026-03", "2026-09"]
    assert visits[-1].memo == "再訪: 記号もOK # [x]"
    assert _visits(result, "Q2") == []  # 次の寺社に紛れ込まない


def test_adds_visit_to_site_without_visits_and_without_date():
    result = add_memo(SITES, "Q2", Visit(memo="一行目\n\n三行目", goshuin=False))
    visits = _visits(result, "Q2")
    assert len(visits) == 1 and visits[0].date is None
    assert visits[0].memo == "一行目\n\n三行目"


def test_unknown_site():
    with pytest.raises(MemoError, match="Q9"):
        add_memo(SITES, "Q9", Visit(memo="x"))


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"wikidata": "伏見稲荷", "memo": "x"}, "Wikidata ID"),
        ({"wikidata": "Q1", "memo": ""}, "空"),
        ({"wikidata": "Q1", "memo": "x", "date": "2026-03-20"}, "年月"),
    ],
)
def test_invalid_issue(fields, message):
    with pytest.raises(MemoError, match=message):
        to_visit(fields)


def test_real_data_round_trip():
    # 実データにも追記でき、追記した参拝以外は変わらないことを確かめる
    from jisha_memo.add_memo import SITES_PATH

    text = SITES_PATH.read_text(encoding="utf-8")
    before = SitesFile.model_validate(yaml.safe_load(text)).sites
    after = SitesFile.model_validate(yaml.safe_load(add_memo(text, "Q56523409", Visit(date="2026-09", memo="追記")))).sites
    changed = [(b.wikidata, b.visits, a.visits) for b, a in zip(before, after) if b != a]
    assert len(changed) == 1 and changed[0][0] == "Q56523409"
    assert changed[0][2][1].memo.endswith("\n追記")
