"""
Acesso à RAIS 2024 no MotherDuck via SDK do DuckDB (sem MCP).

Em vez de expor uma tool MCP, isto é um módulo que você chama direto no seu código.

Instalação:
    pip install duckdb pandas python-dotenv

Token (NUNCA no código): coloque num arquivo .env na raiz do projeto:
    MOTHERDUCK_TOKEN=seu_token

Uso como script:
    python rais_2024.py "SELECT uf, COUNT(*) FROM mte.rais_ident_2024 GROUP BY uf"

Uso como biblioteca:
    from rais_2024 import query_rais
    df = query_rais("SELECT * FROM mte.rais_ident_2024 LIMIT 10")
"""

import os
import sys
import duckdb
from dotenv import load_dotenv

load_dotenv()  # carrega MOTHERDUCK_TOKEN do .env, se existir

DB = "my_data"
TABLE = "mte.rais_ident_2024"


def get_conn():
    """Abre conexão com o MotherDuck. Token vem do ambiente, não do código."""
    token = os.environ.get("MOTHERDUCK_TOKEN")
    if not token:
        raise RuntimeError(
            "Defina MOTHERDUCK_TOKEN (no .env ou no ambiente) antes de rodar."
        )
    return duckdb.connect(f"md:{DB}?motherduck_token={token}")


def query_rais(sql: str):
    """Executa SQL e devolve um DataFrame pandas."""
    with get_conn() as conn:           # fecha a conexão sozinho
        return conn.sql(sql).fetchdf()


def preview(limit: int = 10):
    """Atalho: primeiras linhas da tabela."""
    return query_rais(f"SELECT * FROM {TABLE} LIMIT {int(limit)}")


if __name__ == "__main__":
    sql = sys.argv[1] if len(sys.argv) > 1 else f"SELECT * FROM {TABLE} LIMIT 10"
    df = query_rais(sql)
    print(df.to_string())


