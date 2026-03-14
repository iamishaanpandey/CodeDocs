from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
import uuid
import httpx

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token, get_token_hash
from app.core.config import settings
from app.core.redis_client import get_redis_client
from app.models.user import User
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse, RefreshRequest, AccessTokenResponse, LogoutRequest, UserResponse
from app.api.deps import get_current_user
from app.api.deps_rbac import require_role
import redis.asyncio as redis
from jose import JWTError, ExpiredSignatureError

router = APIRouter()

@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: RegisterRequest, 
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client)
):
    stmt = select(User).where(User.email == data.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
        
    user = User(
        email=data.email,
        name=data.name,
        hashed_password=hash_password(data.password),
        is_active=True,
        is_verified=False
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    
    token_hash = get_token_hash(refresh_token)
    await redis_client.setex(
        f"refresh:{user.id}:{token_hash}", 
        timedelta(days=settings.refresh_token_expire_days), 
        "valid"
    )
    
    return {
        "access_token": access_token, 
        "refresh_token": refresh_token, 
        "token_type": "bearer", 
        "user": user
    }

@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest, 
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client)
):
    stmt = select(User).where(User.email == data.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    
    if not user or not user.hashed_password or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")
        
    access_token = create_access_token(str(user.id))
    refresh_token = create_refresh_token(str(user.id))
    
    token_hash = get_token_hash(refresh_token)
    await redis_client.setex(
        f"refresh:{user.id}:{token_hash}", 
        timedelta(days=settings.refresh_token_expire_days), 
        "valid"
    )
    
    return {
        "access_token": access_token, 
        "refresh_token": refresh_token, 
        "user": user
    }

@router.get("/google")
async def google_auth(redis_client: redis.Redis = Depends(get_redis_client)):
    state = str(uuid.uuid4())
    await redis_client.setex(f"oauth_state:{state}", 600, "valid")
    
    client_id = settings.google_client_id
    redirect_uri = settings.google_redirect_uri
    scope = "openid email profile"
    
    url = f"https://accounts.google.com/o/oauth2/v2/auth?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&state={state}"
    return RedirectResponse(url)

@router.get("/google/callback")
async def google_callback(
    code: str, 
    state: str = Query(None),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client)
):
    if not state or not await redis_client.get(f"oauth_state:{state}"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state")
    
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code"
            }
        )
        if token_response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to fetch access token")
            
        access_token = token_response.json()["access_token"]
        
        user_info_response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user_info = user_info_response.json()
        
    google_id = user_info["id"]
    email = user_info["email"]
    name = user_info.get("name")
    
    stmt = select(User).where(User.google_id == google_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    
    if not user:
        stmt = select(User).where(User.email == email)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user:
            user.google_id = google_id
            await db.commit()
            await db.refresh(user)
        else:
            user = User(
                email=email,
                name=name,
                google_id=google_id,
                is_active=True,
                is_verified=True
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            
    app_access_token = create_access_token(str(user.id))
    app_refresh_token = create_refresh_token(str(user.id))
    
    token_hash = get_token_hash(app_refresh_token)
    await redis_client.setex(
        f"refresh:{user.id}:{token_hash}", 
        timedelta(days=settings.refresh_token_expire_days), 
        "valid"
    )
    
    return RedirectResponse(f"{settings.frontend_url}/auth/callback?access_token={app_access_token}&refresh_token={app_refresh_token}")
    
@router.get("/github")
async def github_auth(redis_client: redis.Redis = Depends(get_redis_client)):
    state = str(uuid.uuid4())
    await redis_client.setex(f"oauth_state:{state}", 600, "valid")
    
    client_id = settings.github_oauth_client_id
    redirect_uri = settings.github_oauth_redirect_uri
    scope = "user:email repo read:org"
    
    url = f"https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&state={state}"
    return RedirectResponse(url)

@router.get("/github/callback")
async def github_callback(
    code: str, 
    state: str = Query(None),
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client)
):
    if not state or not await redis_client.get(f"oauth_state:{state}"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid state")
        
    await redis_client.delete(f"oauth_state:{state}")
    
    async with httpx.AsyncClient() as client:
        # Exchange code for token
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.github_oauth_client_id,
                "client_secret": settings.github_oauth_client_secret,
                "code": code,
                "redirect_uri": settings.github_oauth_redirect_uri
            },
            headers={"Accept": "application/json"}
        )
        if token_response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to fetch GitHub token")
            
        token_data = token_response.json()
        github_access_token = token_data.get("access_token")
        if not github_access_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No access token in GitHub response")
            
        # Fetch user info
        user_response = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {github_access_token}"}
        )
        if user_response.status_code != 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to fetch GitHub user")
            
        github_user = user_response.json()
        github_id = str(github_user["id"])
        github_username = github_user["login"]
        github_avatar_url = github_user.get("avatar_url")
        email = github_user.get("email")
        
        # Fetch email if private
        if not email:
            email_response = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"token {github_access_token}"}
            )
            if email_response.status_code == 200:
                emails = email_response.json()
                for e in emails:
                    if e["primary"] and e["verified"]:
                        email = e["email"]
                        break
        
        if not email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verified email not found on GitHub account")
            
    # Find or create user
    stmt = select(User).where(User.github_id == github_id)
    user = (await db.execute(stmt)).scalar_one_or_none()
    
    if not user:
        stmt = select(User).where(User.email == email)
        user = (await db.execute(stmt)).scalar_one_or_none()
        if user:
            user.github_id = github_id
            user.github_token = github_access_token
            user.github_username = github_username
            user.github_avatar_url = github_avatar_url
            await db.commit()
            await db.refresh(user)
        else:
            user = User(
                email=email,
                name=github_user.get("name") or github_username,
                github_id=github_id,
                github_token=github_access_token,
                github_username=github_username,
                github_avatar_url=github_avatar_url,
                is_active=True,
                is_verified=True
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
    else:
        # Update token and other info
        user.github_token = github_access_token
        user.github_username = github_username
        user.github_avatar_url = github_avatar_url
        await db.commit()
        await db.refresh(user)
            
    app_access_token = create_access_token(str(user.id))
    app_refresh_token = create_refresh_token(str(user.id))
    
    token_hash = get_token_hash(app_refresh_token)
    await redis_client.setex(
        f"refresh:{user.id}:{token_hash}", 
        timedelta(days=settings.refresh_token_expire_days), 
        "valid"
    )
    
    return RedirectResponse(f"{settings.frontend_url}/auth/callback?access_token={app_access_token}&refresh_token={app_refresh_token}")

@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh_token(
    data: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client)
):
    try:
        payload = decode_token(data.refresh_token)
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not a refresh token")
        
    user_id = payload.get("sub")
    token_hash = get_token_hash(data.refresh_token)
    
    is_blacklisted = await redis_client.get(f"blacklist:{token_hash}")
    if is_blacklisted:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been blacklisted")
        
    is_valid = await redis_client.get(f"refresh:{user_id}:{token_hash}")
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
        
    try:
        user_id_obj = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
        
    stmt = select(User).where(User.id == user_id_obj)
    user = (await db.execute(stmt)).scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
        
    new_access_token = create_access_token(user_id)
    return {"access_token": new_access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/logout")
async def logout(
    data: LogoutRequest,
    redis_client: redis.Redis = Depends(get_redis_client)
):
    try:
        payload = decode_token(data.refresh_token)
        user_id = payload.get("sub")
        exp = payload.get("exp")
        
        token_hash = get_token_hash(data.refresh_token)
        await redis_client.delete(f"refresh:{user_id}:{token_hash}")
        
        now = datetime.now(timezone.utc).timestamp()
        ttl = max(0, int(exp - now))
        if ttl > 0:
            await redis_client.setex(f"blacklist:{token_hash}", ttl, "blacklisted")
            
    except JWTError:
        pass
        
    return {"message": "Logged out successfully"}


VALID_ROLES = {"owner", "admin", "member", "viewer"}

class RoleUpdateRequest(BaseModel):
    role: str

@router.patch("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: uuid.UUID,
    data: RoleUpdateRequest,
    current_user: User = Depends(require_role("owner")),
    db: AsyncSession = Depends(get_db)
):
    """
    Owner-only endpoint to change a team member's role.
    Owners cannot demote themselves to prevent admin lockout.
    """
    if data.role not in VALID_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role. Must be one of: {', '.join(sorted(VALID_ROLES))}"
        )

    if user_id == current_user.id and data.role != "owner":
        raise HTTPException(
            status_code=400,
            detail="Owners cannot demote themselves — transfer ownership first."
        )

    stmt = select(User).where(User.id == user_id)
    target_user = (await db.execute(stmt)).scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_user.role = data.role
    await db.commit()
    await db.refresh(target_user)
    return target_user
