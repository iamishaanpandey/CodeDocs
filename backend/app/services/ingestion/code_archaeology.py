"""
Code Archaeology Service
Extracts git commit history for source files to build "Historical Context"
summaries that explain *why* a function exists, not just *how* it works.
These summaries are stored in Documentation.git_blame_summary and are
included in the RAG embedding text.
"""
import subprocess
import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _run_git_log(repo_path: str, file_path: str, max_commits: int = 3) -> list[dict]:
    """
    Runs git log on a specific file path within a cloned repository.
    Returns up to max_commits commit entries with hash, author, date, and subject.
    """
    abs_file = os.path.join(repo_path, file_path)
    if not os.path.exists(abs_file):
        return []

    try:
        result = subprocess.run(
            [
                "git", "log",
                f"-{max_commits}",
                "--format=%H|%an|%ae|%ad|%s",
                "--date=short",
                "--",
                file_path
            ],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return []

        commits = []
        for line in result.stdout.strip().split("\n"):
            if not line.strip():
                continue
            parts = line.split("|", 4)
            if len(parts) == 5:
                commits.append({
                    "hash": parts[0][:8],
                    "author": parts[1],
                    "email": parts[2],
                    "date": parts[3],
                    "subject": parts[4]
                })
        return commits
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        logger.debug(f"Git log failed for {file_path}: {e}")
        return []


def build_git_blame_summary(repo_path: str, file_path: str) -> Optional[str]:
    """
    Builds a plain-text "Historical Context" summary for a file using git log.
    Returns None if no git history is available (e.g. fresh clone with shallow depth).

    Example output:
    "Historical context: Last modified by Alice Smith on 2024-12-01:
     'fix: handle edge case in token refresh'. Originally introduced by
     Bob Jones on 2024-10-14: 'feat: add JWT authentication middleware'."
    """
    commits = _run_git_log(repo_path, file_path)
    if not commits:
        return None

    parts = []

    if len(commits) >= 1:
        last = commits[0]
        parts.append(
            f"Last modified by {last['author']} on {last['date']}: '{last['subject']}'"
        )

    if len(commits) >= 2:
        prev = commits[1]
        parts.append(
            f"Previously changed by {prev['author']} on {prev['date']}: '{prev['subject']}'"
        )

    if len(commits) >= 3:
        orig = commits[-1]
        parts.append(
            f"Originally introduced by {orig['author']} on {orig['date']}: '{orig['subject']}'"
        )

    if not parts:
        return None

    return "Historical context: " + ". ".join(parts) + "."
