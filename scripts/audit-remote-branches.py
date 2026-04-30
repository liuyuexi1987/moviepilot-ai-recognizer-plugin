#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> str:
    completed = subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def remote_branches() -> list[str]:
    output = run("git", "branch", "-r")
    branches: list[str] = []
    for raw in output.splitlines():
        branch = raw.strip()
        if not branch or "->" in branch or branch == "origin/main":
            continue
        branches.append(branch)
    return branches


def pr_map() -> dict[str, dict]:
    output = run(
        "gh",
        "pr",
        "list",
        "--state",
        "all",
        "--limit",
        "100",
        "--json",
        "number,state,headRefName,baseRefName,title",
    )
    items = json.loads(output)
    mapping = {}
    for item in items:
        head = item.get("headRefName")
        if head:
            mapping[head] = item
    return mapping


def is_ancestor(branch: str) -> bool:
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", branch, "main"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def recommendation(*, has_pr: bool, pr_state: str | None, ancestor: bool) -> str:
    if has_pr and pr_state == "MERGED":
        return "safe_to_prune_after_fetch"
    if ancestor:
        return "likely_stale_check_history"
    if has_pr:
        return f"keep_{str(pr_state).lower()}"
    return "manual_review"


def main() -> int:
    branches = remote_branches()
    prs = pr_map()
    rows = []
    for branch in branches:
        short = branch.removeprefix("origin/")
        pr = prs.get(short)
        ancestor = is_ancestor(branch)
        rows.append(
            {
                "branch": branch,
                "pr": pr.get("number") if pr else None,
                "pr_state": pr.get("state") if pr else None,
                "ancestor_of_main": ancestor,
                "recommendation": recommendation(
                    has_pr=bool(pr),
                    pr_state=pr.get("state") if pr else None,
                    ancestor=ancestor,
                ),
                "title": pr.get("title") if pr else None,
            }
        )
    print(json.dumps({"branches": rows}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
