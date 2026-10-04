from jisha_memo.search import parse_results


def test_parse_results():
    data = {
        "search": [
            {"id": "Q1", "label": "テスト寺", "description": "京都の寺院"},
            {"id": "Q2", "label": "テスト寺駅"},
        ]
    }
    assert parse_results(data) == [("Q1", "テスト寺", "京都の寺院"), ("Q2", "テスト寺駅", "")]
    assert parse_results({}) == []
