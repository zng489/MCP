# 1. kb_server.py — o MCP server (FastMCP)

# kb_server.py
import re
from difflib import SequenceMatcher
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Caminho ancorado no script: kb_server.py está em i_know_everything/,
# e KNOWLEDGE_BASE.md está um nível acima (raiz do drive).
KB_PATH = Path(__file__).resolve().parent.parent / "KNOWLEDGE_BASE.md"
mcp = FastMCP("knowledge-base")

def _sections() -> dict[str, str]:
    text = KB_PATH.read_text(encoding="utf-8")
    sections = {}
    for part in re.split(r"(?m)^(?=##\s)", text):
        if part.strip():
            title = part.strip().splitlines()[0].lstrip("#").strip()
            sections[title] = part.strip()
    return sections

@mcp.tool()
def list_sections() -> str:
    """Lista os títulos de todas as seções da base de conhecimento."""
    return "\n".join(_sections().keys())

def _similar(a: str, b: str) -> float:
    """Similaridade entre duas palavras (0.0 a 1.0). 'kubernets' vs 'kubernetes' ~0.95."""
    return SequenceMatcher(None, a, b).ratio()

@mcp.tool()
def search_kb(query: str, cutoff: float = 0.8) -> str:
    """Busca na base e retorna as 3 seções mais relevantes para a query.

    Combina match exato (substring) com match aproximado (fuzzy), então
    erros de digitação como 'kubernets' ainda encontram 'kubernetes'.
    `cutoff` (0-1) = quão parecida a palavra precisa ser para contar como fuzzy.
    """
    terms = [t.lower() for t in query.split() if len(t) > 2]
    hits = []
    for title, body in _sections().items():
        low = body.lower()
        # Palavras únicas da seção (só letras/números), usadas no match fuzzy.
        words = set(re.findall(r"\w+", low))

        score = 0
        for t in terms:
            # 1) Match EXATO: conta ocorrências da substring (peso cheio).
            score += low.count(t)
            # 2) Match FUZZY: conta palavras da seção parecidas com o termo
            #    (ex: 'kubernets' ~ 'kubernetes'), mas só se não houve exato,
            #    pra não contar a mesma palavra duas vezes.
            if t not in low:
                score += sum(1 for w in words if _similar(t, w) >= cutoff)
        if score:
            hits.append((score, body))
    hits.sort(reverse=True, key=lambda x: x[0])
    return "\n\n---\n\n".join(b for _, b in hits[:3]) or "Nada encontrado. Use list_sections."

@mcp.tool()
def read_section(title: str) -> str:
    """Retorna o conteúdo completo de uma seção pelo título (parcial serve)."""
    for t, body in _sections().items():
        if title.lower() in t.lower():
            return body
    return f"Seção '{title}' não encontrada."


if __name__ == "__main__":
    # Teste rápido (passe um VALOR, não uma anotação de tipo):
    # print(search_kb("kubernet"))
    # Quando for rodar de verdade (via bot/MCP), comente o teste e use:
    mcp.run()   # stdio por padrão