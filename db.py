"""
Conexão com o banco de dados do atlas-geo.

Usa DATABASE_URL se estiver definida (Postgres do Railway, formato
postgresql://...). Se não estiver definida, cai para um arquivo SQLite local
(atlas_geo.db) — útil só para testar no seu próprio computador antes de
publicar; em produção o Railway deve sempre fornecer um Postgres real,
porque o disco de um container Railway não é permanente entre deploys.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./atlas_geo.db")

# Railway (como o Vercel) às vezes entrega a URL como "postgres://" — o
# SQLAlchemy moderno exige o prefixo "postgresql://".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
