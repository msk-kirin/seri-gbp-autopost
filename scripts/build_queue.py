"""GBP投稿集（xlsx）から投稿順のキュー posts/queue.csv を作る。

使い方:
  python scripts/build_queue.py ~/Desktop/一宮整骨院Seri_GBP投稿集_全520本_20261001.xlsx

並べ方:
  1. 投稿A 260本を先に、投稿B 260本を後ろに置く。
     同じ記事のAとBの間は260本（週2本で約2年半）空く。
  2. A・Bそれぞれの中では、カテゴリが偏らないように混ぜる。
     カテゴリごとに「全体のどの位置に来るか」を 本数に比例して均等に割り振り、
     その位置の順に並べる（本数の多い腱鞘炎・ばね指も、少ない起立性調節障害も全期間に散らばる）。
  3. カテゴリ内の順序は xlsx の並び（No順）を保つ。

予約（未公開）記事は並びには含めておき、投稿時に「記事公開日が今日以前か」を見て飛ばす。
"""
import csv, os, sys
import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "posts", "queue.csv")
FIELDS = ["id", "no", "category", "set", "headline", "url", "publish_date", "summary"]


def spread(rows):
    """カテゴリごとに均等な位置を割り振り、その位置の順に並べる。"""
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["category"], []).append(r)
    keyed = []
    for cat, items in by_cat.items():
        n = len(items)
        for i, r in enumerate(items):
            keyed.append(((i + 0.5) / n, cat, i, r))
    keyed.sort(key=lambda k: (k[0], k[1], k[2]))
    return [k[3] for k in keyed]


def main(path):
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.worksheets[0]
    rows = []
    for v in ws.iter_rows(min_row=2, values_only=True):
        if not v or not v[0]:
            continue
        # 列: No／カテゴリ／slug／セット／見出し／投稿本文／リンクURL／文字数／公開状況／記事公開日
        no, cat, slug, st, head, body, url, _n, _status, pdate = v[:10]
        rows.append({
            "id": f"{slug}-{st}",
            "no": int(no),
            "category": cat,
            "set": st,
            "headline": head,
            "url": url,
            # 公開済みの行は「—（公開済み）」と書かれているので空にする
            "publish_date": str(pdate)[:10] if pdate and str(pdate)[:1].isdigit() else "",
            "summary": body,
        })
    rows.sort(key=lambda r: r["no"])
    ordered = spread([r for r in rows if r["set"] == "A"]) + spread([r for r in rows if r["set"] == "B"])

    ids = [r["id"] for r in ordered]
    assert len(ids) == len(set(ids)), "id が重複している"
    for r in ordered:
        assert len(r["summary"]) <= 1500, f"{r['id']} が1500字を超えている"

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(ordered)
    print(f"{len(ordered)} 本を {OUT} に書き出した")


if __name__ == "__main__":
    main(sys.argv[1])
