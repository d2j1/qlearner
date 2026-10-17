"""Register, login and current-user endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pymongo.errors import DuplicateKeyError, ServerSelectionTimeoutError

from app.auth import create_access_token, get_current_user, hash_password, verify_password
from app.config import get_settings
from app.database import ensure_beanie_initialized
from app.models.user import User
from app.schemas.auth_schema import LoginRequest, RegisterRequest, TokenResponse, UserRead

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _serialize_user(user: User) -> UserRead:
    return UserRead(
        id=str(user.id),
        email=user.email,
        name=user.name,
        role=user.role,
        created_at=user.created_at,
    )


def _token_response(user: User) -> TokenResponse:
    token, expires_in = create_access_token(user)
    return TokenResponse(access_token=token, expires_in=expires_in, user=_serialize_user(user))


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(request: Request, body: RegisterRequest) -> TokenResponse:
    """Create an account and log the user in immediately."""

    email = body.email.lower()
    role = "admin" if email in get_settings().admin_email_list else "user"

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        user = User(email=email, name=body.name.strip(), password_hash=hash_password(body.password), role=role)
        await user.insert()
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=409, detail="Email is already registered") from exc
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    return _token_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(request: Request, body: LoginRequest) -> TokenResponse:
    """Exchange email and password for a bearer token."""

    try:
        await ensure_beanie_initialized(request.app.state.mongo_client)
        user = await User.find_one(User.email == body.email.lower())
    except ServerSelectionTimeoutError as exc:
        raise HTTPException(status_code=503, detail="MongoDB is unavailable.") from exc

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    # Promote users added to ADMIN_EMAILS after they registered.
    if user.role != "admin" and user.email in get_settings().admin_email_list:
        user.role = "admin"
        await user.save()

    return _token_response(user)


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)) -> UserRead:
    """Return the logged-in user; use it on app load to restore a session."""

    return _serialize_user(user)
