# 寺社メモ

参拝した寺社の記録です。

寺社の情報は [Wikidata](https://www.wikidata.org/) と [Wikipedia](https://ja.wikipedia.org/)、写真は [Wikimedia Commons](https://commons.wikimedia.org/)、
地図は [OpenStreetMap](https://www.openstreetmap.org/) を利用しています。

## ビルド

```sh
pip install -e ".[dev]"
python -m jisha_memo.search 寺社名   # Wikidata の項目 ID を探す
python -m jisha_memo.wikidata
python -m jisha_memo.build
```
