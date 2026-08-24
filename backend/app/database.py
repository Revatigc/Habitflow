from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from pydantic_settings import BaseSettings
class Settings(BaseSettings):
    database_url: str
    auth_provider_domain: str
    auth_audience: str
    class Config: env_file = ".env"
settings=Settings()
engine=create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal=sessionmaker(bind=engine, autoflush=False)
class Base(DeclarativeBase): pass
def db():
    session=SessionLocal()
    try: yield session
    finally: session.close()
