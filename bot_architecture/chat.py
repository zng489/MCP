"""Orquestração: monta o contexto a partir do retrieval e chama o LLM."""
import config
import llm
from rag import buscar


def montar_contexto(indice, pergunta):
    trechos = buscar(indice, pergunta)
    blocos = "\n\n".join(f"===== {t['arquivo']} =====\n{t['texto']}" for t in trechos)
    return blocos, trechos


def responder(indice, pergunta, historico=None):
    """Responde uma pergunta. Retorna dict com resposta, fontes, custo e tokens.

    `historico` é uma lista de mensagens {role, content} das trocas anteriores
    (sem os trechos — só perguntas/respostas cruas).
    """
    historico = historico or []
    contexto, trechos = montar_contexto(indice, pergunta)
    conteudo = f"Trechos relevantes da documentação:\n{contexto}\n\nPergunta: {pergunta}"

    mensagens = (
        [{"role": "system", "content": config.SYSTEM_PROMPT}]
        + historico
        + [{"role": "user", "content": conteudo}]
    )

    resultado = llm.chamar(mensagens)
    resultado["fontes"] = sorted({t["arquivo"] for t in trechos})
    resultado["trechos"] = [
        {"arquivo": t["arquivo"], "score": t["score"]} for t in trechos
    ]
    return resultado
