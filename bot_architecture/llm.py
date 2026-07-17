"""Camada de acesso ao modelo: cliente DeepSeek, retry e cálculo de custo."""
import time

from openai import OpenAI

import config

_client = None


def cliente():
    global _client
    if _client is None:
        if not config.DEEPSEEK_API_KEY:
            raise RuntimeError(
                "DEEPSEEK_API_KEY não definida. Crie um arquivo .env com "
                "DEEPSEEK_API_KEY=sk-..."
            )
        _client = OpenAI(
            api_key=config.DEEPSEEK_API_KEY,
            base_url=config.DEEPSEEK_BASE_URL,
        )
    return _client


def chamar(mensagens):
    """Chama o modelo com retry. Retorna dict: texto, custo (USD), tokens, latencia."""
    ultimo_erro = None
    for i in range(config.MAX_TENTATIVAS):
        try:
            inicio = time.time()
            r = cliente().chat.completions.create(
                model=config.MODELO_LLM,
                messages=mensagens,
                temperature=config.TEMPERATURE,
                timeout=config.TIMEOUT,
            )
            latencia = time.time() - inicio
            uso = r.usage
            custo = (
                uso.prompt_tokens / 1_000_000 * config.PRECO_INPUT
                + uso.completion_tokens / 1_000_000 * config.PRECO_OUTPUT
            )
            return {
                "texto": r.choices[0].message.content,
                "custo": round(custo, 6),
                "tokens": {"in": uso.prompt_tokens, "out": uso.completion_tokens},
                "latencia": round(latencia, 2),
            }
        except Exception as e:
            ultimo_erro = e
            print(f"  (erro: {e} — tentativa {i + 1}/{config.MAX_TENTATIVAS})")
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"Falha após {config.MAX_TENTATIVAS} tentativas: {ultimo_erro}")
