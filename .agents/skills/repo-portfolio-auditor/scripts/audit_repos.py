#!/usr/bin/env python3
"""
RepoPilot Portfolio Auditor CLI
Audits GitHub repositories against RepoPilot's 5-dimension credit-score model:
- Safety (30%)
- Trust & Governance (25%)
- Maintenance & Recency (20%)
- Maturity & Testing (15%)
- Documentation & Onboarding (10%)
Identifies pending gaps and produces executive scorecards.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8")


def get_token() -> str:
    """Retrieve GitHub token from gh CLI keyring or GITHUB_TOKEN environment variable."""
    env_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env_token:
        return env_token.strip()
    try:
        token = subprocess.check_output(["gh", "auth", "token"], text=True, stderr=subprocess.DEVNULL).strip()
        if token:
            return token
    except Exception:
        pass
    return ""


def call_gh_api(endpoint: str, token: str = "") -> Optional[Any]:
    """Execute API call via gh CLI or urllib with fallback."""
    try:
        cmd = ["gh", "api", endpoint]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8")
        if res.returncode == 0 and res.stdout.strip():
            return json.loads(res.stdout)
    except Exception:
        pass

    # Fallback to urllib
    try:
        import urllib.request
        url = f"https://api.github.com/{endpoint.lstrip('/')}"
        headers = {"User-Agent": "RepoPilot-Auditor/1.0", "Accept": "application/vnd.github.v3+json"}
        if token:
            headers["Authorization"] = f"token {token}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def parse_date(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def audit_repository(repo: Dict[str, Any], token: str, now: datetime) -> Dict[str, Any]:
    full_name = repo["full_name"]
    name = repo["name"]
    is_fork = repo.get("fork", False)
    default_branch = repo.get("default_branch", "main")

    # 1. Inspect tree blobs
    tree_data = call_gh_api(f"repos/{full_name}/git/trees/{default_branch}?recursive=1", token)
    file_paths: List[str] = []
    if tree_data and "tree" in tree_data:
        file_paths = [item["path"] for item in tree_data["tree"] if item.get("type") == "blob"]

    root_files = {p for p in file_paths if "/" not in p}

    critical_issues: List[str] = []
    gaps: List[str] = []

    # ---------------- Dimension 1: Safety (30%) ----------------
    safety_score = 100
    sensitive_patterns = [".env", ".pem", ".key", "id_rsa", "credentials.json", "service-account.json"]
    for path in file_paths:
        base = path.split("/")[-1].lower()
        if base == ".env":
            critical_issues.append(f"Committed .env file detected at `{path}`")
            safety_score -= 40
            gaps.append("REMOVE_COMMITTED_ENV")
        elif any(base.endswith(ext) for ext in [".pem", ".key", "id_rsa"]):
            critical_issues.append(f"Private cryptographic key exposed at `{path}`")
            safety_score -= 40
            gaps.append("EXPOSED_SECRET_KEY")

    if ".gitignore" not in root_files and not is_fork:
        safety_score -= 15
        gaps.append("ADD_GITIGNORE")

    safety_score = max(0, min(100, safety_score))

    # ---------------- Dimension 2: Trust (25%) ----------------
    trust_score = 0
    license_info = repo.get("license")
    if license_info and license_info.get("spdx_id") not in (None, "NOASSERTION"):
        trust_score += 50
    elif license_info:
        trust_score += 30
    else:
        gaps.append("ADD_LICENSE")

    if repo.get("description"):
        trust_score += 25
    else:
        gaps.append("ADD_DESCRIPTION")

    topics = repo.get("topics", [])
    if topics and len(topics) >= 2:
        trust_score += 25
    elif topics:
        trust_score += 15
    else:
        gaps.append("ADD_TOPICS")

    trust_score = max(0, min(100, trust_score))

    # ---------------- Dimension 3: Maintenance (20%) ----------------
    pushed_at = parse_date(repo.get("pushed_at"))
    days_stale = (now - pushed_at).days if pushed_at else 999

    if repo.get("archived"):
        maint_score = 25
        gaps.append("REPO_ARCHIVED")
    elif days_stale <= 30:
        maint_score = 100
    elif days_stale <= 90:
        maint_score = 85
    elif days_stale <= 180:
        maint_score = 65
    elif days_stale <= 365:
        maint_score = 40
        gaps.append("STALE_OVER_6_MONTHS")
    else:
        maint_score = 20
        gaps.append("STALE_OVER_1_YEAR")

    # ---------------- Dimension 4: Maturity (15%) ----------------
    mat_score = 0
    has_ci = any(".github/workflows/" in p for p in file_paths) or any(
        p in root_files for p in [".gitlab-ci.yml", "azure-pipelines.yml", "Jenkinsfile"]
    )
    if has_ci:
        mat_score += 50
    else:
        gaps.append("ADD_CI_WORKFLOW")

    has_tests = any(
        p.startswith("tests/") or p.startswith("__tests__/") or p.startswith("test/") or "test" in p.lower()
        for p in file_paths
    )
    if has_tests:
        mat_score += 50
    else:
        gaps.append("ADD_AUTOMATED_TESTS")

    # ---------------- Dimension 5: Documentation (10%) ----------------
    doc_score = 0
    readme_path = next((p for p in root_files if p.lower().startswith("readme")), None)
    if readme_path:
        doc_score += 50
    else:
        gaps.append("ADD_README")

    has_manifest = any(
        p in root_files
        for p in [
            "package.json",
            "requirements.txt",
            "pyproject.toml",
            "go.mod",
            "Cargo.toml",
            "pom.xml",
            "build.gradle",
        ]
    )
    has_env_sample = any(p in root_files for p in [".env.example", ".env.sample", ".env.template"])

    if has_env_sample:
        doc_score += 50
    elif not has_manifest:
        doc_score += 50
    else:
        gaps.append("ADD_ENV_EXAMPLE")
        doc_score += 20

    # Weighted calculation
    raw_score = (
        (safety_score * 0.30)
        + (trust_score * 0.25)
        + (maint_score * 0.20)
        + (mat_score * 0.15)
        + (doc_score * 0.10)
    )

    final_score = raw_score
    cap_reason: Optional[str] = None
    if critical_issues:
        final_score = min(final_score, 39)
        cap_reason = "CRITICAL security flaw detected (Caps at Grade F)"
    elif "ADD_LICENSE" in gaps and not is_fork:
        final_score = min(final_score, 74)
        cap_reason = "Missing Open Source License (Caps at Grade C)"
    elif "ADD_README" in gaps:
        final_score = min(final_score, 59)
        cap_reason = "Missing README (Caps at Grade D)"

    final_score = int(round(final_score))

    if final_score >= 90:
        grade = "A"
        label = "Excellent"
    elif final_score >= 75:
        grade = "B"
        label = "Good"
    elif final_score >= 60:
        grade = "C"
        label = "Needs Attention"
    elif final_score >= 40:
        grade = "D"
        label = "High Friction"
    else:
        grade = "F"
        label = "Critical Risk"

    return {
        "name": name,
        "full_name": full_name,
        "is_fork": is_fork,
        "language": repo.get("language") or "N/A",
        "score": final_score,
        "grade": grade,
        "label": label,
        "days_stale": days_stale,
        "dimensions": {
            "safety": safety_score,
            "trust": trust_score,
            "maintenance": maint_score,
            "maturity": mat_score,
            "docs": doc_score,
        },
        "critical_issues": critical_issues,
        "gaps": gaps,
        "cap_reason": cap_reason,
    }


def format_markdown_table(results: List[Dict[str, Any]], user: str) -> str:
    lines = [
        f"# RepoPilot Portfolio Scorecard for @{user}",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')} | **Total Repositories:** {len(results)}",
        "",
        "| Repository | Score | Grade | Lang | Safety | Trust | Maint | Mat | Docs | Key Pending Gaps |",
        "|:-----------|:-----:|:-----:|:----:|:------:|:-----:|:-----:|:---:|:----:|:-----------------|",
    ]
    for r in results:
        dims = r["dimensions"]
        gaps_str = ", ".join(r["gaps"][:2]) if r["gaps"] else "None"
        if len(r["gaps"]) > 2:
            gaps_str += f" (+{len(r['gaps'])-2})"
        lines.append(
            f"| [{r['name']}](https://github.com/{r['full_name']}) | **{r['score']}** | `{r['grade']}` | {r['language']} | {dims['safety']} | {dims['trust']} | {dims['maintenance']} | {dims['maturity']} | {dims['docs']} | {gaps_str} |"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="RepoPilot GitHub Portfolio Auditor")
    parser.add_argument("--user", type=str, default="", help="GitHub username or org")
    parser.add_argument("--repo", type=str, default="", help="Single repo (owner/repo)")
    parser.add_argument("--format", choices=["table", "json", "markdown"], default="table", help="Output format")
    parser.add_argument("--out", type=str, default="", help="Output file path")
    args = parser.parse_args()

    token = get_token()
    now = datetime.now(timezone.utc)

    target_user = args.user
    if not target_user and not args.repo:
        user_info = call_gh_api("user", token)
        if user_info and "login" in user_info:
            target_user = user_info["login"]
        else:
            target_user = "sivasubramanian86"

    results: List[Dict[str, Any]] = []

    if args.repo:
        repo_data = call_gh_api(f"repos/{args.repo}", token)
        if not repo_data:
            print(f"Error: Unable to fetch repository {args.repo}", file=sys.stderr)
            sys.exit(1)
        res = audit_repository(repo_data, token, now)
        results.append(res)
    else:
        repos_data = call_gh_api(f"users/{target_user}/repos?per_page=100&sort=updated", token)
        if not repos_data or not isinstance(repos_data, list):
            print(f"Error: Unable to fetch repositories for @{target_user}", file=sys.stderr)
            sys.exit(1)
        for repo in repos_data:
            res = audit_repository(repo, token, now)
            results.append(res)

    results.sort(key=lambda x: x["score"], reverse=True)

    if args.format == "json":
        output = json.dumps(results, indent=2)
    elif args.format == "markdown":
        output = format_markdown_table(results, target_user)
    else:
        # Terminal summary table
        output_lines = [
            f"\n=== RepoPilot Portfolio Scorecard (@{target_user}) ===",
            f"{'Repo':<32} {'Score':<7} {'Grade':<6} {'Safety':<7} {'Trust':<6} {'Maint':<6} {'Mat':<5} {'Docs':<5} {'Pending Gaps'}",
            "-" * 105,
        ]
        for r in results:
            dims = r["dimensions"]
            gaps_str = ", ".join(r["gaps"][:2]) if r["gaps"] else "None"
            output_lines.append(
                f"{r['name']:<32} {r['score']:<7} {r['grade']:<6} {dims['safety']:<7} {dims['trust']:<6} {dims['maintenance']:<6} {dims['maturity']:<5} {dims['docs']:<5} {gaps_str}"
            )
        output = "\n".join(output_lines)

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Report written to {args.out}")
    else:
        print(output)


if __name__ == "__main__":
    main()
