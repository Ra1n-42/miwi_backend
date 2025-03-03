from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os

class Database:
    USER = os.getenv("POSTGRES_USER")
    PASSWORD = os.getenv("POSTGRES_PASSWORD")
    DATABASE = os.getenv("POSTGRES_DB")
    HOST = os.getenv("POSTGRES_HOST")
    DRIVER = "postgresql+psycopg"

# Postgresql
DATABASE_URL = f"{Database.DRIVER}://{Database.USER}:{Database.PASSWORD}@{Database.HOST}/{Database.DATABASE}"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


Base = declarative_base()

metadata = Base.metadata


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()