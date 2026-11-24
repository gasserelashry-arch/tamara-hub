#!/usr/bin/env python3
"""Tamara Hub live sync server — public/cloud friendly."""
import http.server
import json
import os
import re
import socketserver
import time
import urllib.error
import urllib.request

PORT = int(os.environ.get("PORT", "8080"))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
INDEX_FILE = os.path.join(BASE_DIR, "index.html")
STORE_FILE = os.path.join(DATA_DIR, "hub_store.json")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "").strip()
REVISION = str(int(time.time() * 1000))
KB_ASHRY_PATH = os.environ.get(
    "KB_ASHRY_PATH",
    r"C:\Users\gasser.elashry\Downloads\KB Ashry.docx",
).strip()

# Optional GitHub persistence so free-tier hosts keep data across restarts
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
GITHUB_REPO = os.environ.get("GITHUB_REPO", "").strip()  # owner/repo
GITHUB_PATH = os.environ.get("GITHUB_PATH", "hub_store.json").strip()


def _require_admin_pass():
    if not ADMIN_PASS:
        raise RuntimeError(
            "ADMIN_PASS environment variable is required. "
            "Set a strong password before starting the server."
        )


def read_embedded_data():
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        html = f.read()
    db_m = re.search(
        r'<script id="tamara-db-data" type="application/json">\s*([\s\S]*?)\s*</script>',
        html,
    )
    mac_m = re.search(
        r'<script id="tamara-macros-data" type="application/json">\s*([\s\S]*?)\s*</script>',
        html,
    )
    cms_data = json.loads(db_m.group(1)) if db_m else {}
    macros_data = json.loads(mac_m.group(1)) if mac_m else []
    return html, cms_data, macros_data


def load_store():
    """Prefer hub_store.json (local or GitHub), else embedded index.html data."""
    global REVISION
    if os.path.isfile(STORE_FILE):
        try:
            with open(STORE_FILE, "r", encoding="utf-8") as f:
                store = json.load(f)
            if store.get("cmsData") is not None:
                REVISION = str(store.get("revision") or REVISION)
                return store["cmsData"], store.get("masterMacros") or []
        except (OSError, json.JSONDecodeError, TypeError):
            pass

    remote = github_pull_store()
    if remote:
        cms = remote.get("cmsData")
        macros = remote.get("masterMacros") or []
        if cms is not None:
            REVISION = str(remote.get("revision") or REVISION)
            save_store_local(cms, macros, REVISION)
            return cms, macros

    _, cms_data, macros_data = read_embedded_data()
    return cms_data, macros_data


def save_store_local(cms_data, macros_data, revision):
    os.makedirs(DATA_DIR, exist_ok=True)
    store = {
        "revision": str(revision),
        "cmsData": cms_data,
        "masterMacros": macros_data,
    }
    tmp = STORE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STORE_FILE)


def write_embedded_data(cms_data, macros_data):
    global REVISION
    with open(INDEX_FILE, "r", encoding="utf-8") as f:
        html = f.read()
    db_str = json.dumps(cms_data, ensure_ascii=False, indent=2)
    mac_str = json.dumps(macros_data, ensure_ascii=False)
    html = re.sub(
        r'(<script id="tamara-db-data" type="application/json">\s*)[\s\S]*?(\s*</script>)',
        lambda m: m.group(1) + db_str + m.group(2),
        html,
        count=1,
    )
    html = re.sub(
        r'(<script id="tamara-macros-data" type="application/json">\s*)[\s\S]*?(\s*</script>)',
        lambda m: m.group(1) + mac_str + m.group(2),
        html,
        count=1,
    )
    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    REVISION = str(int(time.time() * 1000))
    save_store_local(cms_data, macros_data, REVISION)
    github_push_store(cms_data, macros_data, REVISION)
    return REVISION


def github_api_request(method, url, body=None):
    if not (GITHUB_TOKEN and GITHUB_REPO):
        return None
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {GITHUB_TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "tamara-hub-server",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"[GITHUB] {method} {url} -> HTTP {e.code}: {err_body[:300]}")
        return None
    except Exception as e:
        print(f"[GITHUB] {method} {url} failed: {e}")
        return None


def github_pull_store():
    if not (GITHUB_TOKEN and GITHUB_REPO):
        return None
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}"
    meta = github_api_request("GET", url)
    if not meta or "content" not in meta:
        return None
    import base64

    try:
        raw = base64.b64decode(meta["content"]).decode("utf-8")
        return json.loads(raw)
    except Exception as e:
        print(f"[GITHUB] Failed to decode store: {e}")
        return None


def github_push_store(cms_data, macros_data, revision):
    if not (GITHUB_TOKEN and GITHUB_REPO):
        return
    import base64

    store = {
        "revision": str(revision),
        "cmsData": cms_data,
        "masterMacros": macros_data,
    }
    content_b64 = base64.b64encode(
        json.dumps(store, ensure_ascii=False, indent=2).encode("utf-8")
    ).decode("ascii")
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_PATH}"
    meta = github_api_request("GET", url)
    payload = {
        "message": f"hub live update rev {revision}",
        "content": content_b64,
        "branch": os.environ.get("GITHUB_BRANCH", "main"),
    }
    if meta and meta.get("sha"):
        payload["sha"] = meta["sha"]
    result = github_api_request("PUT", url, payload)
    if result:
        print(f"[GITHUB] Persisted hub_store.json revision {revision}")


def json_response(handler, code, obj):
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json_body(handler):
    length = int(handler.headers.get("Content-Length", 0))
    raw = handler.rfile.read(length).decode("utf-8") if length else "{}"
    return json.loads(raw)


class TamaraHubHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def log_message(self, format, *args):
        print("[%s] %s" % (self.log_date_time_string(), format % args))

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        super().end_headers()

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/health":
            json_response(self, 200, {"ok": True, "revision": REVISION})
            return
        if path == "/api/version":
            json_response(self, 200, {"ok": True, "revision": REVISION})
            return
        if path == "/api/hub-data":
            cms_data, macros_data = load_store()
            json_response(
                self,
                200,
                {
                    "ok": True,
                    "revision": REVISION,
                    "cmsData": cms_data,
                    "masterMacros": macros_data,
                },
            )
            return
        if path == "/api/kb-ashry":
            try:
                from _kb_ashry_backend import read_kb_ashry
                from pathlib import Path

                data = read_kb_ashry(Path(KB_ASHRY_PATH))
                # Query: ?section=sec_1 or ?mode=index (lighter payload)
                qs = ""
                if "?" in self.path:
                    qs = self.path.split("?", 1)[1]
                params = dict(p.split("=", 1) for p in qs.split("&") if "=" in p)
                mode = params.get("mode", "full")
                section_id = params.get("section", "")
                if not data.get("ok"):
                    json_response(self, 404, data)
                    return
                if mode == "index":
                    json_response(
                        self,
                        200,
                        {
                            "ok": True,
                            "path": data["path"],
                            "backend": data["backend"],
                            "modified_at": data["modified_at"],
                            "paras_count": data["paras_count"],
                            "sections_count": data["sections_count"],
                            "section_index": data["section_index"],
                            "loaded_at": data["loaded_at"],
                        },
                    )
                    return
                if section_id:
                    match = next((s for s in data["sections"] if s["id"] == section_id), None)
                    if not match:
                        json_response(self, 404, {"ok": False, "error": "Section not found", "section": section_id})
                        return
                    json_response(
                        self,
                        200,
                        {
                            "ok": True,
                            "path": data["path"],
                            "backend": data["backend"],
                            "modified_at": data["modified_at"],
                            "section": match,
                            "section_index": data["section_index"],
                            "loaded_at": data["loaded_at"],
                        },
                    )
                    return
                json_response(self, 200, data)
            except Exception as e:
                json_response(self, 500, {"ok": False, "error": str(e)})
            return
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/api/auth":
            try:
                body = read_json_body(self)
                if body.get("password") == ADMIN_PASS:
                    json_response(self, 200, {"ok": True})
                else:
                    json_response(self, 403, {"ok": False, "error": "Unauthorized"})
            except Exception as e:
                json_response(self, 500, {"ok": False, "error": str(e)})
            return

        if path == "/api/save-hub":
            try:
                body = read_json_body(self)
                if body.get("password") != ADMIN_PASS:
                    json_response(self, 403, {"ok": False, "error": "Unauthorized"})
                    return
                if "cmsData" not in body:
                    json_response(self, 400, {"ok": False, "error": "cmsData required"})
                    return
                rev = write_embedded_data(body["cmsData"], body.get("masterMacros") or [])
                print(f"[LIVE SYNC] Saved update ({body.get('reason', 'Update')}) -> Revision {rev}")
                json_response(self, 200, {"ok": True, "revision": rev})
            except Exception as e:
                json_response(self, 500, {"ok": False, "error": str(e)})
            return

        self.send_response(404)
        self.end_headers()


class ReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    _require_admin_pass()
    os.makedirs(DATA_DIR, exist_ok=True)
    cms0, mac0 = load_store()
    save_store_local(cms0, mac0, REVISION)
    print(f"Tamara Hub Server LIVE on http://0.0.0.0:{PORT}")
    print(f"Data dir: {DATA_DIR}")
    if GITHUB_TOKEN and GITHUB_REPO:
        print(f"GitHub persistence: {GITHUB_REPO}:{GITHUB_PATH}")
    with ReusableTCPServer(("0.0.0.0", PORT), TamaraHubHandler) as httpd:
        httpd.serve_forever()
