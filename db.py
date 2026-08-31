"""
Conexão com o banco de dados do atlas-geo.

Usa DATABASE_URL se estiver definida (Postgres gerenciado — no Render ela é
injetada pelo vínculo "Add from database", sem ninguém copiar senha). Se não
estiver definida, cai para um arquivo SQLite local (atlas_geo.db).

ATENÇÃO AO SILÊNCIO DESSE FALLBACK: sem DATABASE_URL o serviço SOBE NORMALMENTE
e responde tudo — só que gravando num arquivo dentro do container. O disco do
container é efêmero: no primeiro redeploy ou reinício, a carteira de prospectos
e o histórico do funil desaparecem sem nenhuma mensagem de erro. Como isso é
indistinguível de fora, `descrever_banco()` expõe o estado real na rota `/`.
"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./atlas_geo.db")

# Alguns provedores entregam a URL como "postgres://" — o SQLAlchemy moderno
# exige o prefixo "postgresql://".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def descrever_banco() -> dict:
    """
    Diagnóstico do banco para a rota `/`, sem vazar credencial.

    Devolve APENAS o dialeto (postgresql / sqlite), se o armazenamento é
    permanente e se a conexão responde de fato. Nunca o usuário, a senha, o
    host ou o nome do banco — esses vivem só na variável de ambiente.
    """
    dialeto = engine.url.get_backend_name()          # "postgresql" | "sqlite"
    persistente = not dialeto.startswith("sqlite")
    try:
        with engine.connect() as conexao:
            conexao.execute(text("SELECT 1"))
        conectado = True
        erro = None
    except Exception as exc:                          # noqa: BLE001
        conectado = False
        erro = type(exc).__name__                     # só a classe, não a mensagem
    return {
        "dialeto": dialeto,
        "persistente": persistente,
        "conectado": conectado,
        "erro": erro,
        "aviso": None if persistente else (
            "SQLite em disco efêmero: os dados serão perdidos no próximo "
            "reinício. Vincule um Postgres em DATABASE_URL."
        ),
    }


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
