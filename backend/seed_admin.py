"""
Seed script to create the admin user.
Run with: python seed_admin.py
"""
import asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import get_settings
from app.models.user import User
from app.utils.security import hash_password
from seed import initial_users_from_env

settings = get_settings()


async def seed_admin():
    """Create admin user if it doesn't exist."""
    configured_admin = next(
        (user for user in initial_users_from_env() if user["role"] == "admin"),
        None,
    )
    if configured_admin is None:
        raise RuntimeError("INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD must be configured")

    engine = create_async_engine(settings.async_database_url, pool_size=3)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        # Check if admin already exists
        result = await db.execute(
            select(User).where(User.email == configured_admin["email"])
        )
        existing = result.scalar_one_or_none()

        if existing:
            print("Admin user already exists")
            return

        # Create admin user
        admin = User(
            email=configured_admin["email"],
            hashed_password=hash_password(configured_admin["password"]),
            name=configured_admin["name"],
            role=configured_admin["role"],
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        print("Admin user created successfully!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_admin())
