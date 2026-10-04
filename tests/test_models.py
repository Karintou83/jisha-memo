import pytest
import yaml
from pydantic import ValidationError

from jisha_memo.models import SitesFile


def _load(text):
    return SitesFile.model_validate(yaml.safe_load(text)).sites


def test_month_precision_date():
    sites = _load('sites: [{wikidata: Q1, visits: [{date: "2026-09", memo: よかった}]}]')
    assert sites[0].visits[0].date == "2026-09"


@pytest.mark.parametrize("date", ["2026-09-20", "2026-13", "2026/09"])
def test_rejects_other_date_formats(date):
    # YAML では 2026-09-20 は日付型として読まれるため、文字列以外も拒否されることを確認する
    with pytest.raises(ValidationError):
        _load(f"sites: [{{wikidata: Q1, visits: [{{date: {date}}}]}}]")


def test_rejects_invalid_qid():
    with pytest.raises(ValidationError):
        _load("sites: [{wikidata: 清水寺}]")
