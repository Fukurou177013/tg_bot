from os import getenv
from typing import Optional

from dotenv import load_dotenv

from sqlalchemy import BigInteger, String, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

load_dotenv()  # Загружаем переменные окружения из .env файла

DATABASE_URL = getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("Переменная окружения DATABASE_URL не задана")

# echo=True будет печатать SQL-запросы в консоль.
engine = create_async_engine(DATABASE_URL, echo=True)

async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        index=True,
    )
    name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    birth_date: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )
    gender: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )
    address: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )


async def init_db() -> None:
    """
    Создаёт таблицы в базе данных, если их ещё нет.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    """
    Получить пользователя по telegram_id.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def save_user_name(telegram_id: int, name: str) -> None:
    """
    Сохранить имя пользователя.
    Если пользователь уже есть — обновить имя.
    Если нет — создать нового.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user:
            user.name = name
        else:
            user = User(
                telegram_id=telegram_id,
                name=name,
            )
            session.add(user)

        await session.commit()


async def save_user_profile(
    telegram_id: int,
    birth_date: str,
    gender: str,
    address: str,
) -> None:
    """
    Сохранить данные профиля.
    """
    async with async_session_maker() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(telegram_id=telegram_id)
            session.add(user)

        user.birth_date = birth_date
        user.gender = gender
        user.address = address

        await session.commit()
