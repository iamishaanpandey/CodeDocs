"""
GitHub Client Service

Centralized httpx-based client for all GitHub API interactions:
  - Posting PR comments (for Blast Radius reports)
  - Registering / deleting webhooks on user repos
  - Fetching PR diffs
  - Listing PR files

Uses the user's stored github_token (OAuth token with repo scope).
Falls back gracefully with structured error logging.
"""
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
USER_AGENT = "prime-pulsar-bot/1.0"


def _headers(token: str) -> dict:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28"
    }


async def post_pr_comment(
    owner: str,
    repo: str,
    pr_number: int,
    body: str,
    token: str
) -> Optional[str]:
    """
    Posts a comment on a GitHub Pull Request.
    Returns the comment ID string on success, None on failure.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(url, headers=_headers(token), json={"body": body})
            response.raise_for_status()
            comment_data = response.json()
            logger.info(f"Posted PR comment #{comment_data['id']} on {owner}/{repo}#{pr_number}")
            return str(comment_data["id"])
        except httpx.HTTPStatusError as e:
            logger.error(f"GitHub PR comment failed ({e.response.status_code}): {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"GitHub PR comment unexpected error: {e}")
            return None


async def update_pr_comment(
    owner: str,
    repo: str,
    comment_id: str,
    body: str,
    token: str
) -> bool:
    """Updates an existing PR comment (e.g. when a PR is re-synchronized)."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/comments/{comment_id}"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.patch(url, headers=_headers(token), json={"body": body})
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"GitHub PR comment update failed: {e}")
            return False


async def get_pr_diff(
    owner: str,
    repo: str,
    pr_number: int,
    token: str
) -> Optional[str]:
    """
    Fetches the unified diff for a Pull Request.
    Returns the diff as a raw string, or None on failure.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.get(
                url,
                headers={**_headers(token), "Accept": "application/vnd.github.diff"}
            )
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to fetch PR diff ({e.response.status_code}): {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"PR diff fetch error: {e}")
            return None


async def register_webhook(
    owner: str,
    repo: str,
    callback_url: str,
    secret: str,
    token: str
) -> Optional[str]:
    """
    Registers a webhook on a GitHub repo for push and pull_request events.
    Returns the webhook ID string on success.
    """
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/hooks"
    payload = {
        "name": "web",
        "active": True,
        "events": ["push", "pull_request"],
        "config": {
            "url": callback_url,
            "content_type": "json",
            "secret": secret,
            "insecure_ssl": "0"
        }
    }
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(url, headers=_headers(token), json=payload)
            response.raise_for_status()
            hook_data = response.json()
            logger.info(f"Registered webhook {hook_data['id']} on {owner}/{repo}")
            return str(hook_data["id"])
        except httpx.HTTPStatusError as e:
            # 422 means webhook already exists — not a fatal error
            if e.response.status_code == 422:
                logger.warning(f"Webhook already exists on {owner}/{repo}")
                return "exists"
            logger.error(f"Webhook registration failed ({e.response.status_code}): {e.response.text[:200]}")
            return None
        except Exception as e:
            logger.error(f"Webhook registration error: {e}")
            return None


async def delete_webhook(
    owner: str,
    repo: str,
    webhook_id: str,
    token: str
) -> bool:
    """Removes a previously registered webhook."""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/hooks/{webhook_id}"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.delete(url, headers=_headers(token))
            return response.status_code == 204
        except Exception as e:
            logger.error(f"Webhook deletion error: {e}")
            return False
