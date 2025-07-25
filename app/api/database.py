from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# --- INÍCIO DA CORREÇÃO DEFINITIVA ---

# 1. Encontrar o diretório raiz do projeto de forma fiável.
#    O ficheiro atual está em /app/api/database.py.
#    Subimos dois níveis para chegar à raiz do projeto.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# 2. Definir um diretório de dados dedicado na raiz do projeto.
#    Esta é uma prática recomendada para separar os dados da lógica da aplicação.
DATA_DIR = os.path.join(project_root, "data")

# 3. Criar o diretório de dados se ele não existir.
#    Isto garante que o caminho para a base de dados será sempre válido.
os.makedirs(DATA_DIR, exist_ok=True)

# 4. Definir o caminho completo para o ficheiro da base de dados.
DB_PATH = os.path.join(DATA_DIR, "bobia.db")

# --- FIM DA CORREÇÃO ---

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Mensagem de diagnóstico para confirmar o caminho absoluto da base de dados.
print(f"A base de dados está configurada em: {DB_PATH}")
if not os.path.exists(DATA_DIR):
    print(f"AVISO: Não foi possível criar o diretório de dados em {DATA_DIR}")
