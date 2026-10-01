# seri-gbp-autopost

一宮整骨院〜Seri〜 の Google ビジネスプロフィール（GBP）に、ブログ記事（ichinomiyaseitaiin.com）と連動した投稿を
**毎週 月曜・木曜の朝8時** に1本ずつ自動で出す。GitHub Actions で動くので Mac の電源は不要。

仕組みはみつむら接骨院の `mitsumura-gbp-autopost` と同じ。**GBP の管理アカウントも同じ**なので、
Google Cloud のプロジェクト・API 承認・OAuth クライアント・リフレッシュトークンはみつむらのものをそのまま使う。
違うのはビジネスID（`GBP_LOCATION_ID`）だけ。

## 何をするか

| ワークフロー | 動くタイミング | 内容 |
|---|---|---|
| `post.yml` | 月・木 08:00 JST | キューの次の1本を投稿し、投稿済みとして記録する |

- ストック: `posts/queue.csv`（520本 = 260記事 × 投稿A/B）。週2本で約5年分
- 並び順: 投稿A 260本 → 投稿B 260本。同じ記事のAとBは約2年半空く。カテゴリは偏らないよう全期間に散らしてある
- **公開前の予約記事は飛ばす。** 作成時点で290本が予約（記事公開日 2026-10-01〜2027-02-22）。公開日が来ていない、またはリンク先が表示できない（404など）行は後回しにする
- 画像: 3本に1本は `images/photos/` の院の写真（使用回数の少ない順）、それ以外は `images/cards/` の見出し入り画像
- 「詳細」ボタンに記事URLを付ける。種類は「最新情報」

## ファイル

```
posts/queue.csv          投稿の順番と本文（build_queue.py で xlsx から作る）
images/cards/{id}.jpg    見出し入りの画像（make_cards.py で作る。Mac のヒラギノを使う）
images/photos/           院の写真を入れる場所（jpg/png、横長 4:3 推奨、1枚 5MB 以下）
state/state.json         投稿済みIDと写真の使用回数。二重投稿を防ぐ
state/posted_log.csv     いつ何を投稿したか
scripts/post.py          投稿本体
scripts/setup_auth.py    通常は使わない（認証はみつむら側で済ませる）
```

元データ: `~/Desktop/一宮整骨院Seri_GBP投稿集_全520本_20261001.xlsx`

## 初回セットアップ

### 1. みつむら側の手順1〜3を済ませる

GBP API の申請・承認、API の有効化、OAuth クライアントの作成、トークン取得は
`~/dev/mitsumura-gbp-autopost/README.md` の手順1〜3のとおり。**Seri のために別途申請する必要はない。**

### 2. Seri のビジネスIDを控える

みつむらの手順3（`setup_auth.py`）を実行すると、管理アカウントが管理するビジネスが**すべて**一覧に出る。
そのうち「一宮整骨院〜Seri〜」の行のアカウントIDとビジネスIDを控える（Seri 側で setup_auth.py を実行し直す必要はない。
実行し直すとトークンが新しく発行され、みつむら側の Secret と食い違うので注意）。

### 3. GitHub に登録する

このフォルダを GitHub の新しいリポジトリに置き、Settings → Secrets and variables → Actions:

| 種類 | 名前 | 中身 |
|---|---|---|
| Secret | `GBP_CLIENT_ID` | みつむらと同じ値 |
| Secret | `GBP_CLIENT_SECRET` | みつむらと同じ値 |
| Secret | `GBP_REFRESH_TOKEN` | みつむらと同じ値 |
| Secret | `GBP_ACCOUNT_ID` | 手順2で表示されたアカウントID |
| Secret | `GBP_LOCATION_ID` | 手順2で表示されたビジネスID（**Seri の行**） |

画像は Google が URL から取りに行くので、誰でも開ける URL が必要。画像の URL（`IMAGE_BASE_URL`）は post.yml に既定値として書いてあるので登録不要。**このリポジトリは公開にして、画像をここから配信する**
（投稿文・画像・プログラムは公開される。API の鍵は Secrets に入れるので公開されない。`.env` は git に入らない）。

### 4. テスト投稿

Actions → Seri GBP投稿 → Run workflow

1. `dry_run` にチェックを入れたまま実行 → ログで次に出る投稿を確認
2. `dry_run` を外して1本だけ実行 → GBP とGoogleマップで表示を確認

問題なければ、以後は月・木の朝8時に自動で出る。

## 運用

- **失敗したとき**: GitHub から失敗通知メールが届く。ログの `投稿に失敗` の行を見る
  - `invalid_grant` → トークン切れ。みつむらの手順3をやり直し、両方のリポジトリの `GBP_REFRESH_TOKEN` を更新
  - `429` / `PERMISSION_DENIED` → API 承認前か、API の有効化漏れ
- **院の写真を足す**: `images/photos/` に入れてコミットするだけ
- **ストックを足す**: xlsx を更新して `build_queue.py` → `make_cards.py` を実行してコミット。投稿済みの行は id で判定するので二重には出ない
- **一時停止**: Actions → GBP投稿 → 右上「…」→ Disable workflow

## 投稿内容の約束（生成時に検証済み）

保険への言及なし／体験談・患者エピソードなし／「完治」「必ず治る」等の断定なし／
危険なサインのときは受診するよう全投稿に明記／本文に電話番号を書かない。
詳細は xlsx の「使い方・設計方針」シート。
