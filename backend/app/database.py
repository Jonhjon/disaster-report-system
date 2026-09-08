from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"sslmode": "require"} if settings.DB_REQUIRE_SSL else {},
    pool_pre_ping=True,
    pool_recycle=1800,
)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_statistics_db():
    """Provide one read-only snapshot session for statistics and authentication.

    The transaction mode must be the session's first statement.  The statistics
    authentication dependency reuses this same session, so each request holds
    one connection and all authentication/aggregate queries share one snapshot.
    """
    db = SessionLocal()
    try:
        db.execute(
            text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        )
        yield db
    finally:
        db.close()
