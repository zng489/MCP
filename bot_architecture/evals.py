"""Roda os casos de eval_cases.json.

Cada caso tem:
  pergunta  -> a pergunta
  espera    -> termos que DEVEM aparecer na resposta
  proibido  -> (opcional) termos que NÃO podem aparecer (regressão de relevância)
"""
import json

import config
from rag import criar_indice
from chat import responder


def rodar():
    casos = json.loads((config.RAIZ / "eval_cases.json").read_text(encoding="utf-8"))
    print("Indexando documentos...")
    indice = criar_indice()
    print(f"Rodando {len(casos)} casos...\n")

    passou = 0
    custo_total = 0.0
    for i, caso in enumerate(casos, 1):
        r = responder(indice, caso["pergunta"])
        custo_total += r["custo"]
        resposta = r["texto"].lower()

        faltam = [t for t in caso.get("espera", []) if t.lower() not in resposta]
        proibidos = [t for t in caso.get("proibido", []) if t.lower() in resposta]
        ok = not faltam and not proibidos
        passou += ok

        print(f"[{'PASS' if ok else 'FAIL'}] {i}. {caso['pergunta']}")
        if faltam:
            print(f"         faltou: {faltam}")
        if proibidos:
            print(f"         apareceu (proibido): {proibidos}")

    print(f"\n{passou}/{len(casos)} passaram. Custo total: US$ {custo_total:.4f}")


if __name__ == "__main__":
    rodar()
