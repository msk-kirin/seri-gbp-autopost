"""初回だけ Mac で実行する。GBP の管理アカウントで許可し、リフレッシュトークンを取る。

使い方:
  1. Google Cloud で作った OAuth クライアント（種類: デスクトップアプリ）の
     クライアントID・シークレットを .env に書く（このファイルは git に入らない）
        GBP_CLIENT_ID=...
        GBP_CLIENT_SECRET=...
  2. python scripts/setup_auth.py
  3. ブラウザが開くので、GBP を管理している Google アカウントでログインして許可する
  4. .env にリフレッシュトークンが書き足され、アカウントIDとビジネスIDが表示される

取れた値は GitHub の Secrets に登録する（README 参照）。画面やチャットには貼らないこと。
"""
import http.server, os, secrets, sys, threading, urllib.parse, webbrowser
import requests
from gbp_api import GBP, SCOPE, TOKEN_URL, access_token

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = os.path.join(ROOT, ".env")
PORT = 8765
REDIRECT = f"http://localhost:{PORT}/"


def read_env():
    env = {}
    if os.path.exists(ENV):
        for line in open(ENV, encoding="utf-8"):
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                env[k] = v
    return env


def write_env(env):
    with open(ENV, "w", encoding="utf-8") as f:
        for k, v in env.items():
            f.write(f"{k}={v}\n")
    os.chmod(ENV, 0o600)


def get_code(client_id):
    state = secrets.token_urlsafe(16)
    got = {}

    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == state and "code" in q:
                got["code"] = q["code"][0]
                msg = "許可を受け取りました。このタブは閉じてターミナルに戻ってください。"
            else:
                got["error"] = q.get("error", ["不明"])[0]
                msg = f"許可を受け取れませんでした（{got['error']}）。"
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(msg.encode())

        def log_message(self, *a):
            pass

    srv = http.server.HTTPServer(("localhost", PORT), H)
    t = threading.Thread(target=srv.handle_request)
    t.start()
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",       # 毎回リフレッシュトークンを発行させる
        "state": state,
    })
    print("ブラウザで許可してください。開かない場合は次のURLを開く:\n" + url)
    webbrowser.open(url)
    t.join()
    srv.server_close()
    if "code" not in got:
        sys.exit(f"失敗: {got.get('error')}")
    return got["code"]


def main():
    env = read_env()
    cid, csec = env.get("GBP_CLIENT_ID"), env.get("GBP_CLIENT_SECRET")
    if not cid or not csec:
        sys.exit(".env に GBP_CLIENT_ID と GBP_CLIENT_SECRET を書いてから実行してください")

    code = get_code(cid)
    r = requests.post(TOKEN_URL, data={
        "code": code, "client_id": cid, "client_secret": csec,
        "redirect_uri": REDIRECT, "grant_type": "authorization_code",
    }, timeout=30)
    r.raise_for_status()
    tok = r.json()
    if "refresh_token" not in tok:
        sys.exit("リフレッシュトークンが返ってこなかった。Googleアカウントの「サードパーティ接続」からこのアプリを外して再実行する")
    env["GBP_REFRESH_TOKEN"] = tok["refresh_token"]
    write_env(env)
    print("リフレッシュトークンを .env に保存した")

    gbp = GBP(access_token(cid, csec, env["GBP_REFRESH_TOKEN"]))
    for a in gbp.accounts():
        print(f"\nアカウント: {a.get('accountName')}  ID={a['name'].split('/')[-1]}  種別={a.get('type')}")
        for loc in gbp.locations(a["name"]):
            print(f"  ビジネス: {loc.get('title')}  ID={loc['name'].split('/')[-1]}  {loc.get('websiteUri', '')}")
    print("\nみつむら接骨院の行は mitsumura-gbp-autopost に、一宮整骨院〜Seri〜の行は seri-gbp-autopost の GitHub Secrets に登録する")


if __name__ == "__main__":
    main()
