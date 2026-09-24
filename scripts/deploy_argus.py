#!/usr/bin/env python3
"""Create the ARGUS Vercel project and deploy to production.

Adapted from ~/workspace/skills/vercel/bin/vercel-deploy.py for a pure
static site (no framework preset — Vercel auto-detects static).

Preferred path: git-connected project (repo is source of truth, Vercel
deploys from main). Falls back to direct file upload if the Vercel GitHub
App is not installed for the repo.

Usage:
    deploy_argus.py [--project-name argus] [--repo OWNER/argus]

Auth: uses the stored custom.vercel connector via authd surrogates.
Only talks to api.vercel.com.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.request
import urllib.error

sys.path.insert(0, "/opt/hatch/skills/skill-creator/bin")
from dynamic_credentials import (
    add_surrogate_to_request,
    read_json_response,
    DynamicCredentialError,
)

CRED = "custom.vercel"
HOSTS = ["api.vercel.com"]
API = "https://api.vercel.com"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SKIP_DIRS = {"node_modules", ".next", ".git", "__pycache__", ".vercel"}
SKIP_FILES = {".DS_Store"}


def api(method: str, path: str, payload: dict | None = None) -> dict:
    req = urllib.request.Request(API + path, method=method)
    if payload is not None:
        req = urllib.request.Request(API + path, data=json.dumps(payload).encode(), method=method)
        req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "argus-deploy/1.0")
    add_surrogate_to_request(req, CRED, allowed_hosts=HOSTS)
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            if resp.status == 204:
                return {}
            return read_json_response(resp)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:800]
        raise DynamicCredentialError(f"Vercel {method} {path} -> {e.code}: {body}")


def check_auth() -> None:
    user = api("GET", "/v2/user").get("user", {})
    print(f"authenticated as Vercel user: {user.get('username') or user.get('id')}")


def get_project(name: str) -> dict | None:
    try:
        return api("GET", f"/v10/projects/{name}")
    except DynamicCredentialError as e:
        if "404" in str(e):
            return None
        raise


def create_project(name: str, repo: str) -> tuple[dict, bool]:
    existing = get_project(name)
    if existing:
        linked = bool(existing.get("link", {}).get("repoId"))
        print(f"project exists: {name} (git_linked={linked})")
        return existing, linked
    try:
        # No "framework" key: static site, Vercel auto-detects.
        project = api("POST", "/v10/projects", {
            "name": name,
            "gitRepository": {"type": "github", "repo": repo},
        })
        print(f"project created with GitHub link: {name}")
        return project, True
    except DynamicCredentialError as e:
        print(f"git link failed ({str(e)[:120]}); creating unlinked project")
        project = api("POST", "/v10/projects", {"name": name})
        print(f"project created (unlinked): {name}")
        return project, False


def deploy_from_git(project: dict) -> dict:
    repo_id = project.get("link", {}).get("repoId")
    if not repo_id:
        raise DynamicCredentialError("project has no linked repoId")
    return api("POST", "/v13/deployments", {
        "name": project["name"], "project": project["id"],
        "target": "production",
        "gitSource": {"type": "github", "repoId": repo_id, "ref": "main"},
    })


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


def deploy_from_files(project: dict) -> dict:
    files = collect_files(ROOT)
    print(f"uploading {len(files)} files...")
    file_list = []
    for rel, content in files:
        digest = hashlib.sha1(content).hexdigest()
        req = urllib.request.Request(API + "/v2/files", data=content, method="POST")
        req.add_header("Content-Type", "application/octet-stream")
        req.add_header("x-vercel-digest", digest)
        req.add_header("User-Agent", "argus-deploy/1.0")
        add_surrogate_to_request(req, CRED, allowed_hosts=HOSTS)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                resp.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            raise DynamicCredentialError(f"Vercel file upload -> {e.code}: {body}")
        file_list.append({"file": rel, "sha": digest, "size": len(content)})
    return api("POST", "/v13/deployments?skipAutoDetectionConfirmation=1", {
        "name": project["name"], "project": project["id"],
        "target": "production", "files": file_list,
    })


def wait_for_deploy(deploy_id: str, timeout_s: int = 600) -> dict:
    start = time.time()
    while time.time() - start < timeout_s:
        dep = api("GET", f"/v13/deployments/{deploy_id}")
        if dep.get("status") in ("READY", "ERROR", "CANCELED"):
            return dep
        time.sleep(10)
    raise DynamicCredentialError("deploy timed out waiting for READY")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-name", default="argus")
    ap.add_argument("--repo", default="williamtheconqueror48-art/argus")
    args = ap.parse_args()

    check_auth()
    project, git_linked = create_project(args.project_name, args.repo)
    if git_linked:
        try:
            dep = deploy_from_git(project)
        except DynamicCredentialError as e:
            print(f"git deploy failed ({str(e)[:120]}); falling back to file upload")
            dep = deploy_from_files(project)
    else:
        dep = deploy_from_files(project)

    print(f"deployment {dep['id']} status={dep.get('status')}; waiting...")
    final = wait_for_deploy(dep["id"])
    url = final.get("url")
    print(f"deployment {final['status']}: https://{url}")
    if final.get("status") != "READY":
        raise DynamicCredentialError(f"deploy ended {final.get('status')}")


if __name__ == "__main__":
    main()
