"""
Agente Revisor (agente 4):
Sintetiza o resultado de outros agentes, melhora clareza e entrega ao usuário.
Suporta streaming token-a-token.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI
from observability.tracer import trace_llm, Timer
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODELO_LLM, TEMPERATURE

_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, timeout=60)

SYSTEM = """Você é um revisor de qualidade de respostas de IA.

Sua tarefa:
1. Verificar se a resposta do agente especializado responde à pergunta original
2. Melhorar clareza e estrutura se necessário (sem inventar informações)
3. Manter todos os dados, números e fontes originais intactos
4. Ser conciso — não adicione introduções desnecessárias

Se a resposta já estiver boa, entregue-a com pequenas melhorias de formatação."""


def revisar(pergunta: str, resultado_agente: dict, stream: bool = False):
    """
    stream=True → retorna generator de tokens (para CLI/API com streaming).
    stream=False → retorna dict com resposta completa.
    """
    contexto = f"Pergunta original: {pergunta}\n\nResposta do agente: {resultado_agente['resposta']}"
    if "fontes" in resultado_agente:
        contexto += f"\n\nFontes consultadas: {', '.join(resultado_agente['fontes'])}"
    if "sqls" in resultado_agente and resultado_agente["sqls"]:
        contexto += f"\n\nSQLs executados ({len(resultado_agente['sqls'])}):\n" + \
                    "\n".join(f"  • {s[:100]}" for s in resultado_agente["sqls"])

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": contexto},
    ]

    if stream:
        return _stream(messages, pergunta)
    return _completo(messages, pergunta)


def _stream(messages: list, pergunta: str):
    """Generator que yield tokens conforme chegam da API."""
    with Timer() as t:
        stream = _client.chat.completions.create(
            model=MODELO_LLM,
            messages=messages,
            temperature=TEMPERATURE,
            stream=True,
        )
        texto_completo = ""
        for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            texto_completo += delta
            yield delta

    trace_llm(
        name="reviewer_stream",
        input_text=pergunta,
        output_text=texto_completo,
        model=MODELO_LLM,
        metadata={"latencia_s": round(t.elapsed, 2)},
    )


def _completo(messages: list, pergunta: str) -> dict:
    with Timer() as t:
        resp = _client.chat.completions.create(
            model=MODELO_LLM,
            messages=messages,
            temperature=TEMPERATURE,
        )
    msg = resp.choices[0].message.content

    trace_llm(
        name="reviewer",
        input_text=pergunta,
        output_text=msg,
        tokens_in=resp.usage.prompt_tokens,
        tokens_out=resp.usage.completion_tokens,
        model=MODELO_LLM,
    )
    return {
        "resposta": msg,
        "tokens_in": resp.usage.prompt_tokens,
        "tokens_out": resp.usage.completion_tokens,
        "latencia_s": round(t.elapsed, 2),
    }
