"""Request and response schemas for authentication."""

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Payload for creating a new account."""

    email: EmailStr
    name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    """Payload for logging in with email and password."""

    email: EmailStr
    password: str


class UserRead(BaseModel):
    """Public view of a user (never includes the password hash)."""

    id: str
    email: str
    name: str
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    """Returned by register and login: a bearer token plus the user."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserRead
