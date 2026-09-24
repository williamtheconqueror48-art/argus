#!/usr/bin/env python3
"""Push the ARGUS repo directory to GitHub via the Git Data API.

Adapted from ~/workspace/skills/github/bin/gh-push.py with ARGUS-specific
repo description and seed text. Plain `git push` to github.com does not work
in this workspace.

Usage:
    push_argus.py [--message MSG] [--private]

Auth: uses the stored custom.github connector via authd surrogates.
Only talks to api.github.com.
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
import urllib.request
import urllib.error

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (
    add_surrogate_to_request,
    read_json_response,
    DynamicCredentialError,
)

CRED = "custom.github"
HOSTS = ["api.github.com"]
API = "https://api.github.com"
REPO = "argus"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DESCRIPTION = ("ARGUS — watching the watchers. An open, sourced database of the "
               "commercial spyware industry: vendors, products, corporate structures, "
               "legal actions, and screening-list hits. Public data only.")
SEED_README = ("# ARGUS — watching the watchers\n\nAn open, sourced database of the "
               "commercial spyware industry.\n")

SKIP_DIRS = {"node_modules", ".next", ".git", "__pycache__", ".vercel"}
SKIP_FILES = {".DS_Store"}


def api_request(method: str, path: str, payload: dict | None = None):
    import json as _json
    url = API + path
    req = urllib.request.Request(url, method=method)
    if payload is not None:
        req = urllib.request.Request(url, data=_json.dumps(payload).encode(), method=method)
        req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "argus-push/1.0")
    add_surrogate_to_request(req, CRED, allowed_hosts=HOSTS)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if resp.status == 204:
                return {}
            return read_json_response(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:500]
        raise DynamicCredentialError(f"GitHub {method} {path} -> {e.code}: {body}")


def get_user() -> str:
    return api_request("GET", "/user")["login"]


def ensure_repo(owner: str, private: bool) -> None:
    try:
        api_request("GET", f"/repos/{owner}/{REPO}")
        print(f"repo exists: {owner}/{REPO}")
    except DynamicCredentialError as e:
        if "404" not in str(e):
            raise
        api_request("POST", "/user/repos", {
            "name": REPO, "private": private,
            "description": DESCRIPTION, "auto_init": False,
        })
        print(f"repo created: {owner}/{REPO} (private={private})")


def collect_files(root: str):
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn in SKIP_FILES:
                continue
            full = os.path.join(dirpath, fn)
            out.append((os.path.relpath(full, root), open(full, "rb").read()))
    out.sort()
    return out


def push(private: bool, message: str) -> None:
    owner = get_user()
    ensure_repo(owner, private)

    files = collect_files(ROOT)
    print(f"uploading {len(files)} files...")

    parents: list[str] = []
    try:
        ref = api_request("GET", f"/repos/{owner}/{REPO}/git/ref/heads/main")
        parents = [ref["object"]["sha"]]
    except DynamicCredentialError as e:
        if "404" not in str(e) and "409" not in str(e):
            raise
        api_request("PUT", f"/repos/{owner}/{REPO}/contents/README.md", {
            "message": "seed: initialize main branch",
            "content": base64.b64encode(SEED_README.encode()).decode(),
            "branch": "main",
        })
        ref = api_request("GET", f"/repos/{owner}/{REPO}/git/ref/heads/main")
        parents = [ref["object"]["sha"]]

    # Chunk blobs: 14 files, tiny — single batch is fine.
    tree_entries = []
    for rel, content in files:
        blob = api_request("POST", f"/repos/{owner}/{REPO}/git/blobs", {
            "content": base64.b64encode(content).decode(), "encoding": "base64",
        })
        tree_entries.append({"path": rel, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    tree = api_request("POST", f"/repos/{owner}/{REPO}/git/trees", {"tree": tree_entries})
    commit = api_request("POST", f"/repos/{owner}/{REPO}/git/commits",
                         {"message": message, "tree": tree["sha"], "parents": parents})
    # NOTE: plural /git/refs/heads/main — singular /git/ref/... 404s on PATCH.
    api_request("PATCH", f"/repos/{owner}/{REPO}/git/refs/heads/main", {"sha": commit["sha"]})
    print(f"pushed {commit['sha'][:7]} to {owner}/{REPO}@main https://github.com/{owner}/{REPO}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--message", default="ARGUS v0: vendor seed, screening-list pull, static site")
    ap.add_argument("--private", action="store_true")
    args = ap.parse_args()
    push(args.private, args.message)


if __name__ == "__main__":
    main()
