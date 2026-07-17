"""
LLM-as-judge: avalia qualidade das respostas em 3 dimensões (0-10).
Complementa os evals por palavra-chave com avaliação semântica real.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import OpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, MODELO_JUDGE

_client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL, timeout=60)

SYSTEM_JUDGE = """Você é um avaliador especializado em qualidade de respostas de IA sobre infraestrutura de dados.

Avalie a resposta abaixo em 3 dimensões (0 a 10 cada):
1. **Relevância**: a resposta responde diretamente à pergunta?
2. **Completude**: cobre os aspectos mais importantes da pergunta?
3. **Factualidade**: parece factualmente correta com base no contexto fornecido?

Retorne APENAS um JSON válido, sem texto fora do JSON:
{
  "relevancia": <0-10>,
  "completude": <0-10>,
  "factualidade": <0-10>,
  "media": <média das 3, com 1 casa decimal>,
  "aprovado": <true se média >= 7.0, false caso contrário>,
  "feedback": "<uma frase curta indicando o principal ponto de melhoria, ou 'Boa resposta' se aprovado>"
}"""


def avaliar(pergunta: str, resposta: str, contexto: str = "") -> dict:
    """Avalia uma resposta. Retorna dict com scores, aprovação e feedback."""
    prompt = f"Pergunta: {pergunta}\n\nResposta: {resposta}"
    if contexto:
        prompt += f"\n\nContexto disponível (trecho): {contexto[:600]}"

    try:
        resp = _client.chat.completions.create(
            model=MODELO_JUDGE,
            messages=[
                {"role": "system", "content": SYSTEM_JUDGE},
                {"role": "user", "content": prompt},
            ],
            temperature=0.0,
            response_format={"type": "json_object"},
        )
        resultado = json.loads(resp.choices[0].message.content)
        resultado["tokens"] = resp.usage.total_tokens
        return resultado
    except Exception as e:
        return {
            "relevancia": 0, "completude": 0, "factualidade": 0,
            "media": 0.0, "aprovado": False,
            "feedback": f"Erro na avaliação: {e}",
            "tokens": 0,
        }


def rodar_evals(casos: list[dict], processar_fn) -> dict:
    """
    Roda casos de eval combinando checagem por palavra-chave + LLM-as-judge.

    casos = [
      {"pergunta": "...", "esperado": ["palavra1"], "proibido": ["palavra2"]}
    ]
    processar_fn(pergunta) → dict com chave "resposta"
    """
    resultados = []
    for caso in casos:
        resultado_agente = processar_fn(caso["pergunta"])
        resposta = resultado_agente.get("resposta", "")

        # Checagem por palavra-chave (legado — rápido e determinístico)
        esperados_ok = all(
            e.lower() in resposta.lower() for e in caso.get("esperado", [])
        )
        proibidos_ok = not any(
            p.lower() in resposta.lower() for p in caso.get("proibido", [])
        )
        keywords_ok = esperados_ok and proibidos_ok

        # LLM-as-judge (semântico — mais robusto)
        julgamento = avaliar(caso["pergunta"], resposta)

        resultados.append({
            "pergunta": caso["pergunta"],
            "keywords_ok": keywords_ok,
            "judge_aprovado": julgamento.get("aprovado", False),
            "score": julgamento.get("media", 0.0),
            "relevancia": julgamento.get("relevancia", 0),
            "completude": julgamento.get("completude", 0),
            "factualidade": julgamento.get("factualidade", 0),
            "feedback": julgamento.get("feedback", ""),
        })

    aprovados_judge = sum(1 for r in resultados if r["judge_aprovado"])
    aprovados_keywords = sum(1 for r in resultados if r["keywords_ok"])
    total = len(resultados)

    return {
        "total": total,
        "aprovados_judge": aprovados_judge,
        "aprovados_keywords": aprovados_keywords,
        "taxa_judge": round(aprovados_judge / total * 100, 1) if total else 0,
        "taxa_keywords": round(aprovados_keywords / total * 100, 1) if total else 0,
        "detalhes": resultados,
    }
