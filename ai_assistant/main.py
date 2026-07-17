"""
AI Assistant — ponto de entrada.

Uso:
  python main.py chat          # chat interativo com streaming
  python main.py eval          # roda os evals com LLM-as-judge
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="AI Assistant — infra_mini_cloud (RAG + Multi-agent + Streaming + LLM-as-judge)"
    )
    sub = parser.add_subparsers(dest="cmd", help="Comando")
    sub.add_parser("chat", help="Chat interativo no terminal com streaming")
    sub.add_parser("eval", help="Rodar evals com LLM-as-judge")
    args = parser.parse_args()

    if args.cmd == "eval":
        import json
        from pathlib import Path
        from evals.llm_judge import rodar_evals
        from agents.orchestrator import processar
        from memory.short_term import ShortTermMemory

        casos_path = Path("evals/cases.json")
        if not casos_path.exists():
            print("Arquivo evals/cases.json não encontrado.")
            sys.exit(1)

        casos = json.loads(casos_path.read_text(encoding="utf-8"))

        def fn(pergunta):
            mem = ShortTermMemory()
            r = processar(pergunta, mem, stream=False)
            return r if isinstance(r, dict) else {"resposta": ""}

        relatorio = rodar_evals(casos, fn)
        print(f"\nJudge:    {relatorio['aprovados_judge']}/{relatorio['total']} ({relatorio['taxa_judge']}%)")
        print(f"Keywords: {relatorio['aprovados_keywords']}/{relatorio['total']} ({relatorio['taxa_keywords']}%)\n")
        for d in relatorio["detalhes"]:
            s = "✓" if d["judge_aprovado"] else "✗"
            print(f"  {s} [{d['score']:.1f}] {d['pergunta'][:60]}")
            if not d["judge_aprovado"]:
                print(f"       → {d['feedback']}")
    else:
        from interfaces.cli import rodar
        rodar()


if __name__ == "__main__":
    main()
