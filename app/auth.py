"""Password hashing, JWT handling and FastAPI auth dependencies."""

from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.database import ensure_beanie_initialized
from app.models.user import User

_bearer = HTTPBearer(auto_error=False)
_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def create_access_token(user: User) -> tuple[str, int]:
    """Return a signed JWT for the user and its lifetime in seconds."""

    settings = get_settings()
    expires_in = settings.jwt_expire_minutes * 60
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": datetime.now(UTC) + timedelta(seconds=expires_in),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM), expires_in


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    """Resolve the user from an `Authorization: Bearer <token>` header."""

    if credentials is None:
        raise _unauthorized("Not authenticated")

    try:
        payload = jwt.decode(credentials.credentials, get_settings().jwt_secret, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise _unauthorized("Invalid token") from exc

    await ensure_beanie_initialized(request.app.state.mongo_client)
    user = await User.get(payload.get("sub", ""))
    if user is None:
        raise _unauthorized("User no longer exists")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Allow only admins through."""

    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
