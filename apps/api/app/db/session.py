from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
kwargs={"connect_args":{"check_same_thread":False}} if settings.sync_database_url.startswith("sqlite") else {}
engine=create_engine(settings.sync_database_url,pool_pre_ping=True,**kwargs)
SessionLocal=sessionmaker(bind=engine,autoflush=False,expire_on_commit=False)
def get_db():
    db=SessionLocal()
    try: yield db
    finally: db.close()
