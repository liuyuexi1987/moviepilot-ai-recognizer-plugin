#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def show_help() -> None:
    print(
        "Usage:\n"
        "  python3 scripts/audit-remote-branches.py\n\n"
        "Prints JSON describing remote non-main branches and local non-main\n"
        "branches, including PR linkage, ancestry, unique patch counts and\n"
        "cleanup recommendations."
    )


def run(*args: str) -> str:
    completed = subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def ref_exists(ref: str) -> bool:
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def remote_branches() -> list[str]:
    output = run("git", "branch", "-r", "--format", "%(refname:short)")
    return [
        branch.strip()
        for branch in output.splitlines()
        if branch.strip()
        and "->" not in branch
        and branch.strip() not in {"origin", "origin/main"}
    ]


def local_branches() -> list[str]:
    output = run("git", "branch", "--format", "%(refname:short)")
    return [branch.strip() for branch in output.splitlines() if branch.strip() and branch.strip() != "main"]


def pr_map() -> tuple[dict[str, dict], str]:
    try:
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
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {}, "unavailable"

    items = json.loads(output)
    mapping = {}
    for item in items:
        head = item.get("headRefName")
        if head:
            mapping[head] = item
    return mapping, "ok"


def is_ancestor(branch: str) -> bool:
    if not ref_exists(branch):
        return False
    completed = subprocess.run(
        ["git", "merge-base", "--is-ancestor", branch, "main"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return completed.returncode == 0


def cherry_unique_count(branch: str) -> int:
    if not ref_exists(branch):
        return -1
    try:
        output = run("git", "cherry", "main", branch)
    except subprocess.CalledProcessError:
        return -1
    return len([line for line in output.splitlines() if line.startswith("+ ")])


def remote_recommendation(*, has_pr: bool, pr_state: str | None, ancestor: bool, unique_count: int) -> str:
    if unique_count < 0:
        return "unavailable"
    if has_pr and pr_state == "MERGED":
        return "safe_to_prune_after_fetch"
    if unique_count == 0:
        return "likely_stale_equivalent_history"
    if ancestor:
        return "likely_stale_check_history"
    if has_pr:
        return f"keep_{str(pr_state).lower()}"
    return "manual_review"


def local_recommendation(*, has_remote: bool, has_pr: bool, pr_state: str | None, ancestor: bool, unique_count: int) -> str:
    if unique_count < 0:
        return "unavailable"
    if ancestor or unique_count == 0:
        return "safe_to_delete_local_copy"
    if has_pr and pr_state == "OPEN":
        return "keep_open_pr_branch"
    if has_remote:
        return "keep_tracking_remote"
    return "manual_review"


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in {"--help", "-h"}:
        show_help()
        return 0

    prs, pr_lookup = pr_map()
    remotes = remote_branches()
    locals_ = local_branches()
    remote_set = set(remotes)

    remote_rows = []
    for branch in remotes:
        short = branch.removeprefix("origin/")
        pr = prs.get(short)
        ancestor = is_ancestor(branch)
        unique_count = cherry_unique_count(branch)
        remote_rows.append(
            {
                "branch": branch,
                "pr": pr.get("number") if pr else None,
                "pr_state": pr.get("state") if pr else None,
                "ancestor_of_main": ancestor,
                "unique_patch_commits_vs_main": unique_count,
                "recommendation": remote_recommendation(
                    has_pr=bool(pr),
                    pr_state=pr.get("state") if pr else None,
                    ancestor=ancestor,
                    unique_count=unique_count,
                ),
                "title": pr.get("title") if pr else None,
            }
        )

    local_rows = []
    for branch in locals_:
        pr = prs.get(branch)
        ancestor = is_ancestor(branch)
        unique_count = cherry_unique_count(branch)
        has_remote = f"origin/{branch}" in remote_set
        local_rows.append(
            {
                "branch": branch,
                "has_remote": has_remote,
                "pr": pr.get("number") if pr else None,
                "pr_state": pr.get("state") if pr else None,
                "ancestor_of_main": ancestor,
                "unique_patch_commits_vs_main": unique_count,
                "recommendation": local_recommendation(
                    has_remote=has_remote,
                    has_pr=bool(pr),
                    pr_state=pr.get("state") if pr else None,
                    ancestor=ancestor,
                    unique_count=unique_count,
                ),
                "title": pr.get("title") if pr else None,
            }
        )

    print(
        json.dumps(
            {
                "pr_lookup": pr_lookup,
                "remote_branches": remote_rows,
                "local_branches": local_rows,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
