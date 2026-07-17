"""
Wrapper Langfuse — rastreia latência, tokens e custo de cada chamada LLM.
Se LANGFUSE_SECRET_KEY não estiver configurado, vira no-op silencioso.
"""
import time
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import (
    LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_HOST,
    PRECO_INPUT, PRECO_OUTPUT,
)

_langfuse = None


def _get_langfuse():
    global _langfuse
    if _langfuse is not None:
        return _langfuse
    if not LANGFUSE_SECRET_KEY:
        return None
    try:
        from langfuse import Langfuse
        _langfuse = Langfuse(
            secret_key=LANGFUSE_SECRET_KEY,
            public_key=LANGFUSE_PUBLIC_KEY,
            host=LANGFUSE_HOST,
        )
    except ImportError:
        pass
    return _langfuse


def trace_llm(
    name: str,
    input_text: str,

     tput_text: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    model: str = "",
    metadata: Optional[dict] = None,
):
    """Registra uma chamada LLM no Langfuse (se configurado)."""
    lf = _get_langfuse()
    if not lf:
        return

    custo = (tokens_in * PRECO_INPUT + tokens_out * PRECO_OUTPUT) / 1_000_000
    trace = lf.trace(name=name, metadata=metadata or {})
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
    # --- Teste 1: Timer ---
    print("=== Timer ===")
    with Timer() as t:
        time.sleep(0.3)  # simula uma chamada que demora 300ms
    print(f"Tempo medido: {t.elapsed:.3f}s  (esperado: ~0.3s)")

    # --- Teste 2: trace_llm sem Langfuse configurado (no-op) ---
    print("\n=== trace_llm sem Langfuse (deve ser silencioso) ===")
    trace_llm(
        name="teste_researcher",
        input_text="Qual a porta do Jupyter?",
        output_text="A porta do Jupyter é 8888.",
        tokens_in=120,
        tokens_out=45,
        model="deepseek-chat",
        metadata={"agente": "researcher", "fontes": ["README.md"]},
    )
    print("OK — nenhum erro, nenhuma saída (Langfuse não configurado)")

    # --- Teste 3: custo calculado manualmente ---
    print("\n=== Cálculo de custo ===")
    tokens_in, tokens_out = 500, 200
    custo = (tokens_in * PRECO_INPUT + tokens_out * PRECO_OUTPUT) / 1_000_000
    print(f"tokens_in={tokens_in}  tokens_out={tokens_out}")
    print(f"custo = ({tokens_in} × {PRECO_INPUT} + {tokens_out} × {PRECO_OUTPUT}) / 1_000_000")
    print(f"custo = ${custo:.6f}")

    # --- Teste 4: Timer + trace_llm juntos (fluxo real simulado) ---
    print("\n=== Timer + trace_llm juntos (fluxo real simulado) ===")
    with Timer() as t:
        time.sleep(0.1)  # simula latência do DeepSeek
    trace_llm(
        name="teste_sql_agent",
        input_text="Quantos vínculos há na RAIS 2024?",
        output_text="Há 46.713.482 vínculos na RAIS 2024.",
        tokens_in=310,
        tokens_out=80,
        model="deepseek-chat",
        metadata={"latencia_s": round(t.elapsed, 3), "sqls_count": 2},
    )
    print(f"Latência simulada: {t.elapsed:.3f}s")
    print("trace_llm executado sem erros")
    print("\nTodos os testes passaram.")


