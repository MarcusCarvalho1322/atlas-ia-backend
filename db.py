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


def garantir_colunas() -> list[str]:
    """
    Acrescenta colunas novas a tabelas que já existem.

    `Base.metadata.create_all` cria tabelas que faltam e NÃO TOCA nas que já
    estão lá. Quando um campo novo aparece no modelo, a tabela em produção
    continua sem ele e toda leitura quebra com "column does not exist" — numa
    base que já tem dez mil casos dentro, apagar e recriar não é opção.

    Não se usa Alembic aqui de propósito: é uma dependência e um diretório de
    versões inteiros para um projeto cujo esquema muda uma vez por trimestre.
    O acréscimo abaixo é idempotente e roda na partida.

    Devolve a lista do que foi efetivamente acrescentado, para a rota `/`
    conseguir relatar. Nunca derruba o serviço: banco indisponível na partida
    é situação transitória, e o diagnóstico dela é `descrever_banco()`.
    """
    acrescentadas: list[str] = []
    # (tabela, coluna, tipo em SQL). JSON existe em Postgres e em SQLite 3.9+.
    PENDENTES = [("prospectos", "registro", "JSON")]
    for tabela, coluna, tipo in PENDENTES:
        try:
            with engine.begin() as conexao:
                if engine.url.get_backend_name().startswith("sqlite"):
                    existentes = {l[1] for l in conexao.execute(
                        text(f"PRAGMA table_info({tabela})"))}
                    if coluna in existentes:
                        continue
                    conexao.execute(text(
                        f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}"))
                else:
                    conexao.execute(text(
                        f"ALTER TABLE {tabela} ADD COLUMN IF NOT EXISTS {coluna} {tipo}"))
                acrescentadas.append(f"{tabela}.{coluna}")
        except Exception:
            # Tabela ainda não criada, ou banco fora do ar. create_all cuida do
            # primeiro caso; do segundo, quem reclama é descrever_banco().
            pass
    return acrescentadas


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
