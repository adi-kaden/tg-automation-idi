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

settings = get_settings()


async def seed_admin():
    """Create admin user if it doesn't exist."""
    engine = create_async_engine(settings.async_database_url, pool_size=3)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with AsyncSessionLocal() as db:
        # Check if admin already exists
        result = await db.execute(
            select(User).where(User.email == "admin@idigov.com")
        )
        existing = result.scalar_one_or_none()

        if existing:
            print("Admin user already exists")
            return

        # Create admin user
        admin = User(
            email="admin@idigov.com",
            hashed_password=hash_password("Admin123!"),
            full_name="Admin User",
            role="admin",
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        print("Admin user created successfully!")
        print("Email: admin@idigov.com")
        print("Password: Admin123!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_admin())
