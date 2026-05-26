"""
MotherDuck MCP Server — rais_ident_2024
Expõe tools para consultar a tabela rais_ident_2024 via DuckDB/MotherDuck.
 
Instalação:
    pip install mcp duckdb
 
Configuração da variável de ambiente (token do MotherDuck):
    Windows: set MOTHERDUCK_TOKEN=seu_token_aqui
    Linux/Mac: export MOTHERDUCK_TOKEN=seu_token_aqui
 
Adicione no claude_desktop_config.json:
    "rais": {
      "command": "C:\\Users\\Yuan\\miniconda3\\Scripts\\conda.exe",
      "args": ["run", "-n", "wh", "--no-capture-output", "python",
               "C:\\caminho\\para\\mcp_motherduck.py"],
      "env": { "MOTHERDUCK_TOKEN": "seu_token_aqui" },
      "disabled": false
    }
"""
 
import os
import duckdb
from mcp.server.fastmcp import FastMCP

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6InpoYW5nNDg5eXVhbkBnbWFpbC5jb20iLCJtZFJlZ2lvbiI6ImF3cy11cy1lYXN0LTEiLCJzZXNzaW9uIjoiemhhbmc0ODl5dWFuLmdtYWlsLmNvbSIsInBhdCI6ImRYa21jZjk2ZHNXR253REs5d3hsdjlCa3JMT1Q1VVM1SnB6UGJQaHJNUWsiLCJ1c2VySWQiOiJmZWIwZWM2Ni1jMGEwLTQ2NTgtYTgxMS01OTVlMTYyOTM0YWQiLCJpc3MiOiJtZF9wYXQiLCJyZWFkT25seSI6ZmFsc2UsInRva2VuVHlwZSI6InJlYWRfd3JpdGUiLCJpYXQiOjE3Nzk3NTY5MjZ9.q52ocE1hwc1by187KWGecN6Zz16K17qCf_qK9YDDUl8"
DB = "my_data"
TABLE = "mte.rais_ident_2024"

mcp = FastMCP(
    "RAIS 2024",
    instructions="Servidor MCP para consultar dados da RAIS 2024 no MotherDuck.",
)


def get_conn():
    return duckdb.connect(f"md:{DB}?motherduck_token={TOKEN}")


@mcp.tool()
def query_rais(sql: str) -> str:
    """Executa query SQL na RAIS 2024."""
    conn = get_conn()
    result = conn.sql(sql).fetchdf()
    conn.close()
    return result.to_string()


if __name__ == "__main__":
    mcp.run()