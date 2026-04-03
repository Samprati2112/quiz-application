import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

MYSQL_URL = os.getenv(
    "MYSQL_URL",
    "mysql+pymysql://root:password@localhost:3306/quiz_app",
)

engine = create_engine(MYSQL_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
