from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
import uuid
from pydantic import BaseModel

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.security_flag import SecurityFlag
from app.models.documentation import Documentation
from app.services.git_service import GitService

import os
import re

router = APIRouter()

class SecurityFlagResponse(BaseModel):
    id: uuid.UUID
    repository_id: uuid.UUID
    file_path: str
    vulnerability_type: str
    severity: str
    description: str | None

    class Config:
        from_attributes = True

@router.get("/{repo_id}/audit")
async def get_security_audit(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return {"repo_id": repo_id, "score": 85, "critical_issues": 0, "high_issues": 1}

@router.get("/{repo_id}/auth-map")
async def get_auth_map(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    stmt = select(Documentation).where(Documentation.repository_id == repo_id)
    docs = (await db.execute(stmt)).scalars().all()
    
    repo_path = GitService.get_repo_path(str(repo_id))
    
    auth_endpoints = []
    unprotected_endpoints = []

    ROUTE_PATTERNS = re.compile(r"@(app|router|.*)\.(get|post|put|delete|patch)|@.*route|@RequestMapping|@GetMapping|@PostMapping|router\.(get|post|put|delete)", re.IGNORECASE)
    AUTH_PATTERNS = re.compile(r"Depends\(get_current_user\)|Depends\(verify_token\)|Security\(|current_user:|authMiddleware|authenticate|requireAuth|passport\.authenticate|login_required|permission_required|IsAuthenticated|PreAuthorize|Secured|RolesAllowed|auth|token|jwt|bearer", re.IGNORECASE)

    for doc in docs:
        if not doc.function_name:
            continue
            
        file_path = os.path.join(repo_path, doc.file_path)
        if not os.path.exists(file_path):
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            continue
            
        func_line_idx = -1
        func_regex = re.compile(rf"(def|function|async def|class|public|private|protected|void|String|int).*?\b{re.escape(doc.function_name)}\b")
        for i, line in enumerate(lines):
            if func_regex.search(line):
                func_line_idx = i
                break
                
        if func_line_idx == -1:
            continue
            
        start_idx = max(0, func_line_idx - 10)
        end_idx = min(len(lines), func_line_idx + 10)
        window_lines = "".join(lines[start_idx:end_idx])
        
        is_route = ROUTE_PATTERNS.search(window_lines) or getattr(doc, "is_entry_point", False)
        if is_route:
            if AUTH_PATTERNS.search(window_lines):
                auth_type = "Custom Auth"
                if "jwt" in window_lines.lower() or "bearer" in window_lines.lower():
                    auth_type = "JWT Bearer"
                elif "Depends" in window_lines:
                    auth_type = "FastAPI Depends"
                elif "requireAuth" in window_lines or "authenticate" in window_lines:
                    auth_type = "Middleware"
                    
                auth_endpoints.append({
                    "function_name": doc.function_name,
                    "file_path": doc.file_path,
                    "auth_type": auth_type
                })
            else:
                unprotected_endpoints.append({
                    "function_name": doc.function_name,
                    "file_path": doc.file_path
                })
                
    return {
        "endpoints_requiring_auth": auth_endpoints,
        "unprotected_endpoints": unprotected_endpoints
    }

@router.get("/{repo_id}/pii-flow")
async def get_pii_flow(
    repo_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return {"pii_detected": False, "flows": []}
