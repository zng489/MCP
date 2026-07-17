"""
Interface CLI com streaming, custo da sessão, histórico e comando de eval.
"""
import json
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory.short_term import ShortTermMemory
from agents.orchestrator import processar
from config import PRECO_INPUT, PRECO_OUTPUT

BANNER = """
╔══════════════════════════════════════════════════════════╗
║            AI Assistant — infra_mini_cloud               ║
║  RAG híbrido · Multi-agent · Streaming · LLM-as-judge   ║
╚══════════════════════════════════════════════════════════╝
Comandos: 'sair' encerra | 'eval' roda os evals | 'memoria' mostra histórico
"""


def _calcular_custo(tokens_in: int, tokens_out: int) -> float:
    return (tokens_in * PRECO_INPUT + tokens_out * PRECO_OUTPUT) / 1_000_000


def rodar():
    print(BANNER)
    memoria = ShortTermMemory()
    custo_total = 0.0
    tokens_total = 0

    while True:
        try:
            pergunta = input("\nVocê: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not pergunta:
            continue

        if pergunta.lower() == "sair":
            break

        if pergunta.lower() == "eval":
            _rodar_evals(memoria)
            continue

        if pergunta.lower() == "memoria":
            print("\n--- Histórico da sessão ---")
            print(memoria.resumo() or "(vazio)")
            continue

        print("\nAssistente: ", end="", flush=True)
        inicio = time.perf_counter()

        resultado = processar(pergunta, memoria, stream=True)

        if hasattr(resultado, "__next__"):
            # streaming: imprime token a token
            for token in resultado:
                print(token, end="", flush=True)
            print()
            latencia = time.perf_counter() - inicio
            print(f"\n  [streaming | {latencia:.1f}s]")
        else:
            # resposta direta (guardrail bloqueou, etc.)
            print(resultado.get("resposta", ""))

            tokens_in = resultado.get("tokens_in", 0)
            tokens_out = resultado.get("tokens_out", 0)
            custo = _calcular_custo(tokens_in, tokens_out)
            custo_total += custo
            tokens_total += tokens_in + tokens_out

            latencia = time.perf_counter() - inicio
            agente = resultado.get("agente", "?")
            intent = resultado.get("intent", "?")
            fontes = resultado.get("fontes", [])
            avisos = resultado.get("avisos", [])

            info = f"[{agente} | {intent} | {latencia:.1f}s | ${custo:.5f}]"
            if fontes:
                info += f" fontes: {', '.join(fontes)}"
            print(f"\n  {info}")
            for aviso in avisos:
                print(f"  ⚠ {aviso}")

    print(f"\n[Sessão encerrada | custo total: ${custo_total:.4f} | tokens: {tokens_total}]")


def _rodar_evals(memoria: ShortTermMemory):
    from evals.llm_judge import rodar_evals

    casos_path = Path(__file__).resolve().parent.parent / "evals" / "cases.json"
    if not casos_path.exists():
        print("evals/cases.json não encontrado.")
        return

    casos = json.loads(casos_path.read_text(encoding="utf-8"))
    print(f"\nRodando {len(casos)} casos com LLM-as-judge...\n")

    def fn(pergunta):
        mem = ShortTermMemory()
        r = processar(pergunta, mem, stream=False)
        return r if isinstance(r, dict) else {"resposta": ""}

    relatorio = rodar_evals(casos, fn)
    print(f"Judge:    {relatorio['aprovados_judge']}/{relatorio['total']} aprovados ({relatorio['taxa_judge']}%)")
    print(f"Keywords: {relatorio['aprovados_keywords']}/{relatorio['total']} aprovados ({relatorio['taxa_keywords']}%)\n")
    for d in relatorio["detalhes"]:
        status = "✓" if d["judge_aprovado"] else "✗"
        print(f"  {status} [{d['score']:.1f}] {d['pergunta'][:55]}")
        if not d["judge_aprovado"]:
            print(f"       → {d['feedback']}")
