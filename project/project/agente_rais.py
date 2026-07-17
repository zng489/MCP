"""
Agente autônomo sobre a RAIS 2024 (MotherDuck) usando o DeepSeek.

Junta as peças do projeto:
    .env            -> token do MotherDuck (lido por rais_2024.py)
    rais_2024.py    -> query_rais(sql): a "mão" que executa SQL de verdade
    este arquivo    -> o "loop agêntico": o DeepSeek decide os SQLs sozinho

Você faz uma pergunta em português; o modelo escreve o SQL, chama a ferramenta,
olha o resultado, consulta de novo se precisar, e responde — sem você tocar em SQL.

Instalação:
    pip install openai duckdb pandas python-dotenv
    export DEEPSEEK_API_KEY=sk-...             # chave do DeepSeek (cérebro)
    # MOTHERDUCK_TOKEN vem do .env (dados), igual o rais_2024.py já usa

Uso:
    python agente_rais.py "Quais as 10 UFs com mais vínculos na RAIS 2024?"
    python agente_rais.py "Compare o número de vínculos entre SP e RJ"
"""

import json
import os
import sys
from openai import OpenAI  # a lib do OpenAI também fala com a API do DeepSeek
from rais_2024 import TABLE, query_rais  # reutiliza o helper que o projeto já tem

MODELO = "deepseek-chat"
MAX_PASSOS = 25  # trava de segurança contra loop infinito

SYSTEM = f"""\
Você é um analista de dados autônomo. Responde perguntas sobre a RAIS 2024
consultando a tabela `{TABLE}` no MotherDuck (dialeto DuckDB).

Como trabalhar:
- Você NÃO executa SQL diretamente. Para consultar, chame a ferramenta `consultar_rais`.
- Se não souber o schema, comece com um DESCRIBE ou um SELECT ... LIMIT 5 para
  descobrir as colunas, e só então escreva a consulta final.
- Faça quantas consultas precisar; o usuário não está acompanhando passo a passo.
- Apenas leitura: nunca rode INSERT/UPDATE/DELETE/DROP.
- No fim, responda em português, de forma direta, com os números que encontrou.
"""

# Definição da ferramenta no formato de "function calling" do OpenAI/DeepSeek.
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_rais",
            "description": (
                "Executa uma consulta SQL (somente leitura) na RAIS 2024 e devolve o "
                "resultado como texto. Tabela principal: mte.rais_ident_2024."
            ),
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
    }
]


def consultar_rais(sql: str) -> str:
    """Executa o SQL de verdade (a 'mão' do agente)."""
    proibido = ("insert", "update", "delete", "drop", "alter", "create", "replace")
    if any(p in sql.lower() for p in proibido):
        return "Recusado: somente consultas de leitura (SELECT) são permitidas."
    try:
        df = query_rais(sql)
        return df.to_string()[:20_000] or "(sem resultados)"
    except Exception as e:  # noqa: BLE001
        return f"Erro ao executar SQL: {e}"


def main() -> None:
    pergunta = sys.argv[1] if len(sys.argv) > 1 else "Quantos vínculos há na RAIS 2024?"

    client = OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
        timeout=60.0,      # mais tempo p/ handshake/resposta lenta (default era curto)
        max_retries=3,     # tenta de novo sozinho em timeouts/erros de rede passageiros
    )

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": pergunta},
    ]

    # Loop agêntico: continua enquanto o modelo pedir ferramentas; para quando responder.
    for _ in range(MAX_PASSOS):
        resposta = client.chat.completions.create(
            model=MODELO,
            messages=messages,
            tools=TOOLS,
        )
        msg = resposta.choices[0].message
        messages.append(msg)  # guarda a fala do modelo (pode conter pedidos de ferramenta)

        if not msg.tool_calls:
            # Sem pedido de ferramenta = resposta final.
            print(msg.content)
            return

        # O modelo pediu uma ou mais ferramentas: execute e devolva os resultados.
        for chamada in msg.tool_calls:
            args = json.loads(chamada.function.arguments)
            sql = args.get("sql", "")
            print(f"  → SQL: {sql}", file=sys.stderr)
            resultado = consultar_rais(sql)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": chamada.id,
                    "content": resultado,
                }
            )

    print(f"Parou após {MAX_PASSOS} passos (trava de segurança).", file=sys.stderr)


if __name__ == "__main__":
    main()
