"""Configuração central do bot. Ajuste tudo por aqui."""
import os
import pathlib

from dotenv import load_dotenv

load_dotenv()

RAIZ = pathlib.Path(__file__).parent
PASTA_DOCS = RAIZ
PASTA_CACHE = RAIZ / ".cache"
PASTA_CACHE.mkdir(exist_ok=True)
ARQUIVO_LOG = RAIZ / "historico.jsonl"

# Quais .md fazem parte da base de conhecimento (allowlist — evita indexar
# arquivos .md soltos do projeto, como guias do próprio bot).
ARQUIVOS_DOCS = [
    "README.md",
    "STACK_DOCS.md",
    "jupyterhub_acl.md",
    "redorando.md",
    "re_index.md",
]

# ---- LLM (DeepSeek) ----
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
MODELO_LLM = "deepseek-chat"
TEMPERATURE = 0.1
MAX_TENTATIVAS = 3
TIMEOUT = 30
# Preços aproximados por 1M tokens (USD). Ajuste pela tabela atual do DeepSeek.
PRECO_INPUT = 0.27
PRECO_OUTPUT = 1.10

# ---- Retrieval ----
MODELO_EMB = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 4
LIMIAR_MIN = 0.30          # score (0..1) mínimo p/ um chunk entrar
PESO_SEMANTICO = 0.6       # 0..1 — peso da busca semântica vs. BM25 (palavra-chave)
# small-to-big: busca nos FILHOS (pequenos, precisos); envia os PAIS (grandes, contexto)
TAMANHO_PAI = 2000         # caracteres do bloco enviado ao LLM
TAMANHO_FILHO = 450        # caracteres do pedaço usado na busca

# ---- Reranking (cross-encoder) ----
USAR_RERANK = True
MODELO_RERANK = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"  # multilíngue (PT)
N_CANDIDATOS = 12          # quantos chunks a busca híbrida traz antes de reordenar

# ---- Chat ----
MAX_MENSAGENS_HISTORICO = 12  # mantém só as últimas N mensagens (6 trocas)

SYSTEM_PROMPT = """Você é um assistente técnico da stack "infra_mini_cloud".
Responda SOMENTE com base nos trechos de documentação fornecidos em cada pergunta.
Use APENAS os trechos relevantes para a pergunta; ignore os que não têm relação.
Não acrescente informação que o usuário não perguntou.
Se a resposta não estiver nos trechos, diga claramente que não sabe.
Cite o arquivo de onde tirou a resposta."""
