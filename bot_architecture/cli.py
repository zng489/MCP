"""Chat no terminal, com memória, logging e custo por pergunta."""
import json
from datetime import datetime

import config
from rag import criar_indice
from chat import responder


def registrar(pergunta, resultado):
    linha = {
        "hora": datetime.now().isoformat(timespec="seconds"),
        "pergunta": pergunta,
        "resposta": resultado["texto"],
        "fontes": resultado["fontes"],
        "custo": resultado["custo"],
        "tokens": resultado["tokens"],
        "latencia": resultado["latencia"],
    }
    with open(config.ARQUIVO_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")


def main():
    print("Indexando documentos...")
    indice = criar_indice()
    print("Pronto. Digite sua pergunta (ou 'sair' para encerrar).\n")

    historico = []
    custo_total = 0.0
    while True:
        pergunta = input("Você: ").strip()
        if pergunta.lower() in ("sair", "exit", "quit", ""):
            print(f"\nCusto total da sessão: US$ {custo_total:.4f}. Até mais!")
            break

        try:
            r = responder(indice, pergunta, historico)
        except Exception as e:
            print(f"\nBot: desculpe, não consegui responder agora ({e}).\n")
            continue

        custo_total += r["custo"]
        print(f"\nBot: {r['texto']}\n")
        print(
            f"  [fontes: {', '.join(r['fontes'])} | "
            f"{r['tokens']['in']}+{r['tokens']['out']} tokens | "
            f"US$ {r['custo']:.5f} | {r['latencia']}s]\n"
        )

        registrar(pergunta, r)
        historico.append({"role": "user", "content": pergunta})
        historico.append({"role": "assistant", "content": r["texto"]})
        if len(historico) > config.MAX_MENSAGENS_HISTORICO:
            historico = historico[-config.MAX_MENSAGENS_HISTORICO:]


if __name__ == "__main__":
    main()
