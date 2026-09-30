"""queue.csv の各投稿に付ける画像（1200×900）を images/cards/{id}.jpg に作る。

使い方（Mac で実行。ヒラギノ角ゴシックを使う）:
  python scripts/make_cards.py            # 全件
  python scripts/make_cards.py 3          # 先頭3件だけ（見た目の確認用）

GBP の推奨は 4:3・720×540 以上・JPG/PNG・10KB〜5MB。
見出しは「｜」の前を主題、後ろを副題として描く。
"""
import csv, os, sys, unicodedata
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(ROOT, "posts", "queue.csv")
OUT_DIR = os.path.join(ROOT, "images", "cards")

W, H = 1200, 900
BG = (255, 246, 249)       # 淡いピンク（サイトの #fff2f7 寄り）
ACCENT = (209, 48, 99)     # サイトのローズピンク（#d13063）
INK = (51, 41, 33)
SUB = (110, 96, 84)
WHITE = (255, 255, 255)


def font(weight, size):
    """ヒラギノ角ゴシックは濁点付きのファイル名なので、NFC/NFD の両方で探す。"""
    d = "/System/Library/Fonts"
    want = unicodedata.normalize("NFC", f"ヒラギノ角ゴシック W{weight}.ttc")
    for name in os.listdir(d):
        if unicodedata.normalize("NFC", name) == want:
            return ImageFont.truetype(os.path.join(d, name), size)
    raise FileNotFoundError(want)


# 行頭に来てはいけない文字（禁則）
NO_START = set("、。，．・：；？！ー）」』】〉》”’ぁぃぅぇぉっゃゅょァィゥェォッャュョ")


def chunks(text):
    """カタカナ語・英数字の連なりは1かたまりにして、途中で改行しないようにする。"""
    out = []
    for ch in text:
        kind = ("kata" if "\u30a0" <= ch <= "\u30ff" else
                "alnum" if ch.isascii() and ch.isalnum() else None)
        if out and kind and out[-1][1] == kind:
            out[-1][0] += ch
        else:
            out.append([ch, kind])
    return [c for c, _ in out]


def wrap(draw, text, fnt, max_w):
    lines, cur = [], ""
    for c in chunks(text):
        if draw.textlength(cur + c, font=fnt) <= max_w or not cur:
            cur += c
            continue
        if c[0] in NO_START:        # 禁則文字は前の行にぶら下げる
            cur += c
            continue
        lines.append(cur.rstrip())
        cur = c.lstrip()
    if cur:
        lines.append(cur)
    return lines


def fit_title(draw, text, max_w, max_lines):
    """主題が max_lines 行に収まる最大の文字サイズを選ぶ。"""
    for size in range(84, 47, -4):
        f = font(7, size)
        lines = wrap(draw, text, f, max_w)
        if len(lines) <= max_lines:
            return f, lines, size
    f = font(7, 48)
    return f, wrap(draw, text, f, max_w)[:max_lines], 48


def card(row, path):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    pad = 90

    # 上の帯：カテゴリ
    d.rectangle([0, 0, W, 14], fill=ACCENT)
    cat = row["category"].replace("＋", "・")
    f_cat = font(6, 34)
    tw = d.textlength(cat, font=f_cat)
    d.rounded_rectangle([pad, 80, pad + tw + 56, 80 + 64], radius=32, fill=ACCENT)
    d.text((pad + 28, 80 + 32), cat, font=f_cat, fill=WHITE, anchor="lm")

    # 見出し（主題＋副題）
    head = row["headline"]
    main, sub = (head.split("｜", 1) + [""])[:2]
    f_main, lines, size = fit_title(d, main.strip(), W - pad * 2, 3)
    lh = int(size * 1.4)
    f_sub = font(4, 38)
    sub_lines = wrap(d, sub.strip(), f_sub, W - pad * 2)[:2] if sub.strip() else []
    block = lh * len(lines) + (18 + 54 * len(sub_lines) if sub_lines else 0)
    # カテゴリの下（y=144）から下の帯（H-170）までの間で上下中央に置く
    y = 144 + ((H - 170 - 144) - block) // 2
    for ln in lines:
        d.text((pad, y), ln, font=f_main, fill=INK)
        y += lh
    if sub_lines:
        y += 18
        for ln in sub_lines:
            d.text((pad, y), ln, font=f_sub, fill=SUB)
            y += 54

    # 下の帯：院名と地域
    band = 170
    d.rectangle([0, H - band, W, H], fill=INK)
    d.text((pad, H - band + 58), "一宮整骨院〜Seri〜", font=font(7, 52), fill=WHITE, anchor="lm")
    d.text((pad, H - band + 118), "愛知県一宮市・苅安賀駅　症状別コラム", font=font(4, 30),
           fill=(230, 220, 205), anchor="lm")
    d.rectangle([W - pad - 150, H - band + 40, W - pad, H - band + 46], fill=ACCENT)
    d.text((W - pad, H - band + 100), "記事で詳しく →", font=font(6, 30), fill=ACCENT, anchor="rm")

    img.save(path, "JPEG", quality=88, optimize=True)


def main(limit=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = list(csv.DictReader(open(QUEUE, encoding="utf-8")))
    if limit:
        rows = rows[:limit]
    for r in rows:
        card(r, os.path.join(OUT_DIR, f"{r['id']}.jpg"))
    print(f"{len(rows)} 枚を {OUT_DIR} に作った")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
