"""
Guardrail de saída:
- Trunca respostas acima do limite
- Detecta possível vazamento de credenciais/tokens na resposta
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

'''
from config import MAX_OUTPUT_CHARS

PADROES_CREDENCIAL = [
    r"sk-[a-zA-Z0-9]{20,}",                                  # chaves de API
    r"ey[a-zA-Z0-9_-]{40,}\.[a-zA-Z0-9_-]{40,}",            # JWT tokens
    r"[A-Z0-9]{20}:[A-Za-z0-9+/]{30,}",                      # access key:secret
]


def validar_saida(texto: str) -> tuple[str, list[str]]:
    """
    Retorna (texto_validado, lista_de_avisos).
    Trunca se necessário e avisa sobre credenciais detectadas.
    """
    avisos: list[str] = []

    for padrao in PADROES_CREDENCIAL:
        matches = re.findall(padrao, texto)
        if matches:
            avisos.append(
                f"Possível credencial na resposta ({len(matches)} ocorrência(s)) — revise antes de compartilhar"
            )

    if len(texto) > MAX_OUTPUT_CHARS:
        texto = texto[:MAX_OUTPUT_CHARS] + "\n\n[Resposta truncada — use uma pergunta mais específica]"
        avisos.append("Resposta truncada por exceder limite de caracteres")

    return texto, avisos
'''
