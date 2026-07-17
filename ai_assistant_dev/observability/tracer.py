"""
Wrapper Langfuse — rastreia latência, tokens e custo de cada chamada LLM.
Se LANGFUSE_SECRET_KEY não estiver configurado, vira no-op silencioso.
"""
import time
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    from config import (
        LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_HOST,
        PRECO_INPUT, PRECO_OUTPUT,
    )
except ModuleNotFoundError:
    LANGFUSE_SECRET_KEY = ""
    LANGFUSE_PUBLIC_KEY = ""
    LANGFUSE_HOST = "https://cloud.langfuse.com"
    PRECO_INPUT = 0.0      # modelo local = sem custo por token
    PRECO_OUTPUT = 0.0     # modelo local = sem custo por token

# configuração do modelo local (LM Studio)
LLM_BASE_URL = "http://localhost:1234/v1"
LLM_API_KEY  = "lm-studio"
LLM_MODEL    = "google/gemma-4-12b-qat"

_langfuse = None


def _get_langfuse():
    global _langfuse
    if _langfuse is not None:
        return _langfuse
    if not LANGFUSE_SECRET_KEY:
        return None
    try:
        # Langfuse is an open-source LLM engineering and observability
        from langfuse import Langfuse
        _langfuse = Langfuse(
            secret_key=LANGFUSE_SECRET_KEY,
            public_key=LANGFUSE_PUBLIC_KEY,
            host=LANGFUSE_HOST,
        )
    except ImportError:
        pass
    return _langfuse


def trace_llm(name: str, 
                input_text: str, 
                output_text: str, 
                tokens_in: int = 0,
                tokens_out: int = 0,
                model: str = "",
                metadata: Optional[dict] = None,
                                                ):
    """Registra uma chamada LLM no Langfuse (se configurado)."""
    lf = _get_langfuse()

    # if lf == None:
    if not lf:
        return

    custo = (tokens_in * PRECO_INPUT + tokens_out * PRECO_OUTPUT) / 1_000_000

    trace = lf.trace(name=name, metadata=metadata or {})
    
    # metadata or {}   # → {}  (é None, usa o dicionário vazio)s
    trace.generation(
        name=name,
        model=model,
        input=input_text,
        output=output_text,
        usage={"input": tokens_in, "output": tokens_out, "total": tokens_in + tokens_out},
        metadata={"custo_usd": round(custo, 6)},
    )


class Timer:
    """Context manager para medir latência."""
    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *_):
        self.elapsed = time.perf_counter() - self.start


if __name__ == "__main__":
    import argparse


    # ── Integração real (LM Studio deve estar rodando) ────────────────
    from openai import OpenAI

    client = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)

    pergunta = "Qual a capital do Brasil?"

    with Timer() as t:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "Você é um assistente direto e conciso."},
                {"role": "user",   "content": pergunta},
            ],
            temperature=0.0,
        )

    resposta   = response.choices[0].message.content
    tokens_in  = response.usage.prompt_tokens
    tokens_out = response.usage.completion_tokens

    print(f"Resposta : {resposta}")
    print(f"Tokens   : {tokens_in} in / {tokens_out} out")
    print(f"Latência : {t.elapsed:.3f}s")

    trace_llm(
        name="teste_local",
        input_text=pergunta,
        output_text=resposta,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        model=LLM_MODEL,
        metadata={"latencia_s": round(t.elapsed, 3)},
    )
    print("trace_llm: OK")