"""キューの次の1本を GBP に投稿する（GitHub Actions から月・木 08:00 JST に呼ばれる）。

環境変数:
  GBP_CLIENT_ID / GBP_CLIENT_SECRET / GBP_REFRESH_TOKEN  … OAuth（setup_auth.py で取得）
  GBP_ACCOUNT_ID / GBP_LOCATION_ID                      … 数字のID（setup_auth.py で表示）
  IMAGE_BASE_URL   … images/ を公開しているURL（末尾スラッシュなし）。空なら画像なしで投稿
  POST_COUNT       … この実行で投稿する本数（既定 1）
  DRY_RUN=1        … 実際には投稿せず、次に出す内容だけ表示する

次の1本の選び方:
  queue.csv を上から見て、まだ投稿していない行のうち
    - 記事公開日が今日以前で
    - リンク先の記事が実際に表示できる（HTTP 200）
  最初の1本。予約記事で公開前のものは飛ばし、公開後の回で拾う。

画像:
  PHOTO_EVERY 本に1本は images/photos/ の院の写真を使い（使用回数の少ない順）、
  それ以外は images/cards/{id}.jpg（見出し入りの画像）を使う。写真が1枚もなければ常に見出し画像。
"""
import csv, json, os, sys, datetime
from zoneinfo import ZoneInfo
import requests
from gbp_api import GBP, GBPError, access_token

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(ROOT, "posts", "queue.csv")
STATE = os.path.join(ROOT, "state", "state.json")
LOG = os.path.join(ROOT, "state", "posted_log.csv")
PHOTOS = os.path.join(ROOT, "images", "photos")
JST = ZoneInfo("Asia/Tokyo")

PHOTO_EVERY = 3        # 3本に1本は院の写真
LOW_STOCK = 20         # 残りがこれを切ったら警告


def load_state():
    if os.path.exists(STATE):
        return json.load(open(STATE, encoding="utf-8"))
    return {"posted": [], "photo_uses": {}}


def save_state(st):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def article_is_live(url):
    try:
        r = requests.get(url, timeout=30, allow_redirects=True)
        return r.status_code == 200
    except requests.RequestException:
        return False


def pick(rows, st, today):
    done = set(st["posted"])
    for r in rows:
        if r["id"] in done:
            continue
        if r["publish_date"] and r["publish_date"] > today.isoformat():
            continue
        if not article_is_live(r["url"]):
            print(f"  飛ばす（記事が表示できない）: {r['id']} {r['url']}")
            continue
        return r
    return None


def choose_image(row, st):
    """(images/ からの相対パス, 種別) を返す。"""
    photos = sorted(p for p in os.listdir(PHOTOS)
                    if p.lower().endswith((".jpg", ".jpeg", ".png"))) if os.path.isdir(PHOTOS) else []
    n = len(st["posted"])
    if photos and n % PHOTO_EVERY == PHOTO_EVERY - 1:
        uses = st.setdefault("photo_uses", {})
        p = min(photos, key=lambda x: (uses.get(x, 0), x))
        return f"photos/{p}", "photo"
    return f"cards/{row['id']}.jpg", "card"


def append_log(row, image, result):
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["posted_at", "id", "category", "set", "image", "state", "post_name", "search_url"])
        w.writerow([datetime.datetime.now(JST).isoformat(timespec="seconds"), row["id"], row["category"],
                    row["set"], image, result.get("state", ""), result.get("name", ""),
                    result.get("searchUrl", "")])


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    count = int(os.environ.get("POST_COUNT") or 1)
    base = os.environ.get("IMAGE_BASE_URL", "").rstrip("/")
    today = datetime.datetime.now(JST).date()

    rows = list(csv.DictReader(open(QUEUE, encoding="utf-8")))
    st = load_state()

    gbp = None
    if not dry and not os.environ.get("GBP_REFRESH_TOKEN"):
        # API 承認前・Secrets 未登録のあいだは、失敗扱いにせず何もしない
        print("::warning::GBP の Secrets が未登録のため投稿しない（README の初回セットアップ参照）")
        return
    if not dry:
        token = access_token(os.environ["GBP_CLIENT_ID"], os.environ["GBP_CLIENT_SECRET"],
                             os.environ["GBP_REFRESH_TOKEN"])
        gbp = GBP(token)

    posted = 0
    for _ in range(count):
        row = pick(rows, st, today)
        if not row:
            print("投稿できる行が残っていない")
            break
        image, kind = choose_image(row, st)
        image_url = f"{base}/{image}" if base else None
        print(f"[{row['id']}] {row['category']} / {row['set']} / 画像={image}")
        print(f"  見出し: {row['headline']}")
        print(f"  リンク: {row['url']}")
        if dry:
            print("  （試し打ち：投稿しない）")
            print(row["summary"])
            st["posted"].append(row["id"])   # 本数分を先読みするためメモリ上だけ進める
            if kind == "photo":
                name = image.split("/", 1)[1]
                st["photo_uses"][name] = st["photo_uses"].get(name, 0) + 1
            continue

        try:
            res = gbp.create_post(os.environ["GBP_ACCOUNT_ID"], os.environ["GBP_LOCATION_ID"],
                                  row["summary"], row["url"], image_url)
        except GBPError as e:
            print(f"::error::投稿に失敗: {e}")
            sys.exit(1)

        print(f"  → {res.get('state')} {res.get('searchUrl', '')}")
        if res.get("state") == "REJECTED":
            print("::warning::GBP が投稿を却下した。内容を確認すること")
        st["posted"].append(row["id"])
        if kind == "photo":
            name = image.split("/", 1)[1]
            st["photo_uses"][name] = st["photo_uses"].get(name, 0) + 1
        save_state(st)
        append_log(row, image, res)
        posted += 1

    left = len([r for r in rows if r["id"] not in set(st["posted"])])
    print(f"投稿 {posted} 本／残り {left} 本")
    if left < LOW_STOCK:
        print(f"::warning::キューの残りが {left} 本。ストックの補充を検討すること")


if __name__ == "__main__":
    main()
