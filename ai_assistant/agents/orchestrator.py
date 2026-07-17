"""
Orquestrador (agente 1):
- Consulta memória de longo prazo para enriquecer contexto
- Decide qual agente usar com base no intent classificado
- Coordena o fluxo completo: guardrail → memória → agente → revisor → guardrail → memória
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from guardrails.input_validator import validar_entrada
from guardrails.output_validator import validar_saida
from memory.short_term import ShortTermMemory
from memory.long_term import buscar_conversas_similares, salvar_conversa
from agents import researcher, sql_agent, reviewer


def processar(pergunta: str, memoria: ShortTermMemory, stream: bool = False):
    """
    Fluxo:
    1. Guardrail entrada → bloqueia se necessário
    2. Memória longo prazo → enriquece contexto com conversas anteriores similares
    3. Delega ao agente certo (researcher | sql_agent)
    4. Revisor sintetiza (com streaming se stream=True)
    5. Guardrail saída → valida e trunca
    6. Salva na memória curto + longo prazo

    Retorna dict (stream=False) ou generator de tokens (stream=True).
    """
    # 1. Guardrail de entrada
    intent, motivo = validar_entrada(pergunta)
    if intent == "bloqueado":
        return {
            "resposta": f"Pergunta bloqueada: {motivo}",
            "agente": "guardrail",
            "intent": "bloqueado",
            "bloqueado": True,
            "avisos": [],
            "latencia_s": 0,
            "tokens_in": 0,
            "tokens_out": 0,
        }

    # 2. Memória de longo prazo
    similares = buscar_conversas_similares(pergunta, limite=2)
    if similares:
        resumo = "Contexto de conversas anteriores relacionadas:\n" + "\n".join(
            f"- Pergunta: {s['pergunta'][:80]}\n  Resposta: {s['resposta'][:120]}"
            for s in similares
        )
        memoria.adicionar("system", resumo)

    historico = memoria.para_openai()

    # 3. Delegar ao agente especializado
    if intent == "sql":
        resultado = sql_agent.responder(pergunta)
    elif intent == "docs":
        resultado = researcher.responder(pergunta, historico=historico)
    else:
        # ambíguo: tenta docs primeiro; se não encontrar, tenta SQL
        resultado = researcher.responder(pergunta, historico=historico)
        resposta_docs = resultado["resposta"].lower()
        nao_encontrou = (
            "não encontrei" in resposta_docs
            or "não está na documentação" in resposta_docs
            or "não sei" in resposta_docs
        )
        if nao_encontrou:
            resultado = sql_agent.responder(pergunta)

    # 4. Revisor
    if stream:
        return _stream_com_pos_processamento(pergunta, resultado, memoria, intent)
    else:
        revisado = reviewer.revisar(pergunta, resultado, stream=False)
        texto_validado, avisos = validar_saida(revisado["resposta"])

        # 5 + 6. Persiste
        memoria.adicionar("user", pergunta)
        memoria.adicionar("assistant", texto_validado)
        salvar_conversa(pergunta, texto_validado, resultado.get("agente", "unknown"))

        tokens_in = resultado.get("tokens_in", 0) + revisado.get("tokens_in", 0)
        tokens_out = resultado.get("tokens_out", 0) + revisado.get("tokens_out", 0)

        return {
            "resposta": texto_validado,
            "agente": resultado.get("agente", "unknown"),
            "intent": intent,
            "avisos": avisos,
            "fontes": resultado.get("fontes", []),
            "sqls": resultado.get("sqls", []),
            "latencia_s": resultado.get("latencia_s", 0) + revisado.get("latencia_s", 0),
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }


def _stream_com_pos_processamento(pergunta, resultado, memoria, intent):
    """Generator que faz streaming e, ao terminar, salva na memória."""
    texto_completo = ""
    for token in reviewer.revisar(pergunta, resultado, stream=True):
        texto_completo += token
        yield token

    texto_validado, _ = validar_saida(texto_completo)
    memoria.adicionar("user", pergunta)
    memoria.adicionar("assistant", texto_validado)
    salvar_conversa(pergunta, texto_validado, resultado.get("agente", "unknown"))
