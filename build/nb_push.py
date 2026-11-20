# -*- coding: utf-8 -*-
"""推送新大屏B（优爆品 & 市场热卖品）到 GitHub Pages。

用法：python build\\nb_push.py [--dry]
清单：index.html / board.json / README.md / build/nb_*.py / build/nb_history.json
只推 blob sha 有变化的文件。
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

OWNER = "PengyuanBruce"
REPO = "youpin-customer-board"
BRANCH = "main"
API = "https://api.github.com"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["index.html", "board.json", "README.md",
         "build/nb_config.py", "build/nb_build.py", "build/nb_render.py",
         "build/nb_push.py", "build/nb_history.json"]

TOKEN = None


def token():
    t = os.environ.get("GITHUB_TOKEN")
    if not t:
        raise SystemExit("缺少 GITHUB_TOKEN 环境变量")
    return t.strip()


def call(method, path, payload=None):
    headers = {
        "Authorization": f"token {TOKEN}",
        "User-Agent": "accio-dashboard",
        "Accept": "application/vnd.github+json",
    }
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            body = r.read()
            return json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"{method} {path} -> {e.code} {detail}") from None


def blob_sha(path):
    data = open(path, "rb").read()
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest(), data


def remote_tree():
    try:
        ref = call("GET", f"/repos/{OWNER}/{REPO}/git/ref/heads/{BRANCH}")
        sha = ref["object"]["sha"]
        t = call("GET", f"/repos/{OWNER}/{REPO}/git/trees/{sha}?recursive=1")
        return {n["path"]: n["sha"] for n in t.get("tree", []) if n["type"] == "blob"}
    except (RuntimeError, KeyError) as e:
        print("读取远端树失败（按空处理）：", e)
        return {}


def main():
    global TOKEN
    TOKEN = token()
    dry = "--dry" in sys.argv

    me = call("GET", "/user")
    print("账号:", me.get("login"), "| 仓库:", f"{OWNER}/{REPO}")

    remote = remote_tree()
    changed = []
    for f in FILES:
        p = os.path.join(ROOT, f.replace("/", os.sep))
        if not os.path.exists(p):
            print("跳过（本地缺）", f)
            continue
        sha, data = blob_sha(p)
        if remote.get(f) == sha:
            continue
        changed.append((f, data))

    if not changed:
        print("没有变化，跳过推送")
        return

    print(f"待上传 {len(changed)} 个文件：" + "、".join(p for p, _ in changed))
    if dry:
        return

    for path, data in changed:
        payload = {
            "message": f"update {path}",
            "content": base64.b64encode(data).decode("ascii"),
            "branch": BRANCH,
        }
        if path in remote:
            payload["sha"] = remote[path]
        for attempt in range(3):
            try:
                call("PUT", f"/repos/{OWNER}/{REPO}/contents/{path}", payload)
                print("  ok", path, len(data), "B")
                break
            except RuntimeError as e:
                if attempt == 2:
                    raise
                print("  重试", path, e)
                time.sleep(1.5)

    print("完成。页面：https://" + OWNER.lower() + ".github.io/" + REPO + "/")


if __name__ == "__main__":
    main()
