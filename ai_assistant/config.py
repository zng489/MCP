"""
Configuração central do AI Assistant.
Todas as constantes e parâmetros ficam aqui.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Diretórios
BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR                          # os .md ficam na raiz do ai_assistant/
CACHE_DIR = BASE_DIR / ".cache"
DB_PATH = BASE_DIR / "memory.db"

# LLM (DeepSeek via SDK OpenAI)
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MODELO_LLM = "deepseek-chat"
MODELO_JUDGE = "deepseek-chat"
TEMPERATURE = 0.0

# RAG
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
TOP_K = 3
N_CANDIDATOS = 15
PESO_SEMANTICO = 0.6
TAMANHO_PAI = 2000
TAMANHO_FILHO = 450
LIMIAR_MIN = 0.0
USAR_RERANK = True

# Docs indexados (allowlist — DOCUMENTACAO_BOT.md não entra, é sobre o próprio bot)
ARQUIVOS_DOCS = [
    "README.md",
    "STACK_DOCS.md",
    "jupyterhub_acl.md",
    "redorando.md",
    "re_index.md",
]

# SQL / MotherDuck
MOTHERDUCK_TOKEN = os.environ.get("MOTHERDUCK_TOKEN", "")
RAIS_TABLE = "mte.rais_ident_2024"
RAIS_DB = "my_data"
MAX_PASSOS_SQL = 10
PALAVRAS_PERIGOSAS_SQL = (
    "insert", "update", "delete", "drop", "alter",
    "create", "replace", "truncate",
)

# Observabilidade (Langfuse — opcional; sem config, vira no-op)
LANGFUSE_SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "")
LANGFUSE_PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_HOST = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

# Guardrails
MAX_OUTPUT_CHARS = 4000

# Preços DeepSeek por 1M tokens (ajuste pela tabela atual)
PRECO_INPUT = 0.27
PRECO_OUTPUT = 1.10
