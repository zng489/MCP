"""
Agente SQL (agente 3):
Loop agêntico com function calling para consultar RAIS 2024 no MotherDuck.
Adaptado do project/agente_rais.py — adicionada observabilidade.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI
from observability.tracer import trace_llm, Timer
from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODELO_LLM,
    MOTHERDUCK_TOKEN, RAIS_TABLE, RAIS_DB,
    PALAVRAS_PERIGOSAS_SQL, MAX_PASSOS_SQL,
)

_client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
    timeout=60,
    max_retries=3,
)

SYSTEM = f"""Você é um analista de dados autônomo. Responde perguntas sobre a RAIS 2024
consultando a tabela `{RAIS_TABLE}` no MotherDuck (dialeto DuckDB).

Regras:
- Chame `consultar_rais` para executar SQL. Nunca execute SQL diretamente no texto.
- Se não souber o schema, comece com DESCRIBE ou SELECT * LIMIT 5.
- Somente SELECT. Nunca rode INSERT/UPDATE/DELETE/DROP/ALTER/CREATE.
- Responda em português com os números que encontrou."""

TOOLS = [{
    "type": "function",
    "function": {
        "name": "consultar_rais",
        "description": "Executa SQL de somente leitura na RAIS 2024 e retorna o resultado como texto.",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "Consulta SELECT no dialeto DuckDB.",
                }
            },
            "required": ["sql"],
        },
    },
}]


def _executar_sql(sql: str) -> str:
    if any(p in sql.lower() for p in PALAVRAS_PERIGOSAS_SQL):
        return "Recusado: somente consultas SELECT são permitidas."
    if not MOTHERDUCK_TOKEN:
        return "MOTHERDUCK_TOKEN não configurado no .env"
    try:
        import duckdb
        with duckdb.connect(f"md:{RAIS_DB}?motherduck_token={MOTHERDUCK_TOKEN}") as conn:
            df = conn.sql(sql).fetchdf()
        return df.to_string()[:10_000] or "(sem resultados)"
    except Exception as e:
        return f"Erro SQL: {e}"


def responder(pergunta: str) -> dict:
    """Retorna dict: resposta, sqls, tokens_in, tokens_out, latencia_s, agente."""
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": pergunta},
    ]
    sqls_executados: list[str] = []
    tokens_in = tokens_out = 0
    resposta_final = f"Parou após {MAX_PASSOS_SQL} passos."

    with Timer() as t:
        for _ in range(MAX_PASSOS_SQL):
            resp = _client.chat.completions.create(
                model=MODELO_LLM,
                messages=messages,
                tools=TOOLS,
            )
            msg = resp.choices[0].message
            tokens_in += resp.usage.prompt_tokens
            tokens_out += resp.usage.completion_tokens
            messages.append(msg)

            if not msg.tool_calls:
                resposta_final = msg.content
                break

            for chamada in msg.tool_calls:
                args = json.loads(chamada.function.arguments)
                sql = args.get("sql", "")
                sqls_executados.append(sql)
                resultado = _executar_sql(sql)
                messages.append({
                    "role": "tool",
                    "tool_call_id": chamada.id,
                    "content": resultado,
                })

    trace_llm(
        name="sql_agent",
        input_text=pergunta,
        output_text=resposta_final,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        model=MODELO_LLM,
        metadata={"sqls_count": len(sqls_executados), "sqls": sqls_executados},
    )

    return {
        "resposta": resposta_final,
        "sqls": sqls_executados,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latencia_s": round(t.elapsed, 2),
        "agente": "sql_agent",
    }
