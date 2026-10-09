"""Issue フォーム（.github/ISSUE_TEMPLATE/memo.yml）の本文から、一言メモを data/sites.yaml に追記する。

- 同じ年月の参拝があればそこにメモを書き足し、なければ新しい参拝として追加する
- data/sites.yaml のコメントや書式を崩さないよう、YAML を読み書きし直さずに該当箇所だけ文字列として編集する

使い方（GitHub Actions から呼ばれる）:
    python -m jisha_memo.add_memo issue_body.md
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import SitesFile, Visit

ROOT = Path(__file__).resolve().parents[2]
SITES_PATH = ROOT / "data" / "sites.yaml"

# Issue フォームの見出し（label）→ 項目名
FIELDS = {
    "Wikidata ID": "wikidata",
    "参拝した年月": "date",
    "一言メモ": "memo",
    "御朱印": "goshuin",
}
NO_RESPONSE = "_No response_"  # 未入力の項目に GitHub が入れる文字列

VISIT_INDENT = " " * 6
KEY_INDENT = " " * 8
TEXT_INDENT = " " * 10


class MemoError(ValueError):
    """Issue の内容が不正なときのエラー。メッセージはそのまま Issue に返信する。"""


def parse_issue_body(body: str) -> dict[str, str]:
    """Issue フォームの本文（### 見出し + 値 の並び）を項目名 → 値 にする。"""
    result: dict[str, str] = {}
    for section in re.split(r"^### ", body.replace("\r\n", "\n"), flags=re.MULTILINE)[1:]:
        heading, _, value = section.partition("\n")
        key = FIELDS.get(heading.strip())
        value = value.strip()
        if key and value and value != NO_RESPONSE:
            result[key] = value
    return result


def to_visit(fields: dict[str, str]) -> tuple[str, Visit]:
    qid = fields.get("wikidata", "").strip()
    if not re.fullmatch(r"Q\d+", qid):
        raise MemoError(f"Wikidata ID「{qid}」の形式が正しくありません（例: Q714828）。")
    memo = fields.get("memo", "").strip()
    if not memo:
        raise MemoError("一言メモが空です。")
    try:
        visit = Visit(date=fields.get("date") or None, memo=memo, goshuin=fields.get("goshuin") == "あり")
    except ValidationError:
        raise MemoError(f"年月「{fields.get('date')}」は YYYY-MM か YYYY の形で書いてください（例: 2026-03）。")
    return qid, visit


def _site_block(lines: list[str], qid: str) -> tuple[int, int]:
    start = next((i for i, line in enumerate(lines) if re.match(rf"  - wikidata: {qid}(\s|$)", line)), None)
    if start is None:
        raise MemoError(f"{qid} は data/sites.yaml に登録されていません。")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("  - ")), len(lines))
    return start, end


def _memo_lines(memo: str) -> list[str]:
    # 改行や記号を含んでも壊れないよう、常にリテラルブロック（|-）で書く
    return [f"{KEY_INDENT}memo: |-"] + [f"{TEXT_INDENT}{line}" if line else "" for line in memo.split("\n")]


def _visit_lines(visit: Visit) -> list[str]:
    if visit.date:
        lines = [f'{VISIT_INDENT}- date: "{visit.date}"'] + _memo_lines(visit.memo)
    else:
        lines = [f"{VISIT_INDENT}- memo: |-"] + _memo_lines(visit.memo)[1:]
    return lines + [_goshuin_line(visit.goshuin)]


def _key_span(lines: list[str], start: int, end: int, key: str) -> tuple[int, int] | None:
    """参拝 1 件の範囲 [start, end) から、キー（memo など）の行範囲を探す。複数行の値も含める。"""
    for i in range(start, end):
        if lines[i].lstrip(" -").startswith(f"{key}:"):
            indent = len(lines[i]) - len(lines[i].lstrip(" -"))
            j = i + 1
            while j < end and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip()) > indent):
                j += 1
            return i, j
    return None


def _visit_span(lines: list[str], qid: str, date: str) -> tuple[int, int] | None:
    """指定の年月の参拝 1 件の行範囲を返す。"""
    start, end = _site_block(lines, qid)
    starts = [i for i in range(start, end) if lines[i].startswith(f"{VISIT_INDENT}- ")]
    for n, i in enumerate(starts):
        if re.fullmatch(rf'{VISIT_INDENT}- date: "?{re.escape(date)}"?\s*', lines[i]):
            v_end = starts[n + 1] if n + 1 < len(starts) else end
            while v_end > i + 1 and not lines[v_end - 1].strip():
                v_end -= 1
            return i, v_end
    return None


def _goshuin_line(goshuin: bool) -> str:
    return f"{KEY_INDENT}goshuin: {'true' if goshuin else 'false'}"


def add_memo(text: str, qid: str, visit: Visit) -> str:
    """sites.yaml の文字列にメモを追記した結果を返す。"""
    lines = text.split("\n")
    span = _visit_span(lines, qid, visit.date) if visit.date else None

    if span is None:
        # 新しい参拝として、寺社のブロックの末尾に追加する
        start, end = _site_block(lines, qid)
        while end > start + 1 and not lines[end - 1].strip():
            end -= 1
        for i in range(start, end):
            if lines[i] == "    visits: []":
                lines[i] = "    visits:"
        lines[end:end] = _visit_lines(visit)
    else:
        # 同じ年月の参拝があれば、既存のメモの後ろに書き足す
        memo_span = _key_span(lines, span[0], span[1], "memo")
        if memo_span:
            old = yaml.safe_load("\n".join(line[len(KEY_INDENT):] for line in lines[memo_span[0]:memo_span[1]]))
            merged = "\n".join(part for part in (old.get("memo") or "", visit.memo) if part)
            lines[memo_span[0]:memo_span[1]] = _memo_lines(merged)
        else:
            lines[span[0] + 1:span[0] + 1] = _memo_lines(visit.memo)

        span = _visit_span(lines, qid, visit.date)  # 行数が変わったので探し直す
        goshuin_span = _key_span(lines, span[0], span[1], "goshuin")
        if goshuin_span:
            lines[goshuin_span[0]] = _goshuin_line(visit.goshuin)
        else:
            lines.insert(span[1], _goshuin_line(visit.goshuin))

    result = "\n".join(lines)
    SitesFile.model_validate(yaml.safe_load(result))  # 書き換え後も正しい YAML・データであることを確かめる
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("issue_body", type=Path, help="Issue 本文を保存したファイル")
    args = parser.parse_args()

    try:
        qid, visit = to_visit(parse_issue_body(args.issue_body.read_text(encoding="utf-8")))
        SITES_PATH.write_text(add_memo(SITES_PATH.read_text(encoding="utf-8"), qid, visit), encoding="utf-8")
    except MemoError as e:
        sys.exit(str(e))  # メッセージを標準エラーに出して終了コード 1 で終わる
    print(f"{qid} に一言メモを追加しました")


if __name__ == "__main__":
    main()
