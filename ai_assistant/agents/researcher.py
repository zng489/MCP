"""
Agente Pesquisador (agente 2):
Usa RAG híbrido para responder perguntas sobre os docs da infra_mini_cloud.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI
from rag.hybrid_rag import HybridRAG
from observability.tracer import trace_llm, Timer
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODELO_LLM, TEMPERATURE

_rag = HybridRAG()
_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, timeout=60)

SYSTEM = """Você é um especialista na stack infra_mini_cloud (Spark, Polaris, RustFS, Airflow, Iceberg).
Responda APENAS com base nos trechos fornecidos abaixo.
Se a resposta não estiver nos trechos, diga: "Não encontrei essa informação na documentação."
Cite o arquivo de origem (ex: [README.md]) ao responder. Seja direto e técnico."""


def responder(pergunta: str, historico: list[dict] | None = None) -> dict:
    """Retorna dict: resposta, fontes, tokens_in, tokens_out, latencia_s, agente."""
    trechos = _rag.buscar(pergunta)
    fontes = list({t["fonte"] for t in trechos})
    contexto = "\n\n---\n\n".join(
        f"[{t['fonte']}]\n{t['texto']}" for t in trechos
    )

    messages = [{"role": "system", "content": SYSTEM}]
    if historico:
        messages.extend(historico[-4:])
    messages.append({
        "role": "user",
        "content": f"Trechos relevantes:\n{contexto}\n\nPergunta: {pergunta}",
    })

    with Timer() as t:
        resp = _client.chat.completions.create(
            model=MODELO_LLM,
            messages=messages,
            temperature=TEMPERATURE,
        )

    msg = resp.choices[0].message.content
    usage = resp.usage

    trace_llm(
        name="researcher",
        input_text=pergunta,
        output_text=msg,
        tokens_in=usage.prompt_tokens,
        tokens_out=usage.completion_tokens,
        model=MODELO_LLM,
        metadata={"fontes": fontes},
    )

    return {
        "resposta": msg,
        "fontes": fontes,
        "tokens_in": usage.prompt_tokens,
        "tokens_out": usage.completion_tokens,
        "latencia_s": round(t.elapsed, 2),
        "agente": "researcher",
    }
