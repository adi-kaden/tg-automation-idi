from datetime import timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.config import get_settings
from app.dependencies import DBSession, CurrentUser
from app.models.user import User
from app.schemas.user import UserLogin, UserResponse, Token
from app.utils.security import verify_password, create_access_token

router = APIRouter()
settings = get_settings()


@router.post("/login", response_model=Token)
async def login(
    credentials: UserLogin,
    db: DBSession,
):
    """
    Login with email and password to get JWT token.
    """
    # Find user by email
    result = await db.execute(
        select(User).where(User.email == credentials.email)
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = create_access_token(
        subject=user.id,
        expires_delta=access_token_expires,
        extra_claims={"role": user.role},
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse.model_validate(user),
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    current_user: CurrentUser,
):
    """
    Refresh the JWT token for the current user.
    """
    access_token_expires = timedelta(minutes=settings.jwt_access_token_expire_minutes)
    access_token = create_access_token(
        subject=current_user.id,
        expires_delta=access_token_expires,
        extra_claims={"role": current_user.role},
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.jwt_access_token_expire_minutes * 60,
        user=UserResponse.model_validate(current_user),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
    current_user: CurrentUser,
):
    """
    Get the current authenticated user's profile.
    """
    return UserResponse.model_validate(current_user)
