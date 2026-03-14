"""
RBAC (Role-Based Access Control) FastAPI Dependencies

Role hierarchy (ascending privileges):
  viewer  → can only read documentation
  member  → can trigger scans
  admin   → can add/remove repos
  owner   → can manage users and roles

Usage:
    from app.api.deps_rbac import require_role

    @router.delete("/{repo_id}")
    async def delete_repo(..., user: User = Depends(require_role("admin", "owner"))):
        ...
"""
from fastapi import Depends, HTTPException, status
from app.models.user import User
from app.api.deps import get_current_user

ROLE_ORDER = ["viewer", "member", "admin", "owner"]


def require_role(*roles: str):
    """
    Returns a FastAPI dependency that verifies the current user has
    one of the specified roles. Raises 403 if not authorized.
    """
    allowed = set(roles)

    async def _check(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required role: {' or '.join(sorted(allowed))}. "
                       f"Your role: {current_user.role}."
            )
        return current_user

    return _check


def require_min_role(min_role: str):
    """
    Alternative to require_role — requires the user to have at least
    the specified role level in the hierarchy.

    Example: require_min_role("admin") allows "admin" and "owner".
    """
    if min_role not in ROLE_ORDER:
        raise ValueError(f"Invalid role: {min_role}. Valid roles: {ROLE_ORDER}")

    min_idx = ROLE_ORDER.index(min_role)

    async def _check(current_user: User = Depends(get_current_user)) -> User:
        user_idx = ROLE_ORDER.index(current_user.role) if current_user.role in ROLE_ORDER else -1
        if user_idx < min_idx:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Minimum required role: {min_role}. "
                       f"Your role: {current_user.role}."
            )
        return current_user

    return _check
