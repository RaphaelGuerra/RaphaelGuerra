#!/usr/bin/env python3
"""Run one substantive README maintenance pass across RaphaelGuerra repositories."""

from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

OWNER = "RaphaelGuerra"
START_DATE = dt.date(2026, 7, 13)
MAX_REPOS = 200


def run(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=check)
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    return result.stdout.strip()


def openai_edit(readme: str, tree: str, repo: str) -> dict:
    prompt = f"""You are maintaining the README for {repo}.
Return JSON only with this exact shape:
{{"action":"skip","reason":"..."}} or {{"action":"update","readme":"...","reason":"..."}}

Make an update only when it is a concrete documentation improvement supported by the supplied source context. Examples: replace starter-template text with an accurate project guide, correct setup commands, document actual routes or scripts, fix a broken local path, or clarify current project status.
Skip if the README is already accurate and useful.
Never add dates, activity notes, filler, badges, "last updated" lines, vague marketing claims, or content not supported by the source.
Do not change code or licenses. Preserve useful existing sections and keep the README concise.

CURRENT README:
---BEGIN README---
{readme[:30000]}
---END README---

ROOT FILES:
{tree[:12000]}
"""
    payload = json.dumps({
        "model": os.environ.get("OPENAI_MODEL", "gpt-5.4-mini"),
        "input": prompt,
        "temperature": 0.1,
        "max_output_tokens": 7000,
    }).encode()
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=payload,
        headers={
            "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        body = json.load(response)
    text = body.get("output_text", "")
    if not text:
        for item in body.get("output", []):
            for part in item.get("content", []):
                if part.get("type") == "output_text":
                    text += part.get("text", "")
    return json.loads(text)


def main() -> int:
    if not os.environ.get("GH_TOKEN"):
        raise SystemExit("Missing README_MAINTENANCE_TOKEN secret")
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("Missing OPENAI_API_KEY secret")

    raw = run(
        "gh", "repo", "list", OWNER, "--limit", str(MAX_REPOS),
        "--json", "nameWithOwner,isArchived,isFork",
    )
    repos = [
        item["nameWithOwner"]
        for item in json.loads(raw)
        if not item["isArchived"] and not item["isFork"]
    ]
    repos.sort()
    if not repos:
        print("No eligible repositories found.")
        return 0

    today = dt.date.today()
    selected = repos[(today - START_DATE).days % len(repos)]
    print(f"Selected repository: {selected}")

    workdir = Path(tempfile.mkdtemp(prefix="readme-maintenance-"))
    try:
        clone = workdir / selected.split("/", 1)[1]
        run("gh", "repo", "clone", selected, str(clone), "--", "--depth=1")
        readme_path = next(
            (clone / name for name in ("README.md", "README", "readme.md") if (clone / name).is_file()),
            None,
        )
        if readme_path is None:
            print("Skipped: repository has no README file.")
            return 0

        tree_lines = []
        for path in sorted(clone.iterdir()):
            if path.name == ".git":
                continue
            tree_lines.append(path.name + ("/" if path.is_dir() else ""))
        result = openai_edit(readme_path.read_text(encoding="utf-8"), "\n".join(tree_lines), selected)
        if result.get("action") != "update":
            print(f"Skipped: {result.get('reason', 'no substantive change recommended')}")
            return 0

        new_readme = result.get("readme", "").strip() + "\n"
        if not new_readme or new_readme == readme_path.read_text(encoding="utf-8"):
            print("Skipped: model returned no effective change.")
            return 0

        default_branch = run("gh", "repo", "view", selected, "--json", "defaultBranchRef", "--jq", ".defaultBranchRef.name")
        branch = f"automation/readme-maintenance-{today.isoformat()}"
        run("git", "checkout", "-b", branch, cwd=clone)
        readme_path.write_text(new_readme, encoding="utf-8")
        run("git", "config", "user.name", "github-actions[bot]", cwd=clone)
        run("git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com", cwd=clone)
        run("git", "add", readme_path.name, cwd=clone)
        run("git", "commit", "-m", "docs: improve README", cwd=clone)
        run("git", "push", "--set-upstream", "origin", branch, cwd=clone)
        pr_url = run(
            "gh", "pr", "create", "--repo", selected, "--base", default_branch,
            "--head", branch, "--title", "docs: improve README",
            "--body", "This documentation-only change updates the README to reflect the current project. It was generated only after identifying a concrete documentation gap; no cosmetic activity changes were made.",
            "--draft",
            cwd=clone,
        )
        print(f"Opened draft PR: {pr_url}")
        return 0
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
