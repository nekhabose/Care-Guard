from sqlalchemy import func, select

from models.db.user import User
from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        # Emails are case-insensitive for login purposes.
        result = await self.db.execute(
            select(User).where(func.lower(User.email) == email.strip().lower())
        )
        return result.scalar_one_or_none()

    async def count(self) -> int:
        result = await self.db.execute(select(func.count()).select_from(User))
        return int(result.scalar_one())
