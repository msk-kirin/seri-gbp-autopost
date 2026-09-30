"""Google ビジネスプロフィール（GBP）API の最小限のクライアント。

使うAPI:
  - OAuth2 トークン更新      https://oauth2.googleapis.com/token
  - 投稿（localPosts）       https://mybusiness.googleapis.com/v4/...
  - アカウント一覧            https://mybusinessaccountmanagement.googleapis.com/v1/accounts
  - ビジネス（ロケーション）一覧 https://mybusinessbusinessinformation.googleapis.com/v1/...

どれも Google Cloud 側で API を有効化し、かつ GBP API の利用申請が承認されていないと
429 / 403（割り当て0）になる。
"""
import requests

SCOPE = "https://www.googleapis.com/auth/business.manage"
TOKEN_URL = "https://oauth2.googleapis.com/token"
V4 = "https://mybusiness.googleapis.com/v4"
ACCOUNTS = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
INFO = "https://mybusinessbusinessinformation.googleapis.com/v1"


class GBPError(Exception):
    pass


def access_token(client_id, client_secret, refresh_token):
    r = requests.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }, timeout=30)
    if r.status_code != 200:
        # invalid_grant = リフレッシュトークンの失効。setup_auth.py で取り直す
        raise GBPError(f"トークン更新に失敗 {r.status_code}: {r.text}")
    return r.json()["access_token"]


class GBP:
    def __init__(self, token):
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {token}"

    def _check(self, r):
        if r.status_code >= 300:
            raise GBPError(f"{r.request.method} {r.url} → {r.status_code}: {r.text}")
        return r.json()

    def accounts(self):
        return self._check(self.s.get(ACCOUNTS, timeout=30)).get("accounts", [])

    def locations(self, account_name):
        r = self.s.get(f"{INFO}/{account_name}/locations",
                       params={"readMask": "name,title,storefrontAddress,websiteUri", "pageSize": 100},
                       timeout=30)
        return self._check(r).get("locations", [])

    def create_post(self, account_id, location_id, summary, url, image_url=None):
        body = {
            "languageCode": "ja",
            "topicType": "STANDARD",          # 画面上の「最新情報」
            "summary": summary,
            "callToAction": {"actionType": "LEARN_MORE", "url": url},   # 「詳細」ボタン
        }
        if image_url:
            body["media"] = [{"mediaFormat": "PHOTO", "sourceUrl": image_url}]
        r = self.s.post(f"{V4}/accounts/{account_id}/locations/{location_id}/localPosts",
                        json=body, timeout=60)
        return self._check(r)
